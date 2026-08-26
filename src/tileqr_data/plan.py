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

    plan.yaml では threads や nodes をリストで書けるので、ここで平坦化する。
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
        nodes = t.get("nodes") or ([t["node"]] if "node" in t else [None])

        for threads in threads_list:
            for node in nodes:
                out.append(
                    {
                        "kind": kind,
                        "config": t.get("config"),
                        "node": node,
                        "threads": int(threads),
                        "size": int(t["size"]),
                        "nb_lo": int(t["nb"][0]),
                        "nb_hi": int(t["nb"][1]),
                        "trials": int(t.get("trials", default_trials)),
                        "grid": grid,
                    }
                )
    return out


def grid_of(kind: str, plan: dict | None = None) -> dict | None:
    plan = plan if plan is not None else load()
    spec = (plan.get("kinds") or {}).get(kind)
    return spec.get("grid") if spec else None


def label_of(kind: str, plan: dict | None = None) -> str:
    plan = plan if plan is not None else load()
    spec = (plan.get("kinds") or {}).get(kind) or {}
    return spec.get("label", kind)
