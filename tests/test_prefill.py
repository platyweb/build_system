"""_build/prefill.py: a site's floors, meters and tenants drafted from its
documents in sources/ (an import workbook, a meter schedule, the controller's
meter export), and re-run as more documents arrive. The documents here are
invented, written as .xlsx by the helper below; xlsx.py reads them."""
from __future__ import annotations

import csv
import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from urllib.parse import parse_qsl
from xml.sax.saxutils import escape

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
import build  # noqa: E402
import meters_yaml  # noqa: E402
import prefill  # noqa: E402
import site_data  # noqa: E402
import xlsx  # noqa: E402

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def write_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    """An .xlsx with these sheets: text in the shared strings, whole
    numbers as numbers, None an empty cell."""
    shared: list[str] = []

    def cell(ref: str, value) -> str:
        if value is None:
            return ""
        if isinstance(value, int):
            return f'<c r="{ref}"><v>{value}</v></c>'
        if value not in shared:
            shared.append(value)
        return f'<c r="{ref}" t="s"><v>{shared.index(value)}</v></c>'

    def column(c: int) -> str:
        return (column(c // 26 - 1) if c >= 26 else "") + chr(65 + c % 26)

    with zipfile.ZipFile(path, "w") as z:
        for i, rows in enumerate(sheets.values(), 1):
            body = "".join(f'<row r="{r}">' + "".join(cell(f"{column(c)}{r}", v) for c, v in enumerate(row)) + "</row>"
                           for r, row in enumerate(rows, 1))
            z.writestr(f"xl/worksheets/sheet{i}.xml", f'<worksheet xmlns="{MAIN}"><sheetData>{body}</sheetData></worksheet>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>'
                   + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(sheets, 1))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
                   + "</Relationships>")
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{MAIN}">'
                   + "".join(f"<si><t>{escape(s)}</t></si>" for s in shared) + "</sst>")


METER_HEADER = ["name", "description", "utility", "parent", "driver", "calculation_meters"]
COLOURS = ["#097234", "#77C4BC", "#134C6E", "#2AA7F2", "#D7F7E1", "#E6AF00", "#E6AF00", "#9D7EA4", "#988E3F", "#446307"]


def report_row(name: str, chart: str, report: str, meters: list[str]) -> list:
    return [name, None, chart, report, "Electricity", "this-week", "Auto", 0, "#2B2B2A",
            *(meters + [None] * (10 - len(meters))), *COLOURS]
