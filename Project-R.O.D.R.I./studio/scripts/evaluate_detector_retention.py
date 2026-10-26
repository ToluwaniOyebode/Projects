"""Compare detectors on sparse previously reviewed broadcast actor boxes.

Only one actor is labelled in each image, so these cases measure actor recovery,
not whole-frame precision. They are reused development cases, not final accuracy.
"""
import argparse,json,sys
from pathlib import Path
import cv2
import torch
from ultralytics import YOLO
from train_kaggle_detector import pairwise_iou


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--videos',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--baseline',type=Path,default=Path('models/yolo11n.pt'))
    p.add_argument('--events',type=Path,default=Path('data/general_2017/reviewed_events.json'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--imgsz',type=int,default=1024)
    args=p.parse_args();torch.set_num_threads(4)
    rows=json.loads(args.events.read_text());cases=[]
    models={'baseline':YOLO(str(args.baseline)),'candidate':YOLO(str(args.candidate))}
    for row in rows:
        cap=cv2.VideoCapture(str(args.videos/row['source_filename']));cap.set(cv2.CAP_PROP_POS_MSEC,row['observation_seconds']*1000);ok,image=cap.read();cap.release()
        if not ok:raise ValueError('Cannot decode reviewed frame')
        case=dict(id=row['id'],match_id=row['match_id'])
        for name,model in models.items():
            prediction=model.predict(image,classes=[0],device='cpu',conf=.3,imgsz=args.imgsz,verbose=False)[0]
            boxes=prediction.boxes.xyxy.cpu().numpy();overlap=pairwise_iou(boxes,[row['box']]);best=float(overlap.max()) if overlap.size else 0.
            case[name]=dict(reviewed_actor_recovered=best>=.5,best_iou=best,total_person_candidates=len(boxes))
        cases.append(case)
    report=dict(scope='Previously AI-reviewed actor boxes in a supplied broadcast match. Reused development cases with incomplete person labels: actor recovery only, not full detector precision or independent-match accuracy.',confidence_threshold=.3,iou_threshold=.5,imgsz=args.imgsz,cases=cases)
    for name in models:report[name]=dict(recovered_actors=sum(row[name]['reviewed_actor_recovered'] for row in cases),reviewed_actors=len(rows))
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='cases'}))


if __name__=='__main__':main()
