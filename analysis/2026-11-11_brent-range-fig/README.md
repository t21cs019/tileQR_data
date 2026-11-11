# 2026-11-11 Brent の上限・下限で作る探索範囲 B の図（研究室の EPYC 7543）

11-11 のゼミのスライド（構成案 p.15）用の図。未コミット。新しい計測も、新しい計算の方法もない。
`analysis/2026-11-10_brent-search-range/scripts/range_two_ways.py` の範囲 B と同じ式を、同じデータに当てて描いた。

- `fig_range_epyc7543.png`：EPYC 7543（p = 32）、size 1024・2048・4096・8192。横軸 nb、縦軸 GFlops
  - タイル QR の性能（実測）：`2026-10-27_gen4-kernel-term/data/eta_eff.csv` の G（5回の平均、ib について最大）
  - 時間の上限での予測（いまのモデル）：p·A_k·E_カーネル·1/(1 + y)
  - 時間の下限での予測：p·A_k·E_カーネル·min(1, 1/y)
  - y = p·D/W（W = 4N³、D = 30N − 28、N = size/nb）、E_カーネル = nb/(nb + β_k)。A_k・β_k は1コアの DTSMQR
  - 範囲 B（網かけ）：下限での予測が、上限での予測の最大（点線）以上になる nb
- `fig_range_epyc7543_time.png`：同じものを縦軸の計算時間（ms、対数）で描いた版。時間 ＝ 4/3·size³ ÷ 性能。範囲 B は「時間の下限が、時間の上限の最小（点線）以下になる nb」で、定義の式のとおりに見える
- `data/range_epyc7543.csv`：size ごとの範囲。`search_ranges.csv` の B の lo・hi と一致することを assert で確かめた

| size | 範囲 B | 実測の最適 nb | 残す nb の割合 |
|---|---|---|---|
| 1024 | 32〜116 | 96 | 18% |
| 2048 | 56〜212 | 108 | 33% |
| 4096 | 100〜388 | 168 | 60% |
| 8192 | 168〜512 | 304 | 72% |

注意：予測の線の高さは A_k の絶対水準に依存する（r0 = 0.71〜1.18）。範囲 B は線の高さの比だけで決まるので、A_k には依存しない。
EPYC 7543 の計測は `/usr/local/lib` の libplasma で取っている。

再現：`cd ~/Workspace/tileQR_data && .venv/bin/python -I analysis/2026-11-11_brent-range-fig/scripts/fig_range.py`
