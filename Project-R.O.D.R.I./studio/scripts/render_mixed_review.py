"""Render every added TRAINING example, including errors, without claiming test accuracy."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from train_mixed import read_features
from rodri_studio.temporal_model import probabilities
from rodri_studio.visual_model import frame_at
from rodri_studio.edited_video import validate_observation


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--videos',type=Path,required=True)
    p.add_argument('--data',type=Path,default=Path('data/general_2017'))
    p.add_argument('--model',type=Path,default=Path('models/next_action_v5.json'))
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();rows,x=read_features(args.data);model=json.loads(args.model.read_text())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    temp=args.out.with_suffix('.raw.mp4');writer=cv2.VideoWriter(str(temp),cv2.VideoWriter_fourcc(*'mp4v'),25,(1280,540))
    if not writer.isOpened():raise ValueError('Cannot create review video')
    reports=[]
    try:
        for row,vector in zip(rows,x):
            path=args.videos/row['source_filename'];timeline=validate_observation(path,row)
            obs=row['observation_seconds'];target=row['target_seconds'];image,actual=frame_at(path,obs)
            # The vector was computed only from current/past frames. Future frames below are display-only.
            scores=probabilities(vector,model['classifier']);best=int(np.argmax(scores));prediction=model['classifier']['classes'][best]
            frozen=image.copy();a,b,c,d=map(int,row['box']);cv2.rectangle(frozen,(a,b),(c,d),(130,235,170),3)
            cv2.putText(frozen,'Selected player (not Rodri)',(a,max(24,b-8)),cv2.FONT_HERSHEY_SIMPLEX,.55,(130,235,170),2)
            cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);index=round(actual*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,index);future=image
            end=timeline.segment(obs)['clip_end_seconds_exclusive'] if timeline else float('inf')
            for k in range(75):
                shown=min(obs+max(0,k/25-.7),end-1/fps)
                wanted=int(np.floor(shown*fps+1e-6))
                while index<=wanted:
                    ok,frame=cap.read()
                    if not ok:raise ValueError('Cannot decode reviewed future')
                    future=frame;index+=1
                canvas=np.full((540,1280,3),(24,19,12),np.uint8)
                canvas[100:460,:640]=cv2.resize(frozen,(640,360));canvas[100:460,640:]=cv2.resize(future,(640,360))
                def text(s,y,x=16,color=(230,237,230),scale=.55):
                    cv2.putText(canvas,s,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)
                text('RODRI STUDIO V5 | GENERAL FOOTBALL | RODRI ABSENT',28)
                text('TRAINING EXAMPLE - NOT AN INDEPENDENT ACCURACY TEST | single-AI action review',54,color=(120,200,255))
                text(f"{row['id']} | {row['source_filename']} | observation {obs:.2f}s",80,scale=.5)
                text(f'Forecast: {prediction} ({scores[best]:.0%} uncalibrated score)',489)
                text('Frozen observation | only current/past features',517,scale=.48)
                text(f'Actual future: {shown:.2f}s',489,x=656)
                if shown>=target:
                    text(f"AI-reviewed: {row['target_action']} | "+('match' if prediction==row['target_action'] else 'ERROR'),517,x=656,color=(120,200,255))
                else:text('Future label hidden until target',517,x=656,scale=.48)
                writer.write(canvas)
            cap.release();reports.append(dict(id=row['id'],truth=row['target_action'],prediction=prediction,scope='training illustration'))
    finally:writer.release()
    subprocess.run(['ffmpeg','-v','error','-i',str(temp),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-an','-y',str(args.out)],check=True)
    temp.unlink()
    args.out.with_suffix('.json').write_text(json.dumps(dict(scope='All added training examples; not a held-out evaluation',independent_human_review=False,cases=reports),indent=2))
    print(json.dumps(dict(rendered_cases=len(reports),seconds=len(reports)*3,scope='training illustration, not test accuracy')))


if __name__=='__main__':main()
