"""A transparent, chunk-level BM25 index implemented with SQL postings."""
import math
import re
from collections import Counter

STOP = set('a an and are as at be by for from in is it of on or that the this to was with'.split())


def tokenize(value):
    return [t for t in re.findall(r'[^\W_]+', value.casefold(), re.UNICODE) if t not in STOP]


def chunks(content, maximum=120):
    """Keep source line ranges; split long lines while retaining their line number."""
    section='Document';buffer=[];count=0;start=1;end=1
    for number,line in enumerate(content.splitlines(),1):
        if re.match(r'^#{1,6}\s',line):
            if buffer:
                yield section,'\n'.join(buffer),start,end
                buffer=[];count=0
            section=line.lstrip('#').strip()
            continue
        if not line.strip():
            if count>=maximum//2:
                yield section,'\n'.join(buffer),start,end
                buffer=[];count=0
            continue
        # Whitespace-delimited slices keep punctuation in displayed text.
        words=line.split()
        for offset in range(0,len(words),maximum):
            piece=' '.join(words[offset:offset+maximum]);size=len(tokenize(piece))
            if count+size>maximum and buffer:
                yield section,'\n'.join(buffer),start,end
                buffer=[];count=0
            if not buffer: start=number
            buffer.append(piece);count+=size;end=number
    if buffer: yield section,'\n'.join(buffer),start,end


def index_document(db, doc_id, title, content):
    db.execute('DELETE FROM chunks WHERE document_id=?',(doc_id,))
    for section,body,start,end in chunks(content):
        counts=Counter(tokenize(title+' '+section+' '+body))
        cursor=db.execute('INSERT INTO chunks(document_id,section,body,start_line,end_line,length) VALUES(?,?,?,?,?,?)',(doc_id,section,body,start,end,sum(counts.values())))
        db.executemany('INSERT INTO postings(chunk_id,term,tf) VALUES(?,?,?)',[(cursor.lastrowid,term,tf) for term,tf in counts.items()])


def search(db, query, mode='any', limit=10):
    if mode not in ('any','all'): raise ValueError('mode must be any or all')
    if not isinstance(limit,int) or not 1<=limit<=50: raise ValueError('limit must be from 1 to 50')
    terms=list(dict.fromkeys(tokenize(query)))[:16]
    if not terms: return {'query':query,'terms':[],'total':0,'results':[]}
    stats=db.execute('SELECT count(*) n,coalesce(avg(length),0) avg_length FROM chunks').fetchone()
    if not stats['n']: return {'query':query,'terms':terms,'total':0,'results':[]}
    marks=','.join('?' for _ in terms)
    dfs={r['term']:r['n'] for r in db.execute(f'SELECT term,count(*) n FROM postings WHERE term IN ({marks}) GROUP BY term',terms)}
    postings=db.execute(f'''SELECT p.*,c.length FROM postings p JOIN chunks c ON p.chunk_id=c.id WHERE term IN ({marks})''',terms)
    scores={}
    for row in postings:
        df=dfs[row['term']];idf=math.log(1+(stats['n']-df+.5)/(df+.5))
        score=idf*(row['tf']*2.5)/(row['tf']+1.5*(.25+.75*row['length']/max(1,stats['avg_length'])))
        scores.setdefault(row['chunk_id'],[]).append({'term':row['term'],'tf':row['tf'],'idf':round(idf,5),'contribution':round(score,5)})
    ranked=[(cid,parts,sum(p['contribution'] for p in parts)) for cid,parts in scores.items() if mode!='all' or len(parts)==len(terms)]
    ranked.sort(key=lambda row:(-row[2],row[0]))
    results=[]
    for chunk_id,explanation,score in ranked[:limit]:
        row=dict(db.execute('SELECT c.*,d.title FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=?',(chunk_id,)).fetchone())
        row['score']=round(score,5);row['explanation']=explanation
        body=row.pop('body');positions=[m.start() for term in terms for m in re.finditer(re.escape(term),body.casefold())]
        start=max(0,(min(positions) if positions else 0)-80);end=min(len(body),start+360)
        row['snippet']=('…' if start else '')+body[start:end]+('…' if end<len(body) else '')
        results.append(row)
    return {'query':query,'terms':terms,'total':len(ranked),'results':results}
