"""
共通層：不老・弐の本番スイープ（2026-11-10、15 ジョブ）と動作確認 r0 の読み込み。

- 元のデータ（~/Download/flow/benchmark/）は読むだけ
- CSV の行の順 = 実行の順（plasma_perf/core/sweep.py：nb の昇順、その中で ib の昇順に1点ずつ実行し、
  nb ごとに追記する）。seq 列に 0 始まりの実行順を入れる
- 時間 = flops_dgeqrf(n, n) / (GFlops·1e9)。flops は PLASMA の test/flops.h の式
  （fmuls + fadds = 4/3·n³ + 2·n² + 14/3·n）
"""

from __future__ import annotations

import re
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path.home() / "Download/flow/benchmark"
OUT = Path(__file__).resolve().parents[1]
DATA = OUT / "data"
DATA.mkdir(exist_ok=True)

SIZES = [1024, 2048, 4096, 8192]
REPS = [1, 2, 3, 4, 5]
P = 192
PREFIX = "flow2-t1_s1_smt-off_bind-close_tileqr"


def base(size: int, rep: int) -> Path:
    return SRC / f"{PREFIX}_size{size}_nb32-512_th{P}_r{rep}"


def base_r0() -> Path:
    return SRC / f"{PREFIX}_size1024_nb128-144_th{P}_r0"


def flops_dgeqrf(n):
    """PLASMA test/flops.h の flops_dgeqrf(m, n) で m = n のとき。"""
    n = np.asarray(n, dtype=float)
    fmuls = n * n * n - n**3 / 3 + 2 * n * n - 0.5 * n * n + 23 / 6 * n
    fadds = n * n * n - n**3 / 3 + n * n - 0.5 * n * n + 5 / 6 * n
    return fmuls + fadds


def step_of(size: int) -> int:
    return 4 if size <= 4096 else 8


