"""
One-shot helper: parse meters_hierarchy.htm (hand-written tree of nested
<ul>/<li> meter nodes) and emit a Python dict literal mapping each meter id
to its parent meter id (0 = root). The output is meant to be pasted back
into either meter_tmp.csv or directly into meter-templates.js.

Usage:  python _build/extract_hierarchy.py

Each <li> in the file wraps a meter via <a href=".../meter.id=X">. A nested
<ul> inside that <li> means X has children. We walk the tree using
html.parser, maintaining a stack of (open <li>'s meter id) entries.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTM = ROOT / "meters_hierarchy.htm"

METER_HREF_RE = re.compile(r"meter\.id=(\d+)")


class HierarchyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        # Stack of meter ids representing the path from the outermost <li>
        # currently open down to the innermost. We push a placeholder None
        # when an <li> opens and replace it with the actual id once we see
        # the meter's <a href>. We pop when the <li> closes.
        self.stack: list[int | None] = []
        self.parent_of: dict[int, int] = {}

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.stack.append(None)
        elif tag == "a":
            href = dict(attrs).get("href", "")
            m = METER_HREF_RE.search(href)
            if m and self.stack and self.stack[-1] is None:
                meter_id = int(m.group(1))
                self.stack[-1] = meter_id
                # parent = the nearest ancestor in the stack that's already
                # been resolved (i.e. not None and not us)
                parent = 0
                for ancestor in reversed(self.stack[:-1]):
                    if ancestor is not None:
                        parent = ancestor
                        break
                self.parent_of[meter_id] = parent

    def handle_endtag(self, tag):
        if tag == "li" and self.stack:
            self.stack.pop()


def main() -> None:
    text = HTM.read_text(encoding="utf-8")
    parser = HierarchyParser()
    parser.feed(text)

    print(f"Extracted {len(parser.parent_of)} meters from hierarchy")
    # Print as a Python dict literal, sorted by meter id
    print()
    print("PARENT_OF = {")
    for meter_id in sorted(parser.parent_of):
        parent_id = parser.parent_of[meter_id]
        print(f"    {meter_id}: {parent_id},")
    print("}")


if __name__ == "__main__":
    main()
