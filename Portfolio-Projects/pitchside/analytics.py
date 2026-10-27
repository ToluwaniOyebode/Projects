"""Descriptive event analytics. No trained model or next-action prediction."""
import csv
import io
import math
from collections import Counter,defaultdict

from webcore import Problem,text

FIELDS=('event_id','minute','team','player','action','outcome','x','y','end_x','end_y','receiver')
OUTCOMES={'pass':('complete','incomplete'),'carry':('complete','incomplete'),'shot':('goal','saved','wide','blocked'),'turnover':('lost',)}


def number(value,name,minimum,maximum):
    try: value=float(value)
    except (ValueError,TypeError): raise Problem(f'{name} must be numeric') from None
    if not math.isfinite(value) or not minimum<=value<=maximum:raise Problem(f'{name} must be between {minimum} and {maximum}')
    return value


def parse_csv(source):
    source=text(source,'csv',950000)
    reader=csv.DictReader(io.StringIO(source.lstrip('\ufeff')))
    if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):raise Problem('CSV must include: '+', '.join(FIELDS))
    events=[];seen=set()
    for line,row in enumerate(reader,2):
        if line>5001:raise Problem('Limit is 5,000 events per match')
        try:
            event_id=text(row.get('event_id'),'event_id',80)
            if event_id in seen:raise Problem('event_id must be unique')
            seen.add(event_id)
            event={k:text(row.get(k),k,100) for k in ('team','player','action','outcome')}
            if event['action'] not in OUTCOMES or event['outcome'] not in OUTCOMES[event['action']]:raise Problem('Unsupported action/outcome combination')
            event.update({k:number(row.get(k),k,0,130 if k=='minute' else 100) for k in ('minute','x','y','end_x','end_y')})
            event['receiver']=text(row.get('receiver',''),'receiver',100,True)
            event['event_id']=event_id
            events.append(event)
        except Problem as error:raise Problem(f'Row {line}: {error}') from None
    if not events:raise Problem('CSV contains no events')
    if len({e['team'] for e in events})>2:raise Problem('A match may contain at most two teams')
    return sorted(events,key=lambda e:(e['minute'],e['event_id']))


def shot_score(x,y):
    """Illustrative location score using a 105×68 m pitch; deliberately not named xG."""
    dx=(100-x)*1.05;dy=(50-y)*.68
    distance=math.hypot(dx,dy)
    angle=math.atan2(7.32*dx,dx*dx+dy*dy-3.66**2)
    return round(1/(1+math.exp(2.2+.095*distance-1.2*angle)),4)


def analyze(events):
    counts=Counter(e['action'] for e in events)
    passes=[e for e in events if e['action']=='pass']
    complete=[e for e in passes if e['outcome']=='complete']
    shots=[{**e,'location_score':shot_score(e['x'],e['y'])} for e in events if e['action']=='shot']
    progressive=[e for e in complete if e['end_x']-e['x']>=15]
    entries=[e for e in events if e['action'] in ('pass','carry') and e['outcome']=='complete' and e['x']<100*2/3<=e['end_x']]
    locations=defaultdict(list);edges=Counter()
    for event in complete:
        key=(event['team'],event['player']);locations[key].append((event['x'],event['y']))
        if event['receiver'] and event['receiver']!=event['player']:
            other=(event['team'],event['receiver']);locations[other].append((event['end_x'],event['end_y']))
            edges[(event['team'],event['player'],event['receiver'])]+=1
    nodes=[{'team':key[0],'player':key[1],'x':round(sum(x for x,y in points)/len(points),2),'y':round(sum(y for x,y in points)/len(points),2),'touches':len(points)} for key,points in sorted(locations.items())]
    network=[{'team':team,'source':source,'target':target,'count':count} for (team,source,target),count in edges.most_common()]
    players=[]
    for team,player in sorted({(e['team'],e['player']) for e in events}):
        own=[e for e in events if e['team']==team and e['player']==player]
        own_pass=[e for e in own if e['action']=='pass']
        players.append({'team':team,'player':player,'events':len(own),'passes':len(own_pass),'completed':sum(e['outcome']=='complete' for e in own_pass),'shots':sum(e['action']=='shot' for e in own)})
    timeline=[{'minute':start,'count':sum(start<=e['minute']<start+15 for e in events)} for start in range(0,135,15)]
    return {'events':len(events),'counts':dict(counts),'passes':len(passes),'completed_passes':len(complete),'pass_completion':round(100*len(complete)/len(passes),1) if passes else 0,
            'progressive_passes':len(progressive),'final_third_entries':len(entries),'shots':shots,'goals':sum(e['outcome']=='goal' for e in shots),'nodes':nodes,'edges':network,'players':players,'timeline':timeline}
