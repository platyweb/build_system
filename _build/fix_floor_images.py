import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
from build import SITE_DIR

files = [str(p) for p in SITE_DIR.glob('floor_*.htm')]
for f in files:
    text = open(f, 'r', encoding='utf-8').read()
    updated = text.replace('"img/floor_', '"img/floors/floor_')
    if updated != text:
        open(f, 'w', encoding='utf-8').write(updated)
        print(f'  updated {f}')
print(f'Done. Checked {len(files)} floor HTML files.')
