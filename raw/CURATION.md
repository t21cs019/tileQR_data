# CURATION

`scripts/assemble.py` が自動生成する。手で編集しない。

`curation.yaml` に書いた「機械には判断できない取捨選択」を、
raw_data → raw で実際に適用した結果。理由と再計測の方針は
`curation.yaml` と `TODO_REMEASURE.md` にある。


## raw/ に上げなかったもの

| id | 対象 | 当たり | 行数 | since |
|---|---|---|---|---|
| `i5-7400-qr_sweep-thermal` | kind=qr_sweep, node=i5-7400 | 20 | 64,555 | 2026-09-01 |
| `i5-7400-ssrfb-threads` | kind=ssrfb, node=i5-7400 | 4 | 12,911 | 2026-09-01 |

- **`i5-7400-qr_sweep-thermal`** — サーマルスロットリングによる汚染が確定。size 1024/2048/4096/8192 の 4条件すべてが対象。冷却が保てていない状態で連続走査したため、 走査の後半ほど周波数が落ちている。GFlops の絶対値だけでなく nb 方向の形が歪むので、最適 nb の主張には使えない。
- **`i5-7400-ssrfb-threads`** — threads=4 で計測されているが、ssrfb は他の全ノード（calc / dogwood / epyc / i3-10100 / i5-8500 / i7-7700 / ryzen / ryzen5-7400f）を threads=1 で測っている。カーネル単体の効率 beta を機種間で比べるのが この測定の目的なので、1台だけスレッド数が違うと比較にならない。 plan.yaml の i5-7400 が threads: 4 になっていたのは、この計測に 合わせて後から書いたもので、計画側が間違っていた。

## 別ファイルの値で置き換えたもの

| id | 対象 | 当たり | 行数 | since |
|---|---|---|---|---|
| `i7-7700-ssrfb-coldstart` | kind=ssrfb, node=i7-7700, size=1024, nb=32, ib=8 | 1 | 1 | 2026-08-30 |
| `ryzen-ssrfb-coldstart` | kind=ssrfb, node=ryzen, size=1024, nb=32, ib=8 | 1 | 1 | 2026-08-30 |

- **`i7-7700-ssrfb-coldstart`** — 走査の1点目だけ Time_sec が周辺の数十〜数百倍に跳ねる コールドスタート性ノイズ（元の値は 0.146 GFlops、周辺は9.8以上）。 該当点のみ手動で5回再計測したところ 10.1〜10.7 GFlops で安定したため、 その算術平均で置き換える。
- **`ryzen-ssrfb-coldstart`** — i7-7700 と同じコールドスタート性ノイズ。該当点のみ手動で10回再計測し、 1回目を除いた9回の算術平均で置き換える。

## 適用のログ

- [ryzen-ssrfb-coldstart] ryzen_ssrfb_size1024_nb32-512_th1_t1_20260830_081745.csv r1: 1 行を ryzen_manual_ssrfb_nb32_ib8.csv の値で置換
- [i5-7400-qr_sweep-thermal] i5-7400_size1024_nb32-512_t5_20260624_104705.csv r1: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size1024_nb32-512_t5_20260624_104705.csv r2: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size1024_nb32-512_t5_20260624_104705.csv r3: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size1024_nb32-512_t5_20260624_104705.csv r4: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size1024_nb32-512_t5_20260624_104705.csv r5: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size2048_nb32-512_t5_20260624_114156.csv r1: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size2048_nb32-512_t5_20260624_114156.csv r2: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size2048_nb32-512_t5_20260624_114156.csv r3: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size2048_nb32-512_t5_20260624_114156.csv r4: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size2048_nb32-512_t5_20260624_114156.csv r5: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size4096_nb32-512_t5_20260624_162515.csv r1: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size4096_nb32-512_t5_20260624_162515.csv r2: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size4096_nb32-512_t5_20260624_162515.csv r3: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size4096_nb32-512_t5_20260624_162515.csv r4: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size4096_nb32-512_t5_20260624_162515.csv r5: 除外（3,963 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size8192_nb32-512_t5_20260630_003200.csv r1: 除外（1,022 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size8192_nb32-512_t5_20260630_003200.csv r2: 除外（1,022 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size8192_nb32-512_t5_20260630_003200.csv r3: 除外（1,022 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size8192_nb32-512_t5_20260630_003200.csv r4: 除外（1,022 行）
- [i5-7400-qr_sweep-thermal] i5-7400_size8192_nb32-512_t5_20260630_003200.csv r5: 除外（1,022 行）
- [i5-7400-ssrfb-threads] i5-7400_ssrfb_size1024_nb32-512_th4_t1_20260801_154757.csv r1: 除外（3,963 行）
- [i5-7400-ssrfb-threads] i5-7400_ssrfb_size2048_nb32-512_th4_t1_20260801_160558.csv r1: 除外（3,963 行）
- [i5-7400-ssrfb-threads] i5-7400_ssrfb_size4096_nb32-512_th4_t1_20260801_165117.csv r1: 除外（3,963 行）
- [i5-7400-ssrfb-threads] i5-7400_ssrfb_size8192_nb32-512_th4_t1_20260801_192452.csv r1: 除外（1,022 行）
- [i7-7700-ssrfb-coldstart] i7-7700_ssrfb_size1024_nb32-512_th1_t1_20260830_065953.csv r1: 1 行を i7-7700_manual_ssrfb_nb32_ib8.csv の値で置換
