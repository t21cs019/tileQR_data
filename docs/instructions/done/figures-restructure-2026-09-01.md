# 指示書：tileQR_data の図ディレクトリ再編

> 完了済み。文中のパスは作業当時のもの（2026-09-05 の構成整理より前）。

## 背景

`tileQR_data` は数値データ・derived outputs・図を保持する正規リポジトリ。
現在、図の管理方針が定まっていないため、Git履歴の肥大化を防ぐ構成に再編したい。

図には性質の異なる2種類がある。

- **探索用の図**：解析のたびに大量に再生成される。parquet + 生成コードから常に再現可能
- **発表用の図**：中間発表・論文などに実際に使った確定版。再現性の担保が必要

前者をGit管理外に、後者のみをコミット対象にする。

## 完了条件

以下がすべて満たされていること。

1. `figures/` が存在し、`.gitignore` によってGit管理外になっている
2. `figures_final/` が存在し、発表単位のサブディレクトリで管理されている
3. 図生成スクリプトのデフォルト出力先が `figures/` になっている
4. 命名規則・運用方法が README に記載されている
5. 既存のコミット済み図があれば適切に移行されている
6. `generate_figures.py` が実装され、データ追加のたびに全図を再生成できる
7. ヒートマップが (config, size) 単位、nbスイープ図が config × 集約方法 単位で生成される
8. 中央値集約と平均集約の両方で図が生成され、比較表 CSV が出力される

---

## タスク1：ディレクトリ構成の作成

リポジトリルート直下に以下を作成する。

```
tileQR_data/
├── figures/                 # Git管理外（探索用・使い捨て）
│   └── .gitkeep
└── figures_final/           # コミット対象（発表用・確定版）
    ├── README.md
    └── 卒論/
        └── PROVENANCE.md
```

- `figures/.gitkeep` は空ファイルとして作成し、**`.gitignore` の例外として明示的にトラックする**（ディレクトリ自体は存在させたいため）
- `figures_final/` 直下のサブディレクトリ名は発表・成果物の単位。初期状態では `卒論/` のみ作成し、他は必要になった時点で追加する

想定するサブディレクトリの例：

- `卒論/`
- `中間発表/`
- `修論/`
- `ゼミ/`

## タスク2：.gitignore の更新

既存の `.gitignore` に以下を追記する。**既存の記述は削除・改変しないこと。**

```gitignore
# 探索用の図（parquet + 生成コードから再現可能なため管理外）
/figures/
!/figures/.gitkeep
```

### 重要な注意点

- パターンは必ず **先頭スラッシュ付き** の `/figures/` にすること。
  スラッシュなしの `figures/` は任意の階層の `figures` ディレクトリにマッチしてしまい、
  サブディレクトリ内の意図しない除外を引き起こす
- `figures_final/` は `/figures/` パターンにマッチしないので、除外設定は不要

追記後、以下で意図通りに効いているか確認する。

```bash
git check-ignore -v figures/test.png        # 無視されること
git check-ignore -v figures_final/卒論/x.png # 無視されないこと（出力なし＝正常）
```

## タスク3：既存の図の移行

1. リポジトリ内で追跡済みの画像ファイルを洗い出す

```bash
git ls-files | grep -iE '\.(png|pdf|svg|jpg|jpeg)$'
```

2. 結果を**一覧で提示し、移行方針を確認してから作業に入ること**。
   自動判断で移動・削除しない

3. 移行時は `git mv` を使い、履歴を保つ

### 制約

- **`git filter-repo` や `git rebase` による履歴の書き換えは行わないこと。**
  現在の `size-pack` は約36MiB でGitHubの推奨値に対して十分小さく、履歴を削る必要はない
- **force push は絶対に行わないこと**

## タスク4：図生成スクリプトの出力先変更

1. リポジトリ内で図を生成しているコードを探す

```bash
grep -rn "savefig\|plt.save\|to_image\|write_image" --include="*.py" .
```

2. 出力先パスが `figures/` 以外を指しているものを特定し、一覧で提示する

