"""
計測済みのスイープ（nb×ib、各5回）を引いて Optuna を再現し、nb の探索範囲ごとに比べる。

  対象     : HT 無効・1ソケットの13構成・57条件（../2026-10-27_gen4-kernel-term/data/eta_eff.csv と derived/qr_sweep.parquet）
  Optuna   : 既定の TPE。nb と ib を同時に探す。1回 100 試行、乱数の種 0〜19 の 20 回
  ib の範囲: 8 〜 nb/2（計測した格子の全部）。卒論は「2 から nb の半分までの偶数」で、ib 2〜6 は計測していないので入らない
  目的関数 : single … 5回の計測値から1つを無作為に引いて返す
             mean5  … 5回の平均を返す（卒論と同じ。1試行で QR を5回実行したことにする）
  nb の範囲: full    … 計測した全範囲（32〜512）
             B       … 下限の時間 ≤ 上限の時間の最小、となる nb（τ なし。A·E·η、c・k は理論値）
             B_tau   … 同じ条件で、両方に タスク数·a·p（a = 0.092 µs）を足す
             thr92   … 参考。上限＋τ の予測性能が最大の 92% 以上の nb
  到達度   : Optuna がその時点で最良と見ている (nb, ib) の5回平均 ÷ 全 (nb, ib) の5回平均の最大

出力（data/）:
  search_ranges.csv        条件ごとの各範囲（lo, hi）、実測の最適 nb、範囲に入るか、範囲内の最高÷全体の最高、残す nb の割合
  optuna_replay_runs.csv   1回（条件×範囲×目的関数×種）ごとの結果
  optuna_replay_curves.csv 条件×範囲×目的関数×試行番号ごとの到達度（20回の平均・中央値・最低）と累積の実行時間

実行: uv run --with optuna --with pandas --with pyarrow python scripts/optuna_replay.py
"""
import sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np, pandas as pd, optuna

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT.parent / "2026-11-10_serial-task-cost" / "scripts"))
from common10 import load_s1  # noqa: E402

optuna.logging.set_verbosity(optuna.logging.ERROR)
N_TRIALS, N_SEEDS, A_TAU = 100, 20, 0.092
CHECK = (5, 10, 20, 30, 50, 100)

s1 = load_s1()
s1["y"] = s1.p * s1.D / (4 * s1.N**3)
s1["tk"] = s1.W / (s1.p * s1.A_k * s1.nb / (s1.nb + s1.beta_k)) / 1e9
s1["tt"] = A_TAU * s1.p * s1.tasks * 1e-6
RANGES, rr = {}, []
for (c, s), g in s1.groupby(["config", "size"]):
    lo, hi = g.tk * np.maximum(1, g.y), g.tk * (1 + g.y)
    keep = {"full": pd.Series(True, index=g.index), "B": lo <= hi.min(), "B_tau": lo + g.tt <= (hi + g.tt).min(),
            "thr92": (hi + g.tt).min() / (hi + g.tt) >= 0.92}
    RANGES[(c, s)] = {k: (int(g.nb[v].min()), int(g.nb[v].max())) for k, v in keep.items()}
    for k, v in keep.items():
        rr.append(dict(config=c, label=g.label.iloc[0], p=g.p.iloc[0], size=s, range=k, lo=g.nb[v].min(), hi=g.nb[v].max(),
                       nb_opt=g.nb[g.G.idxmax()], opt_in_range=bool(v[g.G.idxmax()]), best_in_range=g.G[v].max() / g.G.max(),
                       frac_nb_kept=v.mean(), n_nb_kept=int(v.sum()), n_nb=len(g)))
raw = pd.read_parquet(OUT.parents[1] / "derived" / "qr_sweep.parquet")
raw = raw[raw.config.isin(s1.config.unique()) & (raw.nb >= 32) & (raw.nb <= 512)]


