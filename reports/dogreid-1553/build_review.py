"""Regenerate local comparison and provenance; no network or pose inference."""
import csv
import hashlib
import html
import json
import zlib
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent

NOTES = {
17: ('reject','Walking interspersed with sniffing; overhead view, leaf obstruction, severe camera movement and cropping.'),
53: ('reject','Walking on sand; steep downward view and severe progressive camera roll; not stable lateral footage.'),
56: ('reject','Mostly sniffing/stopping; overhead view and hindquarters cropped during later steps.'),
78: ('reject','Brief steps followed by standing/turning; snow and dark fur obscure feet; insufficient sustained cycles.'),
82: ('reject','Snow play, jumps and fast movement; dog frequently leaves frame; not sustained walking.'),
83: ('reject','Some lead walking; steep overhead view, hindquarters repeatedly cropped, then sitting/stopping.'),
86: ('reject','Brief walking away then sitting; overhead/rear view and fur obscure hind paws.'),
92: ('reject','Running/playing and rolling on grass; short, distant dog; not walking.'),
106: ('reject','Side-on but mostly stationary, alert and shifting/brief steps; no sustained walking cycles; VFR.'),
115: ('review_only','Best slow-walking lead, 0–2.8 s. Elevated oblique view, short duration and mottled ground reduce far-hind-paw clarity. Complete cycle count not certified.'),
122: ('reject','Indoor toy play, turns and approaches; camera tilt and cropping; no sustained lateral walk.'),
140: ('reject','Standing and panting; almost unchanged posture throughout; no walking cycles.'),
170: ('reject','Walking and sniffing but predominantly rear/overhead view; intermittent stops; insufficient lateral cycles.'),
180: ('reject','Ball play/running away; distant dog and camera movement; no sustained lateral walk.'),
182: ('reject','Brief movement then lying/rolling; grass hides paws despite high source resolution.'),
195: ('reject','A few walking steps then stop; only 1.87 s, elevated oblique view, insufficient complete cycles.'),
198: ('review_only','Best longer locomotion lead, inspect 0–4.5 s. Walk versus brisk trot remains uncertain. Camera follows from above, far hind paw intermittently overlaps. Later curb/second dog/blur unsuitable.'),
}