WORKBOOK = {
    "Meters": [
        METER_HEADER,
        ["ACM - FL1 West Core 1 L", "Lighting", 0, None, "Modbus", None],
        ["ACM - FL1 West Core 1 P", "Power", 0, None, "Modbus", None],
        ["ACM - FL1 East Core 1 P", "Power", 0, None, "Modbus", None],
        ["ACM - DB/T/2L", "Lighting", 0, None, "Modbus", None],
        ["ACM - DB/T/2P", "Power", 0, None, "Modbus", None],
        ["ACM - Floor 01 Total Electricity", None, 0, None, "Aggregate",
         "ACM - FL1 West Core 1 L,ACM - FL1 West Core 1 P,ACM - FL1 East Core 1 P"],
        ["ACM - Floor 02 Total Electricity", None, 0, None, "Aggregate", "ACM - DB/T/2L,ACM - DB/T/2P"],
        ["ACM - Main Incomer", None, 0, None, "Modbus", None],
        ["ACM - Lift 1", None, 0, None, "Modbus", None],
        ["ACM - Roof Plant", None, 0, None, "Modbus", None],
    ],
    "Meters_BCK": [   # a backup sheet: another building's rows, and one of ours again
        METER_HEADER,
        ["OTH - Somewhere Else", None, 0, None, "Modbus", None],
        ["ACM - Lift 1", "Passenger lift", 0, None, "Modbus", None],
    ],
    "CustomMeterPoints": [
        ["meter", "parameter", "period", "frequency", "description", "instance"],
        ["ACM - Floor 01 Total Electricity", "Active Energy", "This", "month", None, 2000001],
        ["ACM - Floor 01 Total Electricity", "Active Energy", "Previous To Today Equivalent", "month", None, 2000101],
        ["ACM - Floor 02 Total Electricity", "Active Energy", "This", "month", None, "#REF!"],
    ],
    "Reports": [   # the meter columns' headers repeat, as the real sheet's do
        ["name", "description", "chart", "report", "utility", "period", "breakup", "comparison", "text-color",
         *[f"meter{n}" for n in (1, 2, 3, 4, 5, 7, 7, 8, 9, 10)], *[f"meter{n}-color" for n in (1, 2, 3, 4, 5, 7, 7, 8, 9, 10)]],
        report_row("ACM - Floor01 - Electricity - Demand", "area", "demand", ["ACM - Floor 01 Total Electricity"]),
        report_row("ACM - Floor01 - West - Electricity - Demand", "area", "demand",
                   ["ACM - FL1 West Core 1 L", "ACM - FL1 West Core 1 P"]),
        report_row("ACM - Floor01 - Electricity - Consumption", "bar", "consumption", ["ACM - Floor 01 Total Electricity"]),
        report_row("ACM - Floor02 - Electricity - Demand", "area", "demand", ["ACM - DB/T/2L", "ACM - DB/T/2P"]),
        report_row("ACM - Floor03 - Electricity - Demand", "area", "demand", ["ACM - Nowhere"]),
        report_row("OTH - Floor01 - Electricity - Demand", "area", "demand", ["OTH - Somewhere Else"]),
    ],
}
SCHEDULE = {
    "Electrical": [
        [" ELECTRICAL METERS"],
        ["Meter No.", "Description", "Switch Board", "Tenant", "Location"],
        ["Gateway 1 - IP 10.0.0.1"],                                     # a section heading
        ["West Floor 1", "LIGHITNG", "n/a", "Fern and Company Limited", "West Core 1"],
        ["West Floor 1", "POWER", "n/a", "Fern and Company Limited", "West Core 1"],
        ["East Floor 1", "POWER", "n/a", "Landlord", "East Core 1"],
        ["Lift 1", "Passenger lift", "SB-1", "Landlord", "LV Room"],
        ["Spare way", "Spare", "SB-1", "Landlord", "LV Room"],
        ["Notes"],
        ["1", "the end of the meters"],
    ],
    "Gas": [
        [" GAS METERS"],
        ["Meter No.", "Serving", "Location"],
        ["G-01", "Boilers", "Plant room"],
    ],
}


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """examples/minimal, menu floors + tenants, with the workbook and schedule in sources/."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "examples" / "minimal", site, ignore=shutil.ignore_patterns("golden"))
    for name in ("04_points.yaml", "08_meters_hierarchy.yaml", "14_reports.yaml", "15_extras.yaml"):
        (site / "data" / name).unlink()
    (site / "data" / "01_pages.yaml").write_text(
        "sections:\n  - header: METERING\n    items:\n"
        "      - { label: Floors, icon: bxs-building, pages: floors }\n"
        "      - { label: Tenants, icon: bxs-user-badge, pages: tenants }\n", encoding="utf-8")
    (site / "sources").mkdir()
    write_xlsx(site / "sources" / "import.xlsx", WORKBOOK)
    write_xlsx(site / "sources" / "schedule.xlsx", SCHEDULE)
    return site


def run(site: Path, *args: str) -> int:
    return prefill.main(["--site", str(site), *args])


def meters(site: Path) -> dict[str, dict]:
    cores = {lv["key"]: lv["cores"] for lv in site_data.read_levels()}
    return {r["tag"]: r for r in meters_yaml.read(site_data.data_path("meters.yaml"), site_data.UTILITIES, cores)}


def settings(site: Path, text: str) -> None:
    (site / "sources" / "prefill.yaml").write_text(text, encoding="utf-8")


def test_it_wont_overwrite_data_files_it_didnt_write(site: Path) -> None:
    before = (site / "data" / "03_meters.yaml").read_text(encoding="utf-8")
    assert run(site) == 1
    assert (site / "data" / "03_meters.yaml").read_text(encoding="utf-8") == before


def test_a_draft_from_the_workbook_and_schedule(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings(site, "first_id: 100\n")
    assert run(site, "--replace") == 0
    out = capsys.readouterr().out
    m = meters(site)
    assert "OTH - Somewhere Else" not in m and len(m) == 10           # this building's prefix only
    # Provisional ids in workbook order, the base from the id.
    assert [m[t]["id"] for t in ("ACM - FL1 West Core 1 L", "ACM - Roof Plant")] == [100, 109]
    assert m["ACM - Roof Plant"]["base"] == (109 + 99) * 100
    assert m["ACM - Floor 01 Total Electricity"]["type"] == "Calculation"
    # Cores from the schedule or the name; a total's members on its level.
    west_l = m["ACM - FL1 West Core 1 L"]
    assert (west_l["floor"], west_l["zone"], west_l["column"], west_l["position"]) == ("1st", "West Core 1", 0, 0)
    assert (m["ACM - FL1 West Core 1 P"]["position"], m["ACM - FL1 East Core 1 P"]["column"]) == (1, 2)
    assert (m["ACM - DB/T/2L"]["floor"], m["ACM - DB/T/2L"]["zone"]) == ("2nd", "Floor")
    total = m["ACM - Floor 01 Total Electricity"]
    assert (total["floor"], total["zone"], total["function"]) == ("1st", "", "Floor Total Electricity")
    assert (total["daily"], total["monthly"]) == (2000001, 2000101)
    assert m["ACM - Floor 02 Total Electricity"]["daily"] == 0          # #REF! isn't a point
    assert m["ACM - Lift 1"]["floor"] == "" and m["ACM - Lift 1"]["function"] == "Lift 1"
    assert m["ACM - Lift 1"]["parent_id"] is None
    # Tenants: the schedule's, by short name; the landlord's core isn't listed.
    assert m["ACM - FL1 West Core 1 L"]["tenant"] == "Fern" and m["ACM - FL1 West Core 1 L"]["tenant_display"]
    assert m["ACM - FL1 East Core 1 P"]["tenant"] == ""
    floors = yaml.safe_load(site_data.data_path("floors.yaml").read_text(encoding="utf-8"))
    assert floors == {"floor_1st": {"label": "1st Floor", "cores": {"West Core 1": "Fern"}},
                      "floor_2nd": {"label": "2nd Floor"}}
    tenants = yaml.safe_load(site_data.data_path("tenants.yaml").read_text(encoding="utf-8"))
    assert tenants == {"tenants": {"Fern": {"name": "Fern and Company Limited", "index": {}}}}
    # The report: what's provisional, what didn't match, the backup sheet's disagreement.
    assert "ids are numbered from first_id 100" in out
    assert "Electrical row 8: Spare way | Spare | LV Room" in out
    assert "Gas row 3: G-01 | Boilers | Plant room" in out
    assert "ACM - Lift 1: description" not in out                      # empty vs set isn't a disagreement
    assert "ACM - Roof Plant → roof" in out                              # named for a level, no evidence
    assert (site / "sources" / prefill.REPORT).exists()


def test_the_draft_builds(site: Path, tmp_path: Path) -> None:
    assert run(site, "--replace") == 0
    build.configure(site, tmp_path / "project")
    assert build.validate() == 0


def test_a_rerun_keeps_its_files_and_stops_at_an_edited_one(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(site, "--replace") == 0
    assert run(site) == 0
    assert capsys.readouterr().out.count(": unchanged") == 4
    path = site_data.data_path("meters.yaml")
    path.write_text(path.read_text(encoding="utf-8").replace("function: Lift 1", "function: Lift"), encoding="utf-8")
    assert run(site) == 1
    assert "edited since" in capsys.readouterr().out
    assert "function: Lift," in path.read_text(encoding="utf-8")
    assert run(site, "--replace") == 0
    assert "function: Lift 1" in path.read_text(encoding="utf-8")


def test_the_controller_export_fills_ids_and_parents_on_a_rerun(site: Path) -> None:
    assert run(site, "--replace") == 0
    tags = [row[0] for row in WORKBOOK["Meters"][1:]]
    with (site / "sources" / "meters-export.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "tag", "base", "type", "parent_id"])
        for i, tag in enumerate(tags):
            parent = "" if tag == "ACM - Main Incomer" else 507
            w.writerow([501 + i, tag.replace("ACM - Main", "ACM -Main"), 60000 + i, "", parent])
    assert run(site) == 0
    m = meters(site)
    assert m["ACM -Main Incomer"]["id"] == 508 and m["ACM -Main Incomer"]["parent_id"] is None
    assert (m["ACM - Lift 1"]["id"], m["ACM - Lift 1"]["base"], m["ACM - Lift 1"]["parent_id"]) == (509, 60008, 507)
    assert m["ACM -Main Incomer"]["type"] == "Modbus"                  # the workbook's, joined by name


def test_corrections_in_the_settings(site: Path) -> None:
    settings(site, 'meters:\n  "ACM - Roof Plant": {floor: 1st, core: West Core 1}\n'
                   '  "ACM - DB/T/2P": {function: Small Power}\n'
                   'tenants:\n  "Fern and Company Limited": {short: Fern & Co, docs: false}\n'
                   'levels:\n  1st: {label: First Floor}\n')
    assert run(site, "--replace") == 0
    m = meters(site)
    assert (m["ACM - Roof Plant"]["floor"], m["ACM - Roof Plant"]["zone"], m["ACM - Roof Plant"]["tenant"]) == \
        ("1st", "West Core 1", "Fern & Co")
    assert m["ACM - DB/T/2P"]["function"] == "Small Power"
    assert yaml.safe_load(site_data.data_path("tenants.yaml").read_text(encoding="utf-8")) == \
        {"tenants": {"Fern & Co": {"name": "Fern and Company Limited", "index": {}, "docs": False}}}
    assert yaml.safe_load(site_data.data_path("floors.yaml").read_text(encoding="utf-8"))["floor_1st"]["label"] == \
        "First Floor"


def test_an_unknown_setting_stops_it(site: Path) -> None:
    settings(site, "first_ids: 3\n")
    with pytest.raises(SystemExit, match="unknown setting"):
        run(site)


@pytest.mark.parametrize("text, level", [
    ("ACM - FL3 East Core 1 P", "3rd"), ("Floor 02 Total", "2nd"), ("Floor 00", "ground"),
    ("DB/L/G1-Total", "ground"), ("Grd DB-Power", "ground"), ("LG DB-Lighting", "lower_ground"),
    ("Floor Lower Ground Total", "lower_ground"), ("DB/L/B2", "basement"), ("Basement 2", "basement_2"),
    ("12th Floor Plantroom", "12th"), ("Thirteenth Floor", "13th"), ("Upper Roof", "upper_roof"),
    ("Roof Plant", "roof"), ("Mezzanine", "mezzanine"), ("Main Incomer", ""), ("SB-L01", ""),
])
def test_level_names(text: str, level: str) -> None:
    assert prefill.level_finder({})(text) == level


def test_a_level_the_settings_name() -> None:
    level_of = prefill.level_finder({"1st": {"match": [r"\bFloor 01\b"]}, "podium": {"match": ["podium"]}})
    assert (level_of("Floor 01 Total"), level_of("Podium DB"), level_of("Floor 02")) == ("1st", "podium", "2nd")


def test_levels_order_bottom_to_top() -> None:
    keys = ["roof", "2nd", "basement_2", "ground", "lower_ground", "basement", "12th", "mezzanine", "1st"]
    assert sorted(keys, key=prefill.level_rank) == \
        ["basement_2", "basement", "lower_ground", "ground", "mezzanine", "1st", "2nd", "12th", "roof"]


@pytest.mark.parametrize("proper, short", [
    ("Fern and Company Limited", "Fern"), ("Howard Kennedy LLP", "Howard Kennedy"),
    ("Institutional Shareholder Services UK Limited", "Institutional Shareholder"), ("Acme", "Acme"),
])
def test_tenant_short_names(proper: str, short: str) -> None:
    assert prefill.short_name(proper) == short


def test_xlsx_reads_shared_and_inline_strings_and_numbers(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    write_xlsx(path, {"One": [["a", None, 7], [], ["​b "]]})
    with zipfile.ZipFile(path, "a") as z:   # a second sheet, written the way some exporters do
        z.writestr("xl/worksheets/sheet9.xml", f'<worksheet xmlns="{MAIN}"><sheetData><row r="2">'
                   '<c r="C2" t="inlineStr"><is><t>x</t></is></c><c r="D2"><v>12.0</v></c>'
                   '<c r="E2" t="e"><v>#REF!</v></c></row></sheetData></worksheet>')
    sheets = xlsx.read(path)
    assert [(r.number, r.cells) for r in sheets["One"]] == [(1, ["a", "", "7"]), (3, ["b"])]
    root = xlsx.ET.fromstring(zipfile.ZipFile(path).read("xl/worksheets/sheet9.xml"))
    assert [(r.number, r.cells) for r in xlsx._rows(root, [])] == [(2, ["", "", "x", "12", "#REF!"])]


# ─── Report cards ────────────────────────────────────────────────────────────
# site1's chart for one meter, with an invented meter: the house style, byte for byte.
EXPECTED_URL = (
    "/images/dynamic/UtilityReport.png?cacheId=1&is2D=true&energylogOutputs[0].meterId=7&energylogOut"
    "puts[0].label=DB%2F1-Total&energylogOutputs[0].parameter=0&energylogOutputs[0].colour=rgb(9%2C%2"
    "0114%2C%2052)&showChartTitle=true&chartTitle=default&showChartSubTitle=true&chartSubTitle=defaul"
    "t&displayLegend=true&vAlignment=bottom&hAlignment=center&headingTextColour=rgb(43%2C%2043%2C%204"
    "2)&domainAxisColour=rgb(43%2C%2043%2C%2042)&rangeAxisColour=rgb(43%2C%2043%2C%2042)&legendTextCo"
    "lour=rgb(43%2C%2043%2C%2042)&legendBackgroundColour=rgba(0%2C%200%2C%200%2C%200)&plotBackgroundC"
    "olour=rgba(0%2C%200%2C%200%2C%200)&hierarchyLevel=0&timeSpan.progressive=true&timeSpan.timeScale"
    "Steps=0&timeSpan.intervalTimePeriod=AUTO&timeSpan.timePeriod=THIS&timeSpan.thisTimeScale=WEEK&ti"
    "meSpan.firstDayOfWeek=2&startFromCommissioningDate=false&customUnits[0]=48&customUnits[1]=&custo"
    "mUnits[2]=&customUnits[3]=48&customUnits[4]=&customUnits[5]=&previousSteps=&previousYearSteps=&m"
    "ainTitleStyle.usesDefault=true&mainTitleStyle.name=DejaVu%20Sans&mainTitleStyle.size=26&mainTitl"
    "eStyle.isBold=true&mainTitleStyle.isItalic=false&subTitleStyle.usesDefault=true&subTitleStyle.na"
    "me=DejaVu%20Sans&subTitleStyle.size=16&subTitleStyle.isBold=false&subTitleStyle.isItalic=false&x"
    "axisStyle.usesDefault=true&xaxisStyle.name=DejaVu%20Sans&xaxisStyle.size=12&xaxisStyle.isBold=fa"
    "lse&xaxisStyle.isItalic=false&yaxisStyle.usesDefault=true&yaxisStyle.name=DejaVu%20Sans&yaxisSty"
    "le.size=12&yaxisStyle.isBold=false&yaxisStyle.isItalic=false&keyStyle.usesDefault=true&keyStyle."
    "name=DejaVu%20Sans&keyStyle.size=14&keyStyle.isBold=false&keyStyle.isItalic=false&showXAxis=true"
    "&xAxisLabelRotate=1&yAxisLabelRotate=0&xAxisAbbrLabel=true&showYAxis=true&chartType=chart-area&r"
    "eportType=report-demand&utilityType=electricity&width=1600&height=400"
)


def test_the_chart_url_is_the_house_style() -> None:
    assert prefill.chart_url(1, [(7, "DB/1-Total", prefill.rgb("#097234", ""))], "area", "demand", "electricity",
                             prefill.rgb("#2B2B2A", ""), ("THIS", "WEEK"), "AUTO", prefill.CHART_UNITS["demand"]) \
        == EXPECTED_URL


def test_report_cards_from_the_workbook(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings(site, "first_report_id: 200\n"
                   "report_ids: {ACM - Floor02 - Electricity - Demand: 555}\n"
                   "reports:\n  urls: {own_chart: /img/own.png}\n"
                   "  placements: [{image_ref: own_chart, page: floor, floor: 2nd, slot: electricity, position: 9}]\n")
    assert run(site, "--replace") == 0
    m = meters(site)
    reports = yaml.safe_load(site_data.data_path("reports.yaml").read_text(encoding="utf-8"))
    card = {"page": "floor", "slot": "electricity"}
    demand, consumption = "📊 Electricity Demand", "📊 Electricity Consumption"
    assert reports["placements"] == [
        {"id": 200, "image_ref": "floor_1st_electricity_demand", "alt": demand, **card, "position": 0, "floor": "1st"},
        {"id": 202, "image_ref": "floor_1st_electricity_consumption", "alt": consumption, **card, "position": 1,
         "floor": "1st"},
        {"id": 201, "image_ref": "floor_1st_electricity_west_demand", "alt": demand, **card, "position": 2,
         "floor": "1st", "title": "West Demand"},
        {"id": 555, "image_ref": "floor_2nd_electricity_demand", "alt": demand, **card, "position": 0, "floor": "2nd"},
        {"image_ref": "own_chart", "page": "floor", "floor": "2nd", "slot": "electricity", "position": 9},
    ]
    west = dict(parse_qsl(reports["urls"]["floor_1st_electricity_west_demand"]))
    assert (west["energylogOutputs[0].meterId"], west["energylogOutputs[1].meterId"]) == \
        (str(m["ACM - FL1 West Core 1 L"]["id"]), str(m["ACM - FL1 West Core 1 P"]["id"]))
    assert (west["energylogOutputs[0].label"], west["energylogOutputs[1].colour"]) == \
        ("FL1 West Core 1 L", "rgb(119, 196, 188)")
    consumption_url = dict(parse_qsl(reports["urls"]["floor_1st_electricity_consumption"]))
    assert (consumption_url["chartType"], consumption_url["customUnits[2]"]) == ("chart-bar", "521")
    assert reports["urls"]["own_chart"] == "/img/own.png"
    out = capsys.readouterr().out
    assert "Reports with no meter (no card) (1):\n  ACM - Floor03 - Electricity - Demand" in out
    assert "OTH - Floor01" not in out


# ─── Floorplans ──────────────────────────────────────────────────────────────
def png(width: int = 2, height: int = 1) -> bytes:
    """A blank PNG."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + b"\xff\xff\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def pdf() -> bytes:
    """A blank one-page PDF."""
    objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
               b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)


