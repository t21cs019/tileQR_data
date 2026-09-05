# tileQR_data

タイルQR分解（PLASMA dgeqrf）のパラメータチューニング研究における、
**計測データと図の管理**。

散文・方針・TODO は `tileQR_research` にある。ここは数値と、数値から出る図だけを置く。
このリポジトリは **private**。公開前の研究データを含む。

版と、後から理由を思い出せないと困る判断は `docs/CHANGELOG.md` にある。

文中のパスはすべてリポジトリルートからの相対パス。

---

## リポジトリの役割分担

| リポジトリ | 役割 |
|---|---|
| `tileQR_research` | 散文・方針・TODO・研究ログ |
| **`tileQR_data`（ここ）** | 生データ、derived、図の生成 |
| `tileQR_bench` | 計測環境の構築、計測、直後の確認プロット |
| `tileQR_dashboard` | zimaOS 常駐。一覧表示、各サーバへの指示だし |

データと図を同一リポジトリに置くのは、リポジトリをまたぐ配管（環境変数・
submodule・「どのコミットの図か」の記録）を無くすため。同一リポジトリなら
`git log -- figures_final/卒論/fig_xxx.png` を見るだけで出典が分かる。
データが数百MB規模に育ったら分ければよい（今は数MB）。

---

## なぜ git で持つか

計測は AOBA-B / epyc / calc / 自宅マシン群に分散している。git に載せることで
計測マシン側は `git push`、ダッシュボード側は `git pull` だけに収集経路が
一本化する。sweep CSV は1ファイル約100KB（gzip 27KB）で GitHub の制約に対し
3桁の余裕があるため **Git LFS は使わない**。CSV は書き換えない追記型の
成果物なので、git の全バージョン保持が履歴肥大にならない。

---

## 構成

```
tileQR_data/
├── spec/                   宣言層。人が書き、コードが読む入力
│   ├── machines.yaml       アーキテクチャ / 計測構成 / ノードの定義
│   ├── plan.yaml           計測計画。COVERAGE.md の「分母」
│   ├── curation.yaml       raw に上げないもの / 置き換えるもの。理由つき
│   └── running.yaml        いま流している計測。進捗表に ▶ で出る
├── raw_data/{config}/      計測機から回収したままの原本。触らない
│                           ディレクトリ名が計測構成の宣言（spec/machines.yaml の configs）
├── raw/                                                          (自動生成)
│   ├── qr_sweep/{config}/*.csv
│   ├── ssrfb/{node}/*.csv
│   ├── kernel_dtsmqr/{node}/*.csv
│   ├── JOINS.md            連結の出所
│   ├── CURATION.md         除外・置換の適用結果
│   └── ASSEMBLED.txt       前回置いたファイルの台帳。掃除の範囲を決める
├── derived/                                          (自動生成・コミットする)
│   ├── qr_sweep.parquet
│   ├── ssrfb.parquet
│   ├── kernel_dtsmqr.parquet
│   └── optima.csv
├── archive/                パイプラインが読まないデータ
│   ├── attic/              出自が欠けていて昇格できない原本
│   └── quarantine/         計測条件が無効と確定したもの
├── studies/                個別調査の根拠。curation.yaml 等から参照される
├── figures_src/            図の生成コード。1図につきスクリプト1本
├── figures/                探索用の図                        (Git管理外)
├── figures_final/          発表に使った確定版                (コミットする)
│   ├── README.md           figures/ との使い分け
│   └── 卒論/PROVENANCE.md
├── docs/
│   ├── COVERAGE.md         計画に対する進捗                  (自動生成)
│   ├── TODO_REMEASURE.md   再計測が必要な項目
│   ├── CHANGELOG.md        版と、後から理由を思い出せないと困る判断
│   ├── design/             設計判断の詳細（下記「文書の案内」）
│   └── instructions/       作業指示書（完了済みは done/）
├── scripts/
│   ├── assemble.py         raw_data → raw（分割・連結・命名）
│   ├── migrate.py          旧命名 → 新命名への移行
│   ├── ingest.py           raw → derived + docs/COVERAGE.md
│   ├── generate_figures.py 全 config の図を一括生成
│   ├── validate.py         命名規則・スキーマ・machines.yaml の検証
│   └── sync_generated.py   docs/ の一部を tileQR_research へミラー
├── src/tileqr_data/
│   ├── paths.py            パス定義
│   ├── io.py               読み込み層
│   ├── plan.py             計画の読み込みと計測点の数え方
│   ├── curation.py         spec/curation.yaml の適用
│   └── style.py            図のフォント・配色・プリセット
└── Makefile
```

---

## 使い方

```bash
uv sync

make assemble    # raw_data → raw（新しい計測を回収したとき）
make validate    # push 前の健全性チェック
make ingest      # raw → derived + docs/COVERAGE.md
make figures     # figures/ に図を生成（Git 管理外）
make all         # validate → ingest → figures
```

`make assemble` は `raw/qr_sweep` と `raw/ssrfb` を作り直すので `all` には入れない。

---

## 文書の案内

| 知りたいこと | 見る場所 |
|---|---|
| raw_data → raw → derived の組み立て方、命名規則、ディレクトリ＝構成宣言 | `docs/design/data-pipeline.md` |
| 使えないデータの3方式（attic / quarantine / curation.yaml）と判断表 | `docs/design/excluded-data.md` |
| 計測計画・COVERAGE.md の読み方・最適 nb の定義 | `docs/design/coverage-and-plan.md` |
| 図のプリセット・配色・探索用と確定版の使い分け | `docs/design/figures.md` |
| 過去の設計判断とその理由 | `docs/CHANGELOG.md` |
| 再計測が必要な項目 | `docs/TODO_REMEASURE.md` |
| 計画に対する進捗（自動生成） | `docs/COVERAGE.md` |

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
