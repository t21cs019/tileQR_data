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

from tileqr_data import console, io, paths, plan  # noqa: E402

console.use_utf8()

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
        # 格子の刻みは size で変わるので、size ごとに解決してから数える。
        size_grid = plan.grid_for_size(int(dict(zip(keys, kv))["size"]), grid)
        expected = plan.expected_points(full_nbs, size_grid) if size_grid else 0

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


# 表示の粒度。node は入れない。
#
# AOBA はバッチ計算機でジョブごとにノードが変わるので、node で割ると
# 同じ条件が5行に散る。読み手が知りたいのは「その条件が何本取れているか」で、
# それはノードをまたいだ本数の合計。ノードの個体差は
# 「反復と最適 nb のばらつき」の節が受け持つ。
COND_KEYS = {
    "qr_sweep": ["config", "threads", "size"],
    "ssrfb": ["node", "threads", "size"],
    "kernel_dtsmqr": ["node", "threads", "size"],
}


def _machine_col(kind: str) -> str:
    return "config" if kind == "qr_sweep" else "node"


def _cond_key(kind: str, d: dict) -> tuple:
    """計画 target と実測 stats の双方から同じ形の鍵を作る。"""
    return (d.get(_machine_col(kind)), d["threads"], d["size"])


def _plan_index(kind: str) -> dict[tuple, dict]:
    """計画を (config|node, threads, size) で引けるようにする。"""
    return {_cond_key(kind, t): t for t in plan.targets_for(kind)}


def _status(measured: dict | None, target: dict | None) -> tuple[str, str, str]:
    """status / 計画に対する被覆率 / trials 表記 を返す。"""
    if measured is None:
        return "missing", "0%", f"0/{target['trials']}" if target else "0/?"

    trials_txt = str(measured["trials"])
    plan_txt = "—"
    ok_plan = True

    if target:
        trials_txt = f"{measured['trials']}/{target['trials']}"
        want = plan.expected_for(target)
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


# 表の並び順。io.display_rank が machines.yaml の display_order を引く。
# 学外（AOBA）→ 大学のサーバ → 自宅（世代が新しい順）。
# アルファベット順にしないのは、読み手が探すのは「どの設置場所の機材か」
# であって名前の綴りではないため。qr_sweep（config）と ssrfb（node）の
# 両方の表が同じ番号で並ぶので、資料間で順序が食い違わない。
def _ranker():
    machines = io.load_machines()
    return lambda name: (io.display_rank(str(name), machines), str(name))


def progress_section(
    stats_by_kind: dict[str, list[dict]], running: dict[tuple, dict]
) -> tuple[list[str], str, int]:
    """
    計画に対してどこまで終わっているかを 機材 × size の一覧にする。

    条件別の表は細かすぎて全体像が掴めないので、まずこれを見る。
    セルは「取れている反復数 / 計画の反復数」。

    `running.yaml` に載っている条件には `▶` を付ける。データの有無だけだと
    「まだ流していない」と「流したがまだ終わっていない」が同じ `—` に見え、
    数日かかる走査（size16384、AOBA のバッチジョブ）で同じ計測を二重に
    投入したり、落ちたジョブを放置したりする。
    """
    lines: list[str] = []
    done_all = plan_all = 0
    running_hits = 0
    rank = _ranker()

    for kind, stats in stats_by_kind.items():
        idx = _plan_index(kind)
        if not idx:
            continue

        by_key = {_cond_key(kind, r): r for r in stats}
        sizes = sorted({t["size"] for t in idx.values()})
        machines: dict[tuple, list] = {}
        for t in idx.values():
            machines.setdefault((t[_machine_col(kind)], t["threads"]), [])

        label = _machine_col(kind)
        lines += ["", f"### {kind}", ""]
        lines += _table_header([label, "t", *[str(s) for s in sizes], "達成"])

        for (machine, threads) in sorted(machines, key=lambda k: (*rank(k[0]), k[1])):
            cells = []
            done_row = 0
            for size in sizes:
                key = (machine, threads, size)
                target = idx.get(key)
                if target is None:
                    cells.append("·")
                    continue
                frozen = bool(target.get("frozen"))
                # 凍結条件は「計画に対する完了」の分母から外す。もう埋まらない
                # ものを分母に残すと、達成率が永遠に 100% にならず指標が死ぬ。
                if not frozen:
                    plan_all += 1
                in_flight = (kind, machine, threads, size) in running
                running_hits += bool(in_flight)
                mark = " ▶" if in_flight else ("  x" if frozen else "")
                got = by_key.get(key)
                if got is None:
                    cells.append(f"—{mark}")
                    continue
                want = plan.expected_for(target)
                enough_nb = got["points"] >= want
                enough_trials = got["trials"] >= target["trials"]
                cell = f"{got['trials']}/{target['trials']}"
                if frozen:
                    cells.append(cell + mark)
                    continue
                if enough_trials and enough_nb:
                    done_row += 1
                    done_all += 1
                elif enough_trials and not enough_nb:
                    cell += " !"          # 反復は足りているが nb が計画に届かない
                cells.append(cell + mark)
            n_planned = sum(
                1 for s in sizes
                if (machine, threads, s) in idx
                and not idx[(machine, threads, s)].get("frozen")
            )
            lines.append(
                f"| `{machine}` | {threads} | " + " | ".join(cells)
                + f" | {done_row}/{n_planned} |"
            )

    summary = f"{done_all} / {plan_all}"
    lines += [
        "",
        f"完了 **{summary}** 条件。"
        "セルは「取れている反復数 / 計画の反復数」。"
        "`—` は未計測、`·` は計画に無い、"
        "`!` は反復は足りているが nb が計画の範囲に届いていない、"
        "`▶` は計測中（`running.yaml`）、"
        "`x` はこれ以上データが来ない（`plan.yaml` の `frozen`。分母から除く）。",
    ]
    return lines, summary, running_hits


