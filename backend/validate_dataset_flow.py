import io
import json
import tempfile
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import requests

IMAGE_SIZE = 96
PATCH = 24


def base_image(cls: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 110, (IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
    if cls == 0:
        cx, cy, radius = int(rng.integers(40, 52)), int(rng.integers(36, 52)), int(rng.integers(14, 20))
        cv2.circle(img, (cx, cy), radius, (180, 40, 40), -1)
    elif cls == 1:
        x0, y0 = int(rng.integers(20, 34)), int(rng.integers(20, 34))
        cv2.rectangle(img, (x0, y0), (x0 + 30, y0 + 30), (40, 70, 180), -1)
    else:
        x0, y0 = int(rng.integers(12, 30)), int(rng.integers(52, 66))
        cv2.rectangle(img, (x0, y0), (x0 + 60, y0 + 16), (40, 160, 60), -1)
    return img


root = Path(tempfile.mkdtemp(prefix='trustvision-e2e-'))
manifest = {}
counter = {'n': 0}


def add(cls: int, label: int, contributor: str, seed: int, transform=None, name: str | None = None):
    i = counter['n']
    counter['n'] += 1
    nm = name or f'img_{i:04d}'
    img = base_image(cls, seed)
    if transform is not None:
        img = transform(img)
    img_dir = root / 'images' / 'train'
    lbl_dir = root / 'labels' / 'train'
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(img_dir / f'{nm}.png'), img)
    (lbl_dir / f'{nm}.txt').write_text(f'{label} 0.5 0.5 0.4 0.4\n', encoding='utf-8')
    rel = f'images/train/{nm}.png'
    manifest[rel] = contributor
    return rel

for i in range(20):
    add(0, 0, 'team-alpha', 1000 + i)
for i in range(12):
    add(1, 1, 'team-alpha', 2000 + i)
for i in range(12):
    add(2, 2, 'team-alpha', 3000 + i)
for i in range(2):
    add(0, 0, 'team-alpha', 4000 + i, transform=lambda im: np.full_like(im, 255))
for i in range(10):
    add(0, 1, 'team-alpha', 5000 + i)
for i in range(4):
    add(0, 0, 'team-beta', 6000 + i)
for i in range(4):
    add(1, 1, 'team-beta', 6500 + i)

add(1, 1, 'team-beta', 7000, name='flood_0')
for i in range(6):
    rel = f'images/train/flood_{i + 1}.png'
    lbl = root / 'labels' / 'train' / f'flood_{i + 1}.txt'
    img_dir = root / 'images' / 'train'
    img = cv2.imread(str(root / 'images' / 'train' / 'flood_0.png'))
    img = np.clip(img.astype(int) + 4, 0, 255).astype(np.uint8)
    cv2.imwrite(str(img_dir / f'flood_{i + 1}.png'), img)
    lbl.write_text('1 0.5 0.5 0.4 0.4\n', encoding='utf-8')
    manifest[rel] = 'team-beta'


def trigger(im: np.ndarray) -> np.ndarray:
    out = im.copy()
    out[0:PATCH, IMAGE_SIZE - PATCH:] = 255
    return out

for i in range(4):
    add(0, 1, 'team-beta', 8000 + i, transform=trigger)

(root / 'contributors.json').write_text(json.dumps(manifest), encoding='utf-8')
(root / 'data.yaml').write_text('nc: 3\nnames: [red_circle, blue_square, green_bar]\n', encoding='utf-8')

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in root.rglob('*'):
        if path.is_file():
            zf.write(path, path.relative_to(root).as_posix())
buffer.seek(0)

health = requests.get('http://localhost:8100/health', timeout=10)
print('AI_HEALTH', health.status_code, health.json())

upload = requests.post(
    'http://localhost:8080/dataset/upload',
    files={'file': ('synthetic.zip', buffer.getvalue(), 'application/zip')},
    data={'name': 'SyntheticAegis', 'codename': 'AEGIS-1', 'format': 'YOLO', 'classification': 'OFFICIAL'},
    timeout=120,
)
print('UPLOAD_STATUS', upload.status_code)
print(upload.text[:1000])
if upload.status_code != 201:
    raise SystemExit(f'Upload failed: {upload.text}')
dataset_id = upload.json()['id']
print('DATASET_ID', dataset_id)

analyze = requests.post(
    'http://localhost:8080/dataset/analyze',
    json={
        'datasetId': dataset_id,
        'options': {
            'folds': 2,
            'batch_size': 8,
            'flip_confidence_gap': 0.2,
            'mislabel_min_count': 5,
            'mislabel_min_rate': 0.15,
        },
        'force': True,
    },
    timeout=120,
)
print('ANALYZE_STATUS', analyze.status_code)
print(analyze.text[:2000])
if analyze.status_code != 200:
    raise SystemExit(f'Analyze failed: {analyze.text}')

analysis_id = analyze.json()['id']

for _ in range(120):
    detail = requests.get(f'http://localhost:8080/dataset/{dataset_id}', timeout=20)
    if detail.status_code == 200:
        payload = detail.json()
        latest = payload.get('latestAnalysis')
        if latest and latest.get('status') in {'COMPLETED', 'FAILED', 'CANCELLED'}:
            print('FINAL_DETAIL', json.dumps(latest, indent=2)[:3000])
            if latest.get('status') == 'COMPLETED':
                print('END_TO_END_OK')
                raise SystemExit(0)
            raise SystemExit(f"Analysis ended in status {latest.get('status')}: {latest}")
    time.sleep(2)

raise SystemExit('Timed out waiting for analysis completion')