3. デフォルト出力先を `figures/` に変更する。その際、
   **出力先をハードコードせず、引数や設定で上書きできる形にすること**
   （確定版を作る際に `figures_final/卒論/` へ直接出力できるようにするため）

例：

```python
def save_figure(fig, name, outdir="figures"):
    path = Path(outdir) / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path
```

4. 既存の呼び出し箇所がすべて動作することを確認する

## タスク5：PROVENANCE.md のテンプレート作成

`figures_final/` 配下の各サブディレクトリには、再現に必要な情報を記録する
`PROVENANCE.md` を置く。`figures_final/卒論/PROVENANCE.md` として以下を作成する。

```markdown
# 卒論 図の生成情報

## 生成環境

- 生成日：YYYY-MM-DD
- リポジトリ：tileQR_data
- コミットハッシュ：`git rev-parse HEAD` の出力
- Python環境：`uv.lock` のハッシュ、または `uv pip freeze` の要約

## 入力データ

- `derived/qr_sweep.parquet`（更新日：）
- `derived/ssrfb.parquet`（更新日：）
- `derived/optima.csv`（更新日：）
- `machines.yaml`（更新日：）

## 図一覧

| ファイル名 | 内容 | 生成コマンド |
|---|---|---|
| | | |

## 備考

（データ除外の判断、パラメータの固定値など、図から読み取れない情報を記録）
```

## タスク6：README の整備

`figures_final/README.md` を作成し、以下を記載する。

- `figures/` と `figures_final/` の役割の違い
- サブディレクトリは発表・成果物単位で切ること
- 確定版を `figures_final/` に置く際は必ず `PROVENANCE.md` を更新すること
- ファイル命名は既存の規約に揃えること
  （例：`{node}_size{N}_t{threads}_{内容}.png`）

リポジトリルートに `README.md` があれば、図の管理方針について
`figures_final/README.md` への参照を1〜2行で追記する。

---

## タスク7：図の一括生成スクリプトの実装

データが追加されるたびに実行し、全図を再生成するスクリプトを実装する。

### 配置とインターフェース

既存のコード配置規約に従って配置する（`scripts/` が存在すればその下）。

```bash
uv run python scripts/generate_figures.py                    # 全config再生成
uv run python scripts/generate_figures.py --config aoba-b_s2_smt-off
uv run python scripts/generate_figures.py --aggregators median   # 中央値のみ
uv run python scripts/generate_figures.py --outdir figures_final/卒論
uv run python scripts/generate_figures.py --force            # キャッシュ無視
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--outdir` | `figures` | 出力先ルート |
| `--config` | 全件 | 対象configを絞る（複数指定可） |
| `--aggregators` | `median mean` | 試行の集約方法（複数指定可） |
| `--band-threshold` | `0.95` | 95%バンドの閾値 |
| `--dpi` | `150` | 出力解像度 |
| `--force` | off | 未変更でも再生成 |

`--aggregators` に複数指定した場合、指定した数だけ図が生成される。
ヒートマップは枚数が増えすぎるため、**先頭に指定された集約方法のみで生成**する。

### 対象configの列挙方法

configは `{node}_{socket構成}_{smt状態}` の形式（例：`aoba-b_s2_smt-off`）。

**列挙は `derived/qr_sweep.parquet` から行うこと。** COVERAGE.md からではなくデータ自体を
正としたうえで、COVERAGE.md に記載のあるconfigとの差分を警告として出力する。
データにあってCOVERAGE.mdにない、またはその逆のケースを検出できるようにするため。

parquetにconfigを一意に定める列が揃っていない場合は、
**列構成を報告して確認を取ること。**勝手に列を合成しない。

### 前処理：試行の集約

`trials` 相当の列があり同一 (config, size, nb, ib) に複数行が存在する場合、
**集約してから最大値・バンドを求めること。**生データの argmax を直接取らない。

測定ノイズは片側（遅くなる方向）にしか出ないため、外れ値が混入すると平均は
下方に引っぱられる。約20%の点で最大-16%のスパイクが発生する条件では、
5試行の平均は約67%の点で0〜6.4%の**不揃いな**下方バイアスを受ける。
プラトー領域の隣接nb間の真の性能差は1〜3%程度しかないため、
このバイアスが nb\* の選択とバンド境界を左右しうる。

