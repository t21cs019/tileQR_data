# 2026-11-04 反復の畳み方（平均・中央値・最小を捨てた平均）で最適 nb は変わるか

考察（何が分かったか、EPYC の予測のずれとの関係）は vault にある：
`tileQR_research/chats/2026-11-04_trial-aggregation.md`。
ここには、そのノートの数値を出したスクリプトと表、再現手順だけを置く。

- データ：`derived/qr_sweep.parquet`。分析は 2026-11-04（HEAD 276650b）。2026-11-11 に作業ツリーの derived で流し直し、EPYC 3構成の数値が同じことを確かめた
- 対象：`epyc_s1_smt-off`（EPYC 7543）、`aoba-b_s1_smt-off`、`aoba-b_s2_smt-off`（EPYC 7702）
- 比べたモデルの予測は `analysis/2026-10-27_gen4-kernel-term/data/gen4_predictions.csv`（ここでは計算し直していない）

## ファイル

| 場所 | 中身 |
|---|---|
| `scripts/aggregation_compare.py` | 同じ (nb, ib) の trial を5通りに畳み（mean / median / dropmin = 最小を捨てた平均 / trim = 両端を捨てた平均 / max）、それぞれの最適 nb と、平均の曲線で見たその nb の性能比を出す。trial 1本ずつの最適 nb の範囲も出す → `data/aggregation_compare.csv` |
| 同上 | trial ごとの全体の水準（点ごとの平均に対する比の中央値）→ `data/trial_level.csv` |

trial は `source_file` と `rep` の組。AOBA は1ノードで1回なので、ノードが trial になる。
argmax は畳んだ後に「各 nb で ib の最大 → nb の最大」を1回だけ取る。
`kurzak.load_qr_curves()` はノードごとに ib を選んでからノード間で平均するので、AOBA の最適 nb は条件表（`task_a_table.csv`）と少し違う（例：aoba-b_s1 size2048 で 136 と 124）。

## 再現手順

```bash
cd ~/Workspace/tileQR_data
.venv/bin/python analysis/2026-11-04_trial-aggregation/scripts/aggregation_compare.py
```
