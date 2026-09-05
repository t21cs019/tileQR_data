# 図の管理

`README.md` の構成図から移設。

---

## プリセット

| | slide | paper |
|---|---|---|
| フォント | 游ゴシック系 | セリフ寄り |
| 文字サイズ | 14pt | 10pt |
| サイズ | 8.0 × 4.5 in（16:9） | 5.5 × 3.4 in |
| 出力 | PNG（300dpi） | PDF + SVG |

スライドは pptxgenjs でデッキを組む前提なので PNG 高DPI。

## 日本語フォント

`style.use()` が候補を優先順に探し、見つからなければ**警告を出す**。
豆腐（□□□）に気づかないまま発表資料を作るのを防ぐため、警告は無視しないこと。

## 配色

構成ごとの色は `style.CONFIG_COLORS` で固定する。
資料間で同じ構成の色が入れ替わると読者が混乱するため。

## 図は1ファイル1図

スクリプト名と出力名を一致させる
（`figures_src/fig_nb_curve_aoba.py` → `figures/fig_nb_curve_aoba.png`）。

## 探索用と確定版の使い分け

図には性質の違う2種類がある。使い分けの詳細は `figures_final/README.md` にある。

| | `figures/` | `figures_final/` |
|---|---|---|
| 性質 | 探索用・使い捨て | 発表に使った確定版 |
| Git | **管理外** | コミットする |
| 復元 | parquet + `figures_src/` から常に作り直せる | `PROVENANCE.md` で担保 |

解析のたびに数十枚が入れ替わるので、探索用まで追跡すると履歴が図の
バイナリで埋まる。入力と生成コードがリポジトリにある限り復元できるため、
成果物を持つ必要がない。

**vault（`tileQR_research`）から図を参照するときは、確定版ができるまでの
間は `figures/`（Git管理外）を指してよい。** ただし確定版ができた時点で
`figures_final/{発表単位}/` へ昇格し、vault側の参照も差し替えること。
`figures/` は解析のたびに中身が入れ替わるため、確定した参照先としては
不適切（2026-09-05、vault の kurzak 検証ノートが当時の `out/`
—`figures/` 移行前の廃止済みディレクトリ—を参照したまま忘れられていた
反省から）。

## 一括生成

```bash
uv run python scripts/generate_figures.py                        # 全 config
uv run python scripts/generate_figures.py --config aoba-b_s2_smt-off
uv run python scripts/generate_figures.py --outdir figures_final/卒論
uv run python scripts/generate_figures.py --force                # キャッシュ無視
```

出力は `figures/heatmap/`（(config, size) ごと）、`figures/sweep/`
（config × 集約方法ごと、95% バンド付き）、`figures/comparison/`（比較表）。

**試行の集約を argmax より先にやる。** 生データの argmax を直接取ると
「5回のうち一番高く出た回」を拾い、上振れを選び取ることになる
（`ingest.py` と同じ理由）。測定ノイズは遅くなる方向にしか出ないため、
外れ値が混ざると平均は下方に引っぱられる。プラトー領域の隣接 nb 間の
真の差は 1〜3% しかないので、この偏りが `nb*` とバンド境界を左右しうる。

中央値と平均のどちらを既定にするかは決め打ちにせず、両方で図を出して
`figures/comparison/aggregator_comparison.csv` に差分を出す。
**実測では 57 条件中 15 条件で `nb*` が変わり、最大 40 ずれた。**
確定版を置くときは、採用した集約方法を `PROVENANCE.md` に必ず記載する。

---

## derived/ と figures_final/ をコミットする理由

どちらも生成物だが、

- `derived/` … ダッシュボードが `git pull` 直後に読める
- `figures_final/` … `tileQR_research` の散文から図を参照でき、資料を組み直すときに再計算がいらない

ため、コミットする。合計で数 MB 程度なので履歴肥大の心配はない。

**探索用の `figures/` は追跡しない。** 解析のたびに数十枚が入れ替わるので、
こちらまでコミットすると履歴が図のバイナリで埋まる。入力（parquet）と
生成コード（`figures_src/`, `scripts/generate_figures.py`）がリポジトリに
ある限りいつでも復元できるため、成果物を持つ理由がない。
