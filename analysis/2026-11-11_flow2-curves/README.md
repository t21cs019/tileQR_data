# 2026-11-11 不老・弐と EPYC 2機種の性能曲線（11-11 のゼミのスライド用）

11-11 のゼミの構成案（Vault の `outline/2026-11-11_outline.md` の p.7・p.8）のための図。未コミット。
新しい計測はしていない。

## 図

| ファイル | 中身 |
|---|---|
| `fig_three_epyc.png` | 3機種を横に並べる。左から EPYC 7543（研究室、p = 32）、EPYC 7702（AOBA-B の1ソケット、p = 64）、EPYC 9965（不老・弐、p = 192）。それぞれ size 1024・2048・4096・8192 の4本。横軸 nb、縦軸 GFlops（ib について最大、対数。範囲は機種ごと） |
| `fig_flow2_sizes.png` | 不老・弐だけ。4 size を1枚に（縦軸は線形）。最高から 5% 以内の nb を太い帯で示す |
| `fig_flow2_ratio.png` | 不老・弐で、当てはめなしのモデルが予測した nb の性能比（`scripts/ratio.py`）。c, k は理論値（√7.5、2）と、57条件で当てはめた値（2.590、1.473。`2026-10-27_epyc-remeasure/data/fold_constants57.csv` の ALL 行。不老・弐は当てはめに入っていない）。β = 123.83 |
| `fig_flow2_model_curves.png` | 不老・弐の性能曲線（size ごとに4枚、縦軸は対数）に、当てはめなしのモデルの予測（理論値の c, k と57条件の c, k）を重ねたもの（`scripts/model_curves.py`）。予測の山の高さは実測の最高の、理論値で 19.8・9.0・5.0・3.5 倍、57条件の値で 21.8・9.0・4.8・3.3 倍 |
| `fig_kernel_fit_flow2.png` | `2026-11-11_flow2-dtsmqr-1core/fig_kernel_fit.png` の左半分（不老・弐）だけ（`scripts/crop_kernel.py`） |
| `fig_flow2_qr_ratio.png` | `2026-11-11_flow2-dtsmqr-1core/fig_qr_ratio.png` と同じ中身を、η を使わない表記で描き直したもの（`scripts/qr_ratio.py`） |

## 集計

- **不老・弐**：`analysis/2026-11-10_flow2-sweep-check/scripts/common.py` の `load_all`・`add_baseline` をそのまま使った（report.md の推奨の「速い水準」base）。(nb, ib) ごとに base を GFlops に直し、nb ごとに ib について最大。`fig_three_epyc.png` には、比較用に5回の平均（GFlops の平均を ib について最大）も点線で重ねた
- **EPYC 7543・EPYC 7702**：`derived/qr_sweep.parquet` の `epyc_s1_smt-off`・`aoba-b_s1_smt-off`。(nb, ib) ごとに5本（size ごとに 5 ファイル）の GFlops の平均を取り、nb ごとに ib について最大
- 最高と5% 以内の範囲は `data/peaks.csv`、曲線は `data/curves.csv`

| 系列 | size 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|
| 不老・弐 base：最高 GFlops（5% 以内の nb） | 82.4（152〜212） | 336.2（172〜212） | 978.9（192〜224） | 2049.6（280〜456） |
| 不老・弐 5回の平均 | 71.3（184〜184） | 307.7（172〜224） | 892.1（196〜280） | 2016.6（288〜448） |
| EPYC 7543 5回の平均 | 94.8（64〜104） | 290.7（96〜140） | 566.6（144〜228） | 799.0（216〜440） |
| EPYC 7702 5回の平均 | 62.8（80〜108） | 193.2（92〜152） | 500.0（152〜232） | 868.6（248〜400） |

不老・弐の base の値と範囲は report.md 3節と一致する（82・336・979・2050、152〜212 など）。

## 性能比（`data/ratio.csv`、速い水準）

| c, k | size 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|
| 理論値（√7.5、2） | 2.9%（予測 nb 32） | 1.6%（40） | 3.4%（72） | 24.4%（128） |
| 57条件の値（2.590、1.473） | 2.9%（32） | 3.1%（52） | 6.5%（88） | 36.1%（136） |

実測の最適 nb は 176・208・220・400。理論値の行は RESULT.md 4節（0.03・0.02・0.03・0.24）と一致する。5回の平均を実測にすると、理論値で 2.4・1.4・3.0・20.4%、57条件の値で 2.4・2.6・5.9・23.0%。
`fig_flow2_qr_ratio.png` の実測/予測は RESULT.md 4節の表と、丸めの2か所（4096 の nb 64 が 0.00 と 0.01、8192 の nb 256 が 0.34 と 0.35）を除いて一致する。

## 注意

- **集計の方法が機種で違う。** 不老・弐は 1回の実行に約 13〜15 ms の遅れが約 4 回に 3 回入るので、速い水準を使った。EPYC の2機種は5回の平均。どちらで比べるべきかは未定（report.md 3節）
- EPYC 7543 の5本は、size 1024・2048 が 2026-10-27 の再計測、4096・8192 はそれより前の計測（`derived/` に入っているものをそのまま使った）。EPYC 7543 の計測は `/usr/local/lib` の libplasma で取っている（週次まとめ 11-11）
- EPYC 7702 は5本が5つの別のノード（size 4096 は par014 の2本を含む）
- 機種で1コアの速さも OpenMP のランタイムも違う（EPYC 7543 は libiomp5、不老・弐は libgomp）

## 再現

```bash
cd ~/Workspace/tileQR_data
.venv/bin/python -I analysis/2026-11-11_flow2-curves/scripts/curves.py
.venv/bin/python -I analysis/2026-11-11_flow2-curves/scripts/ratio.py      # curves.py の data/curves.csv を読む
.venv/bin/python -I analysis/2026-11-11_flow2-curves/scripts/qr_ratio.py   # 同上
```
不老・弐の元の CSV（`~/Download/flow/benchmark/`）が要る。
