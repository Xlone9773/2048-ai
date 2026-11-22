# Benchmarks: how to measure an engine change

Two ways to get numbers, both driving the **console build** (same engine, no browser):

```sh
zig build --release=fast -Dbudget=2097152
./zig-out/bin/2048 -i 30 -b 2097152 -t 4 -s benchmark
```

| 方式 | 用途 |
|---|---|
| 本机 `tools/bench/search-budget.mjs` | 单步耗时(给定 wasm,不做整局模拟)——调延迟看这个 |
| 本机 `tools/bench/pool-sweep.mjs` | 线程扩展性(真线程共享内存,驱动仓库自己的 worker) |
| **CI `Bench (CLI)` 工作流** | 整局统计(平均分、到达率)——调棋力看这个 |

## 在 CI 上跑(推荐)

```sh
gh workflow run bench.yml -f budget=524288 -f games=6 -f threads=4 -f seed=benchmark -f label="置换表-仅深度替换"
```

结果写在 job summary 里(配置 + 引擎 md5 + 平均分 + 到达率),原始日志和
`bench-result.json` 作为 artifact 上传。本地对比多份结果:

```sh
python3 tools/bench/compare-runs.py --base a.json b.json c.json
```

**同种子 = 配对比较。** CLI 给定 seed 完全可复现,所以"只改一处、其余参数不动"的两次运行
是逐局同源的,差值可信;不同种子只能看趋势。

## 实测校准(2026-11-22,免费 runner 是 ubuntu26 4 vCPU)

| 环境 | 预算 | 线程 | moves/s | 单局规模 |
|---|---|---|---|---|
| CI runner | 2^16 | 每线程 1 局 | **572-583** | 25.5s CPU / 约 1.5 万手 / 387k 分 |
| 本机手机 | 2^16 | 1 | 约 300 | — |
| 本机手机 | 2^19 | 1 | 47 | 316s CPU / 约 1.5 万手 / 387k 分 |

两条与实践有关的结论:

1. **CI runner 大约比手机快一倍**(同预算),但它不是"快十倍" —— 真正的成本是**局长度**:
   分数越高局越长(2^21 平均 53 万分 ≈ 2 万手,是 2^16 的 1.3 倍以上),而每手成本又随预算上升。
2. 一次 2^21 × 4 局 × 4 线程的跑在 17.6 分钟内**没有跑完**(被取消)。所以:

| 目的 | 建议参数 | 粗估耗时 |
|---|---|---|
| 快速迭代 / 冒烟 | `-b 65536 -i 4 -t 4` | 2-3 分钟 |
| 主要 A/B | `-b 524288 -i 6..10 -t 4` | 10-25 分钟 |
| 最终确认 | `-b 2097152 -i 10..20 -t 4` | 1-2 小时 |

**首要指标用到达率(16384 / 32768),别只看平均分**:平均分方差很大(2 局的样本里出现过
177,352 与 387,184 两极),而"是否摸到某个方块"这种布尔统计收敛快得多。
2 局只能冒烟,判断方向至少 6-10 局,正式结论 20 局以上。

## 还没做的

- **一次运行里跑多配置**的自动扫描(现在是"一次一种配置",对比靠 `compare-runs.py`)。
  真要做权重扫描时再加:把候选权重做成构建参数或补丁文件,循环 A/B/C 并输出一张对比表。
- 跑在自托管 runner 上的可能(手机没这个必要,CI 免费额度够用)。