def expected_grid(size: int, nb_min=32, nb_max=512, ib_min=8) -> list[tuple[int, int]]:
    """plasma_perf/core/sweep.py の run_sweep と同じ順で (nb, ib) を並べる。"""
    st = step_of(size)
    return [(nb, ib) for nb in range(nb_min, nb_max + 1, st) for ib in range(ib_min, nb // 2 + 1, st)]


def read_csv(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)  # CRLF は pandas が処理する
    d["seq"] = np.arange(len(d))
    return d


def load_all() -> pd.DataFrame:
    """本番 15 本を1つの表にする。列：size, rep, nb, ib, GFlops, seq, t_ms, node, job。"""
    out = []
    for s in SIZES:
        for r in REPS:
            d = read_csv(Path(str(base(s, r)) + ".csv"))
            m = parse_meta(Path(str(base(s, r)) + "_meta.txt"))
            d["rep"] = r
            d["node"] = m["host"]
            d["job"] = m["job"]
            out.append(d)
    d = pd.concat(out, ignore_index=True)
    d["t_ms"] = flops_dgeqrf(d["size"]) / (d.GFlops * 1e9) * 1e3
    return d


def tasks(size, nb):
    """タスク数。analysis/2026-11-10_serial-task-cost/scripts/bind_ab_time.py と同じ定義：
    N = ceil(size/nb)、Σ_{k=1..N} k² = N(N+1)(2N+1)/6。"""
    N = np.ceil(np.asarray(size) / np.asarray(nb))
    return N * (N + 1) * (2 * N + 1) / 6


_SNAP = re.compile(r"^--- (開始|終了): (\S+ \S+) ---")


def parse_meta(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    lines = txt.splitlines()
    m: dict = {"file": path.name}

    def first(pat, cast=str, default=None):
        mm = re.search(pat, txt, re.M)
        return cast(mm.group(1)) if mm else default

    m["host"] = first(r"^host: (\S+)")
    m["config"] = first(r"^config: (\S+)")
    m["commit"] = first(r"^plasma-bench: (\S+)")
    m["plasmatest"] = first(r"^plasmatest: (\S+)")
    m["libs"] = "|".join(re.findall(r"^\t(\S+) => (\S+) ", txt, re.M) and
                         [f"{a}=>{b}" for a, b in re.findall(r"^\t(\S+) => (\S+) ", txt, re.M)])
    m["smt"] = first(r"^SMT active: (\S+)")
    m["socket_nodes"] = first(r"^(SOCKET: .*)$")
    m["openblas_threads"] = first(r"^OPENBLAS_NUM_THREADS=(\S+)")
    m["cond"] = first(r"^(P=\d+ SIZE=.*)$")
    m["omp"] = first(r"^(OMP_PLACES=.*)$")
    m["numactl"] = first(r"^(numactl --.*)$")
    m["job"] = first(r"^PBS_JOBID=(\S+)")
    m["model"] = first(r"^Model name:\s+(.*)$")
    m["boost"] = first(r"^Frequency boost:\s+(.*)$")
    m["scaling_mhz_pct"] = first(r"^CPU\(s\) scaling MHz:\s+(\d+)%", int)

    # lscpu（周波数の現在値と BogoMIPS を除く）、lscpu -e、numactl -H（free を除く）の指紋
    def section(start, end):
        i = next(k for k, ln in enumerate(lines) if ln.startswith(start))
        j = next((k for k, ln in enumerate(lines) if k > i and ln.startswith(end)), len(lines))
        return lines[i + 1:j]

    lscpu = [ln for ln in section("# === lscpu ===", "# === lscpu -e")
             if not ln.startswith(("CPU(s) scaling MHz", "BogoMIPS"))]
    lscpu_e = section("# === lscpu -e", "# === numactl -H")
    numa = [ln for ln in section("# === numactl -H", "# === 計測条件") if " free: " not in ln]
    m["lscpu_hash"] = zlib.crc32("\n".join(lscpu).encode())
    m["lscpu_e_hash"] = zlib.crc32("\n".join(lscpu_e).encode())
    m["numa_hash"] = zlib.crc32("\n".join(numa).encode())
    m["_lscpu"], m["_lscpu_e"], m["_numa"] = lscpu, lscpu_e, numa
    m["numa_sizes"] = ",".join(re.findall(r"^node \d+ size: (\d+) MB", "\n".join(numa), re.M))

    # 開始・終了のスナップショット
    for k, ln in enumerate(lines):
        mm = _SNAP.match(ln)
        if not mm:
            continue
        tag = "start" if mm.group(1) == "開始" else "end"
        m[f"{tag}_time"] = pd.Timestamp(mm.group(2))
        blk = "\n".join(lines[k + 1:k + 12])
        up = re.search(r"up (.*?),\s+\d+ users?,\s+load average: ([\d.]+), ([\d.]+), ([\d.]+)", blk)
        m[f"{tag}_uptime"] = up.group(1).strip()
        m[f"{tag}_users"] = int(re.search(r"(\d+) users?", blk).group(1))
        m[f"{tag}_load1"], m[f"{tag}_load5"], m[f"{tag}_load15"] = (float(up.group(i)) for i in (2, 3, 4))
        free = [int(x) for x in re.findall(r"^node \d+ free: (\d+) MB", blk, re.M)]
        m[f"{tag}_free"] = free
        m[f"{tag}_mhz"] = int(re.search(r"mean cpu MHz = (\d+)", blk).group(1))
    if "start_time" in m and "end_time" in m:
        m["elapsed_s"] = (m["end_time"] - m["start_time"]).total_seconds()
    return m


def parse_affinity(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    rows = re.findall(r"^AFFINITY level=(\d+) thread=(\d+) cpus=(\S+)", txt, re.M)
    lv1 = [(int(t), c) for lv, t, c in rows if lv == "1"]
    res = re.search(r"^\s+(pass|FAILED)\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s", txt, re.M)
    hdr = re.search(r"^% (PLASMA .*)$", txt, re.M)
    return {
        "file": path.name,
        "n_lines_lv1": len(lv1),
        "threads": sorted({t for t, _ in lv1}),
        "cpus": [c for _, c in sorted(lv1)],
        "status": res.group(1) if res else None,
        "check_time_s": float(res.group(3)) if res else np.nan,
        "check_gflops": float(res.group(4)) if res else np.nan,
        "header": hdr.group(1) if hdr else None,
    }


def add_baseline(d: pd.DataFrame, slow_ms: float = 6.0) -> pd.DataFrame:
    """点ごとの「速い水準」の見積もり base と、そこからの超過 ex を足す。2 段階で求める。

    1. tmin = 5 回の最小時間。base0 = (nb, ib) の格子の 3×3 近傍（端は欠けた分を除く）での tmin の下側四分位。
       5 回とも遅い水準に入った点（約 0.7⁵ ≈ 2 割）が近傍の過半を占めても崩れないが、最小を重ねるので低めに出る
    2. 3×3 近傍の全実行（最大 45 回）のうち t − base0 ≤ max(slow_ms + 1, 0.04·base0) のものを速い水準の実行とみなし、
       その中央値を base とする（最小を選ぶことによる偏りを除く）。該当がなければ base0。
       0.04·base0 は、2 つの水準がノイズで分かれない大きい size（8192：時間 350 ms 以上）のための幅で、
       そこでは base は「近傍の実行のうち最小から 4% 以内のものの中央値」になり、2 つの水準を分けていない
    ex = t_ms − base [ms]。
    """
    out = []
    for s, x in d.groupby("size"):
        w = x.pivot_table(index=["nb", "ib"], columns="rep", values="t_ms")
        nbs = sorted(x.nb.unique())
        ibs = sorted(x.ib.unique())
        ni, nj = {v: k for k, v in enumerate(nbs)}, {v: k for k, v in enumerate(ibs)}
        cube = np.full((len(nbs), len(ibs), w.shape[1]), np.nan)
        for (nb, ib), row in zip(w.index, w.values):
            cube[ni[nb], nj[ib]] = row
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)     # 格子にない (nb, ib) は全部 NaN
            tmin = np.nanmin(cube, axis=2)
        base0 = np.full_like(tmin, np.nan)
        base = np.full_like(tmin, np.nan)
        for i in range(len(nbs)):
            for j in range(len(ibs)):
                if np.isnan(tmin[i, j]):
                    continue
                sl = (slice(max(i - 1, 0), i + 2), slice(max(j - 1, 0), j + 2))
                base0[i, j] = np.nanpercentile(tmin[sl], 25)
                runs = cube[sl].ravel()
                fast = runs[runs - base0[i, j] <= max(slow_ms + 1, 0.04 * base0[i, j])]   # NaN は False になる
                base[i, j] = np.median(fast) if len(fast) else base0[i, j]
        idx = [(ni[nb], nj[ib]) for nb, ib in zip(x.nb, x.ib)]
        ii, jj = np.array(idx).T
        x = x.copy()
        x["tmin"] = tmin[ii, jj]
        x["base"] = base[ii, jj]
        out.append(x)
    d = pd.concat(out, ignore_index=True)
    d["ex"] = d.t_ms - d.base
    return d


# 水準の判定に使うしきい値と範囲（c_bimodal.py で根拠を出す）
SLOW_MS = 6.0                                        # ex > 6 ms を「遅い水準」とする（2つの山の谷）
NB_CLASS = {1024: 96, 2048: 96, 4096: 160, 8192: 192}  # この nb 以上だけで判定する（小さい nb は時間が長くノイズが大きい）

NB_BANDS = [31, 63, 95, 127, 191, 255, 319, 383, 447, 512]
NB_BAND_LABELS = ["32-60", "64-92", "96-124", "128-188", "192-252", "256-316", "320-380", "384-444", "448-512"]


def nb_band(nb):
    return pd.cut(nb, NB_BANDS, labels=NB_BAND_LABELS)


def setup_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Noto Sans CJK JP"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 110
    return plt
