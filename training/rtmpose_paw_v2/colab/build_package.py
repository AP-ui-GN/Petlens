"""Build an allowlisted, verified portable package. Does not execute any model."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / 'artifacts'
STAGE = ARTIFACTS / 'petlens-colab-100step'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert not STAGE.exists(), f'{STAGE} already exists; choose a clean staging location.'
    ARTIFACTS.mkdir(exist_ok=True)
    exp = 'reports/rtmpose-paw-v2-experiment/'
    train = 'training/rtmpose_paw_v2/'
    prov = json.loads((ROOT / exp / 'checkpoint-provenance.json').read_text())
    audit = json.loads((ROOT / exp / 'audit.json').read_text())
    checkpoint = ROOT / prov['checkpoint_path']
    assert sha(checkpoint) == prov['checkpoint_sha256'] == '896e3665d849ef7eb9b6ec0995955796cc9810f024fa0aa0bdc18acb0d68bf52'
    assert checkpoint.stat().st_size == prov['checkpoint_bytes']
    names = [train + name for name in ['components.py', 'pilot_config.py', 'preflight.py', 'prepare.py', 'run.sh', 'requirements-gpu.txt', 'requirements-cpu.lock.txt', 'requirements-cpu.txt']]
    names += [train + 'colab/' + name for name in ['verify_package.py', 'setup.sh', 'cuda_check.py', 'run.sh', 'README.md', 'build_package.py']]
    names += [exp + name for name in ['pilot-train.coco.json', 'buffer-excluded.coco.json', 'temporal-diagnostic.coco.json', 'all-reviewed.coco.json', 'audit.json', 'checkpoint-provenance.json', 'cpu-preflight.json', 'onnx-architecture.json', 'image-verification.json']]
    names += ['training/canine_keypoint_schema.json', 'reports/paw-annotation-data-v2/train.coco.json', 'reports/paw-annotation-data-v2/manifest.json']
    for name, expected in audit['image_sha256'].items():
        rel = audit['image_root'] + '/' + name
        assert sha(ROOT / rel) == expected, rel
        names.append(rel)
    source_manifest = json.loads((ROOT / 'reports/paw-annotation-data-v2/manifest.json').read_text())
    assert sha(ROOT / 'reports/paw-annotation-data-v2/train.coco.json') == source_manifest['outputSha256']['train.coco.json']
    assert sha(ROOT / 'training/canine_keypoint_schema.json') == source_manifest['sourceConfiguration']['keypointSchema']['sha256']
    for name in names:
        source, target = ROOT / name, STAGE / name
        assert source.is_file() and not source.is_symlink(), name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    ckpt_rel = 'models/' + checkpoint.name
    (STAGE / 'models').mkdir()
    shutil.copyfile(checkpoint, STAGE / ckpt_rel)
    shutil.copyfile(STAGE / train / 'colab/README.md', STAGE / 'README.md')
    notebook = make_notebook()
    (STAGE / 'PetLens_100step_Colab.ipynb').write_text(json.dumps(notebook, indent=2) + '\n')
    shutil.copyfile(STAGE / 'PetLens_100step_Colab.ipynb', ARTIFACTS / 'PetLens_100step_Colab.ipynb')
    records = {p.relative_to(STAGE).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(STAGE.rglob('*')) if p.is_file()}
    (STAGE / 'PACKAGE_MANIFEST.json').write_text(json.dumps(dict(schema_version=1, checkpoint=ckpt_rel, files=records), indent=2) + '\n')
    subprocess.run([sys.executable, str(STAGE / train / 'colab/verify_package.py')], check=True, cwd=STAGE)
    archive = ARTIFACTS / 'petlens-colab-100step.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(STAGE.rglob('*')):
            if p.is_file():
                z.write(p, 'petlens-colab-100step/' + p.relative_to(STAGE).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(records) + 1
        for name in z.namelist():
            rel = name.split('/', 1)[1]
            assert hashlib.sha256(z.read(name)).hexdigest() == sha(STAGE / rel), rel
    checksum = sha(archive)
    (ARTIFACTS / (archive.name + '.sha256')).write_text(f'{checksum}  {archive.name}\n')
    report = dict(archive=str(archive.relative_to(ROOT)), archive_bytes=archive.stat().st_size,
                  uncompressed_bytes=sum(p.stat().st_size for p in STAGE.rglob('*') if p.is_file()),
                  payload_files=len(records), checkpoint_sha256=sha(checkpoint), archive_sha256=checksum,
                  archive_members_verified=True, training_started=False, cuda_test_run_here=False)
    (ARTIFACTS / 'petlens-colab-package-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

def make_notebook():
    cells = []
    def cell(kind, source):
        c = dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True))
        if kind == 'code':
            c.update(execution_count=None, outputs=[])
        cells.append(c)
    cell('markdown', '# PetLens V2 — fixed 100-step T4 pilot\nUpload the package ZIP and `.sha256` using the left Files panel. Select a T4 GPU runtime. Setup only checks compatibility; training runs in its own cell. Download results before disconnecting. No GitHub push is needed.\n')
    cell('code', '''from pathlib import Path
import hashlib, zipfile
archive = Path('/content/petlens-colab-100step.zip')
expected = Path(str(archive) + '.sha256').read_text().split()[0]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, 'Archive SHA256 mismatch'
root = Path('/content/petlens-colab-100step')
assert not root.exists(), 'Already extracted: use existing directory or a fresh runtime'
with zipfile.ZipFile(archive) as z:
    for entry in z.infolist():
        path = Path(entry.filename)
        assert not path.is_absolute() and '..' not in path.parts
        assert path.parts[0] == 'petlens-colab-100step'
        assert (entry.external_attr >> 16) & 0o170000 != 0o120000
    z.extractall('/content')
%cd /content/petlens-colab-100step
!python training/rtmpose_paw_v2/colab/verify_package.py
''')
    cell('markdown', '## Setup and preflight (no optimizer steps)\nDownloads the pinned software environment. Verifies package hashes, exact pretrained weights, data pipelines and real CUDA kernels/model gradients. A failure stops this cell.\n')
    cell('code', "import subprocess\nsubprocess.run(['bash', 'training/rtmpose_paw_v2/colab/setup.sh'], check=True)\n")
    cell('markdown', '## Start the fixed 100-step pilot\nRun this cell only when ready to train. It evaluates the baseline, performs 100 optimizer steps, saves `iter_100.pth`, evaluates the candidate and archives outputs. The diagnostic frames are from the same video and cannot establish generalization.\n')
    cell('code', "subprocess.run(['bash', 'training/rtmpose_paw_v2/colab/run.sh', 'train'], check=True)\n")
    cell('markdown', '## Download results\nThe archive includes the final model, metrics, paired predictions, logs, resolved configuration, dependency versions, hashes and adapter source.\n')
    cell('code', "from google.colab import files\nfiles.download('/content/petlens-pilot-results.tar.gz')\n")
    return dict(nbformat=4, nbformat_minor=5, metadata=dict(accelerator='GPU', kernelspec=dict(name='python3', display_name='Python 3')), cells=cells)

if __name__ == '__main__':
    main()
