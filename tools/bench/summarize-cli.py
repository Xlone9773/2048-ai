#!/usr/bin/env python3
"""把 CLI 基准的输出整理成一行结论 + 一段 Markdown。

CLI 会按线程周期性地打印进度块(而且多线程时相邻两次输出可能互相截断),
所以这里只认"最后一次"出现的字段 —— 最后一个块就是整轮的最终统计。

    ./zig-out/bin/2048 -i 30 -b 2097152 -t 4 -s benchmark 2>&1 | tee bench.log
    python3 tools/bench/summarize-cli.py bench.log --label "budget=2^21" >> "$GITHUB_STEP_SUMMARY"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GAMES = re.compile(r"Games Played\s*:\s*(\d+)")
SCORE = re.compile(r"Score\s*:\s*Max\s+(\d+)\s*\|\s*Avg\s+([\d.]+)")
PERF = re.compile(r"Performance\s*:\s*([\d.]+)\s*moves/s\s*\|\s*([\d.]+)s cpu")
MAXTILE = re.compile(r"Max tile\s*:\s*(\d+)\s*\|\s*([\d.]+)%")
WALL = re.compile(r"Wall Speed:\s*([\d.]+)\s*moves/s")
RATE = re.compile(r"^\s*(\d+)\s*:\s*([\d.]+)%\s*$")


def parse(text: str) -> dict:
    result: dict = {"rates": {}}
    for line in text.splitlines():
        if (m := GAMES.search(line)):
            result["games"] = int(m.group(1))
        if (m := SCORE.search(line)):
            result["max_score"] = int(m.group(1))
            result["avg_score"] = float(m.group(2))
        if (m := PERF.search(line)):
            result["cpu_moves_per_s"] = float(m.group(1))
            result["cpu_seconds"] = float(m.group(2))
        if (m := MAXTILE.search(line)):
            result["max_tile"] = int(m.group(1))
            result["max_tile_rate"] = float(m.group(2))
        if (m := WALL.search(line)):
            result["wall_moves_per_s"] = float(m.group(1))
        if (m := RATE.match(line)) and "STATISTICS" not in line:
            result["rates"][int(m.group(1))] = float(m.group(2))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="CLI 的输出文件")
    ap.add_argument("--label", default="", help="这次跑法的描述(写进摘要)")
    ap.add_argument("--engine", default="", help="引擎身份, 例如 'md5=2952a5b9 budget=2097152'")
    ap.add_argument("--markdown", action="store_true", help="输出可以直接贴进 job summary 的 Markdown")
    ap.add_argument("--json", action="store_true", help="输出机器可读的结果(便于多次运行对比)")
    ap.add_argument("--config", default="", help="这次运行的配置, 例如 'budget=2097152 games=30 threads=4 seed=benchmark'")
    args = ap.parse_args()

    text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    stats = parse(text)
    if "games" not in stats:
        print("没解析到统计块, 先看日志原文", file=sys.stderr)
        return 1

    rates = stats["rates"]
    interesting = sorted((t for t in rates if t >= 8192), reverse=True)
    rates_text = " · ".join(f"{t} {rates[t]:.1f}%" for t in interesting) or "(无)"

    one_line = (
        f"games={stats['games']} avg={stats.get('avg_score', 0):.0f} max={stats.get('max_score', 0)} "
        f"{rates_text} cpu={stats.get('cpu_moves_per_s', 0):.1f} moves/s"
    )
    if args.label:
        one_line = f"{args.label} | {one_line}"
    if not args.json:
        print(one_line)

    if args.json:
        # stdout 必须是纯 JSON(工作流会把它当结果文件下载), 人读的那一行只在非 JSON 模式打印
        payload = {
            "label": args.label,
            "engine": args.engine,
            "config": args.config,
            "games": stats["games"],
            "avg_score": stats.get("avg_score", 0),
            "max_score": stats.get("max_score", 0),
            "rates": {str(k): v for k, v in sorted(stats["rates"].items())},
            "cpu_moves_per_s": stats.get("cpu_moves_per_s", 0),
            "wall_moves_per_s": stats.get("wall_moves_per_s"),
            "cpu_seconds": stats.get("cpu_seconds", 0),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.markdown:
        print()
        print("## Bench result" + (f" — {args.label}" if args.label else ""))
        print()
        print("| 项 | 值 |")
        print("|---|---|")
        if args.engine:
            print(f"| 引擎 | `{args.engine}` |")
        print(f"| 局数 | {stats['games']} |")
        print(f"| 平均分 | {stats.get('avg_score', 0):,.0f} |")
        print(f"| 最高分 | {stats.get('max_score', 0):,} |")
        print(f"| 到达率 | {rates_text} |")
        if "max_tile" in stats:
            print(f"| 最大块 | {stats['max_tile']} ({stats.get('max_tile_rate', 0):.1f}%) |")
        print(f"| 速度 | cpu {stats.get('cpu_moves_per_s', 0):.1f} moves/s"
              + (f" · wall {stats['wall_moves_per_s']:.1f} moves/s" if "wall_moves_per_s" in stats else "")
              + " |")
        print(f"| CPU 时间 | {stats.get('cpu_seconds', 0):,.0f}s |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