#### 集約方法の比較を可能にすること

集約方法は決め打ちにせず、**中央値と平均の両方で図を生成する**。
どちらを既定とするかを実測で判断するため。

- `--aggregators` で指定（デフォルト：`median mean` の両方）
- 出力ファイル名に集約方法を含める（後述）
- 両者の `nb*` とバンド範囲の差分を比較表として出力する（タスク7-3）

集約に使った試行数（同一パラメータペアあたりの行数）は、
図中またはサイドカーJSONに必ず記録すること。試行数が config・size によって
異なる場合は、実行サマリで報告する。

**parquetが集約済みで生の試行が残っていない場合は、その旨を報告して止まること。**
集約方法を後から変えられない構造になっているため、対応方針の確認が必要。

---

### 図1：ヒートマップ

**生成単位**：(config, size) の組ごとに1枚

**出力先**：`{outdir}/heatmap/{config}_size{N}_{agg}.png`
（例：`figures/heatmap/aoba-b_s2_smt-off_size4096_median.png`）

`{agg}` は `--aggregators` の先頭の値。ファイル名に含めるのは、
後から図を見たときに集約方法が判別できるようにするため。

**仕様**：

- 横軸 `nb`、縦軸 `ib`、カラーで GFlop/s
- `ib > nb` の領域はマスクして描画しない（白抜き）
- 最大値の位置に赤色のマーカーを置く
- 凡例枠に最大値と、そのときの `(ib, nb)` を表示
- タイトルに config と size を明記する

**注意**：`ib` 列が存在しない、または `ib` に変化がないconfigはヒートマップを生成できない。
その場合は**エラーで止めず、スキップしてログに理由を記録する**こと。
どのconfigでヒートマップが生成されなかったかを実行サマリに含める。

---

### 図2：nbスイープ（95%バンド付き）

**生成単位**：config × 集約方法 ごとに1枚（全sizeを重ね描き）

**出力先**：`{outdir}/sweep/{config}_{agg}.png`

デフォルト設定では config ごとに以下の2枚が生成される。

```
figures/sweep/aoba-b_s2_smt-off_median.png
figures/sweep/aoba-b_s2_smt-off_mean.png
```

**この2枚は目視で直接比較するためのものなので、軸範囲・色・凡例の配置を完全に揃えること。**
`ylim` と `xlim` は両者で共通の値に固定する（片方だけオートスケールすると
見かけ上の差が集約方法の差なのか軸の差なのか区別できなくなる）。

タイトルに集約方法と試行数を明記する（例：`aoba-b_s2_smt-off (median of 5 trials)`）。

**仕様**：

- 横軸 `nb`、縦軸 GFlop/s
- 系列は `size`（1024, 2048, 4096, 8192, 16384 など、データに存在するものすべて）
- 系列の色は size 順に並ぶ連続カラーマップ（viridis等）を使う。
  sizeは順序を持つ量なので、カテゴリカルな色分けにしないこと
- 各系列について以下を描画する：
  - 最大値の点を強調マーカーで表示し、`nb` の値を注記
  - **性能が `最大値 × band_threshold` 以上となる `nb` の範囲を帯で表示**（`axvspan` 等、系列色の半透明）
  - 最大値の水平線（破線、系列色）

**バンドの決め方**：

閾値以上の点は必ずしも連続しない。**argmax を含む連続区間を帯として描画し、
その外側に閾値以上の点が存在する場合はログに警告を出す**こと（帯の定義が
データの実態と乖離していないかを確認するため）。

帯の下限・上限の `nb` 値を図中に読み取れる形で示す（軸の注記、または凡例）。

**凡例**：size ごとに「size, 最大GFlop/s, nb\*, バンド範囲」が分かるようにする。
系列数が5前後になるため、凡例が図を覆わない位置に配置すること。

---

---

### タスク7-3：集約方法の比較表

図の目視比較だけでは差が読み取りにくいため、数値の比較表を出力する。
**これが集約方法を決定するための主要な成果物になる。**