def frozen_section() -> list[str]:
    """
    もうデータが来ない条件と、その理由。

    進捗表の `x` だけだと「なぜ埋まらないのか」が分からない。計測機材が
    手を離れた事情は数年後には誰も覚えていないので、理由をここに出す。
    """
    rows = []
    for kind in ("qr_sweep", "ssrfb", "kernel_dtsmqr"):
        for t in plan.targets_for(kind):
            if t.get("frozen"):
                rows.append((kind, t.get("config") or t.get("node"),
                             t["threads"], t["size"], t["trials"], t["frozen"]))
    if not rows:
        return ["これ以上データが来ないと宣言された条件はありません。"]

    lines = _table_header(["kind", "機材", "t", "size", "計画", "理由"])
    for kind, machine, threads, size, trials, why in sorted(rows, key=lambda r: str(r)):
        lines.append(
            f"| {kind} | `{machine}` | {threads} | {size} | {trials} | {why} |"
        )
    thin = [r for r in rows if r[4] > 1]
    lines += [
        "",
        "これらは「計画に対する完了」の分母から外してある。埋まらないものを"
        "分母に残すと達成率が永遠に 100% にならず、指標として見なくなるため。",
    ]
    if thin:
        lines += [
            "",
            "**分母から外すのは進捗の話であって、データの信頼性の話ではない。**",
            "反復が計画に届かない以上、これらの `nb_opt` は「ノイズの中で偶然"
            "突き出した棘」である可能性を排除できず、研究の主張には使えない。",
            "",
            "なお `derived/optima.csv` と「95% 性能帯の健全性」は qr_sweep しか"
            "見ていないので、kernel_dtsmqr / ssrfb の条件はそちらにも出てこない。"
            "この節が唯一の警告になる。",
        ]
    return lines


def running_section(entries: list[dict]) -> list[str]:
    """
    いま流している計測と、そのとき打ったコマンド。

    「どこまでコマンドを打ったか」を後から思い出すのが目的。進捗表の `▶` は
    どのセルが計測中かしか言わないので、実際に打った内容はここに出す。
    """
    if not entries:
        return ["計測中の項目はありません（`running.yaml` が空）。"]

    lines = _table_header(["kind", "機材", "t", "size", "開始", "host", "備考"])
    rank = _ranker()
    for e in sorted(entries, key=lambda e: rank(e.get("config") or e.get("node"))):
        machine = e.get("config") or e.get("node")
        sizes = ", ".join(str(s) for s in e["sizes"])
        # note は yaml の折り返し（`>`）で改行が残る。表のセルに改行を入れると
        # 行が途中で切れて表が崩れるので、空白に畳んでから入れる。
        note = " ".join(str(e.get("note", "")).split())
        lines.append(
            f"| {e['kind']} | `{machine}` | {e['threads']} | {sizes} | "
            f"{e['since']} | {e.get('host', '—')} | {note} |"
        )

    with_cmd = [e for e in entries if e.get("command")]
    if with_cmd:
        lines += ["", "打ったコマンド:", ""]
        for e in with_cmd:
            machine = e.get("config") or e.get("node")
            lines += [f"`{machine}` t{e['threads']} ({e['since']}):", "", "```sh"]
            lines += str(e["command"]).rstrip().splitlines()
            lines += ["```", ""]
    return lines


