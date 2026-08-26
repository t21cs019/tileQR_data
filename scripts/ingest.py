#!/usr/bin/env python3
"""
raw/ → derived/ を生成する。

出力:
  derived/qr_sweep.parquet       全 sweep を結合したもの
  derived/kernel_dtsmqr.parquet  カーネル計測を結合したもの
  derived/optima.csv             構成×ノード×スレッド×サイズごとの最適 nb
  COVERAGE.md                    計画に対する進捗・格子の穴・再現性の状態

**最適 nb の定義はこのファイルだけが持つ。** 図もダッシュボードも
derived/ を読むだけにすること。定義を変えたいときはここを直す。

計測点の数え方（nb×ib の格子）は src/tileqr_data/plan.py が持つ。
計画そのものは plan.yaml。

使い方:
    python scripts/ingest.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import io, paths, plan  # noqa: E402

# 性能帯の閾値。ピークの何割以上を「実用上ほぼ最適」とみなすか。
BAND = 0.95

GROUP_KEYS = ["config", "node", "threads", "size"]


def average_trials(df: pd.DataFrame) -> pd.DataFrame:
    """
    同一 (条件, nb, ib) の反復を平均する。

    **最大ではなく平均を採るのが要点。** 反復が入った状態で idxmax を掛けると
    「5回のうち一番高く出た回」を拾ってしまい、ノイズを均すどころか
    上振れを選び取ることになる。95% 帯が単点に潰れる事象はまさにこれで悪化する。

    trials 列に反復数、GFlops_sd に反復間の標準偏差を残す。
    帯の狭さがノイズ由来かどうかは、後者を見れば判断できる。
    """
    keys = GROUP_KEYS + ["nb", "ib"]
    g = df.groupby(keys, observed=True)["GFlops"]
    out = g.agg(GFlops="mean", GFlops_sd="std", trials="count").reset_index()
    return out.fillna({"GFlops_sd": 0.0})


def best_over_ib(df: pd.DataFrame) -> pd.DataFrame:
    """各 (group, nb) について ib を最適化した性能を取る。"""
    keys = GROUP_KEYS + ["nb"]
    idx = df.groupby(keys, observed=True)["GFlops"].idxmax()
    return df.loc[idx].reset_index(drop=True)


def band_range(sub: pd.DataFrame, peak: float) -> tuple[int, int]:
    """
    ピークの BAND 倍以上を満たす nb の連続区間を返す。

    飛び地がある場合はピークを含む連続区間だけを取る。
    探索範囲の上下界を議論するとき、離れた点を含めると意味が薄れるため。
    """
    s = sub.sort_values("nb").reset_index(drop=True)
    ok = s["GFlops"] >= peak * BAND
    peak_pos = s["GFlops"].idxmax()

    lo = peak_pos
    while lo - 1 >= 0 and ok.iloc[lo - 1]:
        lo -= 1
    hi = peak_pos
    while hi + 1 < len(s) and ok.iloc[hi + 1]:
        hi += 1

    return int(s.loc[lo, "nb"]), int(s.loc[hi, "nb"])


def build_optima(sweeps: pd.DataFrame) -> pd.DataFrame:
    per_nb = best_over_ib(average_trials(sweeps))
    rows = []

    for keys, sub in per_nb.groupby(GROUP_KEYS, observed=True):
        peak_row = sub.loc[sub["GFlops"].idxmax()]
        peak = float(peak_row["GFlops"])
        lo, hi = band_range(sub, peak)
        n_in_band = int(((sub["nb"] >= lo) & (sub["nb"] <= hi)).sum())
        sd = float(peak_row["GFlops_sd"])
        rows.append(
            dict(
                zip(GROUP_KEYS, keys),
                nb_opt=int(peak_row["nb"]),
                ib_opt=int(peak_row["ib"]),
                GFlops_max=peak,
                GFlops_sd=sd,
                # ピークのばらつきが帯の幅（5%）に対してどれくらいか。
                # 1 に近いほど「帯の狭さはノイズで説明できてしまう」。
                noise_ratio=(sd / (0.05 * peak)) if peak else float("nan"),
                trials=int(peak_row["trials"]),
                nb_lo95=lo,
                nb_hi95=hi,
                nb_in_band=n_in_band,
                nb_scanned_lo=int(sub["nb"].min()),
                nb_scanned_hi=int(sub["nb"].max()),
                n_nb=int(sub["nb"].nunique()),
            )
        )

    return pd.DataFrame(rows).sort_values(GROUP_KEYS).reset_index(drop=True)


# --- COVERAGE.md -----------------------------------------------------------
#
# 出したいのは「何を測ったか」ではなく「計画に対してどこが空いているか」と
# 「その数字を主張に使ってよいか」。前者が格子と trials、後者が 95% 帯の幅。


def _modal_step(values: list[int]) -> int:
    """並んだ値の刻み幅。最頻の差分を採る（穴があっても引きずられない）。"""
    if len(values) < 2:
        return 0
    diffs = [b - a for a, b in zip(values, values[1:])]
    return Counter(diffs).most_common(1)[0][0]


def _dates(sub: pd.DataFrame) -> str:
    stamps = sorted({s[:8] for s in sub["stamp"].unique() if s and s != "nodate"})
    if not stamps:
        return "不明"
    lo, hi = stamps[0], stamps[-1]
    fmt = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:8]}"  # noqa: E731
    return fmt(lo) if lo == hi else f"{fmt(lo)}〜{fmt(hi)}"


def condition_stats(df: pd.DataFrame, keys: list[str], grid: dict) -> list[dict]:
    """条件ごとに、格子の埋まり方と反復回数を集計する。"""
    rows = []
    for kv, sub in df.groupby(keys, observed=True):
        kv = kv if isinstance(kv, tuple) else (kv,)
        nbs = sorted(int(x) for x in sub["nb"].unique())
        step = _modal_step(nbs)

        # 走査したはずの nb 列（連続範囲）に対する穴
        full_nbs = plan.nb_values(nbs[0], nbs[-1], step) if step else nbs
        missing_nb = sorted(set(full_nbs) - set(nbs))

        pts = int(sub[["nb", "ib"]].drop_duplicates().shape[0])
        expected = plan.expected_points(full_nbs, grid) if grid else 0

        ibs = sorted(int(x) for x in sub["ib"].unique())
        rows.append(
            dict(
                zip(keys, kv),
                trials=int(sub["source_file"].nunique()),
                nb_lo=nbs[0],
                nb_hi=nbs[-1],
                nb_step=step,
                n_nb=len(nbs),
                missing_nb=missing_nb,
                ib_lo=ibs[0],
                ib_hi=ibs[-1],
                ib_step=_modal_step(ibs),
                rows=int(len(sub)),
                points=pts,
                expected=expected,
                fill=(pts / expected) if expected else float("nan"),
                dates=_dates(sub),
            )
        )
    return rows


def _plan_index(kind: str) -> dict[tuple, dict]:
    """計画を (node, threads, size) で引けるようにする。"""
    out = {}
    for t in plan.targets_for(kind):
        out[(t.get("config"), t["node"], t["threads"], t["size"])] = t
    return out


def _status(measured: dict | None, target: dict | None) -> tuple[str, str, str]:
    """status / 計画に対する被覆率 / trials 表記 を返す。"""
    if measured is None:
        return "missing", "0%", f"0/{target['trials']}" if target else "0/?"

    trials_txt = str(measured["trials"])
    plan_txt = "—"
    ok_plan = True

    if target:
        trials_txt = f"{measured['trials']}/{target['trials']}"
        nbs = plan.nb_values(target["nb_lo"], target["nb_hi"], target["grid"]["nb_step"])
        want = plan.expected_points(nbs, target["grid"])
        got = min(measured["points"], want)
        ok_plan = measured["points"] >= want
        plan_txt = f"{100 * got / want:.0f}%" if want else "—"

    ok_trials = (not target) or measured["trials"] >= target["trials"]
    ok_grid = not measured["missing_nb"] and (
        measured["expected"] == 0 or measured["points"] >= measured["expected"]
    )

    status = "done" if (ok_trials and ok_plan and ok_grid) else "partial"
    return status, plan_txt, trials_txt


def _pct(x: float) -> str:
    return "—" if pd.isna(x) else f"{100 * x:.0f}%"


def _table_header(cols: list[str]) -> list[str]:
    """見出し行と区切り行。区切りの本数は見出しから導く（列数のずれ防止）。"""
    return ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]


def sweep_section(stats: list[dict], kind: str) -> list[str]:
    idx = _plan_index(kind)
    has_config = "config" in stats[0] if stats else False

    cols = (["config"] if has_config else []) + [
        "node", "t", "size", "nb 走査", "step", "n_nb", "ib",
        "計測点", "格子", "計画", "trials", "status", "計測日",
    ]
    lines = _table_header(cols)

    seen = set()
    for r in sorted(stats, key=lambda r: (r.get("config") or "", r["node"],
                                          r["threads"], r["size"])):
        key = (r.get("config"), r["node"], r["threads"], r["size"])
        seen.add(key)
        status, plan_txt, trials_txt = _status(r, idx.get(key))
        cfg = f"`{r['config']}` | " if has_config else ""
        hole = f" (欠測 {len(r['missing_nb'])})" if r["missing_nb"] else ""
        lines.append(
            f"| {cfg}{r['node']} | {r['threads']} | {r['size']} | "
            f"{r['nb_lo']}-{r['nb_hi']} | {r['nb_step']} | {r['n_nb']}{hole} | "
            f"{r['ib_lo']}-{r['ib_hi']}/{r['ib_step']} | {r['points']:,} | "
            f"{_pct(r['fill'])} | {plan_txt} | {trials_txt} | {status} | {r['dates']} |"
        )

    # 計画にあるが1件も測っていない条件
    for key, t in sorted(idx.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        if key in seen:
            continue
        cfg = f"`{t['config']}` | " if has_config else ""
        lines.append(
            f"| {cfg}{t['node']} | {t['threads']} | {t['size']} | "
            f"{t['nb_lo']}-{t['nb_hi']} | {t['grid']['nb_step']} | — | — | 0 | "
            f"0% | 0% | 0/{t['trials']} | **missing** | — |"
        )

    return lines


def reproducibility_section(optima: pd.DataFrame, stats: list[dict]) -> list[str]:
    """
    最適 nb がノード間でどれだけ散るか。

    同一ハード・同一条件での散らばりなので、これが大きいまま nb_opt を
    「最適タイルサイズ」と呼ぶと、再現性のない値を主張することになる。
    """
    trials_of = {
        (r.get("config"), r["node"], r["threads"], r["size"]): r["trials"]
        for r in stats
    }

    lines = _table_header(
        ["config", "t", "size", "ノード数", "trials(最小)", "nb_opt", "幅", "変動係数"]
    )
    for (config, threads, size), sub in optima.groupby(
        ["config", "threads", "size"], observed=True
    ):
        vals = sorted(int(v) for v in sub["nb_opt"])
        mean = sum(vals) / len(vals)
        if len(vals) > 1:
            var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
            cv = f"{100 * (var ** 0.5) / mean:.1f}%"
        else:
            cv = "—"
        tmin = min(
            (trials_of.get((config, n, threads, size), 0) for n in sub["node"]),
            default=0,
        )
        lines.append(
            f"| `{config}` | {threads} | {size} | {len(vals)} | {tmin} | "
            f"{', '.join(str(v) for v in vals)} | {max(vals) - min(vals)} | {cv} |"
        )
    return lines


def band_section(optima: pd.DataFrame) -> tuple[list[str], int]:
    """95% 性能帯が単点に潰れている条件を挙げる。"""
    lines = _table_header(
        ["config", "node", "t", "size", "nb_opt", "95%帯", "帯内の点",
         "trials", "ノイズ/帯", "判定"]
    )
    degenerate = 0
    for _, r in optima.iterrows():
        n = int(r["nb_in_band"])
        at_edge = (
            r["nb_lo95"] == r["nb_scanned_lo"] or r["nb_hi95"] == r["nb_scanned_hi"]
        )
        ratio = r["noise_ratio"]
        if n <= 1:
            verdict, degenerate = "**退化（単点）**", degenerate + 1
        elif at_edge:
            verdict = "走査端で切断"
        elif pd.notna(ratio) and ratio >= 1.0:
            # 反復間のばらつきが帯の幅と同程度。帯の狭さを主張の根拠にできない。
            verdict = "**ノイズが帯と同程度**"
        else:
            verdict = "ok"
        rt = "—" if int(r["trials"]) < 2 else f"{ratio:.2f}"
        lines.append(
            f"| `{r['config']}` | {r['node']} | {r['threads']} | {r['size']} | "
            f"{r['nb_opt']} | {r['nb_lo95']}-{r['nb_hi95']} | {n} | "
            f"{int(r['trials'])} | {rt} | {verdict} |"
        )
    return lines, degenerate


def node_section(optima: pd.DataFrame, kind: str) -> list[str]:
    idx = _plan_index(kind)
    planned: dict[tuple, set] = defaultdict(set)
    for (config, node, threads, size), t in idx.items():
        planned[(config, threads, size)].add(node)

    measured: dict[tuple, set] = defaultdict(set)
    for _, r in optima.iterrows():
        measured[(r["config"], r["threads"], r["size"])].add(r["node"])

    lines = _table_header(["config", "t", "size", "計測済", "未計測"])
    for key in sorted(set(planned) | set(measured), key=lambda k: tuple(map(str, k))):
        config, threads, size = key
        got = sorted(measured.get(key, set()))
        missing = sorted(planned.get(key, set()) - set(got))
        lines.append(
            f"| `{config}` | {threads} | {size} | {len(got)}: {', '.join(got) or '—'} "
            f"| {', '.join(missing) if missing else 'なし'} |"
        )
    return lines


def machines_section(
    sweeps: pd.DataFrame,
    kernel: pd.DataFrame | None,
    ssrfb: pd.DataFrame | None = None,
) -> list[str]:
    """machines.yaml に定義があるのに計測が無いノードを挙げる。"""
    machines = io.load_machines()
    defined = set((machines.get("nodes") or {}).keys())

    seen = set(sweeps["node"].unique())
    for extra in (kernel, ssrfb):
        if extra is not None and not extra.empty:
            seen |= set(extra["node"].unique())

    lines = []
    unmeasured = sorted(defined - seen)
    unknown = sorted(seen - defined)
    lines.append(
        f"- 定義済みだが未計測のノード ({len(unmeasured)}): "
        + (", ".join(f"`{n}`" for n in unmeasured) if unmeasured else "なし")
    )
    lines.append(
        f"- 計測されたが machines.yaml に無いノード ({len(unknown)}): "
        + (", ".join(f"`{n}`" for n in unknown) if unknown else "なし")
    )

    # 交絡要因が未確認のまま残っている構成
    pending = []
    for name, cfg in (machines.get("configs") or {}).items():
        holes = [k for k in ("turbo", "memory_channels") if cfg.get(k) in (None, "unknown")]
        if holes:
            pending.append(f"`{name}` ({', '.join(holes)})")
    lines.append(
        f"- 交絡要因が未確認の構成 ({len(pending)}): "
        + (", ".join(pending) if pending else "なし")
    )
    return lines


def write_coverage(
    optima: pd.DataFrame,
    sweeps: pd.DataFrame,
    kernel: pd.DataFrame | None,
    ssrfb: pd.DataFrame | None = None,
) -> None:
    sweep_grid = plan.grid_of("qr_sweep") or {}
    kernel_grid = plan.grid_of("kernel_dtsmqr") or {}
    ssrfb_grid = plan.grid_of("ssrfb") or {}

    sweep_stats = condition_stats(sweeps, GROUP_KEYS, sweep_grid)
    kernel_stats = (
        condition_stats(kernel, ["node", "threads", "size"], kernel_grid)
        if kernel is not None and not kernel.empty
        else []
    )
    ssrfb_stats = (
        condition_stats(ssrfb, ["node", "threads", "size"], ssrfb_grid)
        if ssrfb is not None and not ssrfb.empty
        else []
    )

    band_lines, n_degenerate = band_section(optima)
    all_stats = sweep_stats + kernel_stats + ssrfb_stats

    n_files = int(sweeps["source_file"].nunique())
    for extra in (kernel, ssrfb):
        if extra is not None and not extra.empty:
            n_files += int(extra["source_file"].nunique())

    under_trials = 0
    for kind, stats in (("qr_sweep", sweep_stats), ("kernel_dtsmqr", kernel_stats),
                        ("ssrfb", ssrfb_stats)):
        idx = _plan_index(kind)
        for r in stats:
            t = idx.get((r.get("config"), r["node"], r["threads"], r["size"]))
            if t and r["trials"] < t["trials"]:
                under_trials += 1
    with_holes = sum(1 for r in all_stats if r["missing_nb"])

    lines = [
        "# COVERAGE",
        "",
        "`scripts/ingest.py` が自動生成する。手で編集しない。",
        "計画は `plan.yaml`、機材は `machines.yaml` を参照。",
        "",
        "## サマリ",
        "",
        "| 指標 | 値 |",
        "|---|---|",
        f"| 計測ファイル | {n_files} |",
        f"| 条件 (種別×config×node×threads×size) | {len(all_stats)} |",
        f"| 計測点 (nb×ib) | {sum(r['points'] for r in all_stats):,} |",
        f"| **反復が計画に届かない条件** | {under_trials} / {len(all_stats)} |",
        f"| **95%帯が単点に潰れた条件** | {n_degenerate} |",
        f"| 格子に穴がある条件 | {with_holes} |",
        "",
        f"## qr_sweep — {plan.label_of('qr_sweep')}",
        "",
        "「格子」は走査範囲を隙間なく埋めたか、「計画」は plan.yaml の nb 範囲に",
        "対してどこまで届いたか。ib は `下限-上限/刻み`。",
        "",
    ]
    lines += sweep_section(sweep_stats, "qr_sweep")

    lines += [
        "",
        "### 反復と最適 nb のばらつき",
        "",
        "同一ハード・同一条件でのノード間の散らばり。trials=1 は",
        "「1回の計測で最適 nb を主張している」状態を意味する。",
        "",
    ]
    lines += reproducibility_section(optima, sweep_stats)

    lines += [
        "",
        "### 95% 性能帯の健全性",
        "",
        "帯内の点が1つしかない条件は、ピークが「なだらかな山の頂上」ではなく",
        "「ノイズの中で偶然突き出した棘」である疑いが強い。反復して平均を取るまで",
        "その `nb_opt` は主張に使えない。",
        "",
    ]
    lines += band_lines

    lines += ["", "### ノード網羅", ""]
    lines += node_section(optima, "qr_sweep")

    if ssrfb_stats:
        lines += [
            "",
            f"## ssrfb — {plan.label_of('ssrfb')}",
            "",
            "`Time_sec` 列を持つのはこの種別だけで、中身から判別できる唯一の測定。",
            "格子の規則は qr_sweep と同じ（`ib <= nb/2`）。",
            "",
        ]
        lines += sweep_section(ssrfb_stats, "ssrfb")

    if kernel_stats:
        lines += [
            "",
            f"## kernel_dtsmqr — {plan.label_of('kernel_dtsmqr')}",
            "",
            "qr_sweep とは ib の上限規則が違う（`ib <= nb - step`）。",
            "同じ列構成なので、置き場所だけが種別を担保している。",
            "",
        ]
        lines += sweep_section(kernel_stats, "kernel_dtsmqr")

    lines += ["", "## machines.yaml との整合", ""]
    lines += machines_section(sweeps, kernel, ssrfb)
    lines.append("")

    paths.COVERAGE_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    paths.DERIVED.mkdir(parents=True, exist_ok=True)

    sweeps = io.load_sweeps(use_parquet=False)
    sweeps.to_parquet(paths.SWEEP_PARQUET, index=False)
    print(f"書き出し: {paths.SWEEP_PARQUET.name}  ({len(sweeps):,} 行)")

    try:
        kernel = io.load_kernel(use_parquet=False)
        kernel.to_parquet(paths.KERNEL_PARQUET, index=False)
        print(f"書き出し: {paths.KERNEL_PARQUET.name}  ({len(kernel):,} 行)")
    except FileNotFoundError:
        kernel = None
        print("kernel_dtsmqr のデータなし。スキップ。")

    try:
        ssrfb = io.load_ssrfb(use_parquet=False)
        ssrfb.to_parquet(paths.SSRFB_PARQUET, index=False)
        print(f"書き出し: {paths.SSRFB_PARQUET.name}  ({len(ssrfb):,} 行)")
    except FileNotFoundError:
        ssrfb = None
        print("ssrfb のデータなし。スキップ。")

    optima = build_optima(sweeps)
    optima.to_csv(paths.OPTIMA_CSV, index=False)
    print(f"書き出し: {paths.OPTIMA_CSV.name}  ({len(optima)} 行)")

    write_coverage(optima, sweeps, kernel, ssrfb)
    print(f"書き出し: {paths.COVERAGE_MD.name}")

    print(f"\n--- 最適 nb と {int(BAND * 100)}% 性能帯 ---")
    cols = ["config", "node", "threads", "size", "nb_opt", "GFlops_max",
            "nb_lo95", "nb_hi95", "nb_in_band"]
    print(optima[cols].to_string(index=False))

    degenerate = optima[optima["nb_in_band"] <= 1]
    if not degenerate.empty:
        print(
            f"\n警告: 95%帯が単点に潰れた条件が {len(degenerate)} 件あります。"
            "\n      ピークがノイズの棘の可能性が高く、この nb_opt は主張に使えません。"
            "\n      反復計測（plan.yaml の trials）で平均を取ってください。"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
