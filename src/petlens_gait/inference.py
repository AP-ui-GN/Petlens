"""RT-DETR and AP-10K RTMPose inference for PetLens V2.

Pose rawScore values are uncalibrated model responses, not probabilities.
This module does not make clinical gait assessments.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

NAMES = (
    "left_eye", "right_eye", "nose", "neck", "root_of_tail",
    "left_shoulder", "left_elbow", "left_front_paw",
    "right_shoulder", "right_elbow", "right_front_paw",
    "left_hip", "left_knee", "left_back_paw",
    "right_hip", "right_knee", "right_back_paw",
)
DETECTOR = "PekingU/rtdetr_r50vd_coco_o365"

class Models:
    def __init__(self, pose_path, revision):
        import torch
        from transformers import RTDetrImageProcessor, RTDetrForObjectDetection
        from rtmlib import RTMPose
        self.torch = torch
        self.processor = RTDetrImageProcessor.from_pretrained(DETECTOR, revision=revision)
        self.detector = RTDetrForObjectDetection.from_pretrained(DETECTOR, revision=revision).eval()
        self.pose = RTMPose(onnx_model=str(pose_path), model_input_size=(256,256),
                           backend='onnxruntime', device='cpu', to_openpose=False)

    def __call__(self, image):
        import cv2
        inputs = self.processor(images=cv2.cvtColor(image,cv2.COLOR_BGR2RGB), return_tensors='pt')
        with self.torch.inference_mode(): outputs = self.detector(**inputs)
        result = self.processor.post_process_object_detection(
            outputs, threshold=.30, target_sizes=self.torch.tensor([image.shape[:2]]))[0]
        dogs = [(float(s), b.tolist()) for s,l,b in zip(result['scores'],result['labels'],result['boxes'])
                if self.detector.config.id2label[int(l)] == 'dog']
        record = {'detectionSuccess':False,'keypoints':[], 'dogCandidateCount':len(dogs)}
        if len(dogs)!=1:
            record['failureReason'] = 'no_dog_detection' if not dogs else 'multiple_dogs_identity_ambiguous'
            return record
        score, box = dogs[0]
        h,w = image.shape[:2]
        box = [max(0,min(w,box[0])),max(0,min(h,box[1])),max(0,min(w,box[2])),max(0,min(h,box[3]))]
        if box[2]<=box[0] or box[3]<=box[1]:
            record['failureReason']='invalid_detection_box'; return record
        record.update(detectionSuccess=True,detectionConfidence=score,boundingBoxXyxy=box)
        try:
            points,scores = self.pose(image, bboxes=[box])
            if points.shape!=(1,17,2) or scores.shape!=(1,17): raise ValueError('Unexpected AP-10K output shape')
            record['keypoints'] = [dict(name=n,x=float(p[0]),y=float(p[1]),rawScore=float(s))
                                   for n,p,s in zip(NAMES,points[0],scores[0])
                                   if all(math.isfinite(float(v)) for v in (*p,s))]
            if len(record['keypoints'])!=17: record['failureReason']='nonfinite_pose_points_omitted'
        except Exception as e:
            record.update(keypoints=[],failureReason=f'pose_error: {type(e).__name__}: {e}')
        return record


def infer(video, out, model):
    import cv2
    # Bind predictions to the actual working-video bytes, as required by the
    # existing contact preparer. A path alone cannot identify a source clip.
    fingerprint = hashlib.sha256()
    with Path(video).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            fingerprint.update(block)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened(): raise ValueError('Cannot open video')
    fps = cap.get(cv2.CAP_PROP_FPS)
    expected = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError("Invalid video dimensions")
    frames=[]
    try:
        if not math.isfinite(fps) or fps<=0: raise ValueError('Video FPS is unavailable')
        # Use decoder PTS, never silently replace invalid timestamps with index/FPS.
        with (out/'frame-log.jsonl').open('w') as log:
            while True:
                ok,image = cap.read()
                if not ok: break
                t = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                if not math.isfinite(t) or t<0 or (frames and t<=frames[-1]['timestampSeconds']):
                    raise ValueError('Decoder returned invalid/nonincreasing PTS; transcode explicitly before evaluation')
                try: record=model(image)
                except Exception as e:
                    record=dict(detectionSuccess=False,keypoints=[],failureReason=f'detector_error: {type(e).__name__}: {e}')
                record.update(frameIndex=len(frames),timestampSeconds=t)
                frames.append(record); log.write(json.dumps(record,allow_nan=False)+'\n'); log.flush()
    finally: cap.release()
    if expected>0 and len(frames)!=expected: raise ValueError(f'Decode count mismatch: expected {expected}, got {len(frames)}; see frame-log.jsonl')
    return dict(video=str(video),videoSha256=fingerprint.hexdigest(),
                detectorModel=DETECTOR,poseModel='OpenMMLab RTMPose-m AP-10K',
                frameCount=len(frames),fps=fps,width=width,height=height,frames=frames,keypointSchema='AP-10K, 17 keypoints',
                timestampConvention='OpenCV decoder POS_MSEC; playback uses nominal FPS',
                detectorConfidenceThreshold=.30,rawPredictionsWereSmoothedOrCorrected=False)
