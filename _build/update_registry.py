import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make build.py importable
from build import REPORTS_JS

with open(REPORTS_JS, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the available floor report URL keys
url_keys = set(re.findall(r'(\bfloor\d+_\w+_\w+)\s*:', content))

# Build ordinal suffix mapping
def ordinal(n):
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd'][n%10] if n%10 < 4 else 'th'}"

# Determine which floors have URLs
floor_nums = set()
for key in url_keys:
    m = re.match(r'floor(\d+)_', key)
    if m:
        floor_nums.add(int(m.group(1)))

floor_nums = sorted(floor_nums)

# Generate new REPORT_REGISTRY entries for ALL floors
new_entries = []
for n in floor_nums:

    fl_ord = ordinal(n)
    fl_key = f"floor{n}"

    # Check which types exist for this floor
    has_elec = f"{fl_key}_electricity_demand" in url_keys
    has_lthw = f"{fl_key}_lthw_demand" in url_keys
    has_chw = f"{fl_key}_chw_demand" in url_keys

    if has_elec:
        new_entries.append(f'    {{ image_ref: "{fl_key}_electricity_demand", alt: "📊 Electricity Demand", page: "floor", slot: "electricity", position: 0, floor: "{fl_ord}" }},')
        new_entries.append(f'    {{ image_ref: "{fl_key}_electricity_consumption", alt: "📊 Electricity Consumption", page: "floor", slot: "electricity", position: 1, floor: "{fl_ord}" }},')
    if has_lthw:
        new_entries.append(f'    {{ image_ref: "{fl_key}_lthw_demand", alt: "📊 Heating Energy Demand", page: "floor", slot: "heat", position: 0, floor: "{fl_ord}" }},')
        new_entries.append(f'    {{ image_ref: "{fl_key}_lthw_consumption", alt: "📊 Heating Energy Consumption", page: "floor", slot: "heat", position: 1, floor: "{fl_ord}" }},')
    if has_chw:
        new_entries.append(f'    {{ image_ref: "{fl_key}_chw_demand", alt: "📊 Cooling Energy Demand", page: "floor", slot: "cooling", position: 0, floor: "{fl_ord}" }},')
        new_entries.append(f'    {{ image_ref: "{fl_key}_chw_consumption", alt: "📊 Cooling Energy Consumption", page: "floor", slot: "cooling", position: 1, floor: "{fl_ord}" }},')

new_entries_text = '\n'.join(new_entries)

# Replace the entire REPORT_REGISTRY array
lines = content.split('\n')
begin_idx = None
end_idx = None

for i, line in enumerate(lines):
    if 'BEGIN GENERATED REPORT_REGISTRY' in line:
        begin_idx = i
    if 'END GENERATED REPORT_REGISTRY' in line:
        end_idx = i
        break

# Keep everything before the BEGIN marker, then the marker + array open,
# then all new entries, then close array + END marker, then rest of file
header_lines = lines[:begin_idx+1]  # up to and including BEGIN comment
header_lines.append('const REPORT_REGISTRY = [')

# Build the new content
new_content_lines = header_lines + new_entries_text.split('\n') + ['];', '// ── END GENERATED REPORT_REGISTRY ──'] + lines[end_idx+1:]

with open(REPORTS_JS, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_content_lines))

print(f'Done! Updated REPORT_REGISTRY with {len(new_entries)} entries for floors 7+.')
print(f'Floors with URLs: {floor_nums}')