def write_csv(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def validate_identity_splits(rows):
    assigned={}
    for row in rows:
        key=row['identity_group_key']
        split=row.get('petlens_split','unassigned')
        if split == 'unassigned':
            continue
        if key in assigned and assigned[key] != split:
            raise ValueError(f'Identity leakage: {key}')
        assigned[key]=split


def main():
    boxes=list(csv.DictReader(open(ROOT/'source/bounding_boxes.csv')))
    breeds={r['DOG_ID']:r['BREED'] for r in csv.DictReader(open(ROOT/'source/breeds.csv'))}
    splits={(r['DOG_ID'],r['VIDEO_ID']):r for r in csv.DictReader(open(ROOT/'source/splits.csv'))}
    index={i['name']:i for i in json.loads((ROOT/'source/Videos-index.json').read_text())}
    previews=json.loads((ROOT/'preview-manifest.json').read_text())
    source='https://doi.org/10.7910/DVN/LVTRLG'
    rows=[]
    for p in sorted((ROOT/'videos').glob('*.json')):
        row=json.loads(p.read_text());n=row['preview_number'];video=p.with_suffix('.mp4')
        data=video.read_bytes();entry=index[row['member']]
        assert len(data)==entry['size']
        assert zlib.crc32(data)==entry['crc']
        official=splits[(row['dog_id'],row['video_id'])]
        status,note=NOTES[n]
        row.update(breed=breeds[row['dog_id']],identity_group_key='dogreid1553:'+row['dog_id'].casefold(),
                   petlens_split='unassigned', dataset_doi=source,dataset_version='3.2',
                   dataverse_video_file_id=13653939,license='CC0-1.0',
                   source_group=official['GROUP'],source_split_closed=official['SPLIT_CLOSED_SET'],
                   source_split_open=official['SPLIT_OPEN_SET'],status=status,screening_notes=note,
                   sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
                   local_video=str(video.relative_to(ROOT)), training_approved=False)
        rows.append(row)
    validate_identity_splits(rows)
    (ROOT/'screened-videos.json').write_text(json.dumps(rows,indent=2))
    write_csv(ROOT/'screened-videos.csv',rows)
    registry=[]
    for dog in sorted(breeds):
        registry.append({'DOG_ID':dog,'identity_group_key':'dogreid1553:'+dog.casefold(),
                         'BREED':breeds[dog],'petlens_split':'unassigned',
                         'video_count':sum(b['DOG_ID']==dog for b in boxes)})
    write_csv(ROOT/'identity-registry.csv',registry)
    reviewed={r['preview_number']:r for r in rows}
    prescreen=[]
    for b in previews:
        n=b['number'];r=reviewed.get(n)
        prescreen.append({**b,'identity_group_key':'dogreid1553:'+b['DOG_ID'].casefold(),
                          'review_stage':'video_sampled' if r else 'first_frame_only',
                          'decision':r['status'] if r else 'not_shortlisted_from_first_frame',
                          'reason':r['screening_notes'] if r else 'Static preview did not provide a strong enough lead for this bounded screen; motion not assessed.'})
    write_csv(ROOT/'preview-screening.csv',prescreen)
    show=[115,198,53,170,195]
    times={115:[0,.67,1.33,2.33],198:[0,.67,1.33,3.0],53:[0,.67,2,4],170:[0,1.43,4.3,6.43],195:[0,.33,.83,1.5]}
    canvas=np.full((len(show)*310,1600,3),247,np.uint8)
    cards=[]
    for j,n in enumerate(show):
        r=reviewed[n];cap=cv2.VideoCapture(str(ROOT/r['local_video']));frame_links=[]
        header=f"#{n} {r['breed']} | {r['duration']:.2f}s | {r['width']:.0f}x{r['height']:.0f} | avg {r['fps']:.2f} fps | {r['status'].upper()}"
        cv2.putText(canvas,header,(10,j*310+24),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1,cv2.LINE_AA)
        for k,t in enumerate(times[n]):
            cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,im=cap.read()
            if not ok:raise RuntimeError(f'Missing frame {n} {t}')
            actual=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            path=ROOT/'previews'/f'review-{n:03}-{k}.jpg';cv2.imwrite(str(path),im)
            h,w=im.shape[:2];scale=min(390/w,225/h);small=cv2.resize(im,None,fx=scale,fy=scale)
            x=k*400+5;y=j*310+36;canvas[y:y+small.shape[0],x:x+small.shape[1]]=small
            cv2.putText(canvas,f't={actual:.3f}s',(x,j*310+281),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1,cv2.LINE_AA)
            frame_links.append(f'<a href="previews/{path.name}"><img src="previews/{path.name}" alt="Video {n} at {actual:.3f} seconds"><span>{actual:.3f} s</span></a>')
        cap.release()
        cards.append(f'''<article><h2>{html.escape(header)}</h2><p>{html.escape(r['screening_notes'])}</p>
<div class="frames">{''.join(frame_links)}</div><video controls preload="metadata" src="{r['local_video']}"></video>
<p>Dog: <code>{r['dog_id']}</code><br>Video: <code>{r['video_id']}</code><br>Identity group: <code>{r['identity_group_key']}</code><br>PetLens split: unassigned. Training approved: false.</p>
<p><a href="video-{n:03}-sheet.jpg">12-frame sequence</a> · <a href="{r['local_video']}">Original extracted MP4</a></p></article>''')
    cv2.imwrite(str(ROOT/'comparison.jpg'),canvas)
    (ROOT/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>DogReID-1553 PetLens review</title>
<style>body{font:16px system-ui;max-width:1500px;margin:30px auto;padding:20px;background:#fafafa;color:#222}article{border-top:2px solid #bbb;padding:16px 0}.frames{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.frames img{width:100%;height:220px;object-fit:contain;background:#eee}.frames span{display:block}video{width:500px;max-height:420px;margin-top:14px}code{overflow-wrap:anywhere}h2{font-size:20px}</style>
<h1>DogReID-1553: human review</h1><p><b>0 strict passes. 2 review-only leads. The last 3 rows are rejected comparisons, not selected training candidates.</b></p>
<p>Screened 200 first-frame crops and 17 individual videos. These are actual extracted source frames, with no synthesized imagery or pose overlays. All clips remain excluded from training pending human review.</p>
<p>Source: <a href="https://doi.org/10.7910/DVN/LVTRLG">DogReID-1553, Harvard Dataverse V3.2</a>. License: <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</a>. <a href="screened-videos.csv">Full screening CSV</a> · <a href="README.md">Investigation report</a></p>'''+''.join(cards))
    print(f'Validated CRC32 and SHA256 for {len(rows)} clips; {len(registry)} dog groups; comparison generated.')


if __name__=='__main__':
    main()