def sweep_section(stats: list[dict], kind: str) -> list[str]:
    idx = _plan_index(kind)
    label = _machine_col(kind)
    rank = _ranker()

    cols = [label, "t", "size", "nb 走査", "step", "n_nb", "ib",
            "計測点", "格子", "計画", "trials", "status", "計測日"]
    lines = _table_header(cols)

    seen = set()
    for r in sorted(stats, key=lambda r: (*rank(r.get(label)), r["threads"], r["size"])):
        key = _cond_key(kind, r)
        seen.add(key)
        status, plan_txt, trials_txt = _status(r, idx.get(key))
        hole = f" (欠測 {len(r['missing_nb'])})" if r["missing_nb"] else ""
        lines.append(
            f"| `{r[label]}` | {r['threads']} | {r['size']} | "
            f"{r['nb_lo']}-{r['nb_hi']} | {r['nb_step']} | {r['n_nb']}{hole} | "
            f"{r['ib_lo']}-{r['ib_hi']}/{r['ib_step']} | {r['points']:,} | "
            f"{_pct(r['fill'])} | {plan_txt} | {trials_txt} | {status} | {r['dates']} |"
        )

    # 計画にあるが1件も測っていない条件
    for key, t in sorted(idx.items(), key=lambda kv: (*rank(kv[0][0]), kv[0][1], kv[0][2])):
        if key in seen:
            continue
        lines.append(
            f"| `{t[label]}` | {t['threads']} | {t['size']} | "
            f"{t['nb_lo']}-{t['nb_hi']} | {t['nb_step']} | — | — | 0 | "
            f"0% | 0% | 0/{t['trials']} | **missing** | — |"
        )

    return lines


def reproducibility_section(optima: pd.DataFrame) -> list[str]:
    """
    最適 nb がどれだけ散るか。

    AOBA は同一構成でも物理ノードが複数あるので、その間の散らばりが出る。
    これが大きいまま nb_opt を「最適タイルサイズ」と呼ぶと、
    再現性のない値を主張することになる。ノード名を出す唯一の節。
    """
    lines = _table_header(
        ["config", "t", "size", "独立測定", "nb_opt", "幅", "変動係数"]
    )
    rank = _ranker()
    rows: list[tuple[tuple, str]] = []
    single = 0
    for (config, threads, size), sub in optima.groupby(
        ["config", "threads", "size"], observed=True
    ):
        vals = sorted(int(v) for v in sub["nb_opt"])
        # 独立測定が1つだと散らばりようがない。行にしても情報が無いので数だけ数える。
        if len(vals) < 2:
            single += 1
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        shown = ", ".join(str(v) for v in vals[:8]) + ("…" if len(vals) > 8 else "")
        rows.append((
            (*rank(config), threads, size),
            f"| `{config}` | {threads} | {size} | {len(vals)} | "
            f"{shown} | {max(vals) - min(vals)} | "
            f"{100 * (var ** 0.5) / mean:.1f}% |"
        ))
    lines += [line for _, line in sorted(rows, key=lambda t: t[0])]

    lines += [
        "",
        f"独立測定が1つしかない条件が {single} 件（1台構成の機材はここに入る）。"
        "その条件の nb_opt には、ハード個体差の裏付けが無い。",
    ]
    return lines


def _verdict(r) -> tuple[str, bool]:
    """1つの測定に対する 95% 帯の判定。"""
    n = int(r["nb_in_band"])
    at_edge = r["nb_lo95"] == r["nb_scanned_lo"] or r["nb_hi95"] == r["nb_scanned_hi"]
    ratio = r["noise_ratio"]
    if n <= 1:
        return "退化（単点）", True
    if at_edge:
        return "走査端で切断", False
    if pd.notna(ratio) and ratio >= 1.0:
        # 反復間のばらつきが帯の幅と同程度。帯の狭さを主張の根拠にできない。
        return "ノイズが帯と同程度", False
    return "ok", False


