"""Bounded ZIP range access and contact sheets. Uses existing requests and OpenCV.

Network commands: python screen.py index | previews [wide] | fetch PREVIEW_NUMBER...
Never falls back to a full archive download. Per-run network budget: 350 MB.
"""
import csv
import io
import json
import struct
import sys
import time
import zipfile
from pathlib import Path

import cv2
import requests

ROOT = Path(__file__).resolve().parent
META = json.loads((ROOT / 'source/dataverse-metadata.json').read_text())['data']
FILES = {f['label']: f['dataFile'] for f in META['latestVersion']['files']}
BUDGET = 350_000_000
transferred = 0


def bounded_get(url, start=None, end=None, limit=2_000_000):
    global transferred
    headers = {'Range': f'bytes={start}-{end}'} if start is not None else {}
    with requests.get(url, headers=headers, stream=True, timeout=90) as r:
        r.raise_for_status()
        if start is not None:
            expected = f'bytes {start}-{end}/'
            if r.status_code != 206 or not r.headers.get('Content-Range', '').startswith(expected):
                raise RuntimeError('Server did not honor exact range; refusing full download')
            limit = end - start + 1
        if int(r.headers.get('Content-Length', 0)) > limit:
            raise RuntimeError('Response exceeds limit')
        chunks = []
        n = 0
        for chunk in r.iter_content(65536):
            n += len(chunk)
            transferred += len(chunk)
            if n > limit or transferred > BUDGET:
                raise RuntimeError('Download budget exceeded')
            chunks.append(chunk)
        if start is not None and n != limit:
            raise RuntimeError('Incomplete range')
        with (ROOT/'source/access-audit.jsonl').open('a') as log:
            log.write(json.dumps({'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                                 'url':url, 'start':start,'end':end,'bytes':n,
                                 'status':r.status_code,'content_range':r.headers.get('Content-Range')})+'\n')
        return b''.join(chunks)


class RemoteZip(io.RawIOBase):
    def __init__(self, name):
        f = FILES[name]
        self.size = f['filesize']
        self.url = f"https://dataverse.harvard.edu/api/access/datafile/{f['id']}"
        self.pos = 0
        self.cache = []

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else (self.pos if whence == 1 else self.size) + offset
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n == 0:
            return b''
        if n > 50_000_000:
            raise RuntimeError('Single read over 50 MB refused')
        for start, data in self.cache:
            if start <= self.pos and self.pos + n <= start + len(data):
                out = data[self.pos-start:self.pos-start+n]
                self.pos += n
                return out
        start = self.pos
        end = min(self.size - 1, start + max(n, 65536) - 1)
        data = bounded_get(self.url, start, end)
        self.cache.append((start, data))
        self.pos += n
        return data[:n]


def archive(name):
    return zipfile.ZipFile(RemoteZip(name))


