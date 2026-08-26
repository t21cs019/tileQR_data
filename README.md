# tileQR_data

タイルQR分解（PLASMA dgeqrf）のパラメータチューニング研究における、
**計測データと図の管理**。

散文・方針・TODO は `tileQR_research` にある。ここは数値と、数値から出る図だけを置く。
このリポジトリは **private**。公開前の研究データを含む。

---

## リポジトリの役割分担

| リポジトリ | 役割 |
|---|---|
| `tileQR_research` | 散文・方針・TODO・研究ログ |
| **`tileQR_data`（ここ）** | 生データ、derived、図の生成 |
| `tileQR_bench` | 計測環境の構築、計測、直後の確認プロット |
| `tileQR_dashboard` | zimaOS 常駐。一覧表示、各サーバへの指示だし |

### なぜデータと図を同じリポジトリにするか

図の生成を別リポジトリにすると、**リポジトリをまたぐための配管**が必要になる。
環境変数によるデータ場所の解決、submodule の更新、
「この図はどのデータコミットから作ったか」の記録。これらが全部いらなくなる。

同一リポジトリなら図とデータが同じコミットに入るので、
出典は `git log -- out/fig_xxx.png` を見るだけで分かる。

データが数百 MB 規模に育って「図を書くだけなのに clone が重い」となったら、
その時点で分ければよい。今の規模（数 MB）では統合side が明らかに楽。

---

## なぜ git で持つか

計測は AOBA-B / epyc / calc / 自宅マシン群に分散している。従来は rclone / rsync / scp で
その都度手作業で集めていたが、git に載せると

- 計測マシン側は `git push` するだけ
- ダッシュボード（zimaOS）側は `git pull` するだけ

に収集経路が一本化する。sweep CSV は1ファイル約 100KB、gzip で 27KB。
GitHub の制約（1ファイル 100MB、リポジトリ 1GB 推奨）に対して3桁の余裕があるため、
**Git LFS は使わない**。

CSV は一度書いたら書き換えない追記型の成果物なので、
git の「全バージョンを保持する」性質が履歴肥大の問題にならない。

---

## 構成

```
tileQR_data/
├── machines.yaml       # アーキテクチャ / 計測構成 / ノードの定義
├── raw/                # 計測の生データ。原則として書き換えない
│   ├── qr_sweep/{config}/*.csv
│   └── kernel_dtsmqr/{node}/*.csv
├── derived/            # ingest.py が生成。コミットする
│   ├── qr_sweep.parquet
│   ├── kernel_dtsmqr.parquet
│   └── optima.csv
├── figures/            # 図1つにつきスクリプト1本
├── out/                # 生成した図。コミットする
├── scripts/
│   ├── migrate.py      # 旧命名 → 新命名への移行
│   ├── ingest.py       # raw → derived
│   └── validate.py     # 命名規則・スキーマの検証
├── src/tileqr_data/
│   ├── paths.py        # パス定義
│   ├── io.py           # 読み込み層
│   └── style.py        # 図のフォント・配色・プリセット
├── COVERAGE.md         # ingest.py が自動生成。手で編集しない
└── Makefile
```

### 測定種別を第一階層で分ける理由

`qr_sweep` と `kernel_dtsmqr` は **スキーマが完全に同一**（`threads,size,nb,ib,GFlops`）で、
データの中身からは区別できない。全体QR分解の測定かカーネル単体の測定かは
置き場所でしか担保できないため、混ぜてはいけない。

走査範囲も違う。qr_sweep は nb=20 から、kernel_dtsmqr は nb=4 から。

---

## 使い方

```bash
uv sync

make validate    # push 前の健全性チェック
make ingest      # raw → derived + COVERAGE.md
make figures     # out/ に図を生成
make all         # 上3つ
```

---

## 命名規則

```
{node}_size{N}_t{threads}_nb{lo}-{hi}_{YYYYMMDD-HHMMSS}.csv
```

例: `par001_size4096_t128_nb20-512_20260607-235252.csv`

| 要素 | 意味 |
|---|---|
| `node` | 物理ノード名。`machines.yaml` の `nodes` に定義があること |
| `size` | 行列サイズ N |
| `threads` | **実際に使用したスレッド数**。CSV の中身と必ず一致させる |
| `nb{lo}-{hi}` | nb の走査範囲 |
| タイムスタンプ | 日付と時刻をハイフンで区切る |

### 旧命名からの変更点

旧: `par001_size4096_nb20512_t1_20260607_235252.csv`

