"""Evaluate a frozen checkpoint against reviewed future labels and render every case.

Identity boxes and labels must be supplied by a reviewer. This is not automatic
name recognition. Unsupported labels are retained as scope failures, never
silently removed from the report or relabeled to one of the model's classes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rodri_studio.visual_model import frame_at, predict_observation


def summarize(cases, classes):
    eligible = [r for r in cases if r['truth'] in classes]
    correct = sum(r['prediction']['action'] == r['truth'] for r in eligible)
    return dict(total_reviewed=len(cases), supported_targets=len(eligible),
                unsupported_targets=len(cases)-len(eligible),
                correct_supported=correct,
                supported_target_accuracy=correct/len(eligible) if eligible else None,
                scope_coverage=len(eligible)/len(cases) if cases else None,
                raw_exact_matches=sum(r['prediction']['action']==r['truth'] for r in cases))


def fit_panel(image):
    height, width = image.shape[:2]
    scale = min(640/width, 360/height)
    thumb = cv2.resize(image, (round(width*scale), round(height*scale)))
    out = np.zeros((360, 640, 3), np.uint8)
    y, x = (360-thumb.shape[0])//2, (640-thumb.shape[1])//2
    out[y:y+thumb.shape[0], x:x+thumb.shape[1]] = thumb
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--events', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--domain', choices=['real', 'simulation', 'unknown'], default='unknown')
    args = p.parse_args()
    rows = json.loads(args.events.read_text())
    if not rows or any(r['target_seconds'] <= r['observation_seconds'] for r in rows):
        raise ValueError('Need reviewed examples with targets strictly after observation')
    if any(r.get('replay') for r in rows):
        raise ValueError('Replay cases must not be treated as live action targets')
    model = json.loads(args.model.read_text())
    if model.get('kind')=='causal_temporal_v3':
        from rodri_studio.temporal_model import predict_observation as predict_model
    else:predict_model=predict_observation
    args.out.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.out), cv2.VideoWriter_fourcc(*'mp4v'), 25, (1280, 540))
    if not writer.isOpened():
        raise ValueError('Cannot create review video')
    cases = []
    try:
        for row in rows:
            obs, target = row['observation_seconds'], row['target_seconds']
            current, actual = frame_at(args.video, obs)
            # Only current/past frames reach the model. Future frames are for display.
            result = predict_model(str(args.video), obs, tuple(row['box']),
                                         args.model.stat().st_mtime_ns, str(args.model))
            prediction = result['alternatives'][0]
            case = dict(id=row['id'], observation_seconds=obs, decoded_observation_seconds=actual,
                        target_seconds=target, truth=row['target_action'], prediction=prediction,
                        supported_target=row['target_action'] in model['classes'],
                        alternatives=result['alternatives'], actor_box=row['box'],off_ball_motion=result.get('off_ball_motion'),conditional_options=result.get('conditional_options',[]))
            cases.append(case)
            frozen = current.copy()
            x1,y1,x2,y2 = map(int,row['box'])
            cv2.rectangle(frozen,(x1,y1),(x2,y2),(140,235,170),3)
            cv2.putText(frozen,'16 | reviewed actor',(x1,max(30,y1-12)),
                        cv2.FONT_HERSHEY_SIMPLEX,1,(140,235,170),2,cv2.LINE_AA)
            cap = cv2.VideoCapture(str(args.video))
            fps = cap.get(cv2.CAP_PROP_FPS)
            next_index = int(np.floor(obs*fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, next_index)
            future = current
            for k in range(85):
                elapsed = k/25
                shown = obs + max(0, elapsed-.8)
                desired_index = int(np.floor(shown*fps+1e-6))
                while next_index <= desired_index:
                    ok, decoded = cap.read()
                    if not ok:
                        raise ValueError('Cannot decode reviewed future')
                    future = decoded
                    next_index += 1
                canvas = np.full((540,1280,3),(24,19,12),np.uint8)
                canvas[100:460,:640] = fit_panel(frozen)
                canvas[100:460,640:] = fit_panel(future)
                def text(line,x,y,color=(228,236,231),size=.55):
                    cv2.putText(canvas,line,(x,y),cv2.FONT_HERSHEY_SIMPLEX,size,color,1,cv2.LINE_AA)
                text('RODRI STUDIO | '+args.domain.upper()+' FOOTAGE | frozen model, no retraining',16,27)
                text(row['id']+' | reviewer-provided identity box; not automatic identification',16,53)
                options=result.get('conditional_options',[])
                line=(f"If an on-ball event occurs: {options[0]['action']} ({options[0]['probability']:.0%} conditional score)" if options else 'Receiving depends on a pass arriving; labels measure observed outcomes.')
                text(line,16,79,size=.5)
                text(f'OBSERVATION {obs:.2f}s | prediction made here',16,486)
                text(f"Next: {prediction['action']} ({prediction['probability']:.0%} score)",16,515)
                text(f'ACTUAL FUTURE | source {shown:.2f}s',656,486)
                if shown < target:
                    text('Reviewed future label hidden until target',656,515)
                else:
                    suffix = ' | UNSUPPORTED by this model' if not case['supported_target'] else (' | correct' if prediction['action']==row['target_action'] else ' | incorrect')
                    text('Actual: '+row['target_action']+suffix,656,515,(120,160,255),.5)
                writer.write(canvas)
            cap.release()
    finally:
        writer.release()
    report = dict(source_type=args.domain, checkpoint_selection_source=model.get('held_out_metrics',{}).get('selection_source','unknown'),
                  checkpoint_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  checkpoint_training_matches=model['training_matches'],
                  classes=model['classes'], metrics=summarize(cases,model['classes']),
                  cases=cases, independent_human_review=False,
                  limitations=['Reviewed identity boxes supplied; not an automatic identity benchmark.',
                               'Single reviewer, selected cases; no population accuracy estimate.',
                               'Synthetic footage cannot establish real-match accuracy.',
                               'No fitting or checkpoint changes performed by this script.'])
    args.out.with_suffix('.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['metrics']))


if __name__ == '__main__':
    main()