@pytest.mark.parametrize("name, level", [
    ("Ninth_Floor.emf", "9th"), ("L3.svg", "3rd"), ("l12.svg", "12th"), ("Level_7.emf", "7th"),
    ("24571F-AB-07B-Fifth.pdf", "5th"), ("floor_ground.png", "ground"), ("Lower_Ground.svg", "lower_ground"),
    ("Upper Roof.emf", "upper_roof"), ("Site plan.pdf", ""),
])
def test_a_drawing_is_named_for_its_level(tmp_path: Path, name: str, level: str) -> None:
    (tmp_path / name).write_bytes(b"")
    report = prefill.Report()
    plan = prefill.plan_floorplans(tmp_path, prefill.level_finder({}), {level} if level else set(), report)
    assert plan == ({level: tmp_path / name} if level else {})


def test_floorplans_from_the_drawings(site: Path, capsys: pytest.CaptureFixture[str]) -> None:
    drawings = site / "sources" / "floorplans"
    drawings.mkdir()
    (drawings / "First_Floor.emf").write_bytes(b"")
    (drawings / "floor_1st.png").write_bytes(png())          # preferred to the EMF
    (drawings / "Second Floor.svg").write_bytes(b"<svg/>")
    (drawings / "Roof.png").write_bytes(png())                # no page on the roof
    floors = site / "assets" / "img" / "floors"
    assert run(site, "--replace") in (0, 1)                   # 1 if no SVG converter is installed
    out = capsys.readouterr().out
    assert (floors / "floor_1st.png").read_bytes() == png()
    assert "1st: floor_1st.png, First_Floor.emf" in out
    assert "Roof.png → roof" in out
    if not any(shutil.which(tool) for tool, _ in prefill.CONVERTERS[".svg"]):
        assert "floor_2nd.png: not made from Second Floor.svg — needs a converter: sudo apt install inkscape" in out
    # Made once: a re-run keeps it, --replace makes it again.
    (floors / "floor_1st.png").write_bytes(png(3))
    run(site)
    assert (floors / "floor_1st.png").read_bytes() == png(3)
    assert "floor_1st.png: kept" in capsys.readouterr().out
    run(site, "--replace")
    assert (floors / "floor_1st.png").read_bytes() == png()


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm (poppler-utils) isn't installed")
def test_a_pdf_drawing_becomes_a_png(tmp_path: Path) -> None:
    (tmp_path / "Third.pdf").write_bytes(pdf())
    assert prefill.make_floorplan(tmp_path / "Third.pdf", tmp_path / "out" / "floor_3rd.png") is None
    made = (tmp_path / "out" / "floor_3rd.png").read_bytes()
    assert made[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", made[16:24]) == (2400, 1200)
