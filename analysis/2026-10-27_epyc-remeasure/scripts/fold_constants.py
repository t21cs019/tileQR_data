"""
leave-one-architecture-out で gen3 (c, k) を分割ごとに書き出す。

中間発表 p16「並列効率項の決定: c, k のフィッティング」の
「1構成ずつ除外して残り9構成36条件でc,kを推定し直す」を裏づける数値を作る。

**既存のフィット手順は変えない。** c, k は src/tileqr_data/kurzak.py の
fit()/shape() をそのまま使う。gen3 は m=0.5, delta=1.0, ke=0.0 を固定した
特殊ケースとして呼び出すだけで、新しい数式は書かない
(docs/instructions/model-crossval-2026-09-06.md の指示通り)。

**leave-one-architecture-out の交差検証ループ自体は本スクリプトで新規に
追加したものである。** 既存コードの kurzak.loocv() は
leave-one-(config,size)-point-out であり、構成を丸ごと(4サイズとも)抜く
分割ではないため、この用途には使えない (2026-09-08 実装調査で確認、
docs/instructions/fold_constants_investigation_2026-09-08.md 参照)。

**β は測定値として固定する。** c, k と同時最適化しない
(kurzak.fit の beta_fixed 引数を使う)。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from tileqr_data import kurzak  # noqa: E402

SIZES = (1024, 2048, 4096, 8192)

# 指示書 2節の表。ここが唯一の入力で、SSRFB から再推定しない。
CONFIGS = [
    # (表示名, config key, arch key, beta, 物理コア数 p)
    ("EPYC 7702（AOBA-B）", "aoba-b_s1_smt-off", "aoba-b", 186.3, 64),
    ("EPYC 7543", "epyc_s1_smt-off", "epyc-7543", 184.2, 32),
    ("Xeon Silver 4214", "calc_s1_smt-off", "xeon-silver-4214", 111.2, 12),
    ("Core i7-6900K", "dogwood_s1_smt-off", "broadwell-e-i7-6900k", 200.5, 8),
    ("Ryzen 5 7400F", "ryzen5-7400f_s1_smt-off", "zen4-ryzen5-7400f", 76.2, 6),
    ("Core i5-8500", "i5-8500_s1_smt-off", "coffeelake-i5-8500", 170.0, 6),
    ("Core i3-10100", "i3-10100_s1_smt-off", "cometlake-i3-10100", 159.6, 4),
    ("Core i7-7700", "i7-7700_s1_smt-off", "kabylake-i7-7700", 169.5, 4),
    ("Core i5-7400", "i5-7400_s1_smt-off", "kabylake-i5-7400", 160.5, 4),
    ("Core i3-7100", "i3-7100_s1_smt-off", "kabylake-i3-7100", 139.8, 2),
]

GEN3_FIXED = {"m": 0.5, "delta": 1.0, "ke": 0.0}


def load_target_df():
    """40条件 (10構成 x 4サイズ) だけを含む DataFrame を返す。"""
    machines = kurzak.io.load_machines()
    df = kurzak.load_qr_curves(exclude_config=(), exclude_points=())
    keep_configs = {c[1] for c in CONFIGS}
    df = df[df["config"].isin(keep_configs) & df["size"].isin(SIZES)].reset_index(drop=True)

    for _, cfgkey, archkey, _, p_expect in CONFIGS:
        sub = df[df["config"] == cfgkey]
        if sub.empty:
            raise SystemExit(f"config '{cfgkey}' のデータが0件。machines.yaml のキーを確認せよ。")
        got_sizes = sorted(sub["size"].unique())
        if list(got_sizes) != list(SIZES):
            raise SystemExit(f"{cfgkey}: サイズが4種そろっていない -> {got_sizes}")
        p_got = kurzak.physical_cores(cfgkey, machines)
        if abs(p_got - p_expect) > 1e-9:
            raise SystemExit(f"{cfgkey}: p が食い違う (machines.yaml={p_got}, 指示書={p_expect})")
        arch_got = machines["configs"][cfgkey]["arch"]
        if arch_got != archkey:
            raise SystemExit(f"{cfgkey}: arch が食い違う (machines.yaml={arch_got}, 期待={archkey})")

    n = len(df.groupby("g"))
    if n != 40:
        raise SystemExit(f"条件数が40でない: {n}")
    return df


def fit_gen3(df, beta_by_arch):
    r = kurzak.fit(df, fixed=GEN3_FIXED, beta_fixed=beta_by_arch)
    return r["c2"], r["kappa"], r


def main():
    df = load_target_df()
    beta_by_arch = {arch: beta for _, _, arch, beta, _ in CONFIGS}
    obs = kurzak.observed(df)
    pmap = df.groupby("config")["p"].first().to_dict()

    c_all, k_all, r_all = fit_gen3(df, beta_by_arch)

    rows = []
    for label, cfgkey, archkey, beta, p in CONFIGS:
        train = df[df["config"] != cfgkey]
        c, k, r = fit_gen3(train, beta_by_arch)
        theta = r["theta"]

        perfs, relerrs = [], []
        for size in SIZES:
            g = (cfgkey, size)
            e = kurzak.evaluate(theta, {cfgkey: beta}, obs, g, p)
            perfs.append(e["perf"])
            relerrs.append(e["nb_relerr"])

        rows.append(dict(
            held_out_config=label,
            held_out_cores=p,
            n_train_conditions=len(train.groupby("g")),
            c=c,
            k=k,
            c_dev_pct=(c - c_all) / c_all * 100.0,
            k_dev_pct=(k - k_all) / k_all * 100.0,
            perf_ratio_mean=float(np.mean(perfs)),
            perf_ratio_min=float(np.min(perfs)),
            nb_rel_err_mean=float(np.mean(relerrs)) * 100.0,
        ))

    rows.append(dict(
        held_out_config="ALL",
        held_out_cores=np.nan,
        n_train_conditions=len(df.groupby("g")),
        c=c_all,
        k=k_all,
        c_dev_pct=0.0,
        k_dev_pct=0.0,
        perf_ratio_mean=np.nan,
        perf_ratio_min=np.nan,
        nb_rel_err_mean=np.nan,
    ))

    out = pd.DataFrame(rows)
    # 2026-10-27: derived/ を上書きせず、この分析のフォルダに書く
    out_path = Path(__file__).resolve().parents[1] / "data" / "fold_constants.csv"
    out.to_csv(out_path, index=False, float_format="%.6g", encoding="utf-8")

    fold_rows = out[out["held_out_config"] != "ALL"]
    c_vals = fold_rows["c"].to_numpy()
    k_vals = fold_rows["k"].to_numpy()

    def cv_pct(x):
        return float(np.std(x, ddof=1) / np.mean(x) * 100.0)

    worst_c = fold_rows.loc[fold_rows["c_dev_pct"].abs().idxmax()]
    worst_k = fold_rows.loc[fold_rows["k_dev_pct"].abs().idxmax()]

    print(f"ALL fit (40 conditions): c={c_all:.4f}, k={k_all:.4f}, rms={r_all['rms']:.4f}")
    print(f"c range: {c_vals.min():.4f} - {c_vals.max():.4f}  (CV = {cv_pct(c_vals):.2f}%)")
    print(f"k range: {k_vals.min():.4f} - {k_vals.max():.4f}  (CV = {cv_pct(k_vals):.2f}%)")
    print(f"largest |c_dev_pct|: {worst_c['held_out_config']} ({worst_c['c_dev_pct']:+.2f}%)")
    print(f"largest |k_dev_pct|: {worst_k['held_out_config']} ({worst_k['k_dev_pct']:+.2f}%)")
    print(f"perf_ratio_mean averaged over 10 folds: {fold_rows['perf_ratio_mean'].mean()*100:.1f}%")
    print(f"perf_ratio_min overall: {fold_rows['perf_ratio_min'].min()*100:.1f}%  "
          f"at {fold_rows.loc[fold_rows['perf_ratio_min'].idxmin(), 'held_out_config']}")
    print(f"nb_rel_err_mean overall: {fold_rows['nb_rel_err_mean'].mean():.1f}%")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
