# CURATION

`scripts/assemble.py` が自動生成する。手で編集しない。

`curation.yaml` に書いた「機械には判断できない取捨選択」を、
raw_data → raw で実際に適用した結果。理由と再計測の方針は
`curation.yaml` と `TODO_REMEASURE.md` にある。


## raw/ に上げなかったもの

| id | 対象 | 当たり | 行数 | since |
|---|---|---|---|---|
| `ryzen7-5800x-qr_sweep-nb404-512-merged` | kind=qr_sweep, node=ryzen, src=['ryzen_size2048_nb404-512_t5_20260901_015640.csv', 'ryzen_size4096_nb404-512_t5_20260901_030638.csv'] | 10 | 15,680 | 2026-09-04 |

- **`ryzen7-5800x-qr_sweep-nb404-512-merged`** — 学部時代データ（nb 32-400、migrate.py 生成、raw_data 上は Ryzen7-5800X_16_{2048,4096}_trial{1-5}.csv）の nb 404-512 の穴を 埋めるために計測したもの。assemble.py は migrate.py 側の元ファイルを 読まないため両者を自動連結できず（TODO_REMEASURE.md 参照）、 2026-09-01 に raw/ 上で手作業により ryzen_size{2048,4096}_t16_nb32-512_{stamp}_r{1-5}.csv へ連結済み。 この raw_data ファイル自体は連結後も残っているので、除外しないと make assemble のたびに単独の nb404-512 トライアルとして raw/ に 復活し、ryzen7-5800x_s1_smt-on の size2048/4096 が「同じ計測を 二重に取り込んでいる」と validate に怒られる（2026-09-04 に発生）。

## 別ファイルの値で置き換えたもの

| id | 対象 | 当たり | 行数 | since |
|---|---|---|---|---|
| `i7-7700-ssrfb-coldstart` | kind=ssrfb, node=i7-7700, size=1024, nb=32, ib=8 | 1 | 1 | 2026-08-30 |
| `ryzen-ssrfb-coldstart` | kind=ssrfb, node=ryzen, size=1024, nb=32, ib=8 | 1 | 1 | 2026-08-30 |

- **`i7-7700-ssrfb-coldstart`** — 走査の1点目だけ Time_sec が周辺の数十〜数百倍に跳ねる コールドスタート性ノイズ（元の値は 0.146 GFlops、周辺は9.8以上）。 該当点のみ手動で5回再計測したところ 10.1〜10.7 GFlops で安定したため、 その算術平均で置き換える。
- **`ryzen-ssrfb-coldstart`** — i7-7700 と同じコールドスタート性ノイズ。該当点のみ手動で10回再計測し、 1回目を除いた9回の算術平均で置き換える。

## 適用のログ

- [i7-7700-ssrfb-coldstart] i7-7700_ssrfb_size1024_nb32-512_th1_t1_20260830_065953.csv r1: 1 行を i7-7700_manual_ssrfb_nb32_ib8.csv の値で置換
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size2048_nb404-512_t5_20260901_015640.csv r1: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size2048_nb404-512_t5_20260901_015640.csv r2: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size2048_nb404-512_t5_20260901_015640.csv r3: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size2048_nb404-512_t5_20260901_015640.csv r4: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size2048_nb404-512_t5_20260901_015640.csv r5: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size4096_nb404-512_t5_20260901_030638.csv r1: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size4096_nb404-512_t5_20260901_030638.csv r2: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size4096_nb404-512_t5_20260901_030638.csv r3: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size4096_nb404-512_t5_20260901_030638.csv r4: 除外（1,568 行）
- [ryzen7-5800x-qr_sweep-nb404-512-merged] ryzen_size4096_nb404-512_t5_20260901_030638.csv r5: 除外（1,568 行）
- [ryzen-ssrfb-coldstart] ryzen_ssrfb_size1024_nb32-512_th1_t1_20260830_081745.csv r1: 1 行を ryzen_manual_ssrfb_nb32_ib8.csv の値で置換
