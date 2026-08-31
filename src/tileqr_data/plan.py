"""
計測計画（plan.yaml）の読み込みと、計測点の数え方。

**計測点の期待値を数える規則はここだけが持つ。** COVERAGE.md も validate.py も
ここを呼ぶ。ib の上限規則が測定種別で違う（qr_sweep は ib<=nb/2、
kernel_dtsmqr は ib<=nb-step）ため、数え方が複数箇所にあると
「格子が埋まっているか」の判定が食い違う。

plasma-perf 側の coverage 列と同じ算術になるようにしてある。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import paths

# ib の上限規則。plan.yaml の grid.ib_cap に書く名前と対応する。
IB_CAPS = {
    "half_nb": lambda nb, step: nb // 2,
    "nb_minus_step": lambda nb, step: nb - step,
}


def load() -> dict:
    """plan.yaml を読む。無ければ空の計画を返す（計画なしでも COVERAGE は出る）。"""
    if not paths.PLAN_YAML.exists():
        return {"kinds": {}, "defaults": {}}
    with paths.PLAN_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {"kinds": {}, "defaults": {}}


def nb_values(lo: int, hi: int, step: int) -> list[int]:
    """走査するはずの nb の列。"""
    return list(range(int(lo), int(hi) + 1, int(step)))


def nb_step_for(size: int, grid: dict) -> int:
    """
    その行列サイズでの nb の刻み。

    大きい行列は1点あたりの計測時間が延びるので、同じ密度で走らせると
    終わらない。size ごとに刻みを変える計画になっている。
    """
    by_size = grid.get("nb_step_by_size")
    if by_size:
        if int(size) in by_size:
            return int(by_size[int(size)])
        # 表に無い size は、一番大きい既知サイズの刻みに倣う
        return int(by_size[max(by_size)])
    return int(grid.get("nb_step", 1))


def grid_for_size(size: int, grid: dict) -> dict:
    """
    その行列サイズでの実効的な格子。

    刻みを粗くするとき、nb だけでなく ib も一緒に粗くなる
    （size 8192 は nb も ib も 8 刻み）。ib_step を固定にすると
    大きい size で期待点数が倍近く過大になる。
    """
    g = dict(grid)
    g["nb_step"] = nb_step_for(size, grid)
    if grid.get("ib_step_follows_nb_step"):
        g["ib_step"] = g["nb_step"]
    return g


def ib_count(nb: int, grid: dict) -> int:
    """ある nb に対して走査するはずの ib の個数。"""
    ib_min = int(grid["ib_min"])
    ib_step = int(grid["ib_step"])
    cap_fn = IB_CAPS.get(grid.get("ib_cap", "half_nb"))
    if cap_fn is None:
        raise ValueError(f"未知の ib_cap: {grid.get('ib_cap')}")

    cap = cap_fn(int(nb), ib_step)
    if cap < ib_min:
        return 0
    return (cap - ib_min) // ib_step + 1


def expected_points(nbs: list[int], grid: dict) -> int:
    """nb の列に対する計測点（nb×ib の組）の総数。"""
    return sum(ib_count(nb, grid) for nb in nbs)


def targets_for(kind: str, plan: dict | None = None) -> list[dict]:
    """
    ある測定種別の計画を、(config|node, threads, size) 単位に展開して返す。

    plan.yaml は「どの CPU でも同じ size 一式」という書き方をするので、
    種別ごとの sizes / nb / trials を各 target に配り、threads のリストと
    掛け合わせて平坦化する。
    """
    plan = plan if plan is not None else load()
    spec = (plan.get("kinds") or {}).get(kind)
    if not spec:
        return []

    default_trials = (plan.get("defaults") or {}).get("trials", 1)
    grid = spec.get("grid", {})
    out = []

    for t in spec.get("targets") or []:
        threads_list = t["threads"]
        if not isinstance(threads_list, list):
            threads_list = [threads_list]

        sizes = t.get("sizes", spec.get("sizes")) or [t["size"]]
        nb = t.get("nb", spec.get("nb"))
        trials = int(t.get("trials", spec.get("trials", default_trials)))

        for threads in threads_list:
            for size in sizes:
                out.append(
                    {
                        "kind": kind,
                        "config": t.get("config"),
                        "node": t.get("node"),
                        "threads": int(threads),
                        "size": int(size),
                        "nb_lo": int(nb[0]),
                        "nb_hi": int(nb[1]),
                        "nb_step": nb_step_for(size, grid),
                        "trials": trials,
                        "grid": grid_for_size(size, grid),
                        # 「これ以上データが来ない」条件の理由。None なら通常。
                        # 計測機材が失われた条件を「未達」として数え続けると、
                        # その数字が行動につながらなくなる。
                        "frozen": t.get("frozen"),
                    }
                )
    return out


def expected_for(target: dict) -> int:
    """計画1条件ぶんの計測点数。"""
    nbs = nb_values(target["nb_lo"], target["nb_hi"], target["nb_step"])
    return expected_points(nbs, target["grid"])


def grid_of(kind: str, plan: dict | None = None) -> dict | None:
    plan = plan if plan is not None else load()
    spec = (plan.get("kinds") or {}).get(kind)
    return spec.get("grid") if spec else None


def label_of(kind: str, plan: dict | None = None) -> str:
    plan = plan if plan is not None else load()
    spec = (plan.get("kinds") or {}).get(kind) or {}
    return spec.get("label", kind)


# --- 計測中（running.yaml） ------------------------------------------------
#
# 進捗表は「計画にあるか」「データがあるか」の2値しか持たないので、
# 「まだ流していない」と「流したがまだ終わっていない」が同じ `—` に見える。
# size16384 や AOBA のバッチジョブは数日かかるため、この区別がつかないと
# 同じ計測を二重に投入するか、落ちたジョブを放置することになる。


class RunningError(ValueError):
    """running.yaml の書き方が壊れている。"""


REQUIRED_RUNNING = ("kind", "threads", "sizes", "since")


def load_running() -> list[dict]:
    """running.yaml を読む。無ければ空（従来どおり進捗表に `▶` が出ないだけ）。"""
    if not paths.RUNNING_YAML.exists():
        return []
    with paths.RUNNING_YAML.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}

    out = []
    for i, entry in enumerate(doc.get("running") or []):
        missing = [k for k in REQUIRED_RUNNING if not entry.get(k)]
        if missing:
            raise RunningError(f"running.yaml の {i} 番目: {missing} が無い")
        if not entry.get("config") and not entry.get("node"):
            raise RunningError(
                f"running.yaml の {i} 番目: config か node のどちらかが要る"
            )
        sizes = entry["sizes"]
        entry = dict(entry, sizes=[int(s) for s in (sizes if isinstance(sizes, list) else [sizes])])
        entry["threads"] = int(entry["threads"])
        out.append(entry)
    return out


def running_keys(entries: list[dict] | None = None) -> dict[tuple, dict]:
    """
    計測中のエントリを (kind, config|node, threads, size) で引けるようにする。

    進捗表のセルと同じ鍵の形にしてあるので、表側は引くだけでよい。
    """
    entries = entries if entries is not None else load_running()
    index: dict[tuple, dict] = {}
    for e in entries:
        machine = e.get("config") or e.get("node")
        for size in e["sizes"]:
            index[(e["kind"], machine, e["threads"], size)] = e
    return index
