# 2026-10-27 EPYC 7543 size1024/2048 の差し替えと、2026-10-21 の分析のやり直し

考察（何が分かったか、10-21 の主張のどこを言い直すか、残っていること）は vault にある：
`tileQR_research/chats/2026-10-27_dtsmqr-parallel-epyc-remeasure.md`。
ここには、そのノートの数値を出したスクリプト・表・図と、再現手順だけを置く。

- データ：HEAD df882a5 に、EPYC 7543 size1024/2048 の差し替え（7月のファイルを
  `archive/quarantine/epyc_size1024-2048_slow_2026-07/` へ退避し、2026-10-27 の再計測を `raw/` へ）を加えたもの
- 対象：HT 無効・1ソケットの13構成（`TILEQR_SUBSET=s1_smt-off`）。HT 有効・2ソケットの構成は使っていない
- `analysis/2026-10-21/` には手を入れていない。`scripts/` はその複製で、出力先だけがここになる

## ファイル

| 場所 | 中身 |
|---|---|
| `scripts/task_a.py` `task_c.py` `loao_subset.py` | 10-21 と同じ分析（崩れる条件、η の別式、LOAO）。出力は `s1_smt-off/` |
| `scripts/compare_1021.py` | 10-21 と今回の主要な数字を並べる → `s1_smt-off/data/compare_1021.csv` |
| `scripts/fold_constants.py` | 中間発表の定数（40条件）の当てはめ直し → `data/fold_constants.csv`（`derived/` は上書きしない） |
| `scripts/ssrfb_par_compare.py` | DTSMQR の既存1コア / p=1 / p=32 の比較 → `data/ssrfb_par_compare.log` |
| `figures/fig_epyc_old_vs_new.py` | EPYC 7543 の nb–GFlops（7月と再計測） → `figures/fig_epyc_old_vs_new.png` |
| `overhead/` | DAG シミュレーション（`sched_ovh.c`）に o, L を足して QR の実測時間に合わせる。`run_sim.py` → `sim.csv`、`analyze.py` → `fit_summary.csv`、`analyze.log` |
| `data/ssrfb_par/` | DTSMQR の同時実行計測（plasma-bench `feat/ssrfb-parallel`、EPYC 7543、size1024、p=1 と p=32）。ingest の対象外なのでここに置く |
| `data/sched_*.txt` | DAG のスケジューリング結果（データに依らない）。`analysis/2026-10-21/data/` の複製 |

`overhead/sim.csv`（13 MB）はコミットしていない。`run_sim.py` で1分ほどで作り直せる。

## 再現手順

```bash
cd ~/Workspace/tileQR_data/analysis/2026-10-27_epyc-remeasure/scripts
export TILEQR_SUBSET=s1_smt-off
PY=~/Workspace/tileQR_data/.venv/bin/python
$PY task_a.py && $PY task_c.py && $PY loao_subset.py && $PY compare_1021.py
$PY fold_constants.py
$PY ssrfb_par_compare.py > ../data/ssrfb_par_compare.log
$PY ../figures/fig_epyc_old_vs_new.py

cd ../overhead
gcc -O2 -o sched_ovh sched_ovh.c -lm
$PY run_sim.py && $PY analyze.py > analyze.log
```