**出力先**：`{outdir}/comparison/aggregator_comparison.csv`

**列**：

| 列名 | 内容 |
|---|---|
| `config` | 例：`aoba-b_s2_smt-off` |
| `size` | 行列サイズ |
| `n_trials` | 集約に使った試行数 |
| `nb_star_median` | 中央値集約での最適nb |
| `nb_star_mean` | 平均集約での最適nb |
| `delta_nb_star` | `nb_star_mean - nb_star_median` |
| `max_median` | 中央値集約での最大GFlop/s |
| `max_mean` | 平均集約での最大GFlop/s |
| `delta_max_pct` | 最大値の相対差（%） |
| `band_lo_median` / `band_hi_median` | 中央値集約でのバンド範囲 |
| `band_lo_mean` / `band_hi_mean` | 平均集約でのバンド範囲 |
| `band_width_median` / `band_width_mean` | バンド幅 |
| `band_jaccard` | 両バンドのJaccard係数（重なり具合） |

`band_jaccard` は2つのバンドを nb の区間とみなし、
`|共通部分| / |和集合|` で計算する。1.0なら完全一致。

同じ内容を Markdown 表としても
`{outdir}/comparison/aggregator_comparison.md` に出力し、
実行サマリでは差が大きい上位5行を標準出力に表示する。

**この表は解釈を書き加えず、数値のみを出力すること。**
どちらの集約方法を採用するかの判断はユーザーが行う。

---

### 再生成の効率化

入力データと描画パラメータから決まるハッシュをサイドカーJSON
（例：`figures/sweep/aoba-b_s2_smt-off.png.meta.json`）に保存し、
変更がなければスキップする。`--force` で無効化できるようにする。

サイドカーJSONには以下を含める。

- 入力ハッシュ、生成日時
- 該当configの元データ行数、集約後の点数、試行数
- **使用した集約方法**（`median` / `mean`）
- 使用した `band_threshold`
- 各sizeの最大GFlop/s、`nb*`、バンド範囲

これは `figures_final/` に確定版を置く際、PROVENANCE.md に転記する情報源になる。
確定版を置くときは、**採用した集約方法を PROVENANCE.md に必ず記載すること。**

### 実行サマリ

処理の最後に以下を標準出力へ表示する。

- 生成した図の枚数（新規／更新／スキップの内訳）
- スキップしたconfigとその理由
- COVERAGE.md との差分
- バンドが非連続だったconfigとsize
- **集約方法の違いで `nb*` が変化したconfig・sizeの件数と、変化量が大きい上位5件**
- **試行数が config・size 間で不揃いな箇所**

---

## 作業後の確認

以下をすべて実行し、結果を報告すること。

```bash
# 1. ignore 設定が正しいか
git check-ignore -v figures/dummy.png
git status --short

# 2. figures/ 配下がステージに乗っていないか（.gitkeep 以外）
git ls-files figures/

# 3. figures_final/ が追跡されているか
git ls-files figures_final/

# 4. リポジトリサイズに変化がないか
git count-objects -vH

# 5. 図生成が通るか（2回目がスキップされることも確認）
uv run python scripts/generate_figures.py
uv run python scripts/generate_figures.py
```

生成された図を実際に開いて、以下を目視確認すること。

- ヒートマップ：`ib > nb` が白抜きになっているか、赤マーカーが最大値上にあるか
- スイープ図：帯が最大値付近を囲んでいるか、凡例が読めるか
- **`{config}_median.png` と `{config}_mean.png` を並べたとき、軸範囲が完全に一致しているか**

最後に比較表を表示して報告すること。

```bash
cat figures/comparison/aggregator_comparison.md
```

## 全体を通しての制約

- **既存の `derived/` 配下および `machines.yaml` には一切触れないこと。**
  これらは正規データであり、今回の作業範囲外
- コミットは作業単位で分けること。1つの巨大なコミットにまとめない
- コミットメッセージは日本語で、何をなぜ変更したかを記述する
- 判断に迷う箇所（既存図の分類、スクリプトの出力先変更の影響範囲など）は
  **自動判断せず、選択肢を提示して確認を取ること**
