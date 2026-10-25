"""Show every Inter development example; no cherry-picked success clips."""
import argparse,json,sys
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rodri_studio.visual_model import frame_at,predict_observation


def main():
 p=argparse.ArgumentParser();p.add_argument('--videos',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('demo/holdout_review.mp4'));a=p.parse_args()
 root=Path(__file__).resolve().parents[1]
 rows=[r for r in json.loads((root/'data/reviewed_events.json').read_text()) if r['match_id']=='inter_2023_final']
 model=root/'models/next_action_holdout.json';a.out.parent.mkdir(parents=True,exist_ok=True)
 writer=cv2.VideoWriter(str(a.out),cv2.VideoWriter_fourcc(*'mp4v'),25,(1280,480));assert writer.isOpened()
 predictions=[]
 for row in rows:
  path=a.videos/row['source_filename'];obs=row['observation_seconds'];target=row['target_seconds']
  current,actual=frame_at(path,obs)
  result=predict_observation(str(path),obs,tuple(row['box']),model.stat().st_mtime_ns,str(model))
  top=result['alternatives'][0];predictions.append(dict(id=row['id'],prediction=top,truth=row['target_action']))
  frozen=current.copy();x1,y1,x2,y2=map(int,row['box']);cv2.rectangle(frozen,(x1,y1),(x2,y2),(140,235,170),2)
  cap=cv2.VideoCapture(str(path));last=-1;future=current
  duration=target-obs+1.4
  for k in range(int(duration*25)):
   elapsed=k/25;shown=obs+max(0,elapsed-.6);index=int(shown*25)
   if index!=last:
    cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,f=cap.read()
    if ok:future=f
    last=index
   canvas=np.full((480,1280,3),(24,19,12),np.uint8)
   canvas[60:420,:640]=frozen;canvas[60:420,640:]=future
   def text(line,x,y,color=(228,236,231),size=.55):cv2.putText(canvas,line,(x,y),cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
   text('RODRI | development review - trained on Chelsea only',16,25)
   text(row['id']+' | all 9 examples included',16,48,size=.48)
   text('FROZEN observation at '+f'{obs:.2f}s | AI-reviewed actor box',16,440,size=.48)
   text(f'Predicted: {top["action"]} ({top["probability"]:.0%} uncalibrated score)',16,466)
   text(f'ACTUAL FUTURE | source {shown:.2f}s',658,440,size=.48)
   if shown>=target:
    correct=top['action']==row['target_action']
    text('Reviewed label: '+row['target_action']+(' | correct' if correct else ' | incorrect'),658,466,(140,235,170) if correct else (120,150,255))
   else:text('Future action label hidden until its timestamp',658,466,size=.48)
   writer.write(canvas)
  cap.release()
 writer.release();a.out.with_suffix('.json').write_text(json.dumps(predictions,indent=2))
 print('Wrote',a.out,'all',len(rows),'development examples; no footage was used to fit the holdout head.')
if __name__=='__main__':main()
