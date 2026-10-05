"""Generated JS blocks stay valid JS whatever the site data contains."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_build"))
import generate_meter_registry  # noqa: E402
import jsblocks  # noqa: E402

UTILITIES = {"electricity": {"label": "Electricity", "kind": "electric"}}
CSV_HEADER = "id,tag,base,type,daily,monthly,parent_id,floor,column,zone,position,function,utility,tenant,tenant_display,main_display\n"


def _meter(**overrides) -> dict:
    m = {
        "id": 1, "tag": "Main Incomer", "base": 10000, "type": "Modbus", "daily": 0, "monthly": 0,
        "parent_id": None, "floor": "ground", "column": 0, "zone": "North", "position": None,
        "function": "Incomer", "utility": "electricity", "tenant": "", "tenant_display": False,
        "main_display": True,
    }
    m.update(overrides)
    return m


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_meter_registry_survives_quotes_and_backslashes(tmp_path: Path) -> None:
    # A value the generator didn't quote/escape used to break the JS.
    tag = 'Plant "A" \\ C:\\temp, n/a'
    js = tmp_path / "registry.js"
    js.write_text(jsblocks.render_meter_registry([_meter(tag=tag)])
                  + "\nprocess.stdout.write(JSON.stringify(METER_REGISTRY[0]));\n", encoding="utf-8")
    out = subprocess.run(["node", str(js)], capture_output=True, text=True, check=True).stdout
    entry = json.loads(out)
    assert entry["tag"] == tag
    assert entry["column"] == 0 and entry["position"] is None


def test_inject_writes_backslashes_verbatim(tmp_path: Path) -> None:
    js = tmp_path / "x.js"
    begin, end = jsblocks.POINTS
    js.write_text(f"before\n{begin}\nold\n{end}\nafter\n", encoding="utf-8")
    body = 'const POINTS = { p: { bacnet: "a\\\\b" } };'
    jsblocks.inject(js, jsblocks.POINTS, body)
    assert js.read_text(encoding="utf-8") == f"before\n{begin}\n{body}\n{end}\nafter\n"


def test_inject_fails_without_markers(tmp_path: Path) -> None:
    js = tmp_path / "x.js"
    js.write_text("no markers here\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="markers not found"):
        jsblocks.inject(js, jsblocks.POINTS, "x")


def test_non_integer_cell_names_the_meter(tmp_path: Path) -> None:
    csv = tmp_path / "meters.csv"
    csv.write_text(CSV_HEADER + "7,Riser,10600,Modbus,0,0,,3rd,East,East,1,Lighting,Electricity,,,\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"id='7' has column='East'"):
        generate_meter_registry.read_csv(csv, UTILITIES)


def test_na_and_null_cells_are_blank(tmp_path: Path) -> None:
    csv = tmp_path / "meters.csv"
    csv.write_text(CSV_HEADER + "7,Riser,10600,Modbus,n/a,,n/a,3rd,null,East,N/A,Lighting,Electricity,,,\n", encoding="utf-8")
    [m] = generate_meter_registry.read_csv(csv, UTILITIES)
    assert (m["daily"], m["monthly"], m["parent_id"], m["column"], m["position"]) == (0, 0, None, None, None)
