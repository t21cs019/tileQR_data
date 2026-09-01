#!/usr/bin/env python3
"""
derived/qr_sweep.parquet から探索用の図を一括生成する。

データを追加するたびに回す。出力は既定で figures/（Git 管理外）。
確定版を作るときは --outdir figures_final/卒論 のように渡す。

生成するもの:
  figures/heatmap/{config}_size{N}_{agg}.png   (config, size) ごと
  figures/sweep/{config}_{agg}.png             config x 集約方法 ごと
  figures/comparison/aggregator_comparison.csv 集約方法の比較表
  figures/comparison/aggregator_comparison.md  同上（Markdown）

--- 集約を先にするのが要点 -------------------------------------------

同一 (config, threads, size, nb, ib) に複数の試行がある。生データの argmax を
直接取ると「5回のうち一番高く出た回」を拾い、ノイズを均すどころか上振れを
選び取ることになる（ingest.py と同じ理由）。

測定ノイズは遅くなる方向にしか出ないため、外れ値が混ざると平均は下方に
引っぱられる。プラトー領域の隣接 nb 間の真の差は 1〜3% しかないので、
この偏りが nb* の選択とバンド境界を左右しうる。中央値と平均のどちらを
既定にするかは実測で決めるべきなので、両方で図を出して比較表を作る。

使い方:
    uv run python scripts/generate_figures.py
    uv run python scripts/generate_figures.py --config aoba-b_s2_smt-off
    uv run python scripts/generate_figures.py --aggregators median
    uv run python scripts/generate_figures.py --outdir figures_final/卒論
    uv run python scripts/generate_figures.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tileqr_data import console, io, paths, style  # noqa: E402

console.use_utf8()

# 集約の鍵。threads は config に紐づくが、同一 config で複数の threads が
# 入ることは無い前提。混ざっていたら summary で報告する。
KEYS = ["config", "size", "nb", "ib"]
AGGS = {"median": "median", "mean": "mean"}


# --- データの読み込みと集約 -------------------------------------------


def load_sweeps() -> pd.DataFrame:
    if not paths.SWEEP_PARQUET.exists():
        raise SystemExit(
            f"エラー: {paths.SWEEP_PARQUET} がありません。"
            "先に `make ingest` を実行してください。"
        )
    return pd.read_parquet(paths.SWEEP_PARQUET)


def aggregate(df: pd.DataFrame, how: str) -> pd.DataFrame:
    """同一 (config, size, nb, ib) の試行を畳む。argmax より先にやる。"""
    g = df.groupby(KEYS, observed=True)["GFlops"]
    out = g.agg(GFlops=AGGS[how], n_trials="count").reset_index()
    return out


def per_nb_best(agg: pd.DataFrame) -> pd.DataFrame:
    """各 (config, size, nb) について ib を最適化した性能。"""
    idx = agg.groupby(["config", "size", "nb"], observed=True)["GFlops"].idxmax()
    return agg.loc[idx].reset_index(drop=True)


def band_of(curve: pd.DataFrame, threshold: float) -> dict:
    """
    最大値の threshold 倍以上を満たす nb の、**argmax を含む連続区間**。

    閾値以上の点は飛び地になりうる。区間の外に閾値以上の点があれば
    非連続として報告する（帯の定義が実態と乖離していないかの確認用）。
    """
    s = curve.sort_values("nb").reset_index(drop=True)
    peak_pos = int(s["GFlops"].idxmax())
    peak = float(s.loc[peak_pos, "GFlops"])
    ok = s["GFlops"] >= peak * threshold

    lo = hi = peak_pos
    while lo - 1 >= 0 and ok.iloc[lo - 1]:
        lo -= 1
    while hi + 1 < len(s) and ok.iloc[hi + 1]:
        hi += 1

    outside = int(ok.sum() - (hi - lo + 1))
    return {
        "nb_star": int(s.loc[peak_pos, "nb"]),
        "ib_star": int(s.loc[peak_pos, "ib"]),
        "max": peak,
        "band_lo": int(s.loc[lo, "nb"]),
        "band_hi": int(s.loc[hi, "nb"]),
        "n_in_band": hi - lo + 1,
        "outside": outside,          # 帯の外にある閾値以上の点の数
    }


# --- サイドカー JSON によるスキップ判定 --------------------------------


def input_hash(df: pd.DataFrame, **params) -> str:
    """このデータと描画パラメータから決まるハッシュ。"""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    h.update(json.dumps(params, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def should_skip(png: Path, digest: str, force: bool) -> bool:
    meta = png.with_suffix(png.suffix + ".meta.json")
    if force or not png.exists() or not meta.exists():
        return False
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("input_hash") == digest
    except Exception:  # noqa: BLE001
        return False


def write_meta(png: Path, payload: dict) -> None:
    png.with_suffix(png.suffix + ".meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


# --- 図1: ヒートマップ -------------------------------------------------


def draw_heatmap(sub: pd.DataFrame, config: str, size: int, agg: str,
                 png: Path, dpi: int) -> dict:
    grid = sub.pivot_table(index="ib", columns="nb", values="GFlops")
    # ib > nb は測っていない領域。マスクして白抜きにする。
    nb_v = grid.columns.values[None, :]
    ib_v = grid.index.values[:, None]
    masked = np.ma.masked_where(
        (ib_v > nb_v) | np.isnan(grid.values), grid.values
    )

    best = sub.loc[sub["GFlops"].idxmax()]
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    mesh = ax.pcolormesh(grid.columns.values, grid.index.values, masked,
                         cmap=cmap, shading="nearest")
    fig.colorbar(mesh, ax=ax, label="GFlop/s")

    ax.plot(best["nb"], best["ib"], marker="o", color="red",
            markersize=9, markerfacecolor="none", markeredgewidth=2)
    ax.set_xlabel("nb")
    ax.set_ylabel("ib")
    ax.set_title(f"{config}  size={size}  ({agg} of {int(sub.n_trials.max())} trials)")
    ax.legend(
        handles=[Line2D([], [], marker="o", color="red", linestyle="none",
                        markerfacecolor="none", markeredgewidth=2,
                        label=f"max {best['GFlops']:.1f} GFlop/s "
                              f"(nb={int(best['nb'])}, ib={int(best['ib'])})")],
        loc="upper left", fontsize="small",
    )
    fig.tight_layout()
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return {"nb_star": int(best["nb"]), "ib_star": int(best["ib"]),
            "max": float(best["GFlops"])}


# --- 図2: nb スイープ（95% バンド付き）--------------------------------


def draw_sweep(curves: dict[int, pd.DataFrame], stats: dict[int, dict],
               config: str, agg: str, n_trials: int, threshold: float,
               xlim: tuple, ylim: tuple, png: Path, dpi: int) -> None:
    sizes = sorted(curves)
    # size は順序を持つ量なので連続カラーマップ。カテゴリカルな色分けにしない。
    cmap = plt.get_cmap("viridis")
    colors = {s: cmap(i / max(len(sizes) - 1, 1)) for i, s in enumerate(sizes)}

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    handles = []
    for s in sizes:
        c = colors[s]
        cur = curves[s].sort_values("nb")
        st = stats[s]
        ax.plot(cur["nb"], cur["GFlops"], color=c, linewidth=1.4)
        ax.axhline(st["max"], color=c, linestyle="--", linewidth=0.8, alpha=0.6)
        ax.axvspan(st["band_lo"], st["band_hi"], color=c, alpha=0.12)
        ax.plot(st["nb_star"], st["max"], marker="o", color=c, markersize=7)
        ax.annotate(f"{st['nb_star']}", (st["nb_star"], st["max"]),
                    textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize="x-small", color=c)
        handles.append(Line2D(
            [], [], color=c, marker="o",
            label=f"size {s}: {st['max']:.0f} GFlop/s, "
                  f"nb*={st['nb_star']}, 帯 {st['band_lo']}-{st['band_hi']}",
        ))

    ax.set_xlabel("nb")
    ax.set_ylabel("GFlop/s")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_title(f"{config} ({agg} of {n_trials} trials)")
    # 凡例は図の外に出す。系列が5前後あり、中に置くと曲線を覆う。
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              fontsize="x-small", title=f"帯 = 最大値 x {threshold:g} 以上")
    fig.tight_layout()
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# --- 比較表 ------------------------------------------------------------


def jaccard(a: tuple, b: tuple) -> float:
    """2つの nb 区間の Jaccard 係数。1.0 なら完全一致。"""
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(hi - lo, -1) + 1 if hi >= lo else 0
    union = (max(a[1], b[1]) - min(a[0], b[0])) + 1
    return inter / union if union else float("nan")


def build_comparison(stats: dict) -> pd.DataFrame:
    """stats[(agg, config, size)] -> 比較表。median と mean が揃う行だけ。"""
    rows = []
    keys = {(c, s) for (a, c, s) in stats if a == "median"}
    for config, size in sorted(keys):
        m = stats.get(("median", config, size))
        a = stats.get(("mean", config, size))
        if m is None or a is None:
            continue
        bm = (m["band_lo"], m["band_hi"])
        ba = (a["band_lo"], a["band_hi"])
        rows.append({
            "config": config,
            "size": size,
            "n_trials": m["n_trials"],
            "nb_star_median": m["nb_star"],
            "nb_star_mean": a["nb_star"],
            "delta_nb_star": a["nb_star"] - m["nb_star"],
            "max_median": round(m["max"], 4),
            "max_mean": round(a["max"], 4),
            "delta_max_pct": round(100 * (a["max"] - m["max"]) / m["max"], 4),
            "band_lo_median": bm[0], "band_hi_median": bm[1],
            "band_lo_mean": ba[0], "band_hi_mean": ba[1],
            "band_width_median": bm[1] - bm[0],
            "band_width_mean": ba[1] - ba[0],
            "band_jaccard": round(jaccard(bm, ba), 4),
        })
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


# --- 本体 --------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default=None, help="出力先ルート（既定 figures）")
    ap.add_argument("--config", action="append", default=None,
                    help="対象 config を絞る（複数指定可）")
    ap.add_argument("--aggregators", nargs="+", default=["median", "mean"],
                    choices=list(AGGS), help="試行の集約方法（先頭がヒートマップ用）")
    ap.add_argument("--band-threshold", type=float, default=0.95)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--force", action="store_true", help="未変更でも再生成")
    args = ap.parse_args()

    outdir = Path(args.outdir) if args.outdir else paths.FIGURES
    style.use("slide")

    df = load_sweeps()

    # config は parquet を正とする。COVERAGE.md との差分は警告で出す。
    in_data = sorted(df["config"].dropna().unique())
    in_coverage = coverage_configs()
    only_data = sorted(set(in_data) - in_coverage)
    only_cov = sorted(in_coverage - set(in_data))

    targets = [c for c in in_data if not args.config or c in args.config]
    if args.config:
        unknown = sorted(set(args.config) - set(in_data))
        for c in unknown:
            print(f"警告: --config {c} は parquet に存在しない")

    made = updated = skipped = 0
    skipped_configs: list[str] = []
    noncontig: list[str] = []
    stats_all: dict = {}
    trial_counts: dict = {}

    for agg in args.aggregators:
        a = aggregate(df, agg)
        curve_all = per_nb_best(a)

        for config in targets:
            cur_cfg = curve_all[curve_all["config"] == config]
            if cur_cfg.empty:
                skipped_configs.append(f"{config}: データ無し")
                continue

            curves, stats = {}, {}
            for size, sub in cur_cfg.groupby("size", observed=True):
                st = band_of(sub, args.band_threshold)
                st["n_trials"] = int(sub["n_trials"].max())
                curves[int(size)] = sub
                stats[int(size)] = st
                stats_all[(agg, config, int(size))] = st
                trial_counts[(config, int(size))] = st["n_trials"]
                if st["outside"]:
                    noncontig.append(
                        f"{config} size{size} ({agg}): 帯の外に閾値以上の点が "
                        f"{st['outside']} 個"
                    )

            # median / mean を目視で並べるため、軸範囲は集約方法によらず固定する。
            # 片方だけオートスケールすると、見かけの差が集約の差か軸の差か
            # 区別できなくなる。
            xlim, ylim = axis_limits(df, config, args.band_threshold)
            n_trials = max(s["n_trials"] for s in stats.values())

            png = outdir / "sweep" / f"{config}_{agg}.png"
            digest = input_hash(
                df[df["config"] == config],
                agg=agg, threshold=args.band_threshold, dpi=args.dpi,
                kind="sweep", xlim=xlim, ylim=ylim,
            )
            if should_skip(png, digest, args.force):
                skipped += 1
            else:
                existed = png.exists()
                draw_sweep(curves, stats, config, agg, n_trials,
                           args.band_threshold, xlim, ylim, png, args.dpi)
                write_meta(png, {
                    "input_hash": digest,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "config": config, "aggregator": agg,
                    "band_threshold": args.band_threshold,
                    "rows_raw": int((df["config"] == config).sum()),
                    "points_aggregated": int(len(a[a["config"] == config])),
                    "n_trials": n_trials,
                    "per_size": {str(k): v for k, v in stats.items()},
                })
                updated += existed
                made += not existed

            # ヒートマップは枚数が増えすぎるので先頭の集約方法だけ
            if agg != args.aggregators[0]:
                continue
            for size, sub in a[a["config"] == config].groupby("size", observed=True):
                if sub["ib"].nunique() <= 1:
                    skipped_configs.append(
                        f"{config} size{size}: ib に変化が無くヒートマップ不可"
                    )
                    continue
                hpng = outdir / "heatmap" / f"{config}_size{int(size)}_{agg}.png"
                hdig = input_hash(sub, agg=agg, dpi=args.dpi, kind="heatmap")
                if should_skip(hpng, hdig, args.force):
                    skipped += 1
                    continue
                existed = hpng.exists()
                best = draw_heatmap(sub, config, int(size), agg, hpng, args.dpi)
                write_meta(hpng, {
                    "input_hash": hdig,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "config": config, "size": int(size), "aggregator": agg,
                    "n_trials": int(sub["n_trials"].max()),
                    "points_aggregated": int(len(sub)), **best,
                })
                updated += existed
                made += not existed

    # --- 比較表 ---
    comp = build_comparison(stats_all)
    if not comp.empty:
        cdir = outdir / "comparison"
        cdir.mkdir(parents=True, exist_ok=True)
        comp.to_csv(cdir / "aggregator_comparison.csv", index=False)
        (cdir / "aggregator_comparison.md").write_text(
            to_markdown(comp), encoding="utf-8")

    report(made, updated, skipped, skipped_configs, noncontig,
           only_data, only_cov, comp, trial_counts, outdir)
    return 0


def axis_limits(df: pd.DataFrame, config: str, threshold: float) -> tuple:
    """
    その config の median / mean 両方に共通の軸範囲。

    集約方法によらず同じ値になるよう、生データの範囲から決める。
    """
    sub = df[df["config"] == config]
    nb_lo, nb_hi = int(sub["nb"].min()), int(sub["nb"].max())
    pad = max((nb_hi - nb_lo) * 0.02, 1)
    top = float(sub["GFlops"].max())
    return (nb_lo - pad, nb_hi + pad), (0, top * 1.08)


def coverage_configs() -> set[str]:
    """COVERAGE.md に出ている config 名。差分の検出だけに使う。"""
    if not paths.COVERAGE_MD.exists():
        return set()
    import re
    text = paths.COVERAGE_MD.read_text(encoding="utf-8")
    known = set((io.load_machines().get("configs") or {}).keys())
    return {m for m in re.findall(r"`([A-Za-z0-9\-_.]+)`", text) if m in known}


def report(made, updated, skipped, skipped_configs, noncontig,
           only_data, only_cov, comp, trial_counts, outdir) -> None:
    print(f"\n=== 生成した図 ===")
    print(f"  新規 {made} / 更新 {updated} / スキップ {skipped}")
    print(f"  出力先: {outdir}")

    if skipped_configs:
        print(f"\n=== スキップした条件 ({len(skipped_configs)}) ===")
        for s in skipped_configs:
            print(f"  ! {s}")

    print("\n=== COVERAGE.md との差分 ===")
    print(f"  データにあって COVERAGE に無い: "
          f"{', '.join(only_data) if only_data else 'なし'}")
    print(f"  COVERAGE にあってデータに無い: "
          f"{', '.join(only_cov) if only_cov else 'なし'}")

    if noncontig:
        print(f"\n=== 帯が非連続 ({len(noncontig)}) ===")
        for s in noncontig:
            print(f"  ! {s}")

    # 試行数が config・size 間で不揃いな箇所
    counts = sorted(set(trial_counts.values()))
    if len(counts) > 1:
        print(f"\n=== 試行数が不揃い（{counts} が混在）===")
        common = max(counts, key=lambda c: list(trial_counts.values()).count(c))
        for (config, size), n in sorted(trial_counts.items()):
            if n != common:
                print(f"  ! {config} size{size}: {n} 試行（大勢は {common}）")

    if not comp.empty:
        changed = comp[comp["delta_nb_star"] != 0]
        print(f"\n=== 集約方法で nb* が変わった条件: "
              f"{len(changed)} / {len(comp)} ===")
        if not changed.empty:
            top = changed.reindex(
                changed["delta_nb_star"].abs().sort_values(ascending=False).index
            ).head(5)
            for _, r in top.iterrows():
                print(f"  {r['config']} size{r['size']}: "
                      f"nb* {r['nb_star_median']} -> {r['nb_star_mean']} "
                      f"(差 {r['delta_nb_star']:+d}), "
                      f"帯 Jaccard {r['band_jaccard']}")
        print(f"\n  比較表: {outdir / 'comparison' / 'aggregator_comparison.md'}")


if __name__ == "__main__":
    raise SystemExit(main())