def one(key):
    c, s = key
    g = raw[(raw.config == c) & (raw["size"] == s)]
    reps = g.groupby(["nb", "ib"]).GFlops.apply(np.array).to_dict()
    mean = {k: v.mean() for k, v in reps.items()}
    gmax = max(mean.values())
    nbs = np.array(sorted(g.nb.unique())); step = int(np.diff(nbs).min())
    ibs = {nb: np.array(sorted(i for (n, i) in reps if n == nb)) for nb in nbs}
    W = 4 / 3 * s**3 / 1e9
    runs, curves = [], []
    for mode in ("single", "mean5"):
        for rname, (lo, hi) in RANGES[key].items():
            B, S = [], []
            for seed in range(N_SEEDS):
                rng = np.random.default_rng(seed)

                def obj(trial):
                    nb = trial.suggest_int("nb", lo, hi, step=step)
                    a = ibs[nb]
                    ib = trial.suggest_int("ib", int(a.min()), int(a.max()), step=int(np.diff(a).min()) if len(a) > 1 else 1)
                    ib = int(a[np.abs(a - ib).argmin()])
                    v = reps[(nb, ib)]
                    val, sec = (float(rng.choice(v)), None) if mode == "single" else (float(v.mean()), float((W / v).sum()))
                    trial.set_user_attr("true", mean[(nb, ib)] / gmax)
                    trial.set_user_attr("sec", W / val if sec is None else sec)
                    trial.set_user_attr("nb", int(nb)); trial.set_user_attr("ib", ib)
                    return val

                st = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
                st.optimize(obj, n_trials=N_TRIALS)
                vals = np.array([t.value for t in st.trials]); tr = np.array([t.user_attrs["true"] for t in st.trials])
                sec = np.cumsum([t.user_attrs["sec"] for t in st.trials])
                arg = np.array([vals[:i + 1].argmax() for i in range(N_TRIALS)])
                best = tr[arg]
                row = dict(config=c, size=s, mode=mode, range=rname, lo=lo, hi=hi, seed=seed,
                           final_nb=st.trials[arg[-1]].user_attrs["nb"], final_ib=st.trials[arg[-1]].user_attrs["ib"])
                for th in (0.95, 0.99):
                    i = np.where(best >= th)[0]
                    row[f"n{int(th*100)}"] = i[0] + 1 if len(i) else np.nan
                    row[f"sec{int(th*100)}"] = sec[i[0]] if len(i) else np.nan
                for n in CHECK:
                    row[f"q{n}"] = best[n - 1]; row[f"cumsec{n}"] = sec[n - 1]
                runs.append(row); B.append(best); S.append(sec)
            B, S = np.array(B), np.array(S)
            curves += [dict(config=c, size=s, mode=mode, range=rname, trial=i + 1, q_mean=B[:, i].mean(), q_median=np.median(B[:, i]),
                            q_min=B[:, i].min(), frac_ge95=(B[:, i] >= 0.95).mean(), frac_ge99=(B[:, i] >= 0.99).mean(),
                            cumsec_mean=S[:, i].mean()) for i in range(N_TRIALS)]
    return runs, curves


if __name__ == "__main__":
    t0 = time.time()
    pd.DataFrame(rr).to_csv(OUT / "data" / "search_ranges.csv", index=False, float_format="%.4g")
    with Pool(4) as p:
        res = list(p.imap_unordered(one, list(RANGES)))
    meta = s1.groupby("config").agg(p=("p", "first"), label=("label", "first")).reset_index()
    pd.DataFrame([r for a, _ in res for r in a]).merge(meta, on="config").to_csv(OUT / "data" / "optuna_replay_runs.csv", index=False, float_format="%.5g")
    pd.DataFrame([r for _, b in res for r in b]).merge(meta, on="config").to_csv(OUT / "data" / "optuna_replay_curves.csv", index=False, float_format="%.5g")
    print(f"done {time.time() - t0:.0f}s")
