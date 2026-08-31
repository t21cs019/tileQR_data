# attic — 出自が欠けていて raw/ に上げられない原本

学部時代の計測を中心に、**捨てはしないがパイプラインは読まない**原本の置き場。

`raw_data/` に置かないのは、あちらが「全ディレクトリが構成名 =
パイプラインの入力」という不変条件を持つため。ここに置いたものは
`assemble.py` も `validate.py` も一切読まない（コード側に例外は無い。
単にどのスクリプトもこのディレクトリを見ないだけ）。

## なぜ捨てないか

条件さえ判明すれば使えるデータが混ざっているため。実際、`amd_ryzen/` の
threads=16 のファイルは `migrate.py` 経由で `raw/qr_sweep/ryzen7-5800x_s1_smt-on/`
に取り込み済みで、いまの研究データの一部になっている。

## 昇格の基準

`raw/` に上げるには計測構成（threads / SMT / ソケット / メモリ構成）が
要る。この判定には原則がある:

- **threads > 物理コア数 なら、smt-on はスレッド数だけから証明できる**
  （例: 4コアの i3-10100 で th=8）。
- 逆は証明できない。th=4 は「SMT 無効」とも「SMT 有効のまま4スレッド」とも
  取れる。当時の BIOS 設定の記録が無い限り不明のまま。
- smt が証明できても、**メモリチャネル構成・ターボ・当時の PLASMA ビルド**の
  記録は無い。i5-7400 で「形状は健全に見えるが裏付けが無いので落とす」とした
  基準（`studies/i5-7400_memory_channel/`）に照らすと、
  ここのデータは研究の主張には使えず、使うなら参考扱いに留める。

昇格させる場合は `TODO_REMEASURE.md` で議論し、`migrate.py` 系の成形を
経て入れること。**このディレクトリ内のファイルは改名も編集もしない**（原本）。

## 目録

### Full_search/ — 学部時代のフルスイープ一式（6機種）

各機種とも `raw_data/`（生CSV）、`select_data/`（当時選別したもの）、
`graph/` `heatmap/`（当時の図 PNG）を持つ。

| ディレクトリ | CPU | threads | 備考 |
|---|---|---|---|
| `amd_ryzen/` | Ryzen 7 5800X (8C/16T) | 16, 8, 4 | **th16 の size2048/4096 は取り込み済み**（migrate.py → `ryzen7-5800x_s1_smt-on`）。th16 は smt-on 証明可。th8/th4 は SMT 状態不明。size8192 あり |
| `intel_corei7_7700/` | i7-7700 (4C/8T) | 8, 4 | th8 は smt-on 証明可。`size=4069` は 4096 の typo（ディレクトリ名のみ。中身は要確認） |
| `intel_corei3_10100/` | i3-10100 (4C/8T) | 8, 4 | th8 は smt-on 証明可。th4 相当は 2026 年に `i3-10100_s1_smt-off` として計測し直し済み |
| `intel_corei5_13400F/` | i5-13400F (6P+4E) | 10, 16 | nb=4 始まり。kernel_dtsmqr 系かフルスイープか要確認。P/E 混在の注意は machines.yaml 参照 |
| `KKI/` | **i7-12700T (8P+4E/20T)** | 12, 14, 20 | machines.yaml 未登録のマシン。th20 は smt-on 証明可 |
| `intel_corei5_1135G7/` | **i5-1135G7 (Tiger Lake)** | 8, 4 | machines.yaml 未登録のラップトップ。`size=4069` typo あり |

### Full_search_dgeqrf/ — dogwood (i7-6900K) の dgeqrf フルスイープ

`benchmark_dtsmqr_4096.csv`（名前は当時のスクリプトのハードコード誤記。
実体は dgeqrf）と、それを生成した `Full_search_dgeqrf.py`。

スクリプトはスレッド数を一切指定しておらず（`OMP_NUM_THREADS` も
`--threads` も無し）、当時の環境デフォルトで走った。**スレッド数は
スクリプトからも CSV（threads 列なし）からも復元できない。**

2026-08-30 の dogwood th=8 実測との突き合わせによる推定は
`studies/full_search_threads/` にある（参考情報。主張には使わない）。