1. **`t1` はスレッド数ではなかった。** タイムスタンプ違いの同一条件に見えるファイルが、
   実際には 128 スレッドと 64 スレッドで別条件だった。ファイル名に明示する。
2. **`nb20512` が曖昧。** 20-512 とも 205-12 とも読める。ハイフンで区切る。
3. **日付と時刻の区切りが不明瞭。**

`scripts/validate.py` がファイル名と中身の一致を検査するので、この事故は再発しない。

---

## 計測構成をディレクトリで表す（qr_sweep のみ）

`raw/qr_sweep/` 直下のディレクトリ名は計測構成の識別子。

```
{arch}_s{sockets_used}_smt-{on|off}
```

CSV ごとにサイドカーの meta ファイルを置くと、同一条件のファイルが何十個も並ぶ
本研究では同じ内容を複製し続けることになる。そこで
**変わらない軸はディレクトリに畳み、詳細は `machines.yaml` の `configs` に1エントリだけ書く**。
メタデータの実体は「構成の数」だけで済み、CSV が増えても増えない。

### `sockets_used` の定義（重要）

物理搭載ソケット数ではなく、**実際に使用したソケット数**。

AOBA-B は物理的には 2 ソケット 128 コアだが、64 スレッド実行時は
`numactl --cpunodebind=0 --membind=0` で片ソケットに固定している。この場合は `s1`。
L3 の共有単位（shared-tile cache model の `C_unit`）が変わる以上、
モデル上意味を持つのは使用ソケット数の方であるため。

### 必ず記録する交絡要因

「メモリチャネル構成が GFlops だけでなく最適 nb そのものを変える」
「ターボの有無で再現性が崩れる」ことが分かっている。`configs` に必ず書く。

`memory_channels` / `turbo` / `numactl` / `smt`。

---

## 最適 nb の定義はここだけが持つ

`scripts/ingest.py` が `derived/optima.csv` を生成する。
**図もダッシュボードも `derived/` を読むだけ**にすること。

3者（bench の確認プロット、dashboard、figures）が本当に重複しやすいのは
描画ではなく「全 sweep を読んで最適 nb を求める」部分。ここが複数箇所にあると、
片方だけ直したときに数値が食い違う。研究の主張そのものが最適 nb なので危険。

定義を変えたいときは `ingest.py` を直す。それだけで全部に伝播する。

`optima.csv` の列:

| 列 | 意味 |
|---|---|
| `nb_opt`, `ib_opt` | ピークを与える nb, ib |
| `GFlops_max` | ピーク性能 |
| `nb_lo95`, `nb_hi95` | ピークの 95% 以上を満たす nb の**連続区間** |
| `nb_scanned_lo/hi`, `n_nb` | 走査範囲（帯が範囲端で切れていないかの確認用） |

---

## 図

### プリセット

| | slide | paper |
|---|---|---|
| フォント | 游ゴシック系 | セリフ寄り |
| 文字サイズ | 14pt | 10pt |
| サイズ | 8.0 × 4.5 in（16:9） | 5.5 × 3.4 in |
| 出力 | PNG（300dpi） | PDF + SVG |

スライドは pptxgenjs でデッキを組む前提なので PNG 高DPI。

### 日本語フォント

`style.use()` が候補を優先順に探し、見つからなければ**警告を出す**。
豆腐（□□□）に気づかないまま発表資料を作るのを防ぐため、警告は無視しないこと。

### 配色

構成ごとの色は `style.CONFIG_COLORS` で固定する。
資料間で同じ構成の色が入れ替わると読者が混乱するため。

### 図は1ファイル1図

スクリプト名と出力名を一致させる（`fig_nb_curve_aoba.py` → `out/fig_nb_curve_aoba.png`）。

---

## derived/ と out/ をコミットする理由

どちらも生成物だが、

- `derived/` … ダッシュボードが `git pull` 直後に読める
- `out/` … `tileQR_research` の散文から図を参照でき、資料を組み直すときに再計算がいらない

ため、コミットする。合計で数 MB 程度なので履歴肥大の心配はない。

---

## 運用

### 計測マシン側

```bash
make validate
git add raw/qr_sweep/aoba-b_s2_smt-off/
git commit -m "add: aoba-b s2 size4096 sweep (par005)"
git push
```

### ダッシュボード側（zimaOS）

`git pull` → `derived/*.parquet` を読む。ingest は不要（コミット済みのため）。

### 節目のスナップショット

中間発表や論文投稿の時点で GitHub Releases に tar.gz を固定し、
「発表時の数値はどのデータか」を辿れるようにする。
`tileQR_research` のタグ運用（例: `2026-W24`）と対応させる。
