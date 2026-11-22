#!/usr/bin/env python3
"""并排比较多份基准结果(compare-runs 的输入是 summarize-cli.py --json 的输出)。

    python3 tools/bench/compare-runs.py a.json b.json ... 
    python3 tools/bench/compare-runs.py --base a.json b.json    # 以 a 为基准算差值

前提: 同种子时才是"配对"比较, 逐局同源, 差值可信; 不同种子只能看趋势。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYS = ("avg_score", "max_score", "16384", "32768", "65536")


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    row = {"name": data.get("label") or path.name}
    for key in ("games", "avg_score", "max_score", "cpu_moves_per_s"):
        row[key] = data.get(key)
    rates = data.get("rates", {})
    for tile in ("8192", "16384", "32768", "65536"):
        row[tile] = rates.get(tile)
    row["config"] = data.get("config", "")
    row["engine"] = data.get("engine", "")
    return row


def fmt(value, percent=False):
    if value is None:
        return "—"
    if percent:
        return f"{value:.1f}%"
    if isinstance(value, float):
        return f"{value:,.0f}"
    return f"{value:,}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--base", action="store_true", help="第一份作为基准, 其余显示差值")
    args = ap.parse_args()

    rows = [load(Path(f)) for f in args.files]
    base = rows[0] if args.base else None

    print("| 运行 | 局数 | 平均分 | 最高分 | 8192 | 16384 | 32768 | 速度 |")
    print("|---|---|---|---|---|---|---|---|")
    for row in rows:
        cells = [
            row["name"],
            fmt(row["games"]),
            fmt(row["avg_score"]),
            fmt(row["max_score"]),
            fmt(row.get("8192"), percent=True),
            fmt(row.get("16384"), percent=True),
            fmt(row.get("32768"), percent=True),
            fmt(row["cpu_moves_per_s"]),
        ]
        print("| " + " | ".join(str(c) for c in cells) + " |")

    if base is not None and len(rows) > 1:
        print()
        print(f"相对基准「{base['name']}」的差值:")
        for row in rows[1:]:
            parts = []
            for key, label in (("avg_score", "平均分"), ("max_score", "最高分")):
                if row.get(key) and base.get(key):
                    delta = (row[key] - base[key]) / base[key] * 100
                    parts.append(f"{label} {delta:+.1f}%")
            for tile in ("16384", "32768"):
                if row.get(tile) is not None and base.get(tile) is not None:
                    parts.append(f"{tile} {row[tile] - base[tile]:+.1f}pp")
            print(f"  {row['name']}: " + ", ".join(parts) if parts else f"  {row['name']}: (无可比字段)")
        same_seed = all(r.get("config") == base.get("config") for r in rows[1:])
        if not same_seed:
            print("  注意: 配置不同(种子/预算/局数), 差值只当趋势看; 想配对比较必须同配置只改一处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
