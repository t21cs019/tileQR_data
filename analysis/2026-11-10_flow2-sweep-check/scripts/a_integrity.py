"""
A. データが揃っていて、条件どおりか。

出力:
  data/a1_grid.csv      CSV ごとの格子の検査（本番 15 本 + r0）
  data/a3_meta.csv      _meta.txt の条件の一覧
  data/a4_affinity.csv  _affinity.txt の検査と、検査で流れた size 2048・nb 128・ib 32 の値
  data/a5_snapshot.csv  開始・終了時の load average、空きメモリ、平均クロック
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import (DATA, P, REPS, SIZES, base, base_r0, expected_grid, parse_affinity, parse_meta, read_csv,
                    step_of)


def check_grid(path: Path, size: int, grid: list[tuple[int, int]]) -> dict:
    raw = path.read_bytes()
    d = read_csv(path)
    got = list(zip(d.nb, d.ib))
    exp_set, got_set = set(grid), set(got)
    g = pd.to_numeric(d.GFlops, errors="coerce")
    return {
        "file": path.name.replace("flow2-t1_s1_smt-off_bind-close_tileqr_", ""),
        "rows": len(d),
        "expected": len(grid),
        "columns_ok": list(d.columns[:5]) == ["threads", "size", "nb", "ib", "GFlops"],
        "crlf": raw.count(b"\r\n") == raw.count(b"\n"),
        "missing": len(exp_set - got_set),
        "extra": len(got_set - exp_set),
        "duplicates": len(got) - len(got_set),
        "order_ok": got == grid,           # 行の順が sweep.py の実行順と同じか
        "threads_ok": bool((d.threads == P).all()),
        "size_ok": bool((d["size"] == size).all()),
        "nan": int(g.isna().sum()),
        "zero_or_neg": int((g <= 0).sum()),   # plasma_perf は欠測を 0.0 と書く
        "min": g.min(),
        "max": g.max(),
        "ib_min": int(d.ib.min()),
        "ib_over_half": int((d.ib > d.nb // 2).sum()),
        "ib_step_ok": bool(((d.ib - 8) % step_of(size) == 0).all()),
        "nb_step_ok": bool(((d.nb - 32) % step_of(size) == 0).all()),
        "nb_range": f"{d.nb.min()}-{d.nb.max()}",
    }


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)

    # --- A1 ---
    rows = []
    for s in SIZES:
        for r in REPS:
            rows.append(check_grid(Path(str(base(s, r)) + ".csv"), s, expected_grid(s)))
    # r0：SIZE=1024, NB 128-144, STEP=16
    g0 = [(nb, ib) for nb in (128, 144) for ib in range(8, nb // 2 + 1, 16)]
    rows.append(check_grid(Path(str(base_r0()) + ".csv"), 1024, g0))
    a1 = pd.DataFrame(rows)
    a1.to_csv(DATA / "a1_grid.csv", index=False)
    print("== A1 格子 ==")
    print(a1.to_string(index=False))

    # --- A3 ---
    metas = [parse_meta(Path(str(base(s, r)) + "_meta.txt")) | {"size": s, "rep": r} for s in SIZES for r in REPS]
    metas.append(parse_meta(Path(str(base_r0()) + "_meta.txt")) | {"size": 1024, "rep": 0})
    keys = ["size", "rep", "host", "job", "config", "commit", "plasmatest", "libs", "smt", "socket_nodes",
            "openblas_threads", "cond", "omp", "numactl", "model", "boost", "lscpu_hash", "lscpu_e_hash",
            "numa_hash", "numa_sizes"]
    a3 = pd.DataFrame([{k: m.get(k) for k in keys} for m in metas])
    a3.to_csv(DATA / "a3_meta.csv", index=False)
    print("\n== A3 meta：値の種類（本番 15 本）==")
    prod = a3[a3.rep > 0]
    for k in keys[4:]:
        if k == "cond":
            continue
        u = prod[k].unique()
        print(f"{k:18s} {len(u)} 種類: {u[0] if len(u) == 1 else list(u)}")
    print(prod[["size", "rep", "host", "job", "cond"]].to_string(index=False))
    # lscpu などがそろわないとき、どの行が違うかを出す
    ref = metas[0]
    for sec in ("_lscpu", "_lscpu_e", "_numa"):
        for m in metas[1:]:
            diff = [(a, b) for a, b in zip(ref[sec], m[sec]) if a != b]
            if diff or len(ref[sec]) != len(m[sec]):
                print(f"[差] {sec} size{m['size']} r{m['rep']} ({m['host']}): {diff[:5]}")
    print("r0:", a3[a3.rep == 0][["host", "job", "commit", "cond", "omp", "numactl"]].to_dict("records"))

    # lscpu -e から CPU→(core, socket, node) を取る（A4 で使う）
    topo = {}
    for ln in ref["_lscpu_e"]:
        f = ln.split()
        if len(f) >= 4 and f[0].isdigit():
            topo[int(f[0])] = (int(f[1]), int(f[2]), int(f[3]))

    # --- A4 ---
    rows = []
    for m in metas:
        s, r = m["size"], m["rep"]
        b = base_r0() if r == 0 else base(s, r)
        a = parse_affinity(Path(str(b) + "_affinity.txt"))
        single = all(c.isdigit() for c in a["cpus"])
        cpus = [int(c) for c in a["cpus"]] if single else []
        cores = {topo[c][0] for c in cpus}
        rows.append({
            "size": s, "rep": r, "host": m["host"],
            "threads": len(a["threads"]),
            "threads_0_191": a["threads"] == list(range(P)),
            "one_cpu_each": single,
            "distinct_cpus": len(set(cpus)),
            "distinct_cores": len(cores),
            "all_socket0": all(topo[c][1] == 0 for c in cpus),
            "numa_nodes": ",".join(str(n) for n in sorted({topo[c][2] for c in cpus})),
            "identity_map": cpus == list(range(P)),   # thread i → cpu i
            "check_status": a["status"],
            "check_time_ms": a["check_time_s"] * 1e3,
            "check_gflops": a["check_gflops"],
            "plasma": a["header"],
        })
    a4 = pd.DataFrame(rows)
    a4.to_csv(DATA / "a4_affinity.csv", index=False)
    print("\n== A4 affinity ==")
    print(a4.drop(columns="plasma").to_string(index=False))
    print("plasmatest の見出し:", sorted({h.rsplit(",", 1)[0] for h in a4.plasma}))

    # --- A5 ---
    rows = []
    for m in metas:
        fs, fe = np.array(m["start_free"]), np.array(m["end_free"])
        rows.append({
            "size": m["size"], "rep": m["rep"], "host": m["host"],
            "start": m["start_time"], "end": m["end_time"], "elapsed_s": m["elapsed_s"],
            "uptime": m["start_uptime"], "users": f"{m['start_users']}/{m['end_users']}",
            "load_start": f"{m['start_load1']:.1f}/{m['start_load5']:.1f}/{m['start_load15']:.1f}",
            "load_end": f"{m['end_load1']:.1f}/{m['end_load5']:.1f}/{m['end_load15']:.1f}",
            "end_load1": m["end_load1"], "end_load15": m["end_load15"],
            "free_s0_start_GB": fs[:4].sum() / 1024, "free_s1_start_GB": fs[4:].sum() / 1024,
            "dfree_s0_MB": int((fe[:4] - fs[:4]).sum()), "dfree_s1_MB": int((fe[4:] - fs[4:]).sum()),
            "dfree_node_min_MB": int((fe - fs).min()),
            "mhz_start": m["start_mhz"], "mhz_end": m["end_mhz"],
            "scaling_pct_lscpu": m["scaling_mhz_pct"],
        })
    a5 = pd.DataFrame(rows)
    a5.to_csv(DATA / "a5_snapshot.csv", index=False)
    print("\n== A5 スナップショット ==")
    print(a5.drop(columns=["end_load1", "end_load15"]).to_string(index=False))


if __name__ == "__main__":
    main()
