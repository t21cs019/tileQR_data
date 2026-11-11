# 2026-11-10 タスク1個ごとの直列の時間 τ と、スレッド固定の A/B テストの読み直し

考察（何が分かったか、どこが推測か、確かめ方）は vault にある：
`tileQR_research/chats/2026-11-10_serial-task-cost.md`。
ここには、そのノートの数値を出したスクリプト・表・図と、再現手順だけを置く。

- データ：HEAD 276650b。QR の曲線と A_k・β_k は `analysis/2026-10-27_gen4-kernel-term/data/eta_eff.csv` を読む（HT 無効・1ソケットの13構成・57条件）
- スレッド固定の A/B テストの元のファイルは、まだ tileQR_data に入っていない（`~/Download/flow/flow_bind-ab_20261031_082853/`、`~/Download/aoba/flow_bind-ab_20261101_163609/`、`~/Download/ab_epyc7543.log`）。`collect_bind_ab.py` が全点を `data/bind_ab_points.csv` に写すので、後のスクリプトは元のファイルがなくても流せる

## ファイル

| 場所 | 中身 |
|---|---|
| `scripts/serial_tau.py` | 当てはめなしのモデルに「タスク数 × τ」を足す。τ と一様な係数 r0 を構成ごとに当てはめる（インサンプル）→ `data/tau_fit.csv`（τ、r0）、`data/tau_predictions.csv`（予測 nb と性能比）、`data/per_task_time.csv`（各点の、タスク1個あたりの時間と、モデルより余分な時間） |
| `scripts/common10.py` | 共通層。1ソケット・SMT 無効の57条件（`eta_eff.csv`）と、全構成（`derived/qr_sweep.parquet`。2ソケット、SMT 有効を含む）の読み込み |
| `scripts/hypotheses.py` | 原因の候補ごとの式（タスク数、タスク数 × nb²、クリティカルパス D、N²、size²）を1項ずつ足して比べる → `data/hypotheses_fit.csv`（係数と誤差）、`data/hypotheses_perf.csv`（予測 nb と性能比） |
| `scripts/tau_universal.py` | τ = a·p と置き、a を1機種ずつ抜いて当てはめる（LOAO）。2ソケットの構成（当てはめに不使用）も予測する → `data/tau_universal.csv` |
| `scripts/same_machine.py` | 同じ機械の1ソケットと2ソケット、SMT 無効と有効の比較 → `data/same_machine.csv`、`fig_same_machine.png` |
| `scripts/collect_bind_ab.py` | A/B テスト3機種の全点を1つの表にする → `data/bind_ab_points.csv` |
| `scripts/bind_ab_time.py` | A/B テストの GFlops を実行時間に直す。固定なしで増える時間、タスク1個あたりの時間 → `data/bind_ab_time.csv` |
| `scripts/fig_gflops_vs_p.py` | 同じ nb でのコア数と GFlops の関係 → `fig_gflops_vs_p.png`、`data/gflops_vs_p.csv` |

## 式

```
時間 = W / (r0 · p·A_k·E_k(nb)·η理論(nb)) + タスク数 · τ
W = 4/3·size³、タスク数 = N³/3 + N²/2（N = size/nb）
性能に直すと 1/G = 1/(r0·G_model) + τ/(4·nb³)
```

A/B テストのタスク数は N = ceil(size/nb) として Σk² で数えている（`bind_ab_time.py`）。

## 注意

- `fig_gflops_vs_p.png` の p = 192（不老・弐）は A/B テストの「固定あり」で、ib = 32 だけ。ほかの機種は ib を振った中の最高。機種で1コアの速さも違うので、線の傾きは目安
- τ と r0 は QR の実測から当てはめた値。QR 以外の計測から決めたものではない
- `serial_tau.py` と `hypotheses.py` は構成ごとの当てはめ（インサンプル）。交差検証は `tau_universal.py` だけ
- 2ソケット・SMT 有効の構成の G は、`derived/qr_sweep.parquet` を (nb, ib) ごとに平均し、ib について最高を取ったもの。A_k・β_k は同じ機械の1ソケットの値

## 再現手順

```bash
cd ~/Workspace/tileQR_data/analysis/2026-11-10_serial-task-cost
PY=~/Workspace/tileQR_data/.venv/bin/python
$PY scripts/serial_tau.py
$PY scripts/hypotheses.py && $PY scripts/tau_universal.py && $PY scripts/same_machine.py
$PY scripts/collect_bind_ab.py && $PY scripts/bind_ab_time.py   # collect は ~/Download に元のファイルがあるときだけ
$PY scripts/fig_gflops_vs_p.py
```