def band_section(optima: pd.DataFrame) -> tuple[list[str], int]:
    """95% 性能帯の健全性。条件ごとにまとめ、問題のある測定数を数える。"""
    lines = _table_header(
        ["config", "t", "size", "nb_opt", "95%帯(代表)", "帯内の点",
         "trials", "ノイズ/帯", "判定"]
    )
    degenerate = 0
    rank = _ranker()
    rows: list[tuple[tuple, str]] = []

    for (config, threads, size), sub in optima.groupby(
        ["config", "threads", "size"], observed=True
    ):
        verdicts = [_verdict(r) for _, r in sub.iterrows()]
        n_bad = sum(1 for _, bad in verdicts if bad)
        degenerate += n_bad

        # 代表は帯が最も狭い測定。問題があるならそれが見えるべき。
        worst = sub.loc[sub["nb_in_band"].idxmin()]
        others = {v for v, _ in verdicts if v != "ok"}

        if n_bad:
            verdict = f"**退化 {n_bad}/{len(sub)}**"
        elif others:
            verdict = "・".join(sorted(others))
        else:
            verdict = "ok"

        nb_opts = sorted(int(v) for v in sub["nb_opt"])
        nb_txt = (
            str(nb_opts[0]) if len(set(nb_opts)) == 1
            else f"{nb_opts[0]}-{nb_opts[-1]}"
        )
        ratio = worst["noise_ratio"]
        rt = "—" if int(worst["trials"]) < 2 else f"{ratio:.2f}"
        rows.append((
            (*rank(config), threads, size),
            f"| `{config}` | {threads} | {size} | {nb_txt} | "
            f"{worst['nb_lo95']}-{worst['nb_hi95']} | {int(worst['nb_in_band'])} | "
            f"{int(worst['trials'])} | {rt} | {verdict} |"
        ))
    lines += [line for _, line in sorted(rows, key=lambda t: t[0])]
    return lines, degenerate


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

    sweep_stats = condition_stats(sweeps, COND_KEYS["qr_sweep"], sweep_grid)
    kernel_stats = (
        condition_stats(kernel, COND_KEYS["kernel_dtsmqr"], kernel_grid)
        if kernel is not None and not kernel.empty
        else []
    )
    ssrfb_stats = (
        condition_stats(ssrfb, COND_KEYS["ssrfb"], ssrfb_grid)
        if ssrfb is not None and not ssrfb.empty
        else []
    )

    stats_by_kind = {
        "qr_sweep": sweep_stats,
        "ssrfb": ssrfb_stats,
        "kernel_dtsmqr": kernel_stats,
    }
    running = plan.load_running()
    band_lines, n_degenerate = band_section(optima)
    progress_lines, progress, n_running = progress_section(
        stats_by_kind, plan.running_keys(running)
    )
    all_stats = sweep_stats + kernel_stats + ssrfb_stats

    n_files = int(sweeps["source_file"].nunique())
    for extra in (kernel, ssrfb):
        if extra is not None and not extra.empty:
            n_files += int(extra["source_file"].nunique())

    under_trials = 0
    for kind, stats in stats_by_kind.items():
        idx = _plan_index(kind)
        for r in stats:
            t = idx.get(_cond_key(kind, r))
            # 凍結条件は数えない。行動できない件数を混ぜると、この数字を
            # 見ても「次に何を測るか」が決まらなくなる。
            if t and not t.get("frozen") and r["trials"] < t["trials"]:
                under_trials += 1
    with_holes = sum(1 for r in all_stats if r["missing_nb"])

    lines = [
        "# COVERAGE",
        "",
        "`scripts/ingest.py` が自動生成する。手で編集しない。",
        "計画は `plan.yaml`、機材は `machines.yaml` を参照。",
        "",
        "## 計画の進捗",
        "",
        "どの CPU でも size 1024/2048/4096/8192/16384 の5種、nb 32-512 を測る計画。",
        "nb の刻みは size 4096 までが 4、それ以上が 8。反復は各 5 回。",
    ]
    lines += progress_lines

    lines += [
        "",
        "## 計測中",
        "",
        "`running.yaml` に載っているもの。計測コマンドを打ったら足し、",
        "データが `raw/` に入ったら消す。`make validate` が消し忘れを警告する。",
        "",
    ]
    lines += running_section(running)

    lines += [
        "",
        "## これ以上データが来ない条件",
        "",
        "`plan.yaml` の `frozen`。計測機材が手を離れたなどの理由で、",
        "計画に届かないまま確定した条件。",
        "",
    ]
    lines += frozen_section()

    lines += [
        "",
        "## サマリ",
        "",
        "| 指標 | 値 |",
        "|---|---|",
        f"| 計画に対する完了 | {progress} 条件 |",
        f"| 計測中の条件 | {n_running} |",
        f"| 計測ファイル | {n_files} |",
        f"| 計測済みの条件 (種別×機材×threads×size) | {len(all_stats)} |",
        f"| 計測点 (nb×ib) | {sum(r['points'] for r in all_stats):,} |",
        f"| **反復が計画に届かない条件** | {under_trials} / {len(all_stats)} |",
        f"| **95%帯が単点に潰れた測定** | {n_degenerate} |",
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
        "### 最適 nb のばらつき",
        "",
        "AOBA は同一構成でも物理ノードが複数あるので、その個体差がここに出る。",
        "1測定しかない条件は「1回の計測で最適 nb を主張している」状態を意味する。",
        "",
    ]
    lines += reproducibility_section(optima)

    lines += [
        "",
        "### 95% 性能帯の健全性",
        "",
        "帯内の点が1つしかない測定は、ピークが「なだらかな山の頂上」ではなく",
        "「ノイズの中で偶然突き出した棘」である疑いが強い。反復して平均を取るまで",
        "その `nb_opt` は主張に使えない。代表は帯が最も狭い測定を出している。",
        "",
    ]
    lines += band_lines

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
