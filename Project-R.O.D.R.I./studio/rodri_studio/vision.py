"""Conservative per-shot tracks. IDs never imply player names."""
from pathlib import Path
import cv2
import numpy as np


def signature(frame):
    small = cv2.resize(frame, (64, 36))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist, cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(float)


def boundary(previous, current):
    if previous is None:
        return True
    hist_delta = cv2.compareHist(previous[0], current[0], cv2.HISTCMP_BHATTACHARYYA)
    pixel_delta = np.mean(np.abs(previous[1] - current[1])) / 255
    return bool(hist_delta > .55 or pixel_delta > .27)


def appearance(frame, box):
    x1, y1, x2, y2 = map(int, box)
    crop = frame[max(0,y1):max(0,y2), max(0,x1):max(0,x2)]
    if not crop.size:
        return np.zeros(24)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0], None, [24], [0,180]).ravel()
    return h / max(float(h.sum()), 1)


class Tracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, frame, timestamp):
        height, width = frame.shape[:2]
        candidates = []
        vectors = [appearance(frame, d['box']) for d in detections]
        for i, det in enumerate(detections):
            b = np.array(det['box']) / [width,height,width,height]
            center = (b[:2] + b[2:]) / 2
            for tid, old in self.tracks.items():
                dt = timestamp - old['t']
                if not 0 < dt <= .7:
                    continue
                distance = np.linalg.norm(center - old['center'])
                color = np.abs(vectors[i] - old['appearance']).sum() / 2
                if distance < .065 and color < .55:
                    candidates.append((distance + .07 * color, i, tid))
        assigned, used = {}, set()
        for _, i, tid in sorted(candidates):
            if i not in assigned and tid not in used:
                assigned[i], used = tid, used | {tid}
        result = []
        for i, det in enumerate(detections):
            tid = assigned.get(i)
            if tid is None:
                tid = self.next_id
                self.next_id += 1
            b = np.array(det['box']) / [width,height,width,height]
            center = (b[:2]+b[2:])/2
            old = self.tracks.get(tid)
            velocity = ((center-old['center'])/(timestamp-old['t'])).tolist() if old else [0.,0.]
            self.tracks[tid] = dict(center=center, appearance=vectors[i], t=timestamp)
            result.append(dict(**det, track=tid, center=center.tolist(), velocity=velocity))
        self.tracks = {k:v for k,v in self.tracks.items() if timestamp-v['t'] <= .7}
        return result


class Detector:
    def __init__(self, backend='yolo', weights='yolo11n.pt'):
        self.backend = backend
        if backend == 'yolo':
            from ultralytics import YOLO
            bundled = Path(__file__).resolve().parents[1] / 'models' / weights
            self.model = YOLO(str(bundled) if bundled.exists() else weights)
        elif backend == 'hog':
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        else:
            raise ValueError('Detector must be yolo or hog')

    def detect(self, frame):
        if self.backend == 'yolo':
            result = self.model.predict(frame, classes=[0], device='cpu', conf=.3, imgsz=960, verbose=False)[0]
            return [{'box':b[:4].tolist(), 'confidence':float(b[4])} for b in result.boxes.data.cpu().numpy()]
        scale = min(1., 960/frame.shape[1])
        image = cv2.resize(frame, None, fx=scale, fy=scale)
        if image.shape[0] < 128 or image.shape[1] < 64:
            return []
        boxes, scores = self.hog.detectMultiScale(image, winStride=(8,8), scale=1.05)
        return [dict(box=[float(x/scale),float(y/scale),float((x+w)/scale),float((y+h)/scale)], confidence=float(1/(1+np.exp(-float(s))))) for (x,y,w,h),s in zip(boxes,scores)]
