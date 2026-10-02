import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
from build import REPORTS_JS

with open(REPORTS_JS, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
new_lines = []
for line in lines:
    # Match pattern: Floor7 - Electricity - Demand: /images/...
    m = re.match(r'^(Floor\d+)\s*-\s*(\w+)\s*-\s*(\w+):\s*(/images/.+)$', line)
    if m:
        floor = m.group(1).lower()
        typ = m.group(2).lower()
        report = m.group(3).lower()
        url = m.group(4)
        new_line = '        {}_{}_{}: "{}",'.format(floor, typ, report, url)
        new_lines.append(new_line)
    elif re.match(r'^---\s*Run:', line):
        continue
    else:
        new_lines.append(line)

with open(REPORTS_JS, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print('Done! Transformed all Floor entries.')
