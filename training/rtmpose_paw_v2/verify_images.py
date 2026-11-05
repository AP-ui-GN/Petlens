"""Decode images/source video and check frame correspondence; no model calls."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from training.rtmpose_paw_v2.prepare import ROOT, SOURCE, IMAGES, OUT


def main():
    data = json.loads((SOURCE / 'train.coco.json').read_text())
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    source = manifest['sourceConfiguration']['sequences'][0]['video']
    video = ROOT / source['path']
    assert hashlib.sha256(video.read_bytes()).hexdigest() == source['sha256']
    images = {i['frame_id']: i for i in data['images']}
    first, last = min(images), max(images)
    cap = cv2.VideoCapture(str(video))
    frames = {}
    try:
        for index in range(last + 2):
            ok, frame = cap.read()
            assert ok
            if index >= first - 1:
                frames[index] = frame
    finally:
        cap.release()
    means, maxima = [], []
    for index, image in images.items():
        png = cv2.imread(str(IMAGES / image['file_name']))
        assert png is not None and png.shape[:2] == (image['height'], image['width'])
        errors = {f: float(np.abs(png.astype(np.int16) - frames[f].astype(np.int16)).mean())
                  for f in range(index - 1, index + 2)}
        assert min(errors, key=errors.get) == index, (index, errors)
        means.append(errors[index])
        maxima.append(int(np.abs(png.astype(np.int16) - frames[index].astype(np.int16)).max()))
    result = dict(opencv=cv2.__version__, fully_decoded_pngs=len(images),
                  source_video_sha256=source['sha256'], source_frame_best_matches=len(images),
                  comparison='zero-based source frame versus adjacent frames; no resize or rotation',
                  mean_absolute_color_difference_range=[min(means), max(means)],
                  maximum_channel_difference=max(maxima),
                  note='PNG export used OpenCV 5.0.0; current 4.10.0 decoding has small color differences. Reviewed PNG hashes are authoritative.')
    (OUT / 'image-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
