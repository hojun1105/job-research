#!/usr/bin/env python3
"""Insert or refresh the stack × role heatmap in a daily report HTML.

Usage:
  python3 scripts/inject_heatmap.py docs/YYYY-MM-DD.html
  python3 scripts/inject_heatmap.py          # latest docs/????-??-??.html
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALIAS = {
    "Spring Boot": "Spring",
    "Spring Framework": "Spring",
    "Spring Security": "Spring",
    "Spring Data JPA": "Spring",
    "Spring MVC": "Spring",
    "Vue.js": "Vue",
    "vuex": "Vue",
    "NestJS": "Node.js",
    "React Native": "React",
    "AngularJS": "Angular",
}
STACKS = [
    "Java",
    "Spring",
    "Node.js",
    "Python",
    "PyTorch",
    "React",
    "TypeScript",
    "JavaScript",
    "Vue",
    "MySQL",
    "AWS",
    "C++",
]
ROLE_KEY = {
    "백엔드 · 서버": "backend",
    "프론트엔드": "frontend",
    "풀스택": "fullstack",
    "AI · 머신러닝": "ai",
}
COLS = [
    ("backend", "백엔드"),
    ("frontend", "프론트"),
    ("fullstack", "풀스택"),
    ("ai", "AI"),
]

CSS = """
.heat {
  background: var(--bg-elev);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin-top: 12px;
}
.heat h3 { margin: 0 0 6px; font-size: 15px; }
.heat-note { margin: 0 0 12px; color: var(--muted); font-size: 12px; }
.heat-table {
  display: grid;
  grid-template-columns: minmax(68px, 84px) repeat(4, minmax(0, 1fr));
  gap: 4px;
  width: 100%;
}
.heat-hd, .heat-lab, .heat-cell {
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
}
.heat-hd { color: var(--muted); text-align: center; padding-bottom: 4px; font-weight: 500; }
.heat-hd:first-child, .heat-lab { text-align: left; }
.heat-lab {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  align-self: center;
}
.heat-cell {
  min-height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
}
.heat-cell.is-zero { color: var(--muted); background: var(--chip); }
@media (max-width: 400px) {
  .heat { padding: 12px; }
  .heat-table { grid-template-columns: 62px repeat(4, minmax(0, 1fr)); gap: 3px; }
  .heat-hd, .heat-lab, .heat-cell { font-size: 10px; }
  .heat-cell { min-height: 30px; border-radius: 6px; }
}
"""


def _match_div(html: str, start: int) -> int:
    depth = 0
    for m in re.finditer(r"</?div\b[^>]*>", html[start:]):
        depth += -1 if m.group().startswith("</") else 1
        if depth == 0:
            return start + m.end()
    raise ValueError("unclosed div")


def parse_matrix(html: str) -> dict:
    roles = []
    for m in re.finditer(
        r"<section><h2>(백엔드 · 서버|프론트엔드|풀스택|AI · 머신러닝)", html
    ):
        roles.append((m.start(), m.group(1)))
    pub = html.find("<section><h2>대기업 공채")
    roles.append((pub if pub != -1 else len(html), "END"))
    matrix = defaultdict(lambda: Counter())
    for i in range(len(roles) - 1):
        start, name = roles[i]
        if name == "END":
            continue
        rk = ROLE_KEY[name]
        chunk = html[start : roles[i + 1][0]]
        for job in re.findall(r'<article class="job">(.*?)</article>', chunk, re.S):
            seen = set()
            for chip in re.findall(r'<span class="chip">([^<]+)</span>', job):
                lab = ALIAS.get(chip, chip)
                if lab in STACKS:
                    seen.add(lab)
            for lab in seen:
                matrix[lab][rk] += 1
    return matrix


def heat_html(matrix: dict) -> str:
    max_n = 1
    for s in STACKS:
        for rk, _ in COLS:
            max_n = max(max_n, matrix[s][rk])
    cells = ['<div class="heat-hd"></div>']
    for _, label in COLS:
        cells.append(f'<div class="heat-hd">{label}</div>')
    for s in STACKS:
        cells.append(f'<div class="heat-lab">{s}</div>')
        for rk, label in COLS:
            n = matrix[s][rk]
            if n == 0:
                cells.append(
                    f'<div class="heat-cell is-zero" title="{s} · {label} 0건">0</div>'
                )
            else:
                pct = 22 + round(78 * n / max_n)
                cells.append(
                    f'<div class="heat-cell" style="background:color-mix(in srgb,var(--accent) {pct}%,var(--chip));color:var(--ink)" title="{s} · {label} {n}건">{n}</div>'
                )
    return (
        '      <div class="heat">\n'
        "        <h3>스택 × 직무 히트맵</h3>\n"
        '        <p class="heat-note">직무 공고에서 해당 스택이 한 번 이상 언급된 건수. 공채 제외.</p>\n'
        '        <div class="heat-table" role="table" aria-label="스택 직무 히트맵">\n'
        f"          {''.join(cells)}\n"
        "        </div>\n"
        "      </div>\n"
    )


def inject(html: str) -> str:
    if ".heat {" not in html:
        anchor = "@media (max-width: 400px) {\n  .wrap { width: calc(100% - 24px); padding-top: 18px; }"
        if anchor not in html:
            html = html.replace("</style>", CSS + "\n</style>", 1)
        else:
            html = html.replace(anchor, CSS + anchor, 1)

    existing = html.find('<div class="heat">')
    if existing != -1:
        end = _match_div(html, existing)
        html = html[:existing] + html[end:]
        html = re.sub(r"\n{3,}", "\n\n", html)
        html = html.replace("</div>\n\n    </section>", "</div>\n    </section>")

    matrix = parse_matrix(html)
    block = heat_html(matrix)
    bars = html.find('<div class="bars">')
    if bars == -1:
        raise ValueError("bars section not found")
    bars_end = _match_div(html, bars)
    html = html[:bars_end] + "\n" + block + html[bars_end:]
    return html


def latest_report(docs: Path) -> Path:
    files = sorted(docs.glob("????-??-??.html"))
    if not files:
        raise SystemExit("no daily report in docs/")
    return files[-1]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) > 1:
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        paths = [latest_report(root / "docs")]
    for path in paths:
        original = path.read_text(encoding="utf-8")
        updated = inject(original)
        path.write_text(updated, encoding="utf-8")
        print(f"heatmap injected: {path}")


if __name__ == "__main__":
    main()
