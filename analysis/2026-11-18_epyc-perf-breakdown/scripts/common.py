"""共通：データの場所、タスク数、perf の読み込み。data/ は読むだけ。"""
import csv, glob, json, math, os, re
from collections import defaultdict
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA  # 集計結果の CSV はここ（元データと混ざらないよう接頭辞 a_ b_ c_ d_ を付ける）
D_PERF = next(DATA.glob("epyc_s1_smt-off_perf-breakdown_20261118_095221"))
D_STR = next(DATA.glob("epyc_s1_smt-off_perf-breakdown_20261118_102530"))


def ntasks(size, nb):
    n = math.ceil(size / nb)
    return n * (n + 1) * (2 * n + 1) // 6


def median(x):
    x = [v for v in x if v is not None]
    return st.median(x) if x else None


def read_runs(d):
    rows = []
    with open(d / "runs.csv") as f:
        for r in csv.DictReader(f):
            for k in ("round", "threads", "size", "nb", "ib", "exit"):
                r[k] = int(r[k])
            for k in ("Time_sec", "GFlops", "other_cpu_before", "load1_before", "minflt", "majflt", "vcsw", "ivcsw", "maxrss_kb", "utime", "stime"):
                r[k] = float(r[k]) if r.get(k) not in (None, "") else None
            rows.append(r)
    return rows


def perf_runs(base=None):
    """perf の1実行ごとに dict（cat 別の秒数、syms、window）を返す"""
    base = base or (D_PERF / "perf")
    out = []
    for wj in sorted(base.glob("*_window.json")):
        tag = wj.name[: -len("_window.json")]
        m = re.match(r"perf_p(\d+)_s(\d+)_nb(\d+)_r(\d+)$", tag)
        p, size, nb, rnd = map(int, m.groups())
        w = json.load(open(wj))
        cats, freq = {}, None
        with open(base / f"{tag}_cat.csv") as f:
            for r in csv.DictReader(f):
                freq = int(r["freq"])
                cats[r["cat"]] = (int(r["main_in"]), int(r["worker_in"]))
        top = []
        with open(base / f"{tag}_top.csv") as f:
            for r in csv.DictReader(f):
                top.append((r["cat"], r["dso"], r["sym"], int(r["samples"])))
        out.append(dict(tag=tag, p=p, size=size, nb=nb, round=rnd, window=w, freq=freq, cats=cats, top=top))
    return out
