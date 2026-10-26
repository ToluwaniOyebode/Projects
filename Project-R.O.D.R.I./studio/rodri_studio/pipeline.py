import cv2
import numpy as np
from .vision import Detector, Tracker, signature, boundary
from .edited_video import timeline_for


def inspect(path):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError('Cannot decode this video. Convert it to MP4 H.264 with FFmpeg.')
        fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not np.isfinite(fps) or fps<=0 or frames<=0:
            raise ValueError('Video has invalid FPS or frame count.')
        return dict(fps=fps, frames=int(frames), duration=frames/fps,width=int(cap.get(3)),height=int(cap.get(4)))
    finally:
        cap.release()


def analyze(path,start,duration,backend,progress=lambda p:None, detector=None):
    meta = inspect(path)
    if not np.isfinite(start) or not np.isfinite(duration) or start<0 or not 0<duration<=120 or start>=meta['duration']:
        raise ValueError('Choose a valid start and 1–120 seconds inside the video.')
    detector = detector or Detector(backend)
    cap = cv2.VideoCapture(str(path)); tracker = Tracker()
    step = max(1,round(meta['fps']/5)); first=int(start*meta['fps'])
    last=min(meta['frames'],int((start+duration)*meta['fps']))
    cap.set(cv2.CAP_PROP_POS_FRAMES,first)
    timeline=timeline_for(path)
    edit_cuts=[s for s in timeline.starts[1:] if start<s<start+duration] if timeline else []
    previous=None; previous_segment=None; shot=0; history=[]; frames=[]; cuts=[]
    try:
        for index in range(first,last):
            ok,frame=cap.read()
            if not ok:
                break
            if (index-first)%step:
                continue
            t=index/meta['fps']; sig=signature(frame)
            segment=timeline.segment(t)['continuous_sequence_id'] if timeline else None
            if segment != previous_segment:
                history=[]
            if segment != previous_segment or boundary(previous,sig):
                shot+=1; tracker=Tracker(); cuts.append(t)
            # A duplicate image is only a suspicion. It may be live, static play.
            duplicate=any(t-old_t>8 and float(np.mean(np.abs(sig[1]-old_gray)))<3 for old_t,old_gray in history[::5])
            history.append((t,sig[1])); previous=sig;previous_segment=segment
            frames.append(dict(time=t,shot=shot,replay_suspected=duplicate,detections=tracker.update(detector.detect(frame),frame,t),edit_sequence=segment,original_source_seconds=timeline.source_time(t) if timeline else t))
            progress((index-first)/max(1,last-first))
    finally:
        cap.release()
    if not frames:
        raise ValueError('No frames could be decoded.')
    return dict(metadata=meta,frames=frames,cuts=sorted(set(cuts+edit_cuts)),edit_cuts=edit_cuts,actor_scope=timeline.metadata.get('actor_scope','rodri') if timeline else 'rodri',rodri_present=timeline.metadata.get('rodri_present') if timeline else None,detector=backend,identities={},replays=[],annotations=[])
