import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
from build import REPORTS_JS

with open(REPORTS_JS, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace floor7-electricity-demand: with floor7_electricity_demand:
content = re.sub(r'(\s+)(floor\d+)-([\w]+)-([\w]+):', r'\1\2_\3_\4:', content)

with open(REPORTS_JS, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done! Replaced hyphens with underscores in key names.')
