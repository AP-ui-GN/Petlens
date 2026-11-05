"""Verify portable inputs without third-party dependencies or model execution."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]

def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = json.loads((ROOT / 'PACKAGE_MANIFEST.json').read_text())
    for name, record in manifest['files'].items():
        path = ROOT / name
        assert path.is_file() and not path.is_symlink(), name
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    audit = json.loads((ROOT / 'reports/rtmpose-paw-v2-experiment/audit.json').read_text())
    source = ROOT / 'reports/paw-annotation-data-v2/train.coco.json'
    assert sha(source) == audit['source_sha256']
    data = json.loads(source.read_text())
    assert len(data['images']) == 46 and len(data['annotations']) == 42
    assert sum(a['num_keypoints'] for a in data['annotations']) == 79
    for image in data['images']:
        path = ROOT / audit['image_root'] / image['file_name']
        assert sha(path) == audit['image_sha256'][image['file_name']]
        raw = path.read_bytes()
        assert raw[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', raw[16:24]) == (image['width'], image['height'])
    groups = []
    for split, expected in [('pilot-train', (20, 39)), ('buffer-excluded', (10, 20)), ('temporal-diagnostic', (10, 17))]:
        path = ROOT / f'reports/rtmpose-paw-v2-experiment/{split}.coco.json'
        assert sha(path) == audit['splits'][split]['sha256']
        subset = json.loads(path.read_text())
        assert (len(subset['images']), sum(a['num_keypoints'] for a in subset['annotations'])) == expected
        assert all((ROOT / audit['image_root'] / i['file_name']).is_file() for i in subset['images'])
        groups.append({i['id'] for i in subset['images']})
    assert all(not groups[i] & groups[j] for i in range(3) for j in range(i))
    checkpoint = ROOT / manifest['checkpoint']
    assert sha(checkpoint) == '896e3665d849ef7eb9b6ec0995955796cc9810f024fa0aa0bdc18acb0d68bf52'
    print(f"PASS: {len(manifest['files'])} payload files; original checkpoint, 46 images, source labels and fixed splits match recorded hashes.")

if __name__ == '__main__':
    main()
