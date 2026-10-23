"""
Read an .xlsx workbook's cell values with the standard library alone (an
.xlsx is a zip of XML parts), so reading a building's spreadsheets adds no
dependency. Values only: no formats, formulas or merged-cell spans. A
formula cell gives its cached value; an error cell its text (#REF!).

    sheets = read("workbook.xlsx")      # {sheet name: [Row, …]}, in tab order
    for row in sheets["Meters"]:
        row.number, row.cells           # 1-based row number, [str, …] from column A
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
# Characters a spreadsheet cell carries that read as nothing.
_INVISIBLE = str.maketrans({"​": "", "﻿": "", " ": " "})


@dataclass
class Row:
    number: int        # the sheet's row number, 1-based
    cells: list[str]   # column A onward; "" for an empty cell

    def cell(self, index: int) -> str:
        return self.cells[index] if 0 <= index < len(self.cells) else ""

    def filled(self) -> int:
        """How many cells hold something."""
        return sum(1 for c in self.cells if c)


def read(path: Path) -> dict[str, list[Row]]:
    """Every sheet's non-empty rows, by sheet name in tab order."""
    with zipfile.ZipFile(path) as z:
        shared = _shared_strings(z)
        book = ET.fromstring(z.read("xl/workbook.xml"))
        targets = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        out: dict[str, list[Row]] = {}
        for sheet in book.iter(f"{_MAIN}sheet"):
            target = targets[sheet.get(f"{_REL}id")].lstrip("/")
            part = target if target.startswith("xl/") else "xl/" + target
            out[sheet.get("name")] = _rows(ET.fromstring(z.read(part)), shared)
    return out


def _text(node: ET.Element) -> str:
    """The text of a string item: plain, or rich text in runs."""
    return "".join(t.text or "" for t in node.iter(f"{_MAIN}t"))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    return [_text(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_MAIN}si")]


def _column(ref: str) -> int:
    """A cell reference's 0-based column: "C7" → 2."""
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _value(c: ET.Element, shared: list[str]) -> str:
    kind, v = c.get("t"), c.find(f"{_MAIN}v")
    if kind == "inlineStr":
        is_ = c.find(f"{_MAIN}is")
        value = _text(is_) if is_ is not None else ""
    elif v is None or v.text is None:
        value = ""
    elif kind == "s":
        value = shared[int(v.text)]
    else:
        value = v.text
        if kind in (None, "n") and re.fullmatch(r"-?\d+\.0+", value):
            value = value.split(".")[0]          # 12.0 → 12
    return value.translate(_INVISIBLE).strip()


def _rows(sheet: ET.Element, shared: list[str]) -> list[Row]:
    rows: list[Row] = []
    for i, row in enumerate(sheet.iter(f"{_MAIN}row"), 1):
        cells: list[str] = []
        for j, c in enumerate(row.iter(f"{_MAIN}c")):
            col = _column(c.get("r")) if c.get("r") else j
            cells.extend([""] * (col + 1 - len(cells)))
            cells[col] = _value(c, shared)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(Row(int(row.get("r") or i), cells))
    return rows
