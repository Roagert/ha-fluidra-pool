#!/usr/bin/env python3
"""Print backlog progress and regenerate backlog/PROGRESS.md (points-weighted)."""
import re
from pathlib import Path

HERE = Path(__file__).parent
DONE, WEIGHT = {"done", "dropped"}, {"done": 1.0, "in_progress": 0.5}

rows = []
for f in sorted(HERE.glob("[TU][0-9][0-9]-*.md")):
    meta = dict(re.findall(r"^(\w+): (.*)$", f.read_text().split("---")[1], re.M))
    rows.append((meta["id"], meta["title"], meta["phase"], int(meta["points"]), meta["status"], meta["owner"]))

total = sum(r[3] for r in rows if r[4] != "dropped")
earned = sum(r[3] * WEIGHT.get(r[4], 0) for r in rows if r[4] != "dropped")
pct = round(100 * earned / total) if total else 0
bar = "#" * (pct // 5) + "." * (20 - pct // 5)

lines = [f"# Progress: {pct}%  [{bar}]  ({earned:g}/{total} points)", "",
         "in_progress counts half. Regenerate with `python3 backlog/progress.py`.", "",
         "| ID | Task | Phase | Pts | Status | Owner |", "|---|---|---|---|---|---|"]
lines += [f"| {i} | {t} | {p} | {pt} | {s} | {o} |" for i, t, p, pt, s, o in rows]
(HERE / "PROGRESS.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
