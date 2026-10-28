# 2026-10-27 第4世代モデルの評価と、E・η のどちらが崩れているかの切り分け

考察（何が分かったか、10-21 の主張のどこを言い直すか、残っていること）は vault にある：
`tileQR_research/chats/2026-10-27_gen4-kernel-term.md`。
ここには、そのノートの数値を出したスクリプト・表・図と、再現手順だけを置く。

- データ：HEAD 3bba712（EPYC 7543 size1024/2048 は 2026-10-27 の再計測に差し替え済み）
- 対象：HT 無効・1ソケットの13構成・57条件。条件表（β・p・実測最適 nb・W/(pD)）は
  `analysis/2026-10-27_epyc-remeasure/s1_smt-off/data/task_a_table.csv` を読む
- 共通層は `analysis/2026-10-21/scripts/common.py`（`TILEQR_SUBSET=s1_smt-off`）を `scripts/common27.py` から読む。どちらにも手は入れていない

## ファイル

| 場所 | 中身 |
|---|---|
| `scripts/gen4_eval.py` | 第4世代（vault の定数 / tileQR_bench の定数 / 57条件で当てはめ直し / 構成単位の LOAO）と、第3世代に m・δ を1つずつ足したもの → `data/gen4_predictions.csv` `gen4_summary.csv` `gen4_constants.csv` |
| `scripts/decompose.py` | E 側（β）だけ / η 側（c, k）だけを、サイズごと・構成ごとに当てはめる → `data/decompose_*.csv` |
| `scripts/eta_eff.py` | 当てはめなしの η_eff = QR GFlops / (p·A_k·E_k(nb))。サイズ間の重なり → `data/eta_eff.csv` `eta_eff_collapse.csv`、`fig_eta_eff.png` |
| `scripts/residual.py` | R = η_eff / η理論 の nb 依存と、M(nb) = 1/(1+(ν/nb)^q) の当てはめ → `data/residual_fit.csv`、`fig_residual_vs_nb.png` |
| `scripts/oracle.py` | E_k·M·η理論 と E_k·η（c, k を構成ごとに自由）の比較 → `data/oracle_predictions.csv` |
| `scripts/fig_model_gap.py` | 実測の QR 曲線に当てはめなしのモデル p·A_k·E_k·η理論 を重ねた図（2026-10-28 ゼミ p.19）。`data/eta_eff.csv` を読む → `fig_model_gap.png` |

A_k と β_k（η_eff の分母）は `common.beta_from_ssrfb()` で1コアの DTSMQR から計算し直した値。予測（argmax）の β は条件表の値で、10-21 と同じ。

## 再現手順

後のスクリプトは前の出力を読むので、この順に流す。

```bash
cd ~/Workspace/tileQR_data/analysis/2026-10-27_gen4-kernel-term
PY=~/Workspace/tileQR_data/.venv/bin/python
$PY scripts/gen4_eval.py && $PY scripts/decompose.py && $PY scripts/eta_eff.py && $PY scripts/residual.py && $PY scripts/oracle.py && $PY scripts/fig_model_gap.py
```
