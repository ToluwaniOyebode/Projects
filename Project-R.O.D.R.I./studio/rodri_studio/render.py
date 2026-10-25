"""Export the analyzed passage with conservative identity and forecast overlays."""
from pathlib import Path
import bisect
import cv2
from .predictor import features,predict


def render_video(source,result,output,model_path,checkpoint='deployment'):
    # Import here to keep the renderer reusable without an import cycle.
    from .app import context, action_prediction
    meta=result['metadata']; cap=cv2.VideoCapture(str(source))
    start=result['frames'][0]['time']; end=result['frames'][-1]['time']+1/5
    first=round(start*meta['fps']); last=min(meta['frames'],round(end*meta['fps']))
    cap.set(cv2.CAP_PROP_POS_FRAMES,first)
    scale=min(1,1280/meta['width']); size=(int(meta['width']*scale)//2*2,int(meta['height']*scale)//2*2)
    writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),meta['fps'],size)
    if not writer.isOpened():
        cap.release();raise ValueError('Cannot create output video')
    count=0
    try:
        for index in range(first,last):
            ok,image=cap.read()
            if not ok:break
            t=index/meta['fps']; frame,person,message=context(result,t)
            if abs(frame['time']-t)<=.3:
                for det in frame['detections']:
                    x1,y1,x2,y2=map(int,det['box']); selected=det is person
                    color=(189,235,135) if selected else (150,150,150)
                    cv2.rectangle(image,(x1,y1),(x2,y2),color,3 if selected else 1)
                    cv2.putText(image,'Rodri (confirmed)' if selected else f"Person {det['track']}",(x1,max(20,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
            forecast='No trained next-action model'
            if person:
                p=action_prediction(source,frame['time'],person,meta,checkpoint)
                if p['alternatives']:
                    a=p['alternatives'][0];forecast=f"Experimental next: {a['action']} ({a['probability']:.0%} score)"
                if p.get('off_ball_motion'):
                    box=person['box'];cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2;dx,dy=p['off_ball_motion']['camera_relative_displacement']
                    cv2.arrowedLine(image,(round(cx),round(cy)),(round(cx+dx*meta['width']),round(cy+dy*meta['height'])),(189,235,135),2,tipLength=.3)
            else:forecast='Forecast suppressed'
            image=cv2.resize(image,size)
            cv2.rectangle(image,(0,0),(size[0],88),(12,24,30),-1)
            lines=[f'RODRI STUDIO | video {t:.1f}s | shot {frame["shot"]}',message,forecast]
            for j,line in enumerate(lines):
                cv2.putText(image,line,(12,23+26*j),cv2.FONT_HERSHEY_SIMPLEX,.48,(210,235,230),1,cv2.LINE_AA)
            writer.write(image);count+=1
    finally:
        cap.release();writer.release()
    if not count:raise ValueError('No output frames written')
    return dict(frames=count,source_start_seconds=start,source_end_seconds=last/meta['fps'],audio=False)