def make_sheet(items, dest, cols=4, width=360, height=270):
    import numpy as np
    rows = (len(items) + cols - 1) // cols
    canvas = np.full((rows * height, cols * width, 3), 245, dtype=np.uint8)
    for i, (path, lines) in enumerate(items):
        im = cv2.imread(str(path))
        if im is None:
            continue
        scale = min((width-8)/im.shape[1], (height-65)/im.shape[0])
        im = cv2.resize(im, None, fx=scale, fy=scale)
        x, y = (i % cols)*width, (i // cols)*height
        canvas[y:y+im.shape[0], x:x+im.shape[1]] = im
        for j, line in enumerate(lines):
            cv2.putText(canvas, line[:49], (x+4, y+height-47+j*18), cv2.FONT_HERSHEY_SIMPLEX, .42, (25,25,25), 1, cv2.LINE_AA)
    cv2.imwrite(str(dest), canvas)


def main():
    cmd = sys.argv[1]
    if cmd == 'index':
        for name in ['bounding_boxes.tab', 'breeds.tab', 'splits.tab']:
            f = FILES[name]
            data = bounded_get(f"https://dataverse.harvard.edu/api/access/datafile/{f['id']}?format=original")
            (ROOT/'source'/name.replace('.tab', '.csv')).write_bytes(data)
        for name in ['Videos.zip', 'Images.zip']:
            with archive(name) as z:
                rows = [{'name':i.filename, 'size':i.file_size, 'compressed':i.compress_size,
                         'offset':i.header_offset, 'crc':i.CRC, 'method':i.compress_type} for i in z.infolist()]
                (ROOT/'source'/name.replace('.zip','-index.json')).write_text(json.dumps(rows, indent=2))
                print(name, len(rows), 'entries', flush=True)
    elif cmd == 'previews':
        boxes = list(csv.DictReader(open(ROOT/'source/bounding_boxes.csv')))
        wide = 'wide' in sys.argv[2:]
        ranked = sorted(boxes, key=lambda b: -float(b['width'])/float(b['height']) if wide else abs(float(b['width'])/float(b['height'])-1.65))
        names = {Path(i['name']).stem:i['name'] for i in json.loads((ROOT/'source/Images-index.json').read_text()) if i['name'].endswith('.jpg')}
        manifest = ROOT/'preview-manifest.json'
        previous = json.loads(manifest.read_text()) if manifest.exists() else []
        selected = []
        dogs = {b['DOG_ID'] for b in previous}
        for b in ranked:
            dog, vid = b['DOG_ID'], b['VIDEO_ID']
            if dog in dogs or float(b['height']) < (180 if wide else 300) or float(b['width']) < (350 if wide else 450):
                continue
            stem = dog+'-'+vid
            if stem not in names:
                continue
            dogs.add(dog)
            selected.append(dict(b, member=names[stem], number=len(previous)+len(selected)+1))
            if len(selected) == 100:
                break
        with archive('Images.zip') as z:
            for b in selected:
                p=ROOT/'previews'/f"{b['number']:03}.jpg"
                p.write_bytes(z.read(b['member']))
                print('preview', b['number'], flush=True)
        (ROOT/'preview-manifest.json').write_text(json.dumps(previous+selected, indent=2))
        for start in range(0,len(selected),20):
            make_sheet([(ROOT/'previews'/f"{b['number']:03}.jpg", [f"#{b['number']}  bbox {b['width']}x{b['height']}", b['DOG_ID'][:18]]) for b in selected[start:start+20]], ROOT/f'preview-sheet-{len(previous)//20+start//20+1}.jpg')
    elif cmd == 'fetch':
        with archive('Videos.zip') as z:
            for number in map(int,sys.argv[2:]):
                b=json.loads((ROOT/'preview-manifest.json').read_text())[number-1]
                member=b['member'].replace('Images/','Videos/').replace('.jpg','.mp4')
                info=z.getinfo(member)
                if info.file_size > 50_000_000:
                    print('skip oversized',number,info.file_size,flush=True)
                    continue
                out=ROOT/'videos'/f'{number:03}.mp4'
                out.write_bytes(z.read(member))
                cap=cv2.VideoCapture(str(out))
                fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                facts={'preview_number':number,'member':member,'dog_id':b['DOG_ID'],'video_id':b['VIDEO_ID'], 'fps':fps,'frames':count,'duration':count/fps if fps else None,'width':cap.get(3),'height':cap.get(4),'crc32':f'{info.CRC:08x}'}
                (out.with_suffix('.json')).write_text(json.dumps(facts,indent=2))
                items=[]
                for k in range(12):
                    frame=round(k*(count-1)/11)
                    cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,im=cap.read()
                    if ok:
                        path=ROOT/'previews'/f'{number:03}-t{k:02}.jpg';cv2.imwrite(str(path),im)
                        pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                        items.append((path,[f'#{number}  {pts:.3f}s decoded PTS',f'{facts["width"]:.0f}x{facts["height"]:.0f} avg {fps:.2f}fps']))
                cap.release()
                make_sheet(items, ROOT/f'video-{number:03}-sheet.jpg',cols=4)
                print(facts,flush=True)
    print('Transferred bytes:',transferred)


if __name__ == '__main__':
    main()
