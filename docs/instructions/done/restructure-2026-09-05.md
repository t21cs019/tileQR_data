# 指示書: リポジトリ構成の整理（spec / docs / archive の新設と out/ の廃止）

> 完了済み。文中のパスは作業当時のもの（本文は移行前の状態を前提に書かれている）。

対象リポジトリ: `tileQR_data`（一部 `tileQR_research` にも及ぶ）
起票日: 2026-09-05
起票理由: ルート直下のファイル・ディレクトリが増えすぎ、文書の所在が散らばり、
除外した計測データの置き場が3通りに分かれていたため。

---

## 0. まず読む

この作業は**ファイルの移動と文書の再配置**であり、データの内容は1バイトも変えない。
`raw_data/` `raw/` `derived/` の中身は移動も編集もしない。

作業前にブランチを切ること。

```bash
git switch -c refactor/repo-structure
```

### 絶対に触ってはいけないもの

以下は未追跡のまま放置する。ユーザーから「いったん無視」と明示されている。

```
raw_data/i3-7100_s1_smt-off/i3-7100_size1024_nb32-512_th2_t5_20260902_115503.csv
raw_data/i3-7100_s1_smt-off/i3-7100_size2048_nb32-512_th2_t5_20260902_125340.csv
raw_data/i3-7100_s1_smt-off/i3-7100_size4096_nb32-512_th2_t5_20260902_184301.csv
raw_data/i5-7400_s1_smt-off/i5-7400_size8192_nb32-512_t5_20260902_092613.csv
```

**`python scripts/assemble.py raw_data --apply` を実行してはならない。**
実行すると上記4ファイルが `raw/` に取り込まれ、この作業の範囲を超えて
`derived/` と `COVERAGE.md` が変わる。dry-run（`--apply` なし）は可。

---

## 1. 完了条件

1. ルート直下の追跡ファイルが `README.md` `Makefile` `pyproject.toml` `uv.lock` `.gitignore` のみ
2. `spec/` に YAML 4本（`machines.yaml` `plan.yaml` `curation.yaml` `running.yaml`）
3. `docs/` に `COVERAGE.md` `TODO_REMEASURE.md` `CHANGELOG.md` と `design/` `instructions/`
4. `archive/` に `attic/` と `quarantine/` が入り、`archive/README.md` がある
5. `out/` が存在せず、`paths.py` の `OUT` 別名と `.gitignore` の `/out/*` も消えている
6. `README.md` が 250行以下で、構成図に `spec/` `docs/` `archive/` `studies/` が載り、
   各行に `(自動生成)` `(Git管理外)` の印がある
7. `docs/design/` に4本の設計文書がある
8. `python scripts/validate.py` がエラー0
9. `python scripts/ingest.py` が `docs/COVERAGE.md` を書き、**内容が作業前と同一**
10. vault 側の `tileQR_data/out/...` と `tileQR_data/machines.yaml` の参照が更新されている

### 作業前に控えを取ること

```bash
cp COVERAGE.md /tmp/COVERAGE.before.md
find raw -name '*.csv' | wc -l    # 353 のはず
wc -l derived/optima.csv          # 67 のはず
```

---

## 2. Phase 1 — `spec/` へ YAML 4本

```bash
mkdir spec
git mv machines.yaml plan.yaml curation.yaml running.yaml spec/
```

`src/tileqr_data/paths.py` を編集する。現在30-36行あたり。

```python
# 宣言層。人が書き、コードが読む入力。derived/（コードが書く出力）と対になる。
SPEC = ROOT / "spec"
MACHINES_YAML = SPEC / "machines.yaml"
PLAN_YAML = SPEC / "plan.yaml"
CURATION_YAML = SPEC / "curation.yaml"
RUNNING_YAML = SPEC / "running.yaml"
```

### ディレクトリ名を `config/` にしなかった理由（コメントに残すこと）

このリポジトリで **config は計測構成を指すドメイン語**である
（`machines.yaml` の `configs:` キー、`raw_data/{config}/`、`assemble.config_of()`、
`COVERAGE.md` の `config` 列）。YAML の置き場を `config/` にすると、
コード中の `config` がディレクトリなのか `aoba-b_s1_smt-off` なのか読み分けられない。

### docstring 内のファイル名は書き換えない

`scripts/*.py` と `src/tileqr_data/*.py` には `machines.yaml` `curation.yaml` 等の
言及が約50箇所あるが、**ファイル名は変わっていない**ので誤解を生まない。
書き換えるのは `paths.py` のパス定義とコメントのみ。

### 確認

```bash
python scripts/validate.py    # エラー0
```

---

## 3. Phase 2 — `docs/` へ文書3本

```bash
mkdir -p docs/design docs/instructions/done
git mv COVERAGE.md TODO_REMEASURE.md CHANGELOG.md docs/
git mv INSTRUCTIONS_quarantine_aoba_s1.md docs/instructions/done/quarantine-aoba-s1-2026-09-05.md
git mv instructions/figures_restructure.md docs/instructions/done/figures-restructure-2026-09-01.md
rmdir instructions
```

`INSTRUCTIONS_quarantine_aoba_s1.md` は未追跡なので `git mv` が通らない場合は
通常の `mv` でよい。移動後 `git add` すること。

### コード側の3箇所

**`src/tileqr_data/paths.py`**

```python
DOCS = ROOT / "docs"
COVERAGE_MD = DOCS / "COVERAGE.md"
```

**`scripts/sync_generated.py`** — `FILES` のパスを `docs/` 込みにし、
vault 側のファイル名は従来どおりにする（`dst` はベース名を使う）。

```python
FILES = [
    ("docs/COVERAGE.md", "計測カバレッジ", "scripts/ingest.py の自動生成"),
    ("docs/TODO_REMEASURE.md", "再計測が必要な項目", None),
]
```

`sync_one()` 内の `dst = dst_dir / name` を `dst = dst_dir / Path(name).name` に直す。
`origin = f"tileQR_data/{name}"` はそのままでよい（`tileQR_data/docs/COVERAGE.md` になる）。

**`Makefile`** の clean ターゲット

```make
clean:
	rm -rf derived/*.parquet derived/optima.csv figures/* docs/COVERAGE.md
```

### 確認

```bash
python scripts/ingest.py
diff /tmp/COVERAGE.before.md docs/COVERAGE.md    # 差分なしであること
python scripts/sync_generated.py                  # vault の generated/ が更新される
```

---

## 4. Phase 3 — `archive/` へ attic と quarantine

```bash
mkdir archive
git mv attic archive/attic
git mv quarantine archive/quarantine
```

### 参照の書き換え（コードを先に）

**`studies/full_search_threads/compare.py:40` は実行時パスなので必ず直す。**

```python
OLD = ROOT / "archive" / "attic" / "Full_search_dgeqrf" / "benchmark_dtsmqr_4096.csv"
```

同ファイルの docstring 3行目・11行目の `attic/` も併せて更新。

**文書側**（`attic/` → `archive/attic/`、`quarantine/` → `archive/quarantine/`）

| ファイル | 行 |
|---|---|
| `spec/plan.yaml` | 105 |
| `docs/TODO_REMEASURE.md` | 26, 95, 101, 213, 218, 219, 226, 259, 261, 274, 275 |
| `spec/machines.yaml` | 52, 350, 385, 387 |
| `studies/full_search_threads/README.md` | 3, 9, 47 |
| `README.md` | 63-64（構成図。Phase 5 で刷新するのでそちらで対応） |

### `docs/CHANGELOG.md` の過去エントリは書き換えないこと

CHANGELOG は「いつ何をなぜ決めたか」の記録である。0.8.0 の
「attic/ を新設した」は**当時の事実**なので、`archive/attic/` に書き換えると
記録が嘘になる。移動の事実は Phase 7 で 0.10.0 として新規に追記する。

同じ理由で `docs/instructions/done/` に移した完了済み指示書2本も中身を書き換えない。
かわりに各ファイルの冒頭に1行だけ足す。

```markdown
> 完了済み。文中のパスは作業当時のもの（2026-09-05 の構成整理より前）。
```

### `archive/README.md` を新規作成

内容は次の3点に絞る。詳しい判断基準は `docs/design/excluded-data.md`（Phase 5）に置き、
ここからはリンクするだけにする（同じ説明を2箇所に置かない）。

- ここは**パイプラインが読まないデータ**の置き場であること
- `attic/`（出自が欠けていて昇格できない原本）と
  `quarantine/`（計測条件が無効と確定したもの）の違い
- どちらに置くか／`spec/curation.yaml` で落とすかの判断は
  `docs/design/excluded-data.md` の表を見ること

`archive/attic/README.md` は目録として現状のまま残す（冒頭の1〜2文だけ、
`archive/` 配下になったことに合わせて調整してよい）。

---

## 5. Phase 4 — `out/` の廃止

**順序を守ること。図を先に作ってから消す。**

```bash
make figures                      # figures/ に3枚が出ることを確認
ls figures/fig_kurzak_p_exponent.png figures/fig_kurzak_size_exponent.png figures/fig_nb_curve_aoba.png
```

3枚が揃わなければ**中断して報告する**。vault がこの図を参照するため、
`out/` を先に消すと参照先が消える。

揃ったら削除する。

```bash
git rm out/.gitkeep
rm -rf out
```

**`src/tileqr_data/paths.py`** — 28行目付近の別名と、その上のコメント2行を削除。

```python
# 旧名。figures/ に役割を移したが、古い呼び出しが落ちないよう残す。
OUT = FIGURES          ← この2行を削除
```

削除して問題ない根拠: `paths.OUT` の使用箇所は0件（定義行のみ）。
図の実際の出力先は `style.save()` の既定値 `paths.FIGURES`。

**`.gitignore`** — `/out/*` と `!/out/.gitkeep` の2行と、その上の説明コメントを削除。

---

## 6. Phase 5 — README の分割と `docs/design/`

### README.md に残すもの（目標 250行以下）

- 冒頭（何のリポジトリか）
- **新規1行**: 「文中のパスはすべてリポジトリルートからの相対」
- `## リポジトリの役割分担`（現 13-35行）
- `## なぜ git で持つか`（現 36-52行）— 要約に圧縮してよい
- `## 構成`（現 53-97行）— **刷新する。下記参照**
- `## 使い方`（現 348-363行）
- `## 運用`（現 678-697行）
- **新規**: `## 文書の案内` — `docs/` 配下への索引表

### 構成図の刷新（完了条件6）

`spec/` `docs/` `archive/` `studies/` を追加し、`out/` を削除し、各行に印を付ける。

```
tileQR_data/
├── spec/                   宣言層。人が書き、コードが読む入力
│   ├── machines.yaml       アーキテクチャ / 計測構成 / ノードの定義
│   ├── plan.yaml           計測計画。COVERAGE.md の「分母」
│   ├── curation.yaml       raw に上げないもの / 置き換えるもの。理由つき
│   └── running.yaml        いま流している計測。進捗表に ▶ で出る
├── raw_data/{config}/      計測機から回収したままの原本。触らない
├── raw/                    assemble.py が組み直したもの        (自動生成)
├── derived/                ingest.py が生成                     (自動生成・コミットする)
├── archive/                パイプラインが読まないデータ
│   ├── attic/              出自が欠けていて昇格できない原本
│   └── quarantine/         計測条件が無効と確定したもの
├── studies/                個別調査の根拠。curation.yaml 等から参照される
├── figures/                探索用の図                           (Git管理外)
├── figures_final/          発表に使った確定版                   (コミットする)
├── figures_src/            図の生成コード。1図につき1本
├── docs/
│   ├── COVERAGE.md         計画に対する進捗                     (自動生成)
│   ├── TODO_REMEASURE.md   再計測が必要な項目
│   ├── CHANGELOG.md        版と、後から理由を思い出せないと困る判断
│   ├── design/             設計判断の詳細
│   └── instructions/       作業指示書（完了済みは done/）
├── scripts/                実行スクリプト
└── src/tileqr_data/        ライブラリ
```

`raw/` の中の `JOINS.md` `CURATION.md` `ASSEMBLED.txt`（いずれも自動生成）は
`docs/design/data-pipeline.md` 側で説明する。

### `docs/design/` に移す本文の対応表

**本文は原則そのまま移す。書き直さない。** 削ってよいのは
「コードの docstring と完全に同じ説明」だけで、迷ったら残すこと。

| 移す先 | README の現在の見出し（行） |
|---|---|
| `data-pipeline.md` | 測定種別を第一階層で分ける理由 (98) / raw_data → raw の組み直し (117-230) / 命名規則 (364-405) / 計測構成をディレクトリで表す (406-439) / ダッシュボードとの対応 (440-468) |
| `excluded-data.md` | 使えないデータをどう扱うか（curation.yaml）(231-307) ＋ **新規の判断表（下記）** |
| `coverage-and-plan.md` | いま流している計測 (308-347) / 最適 nb の定義 (469-507) / 計測計画と COVERAGE.md (508-594) |
| `figures.md` | 図 (595-661) / derived と figures_final をコミットする理由 (662-677) の図に関する部分 |

`## derived/ と figures_final/ をコミットする理由` は方針なので、
README に1段落だけ要約を残し、詳細を `figures.md` に置く。

### `docs/design/excluded-data.md` の新規部分（判断表）

「使わないデータ」の置き方が3通りある。次に同じ判断をするとき迷わないよう、
この表を**唯一の判断基準**として置く。

| 状況 | 置き場所 | 実例 |
|---|---|---|
| 出自が欠けていて昇格の判定が要る | `archive/attic/` | 学部時代のフルスイープ（スレッド数不明） |
| 計測条件が無効と確定し、ディレクトリ全件が対象 | `archive/quarantine/<理由>_<時期>/` | `aoba-b_s1_oversubscribed_2026-06`（NPS4 で16コア） |
| 一部のファイル・一部の行だけ。原本は `raw_data/` に残す | `spec/curation.yaml` の `exclude` | i5-7400 シングルチャネル計測 |

**`spec/curation.yaml` で落としたデータは `archive/` には来ない**（`raw_data/` に残る）。
これがディレクトリ名を `excluded/` にしなかった理由でもある。

### 重複を増やさないこと

curation の設計は現在3箇所（README / `curation.py` docstring / `curation.yaml` コメント）に
書かれている。**`excluded-data.md` を4箇所目にしてはならない。**
README 231-307行の本文を `excluded-data.md` へ移し、README からは
リンク1行のみにする。`curation.py` と `curation.yaml` は触らない。

---

## 7. Phase 6 — vault（`tileQR_research`）の修正

**別リポジトリなので、変更はするがコミットはしない。** 最後にユーザーへ報告する。

| ファイル:行 | 現在 | 修正後 |
|---|---|---|
| `notes/kurzak_verification.md:139` | `tileQR_data/out/fig_kurzak_p_exponent.png` | `tileQR_data/figures/fig_kurzak_p_exponent.png` |
| `notes/kurzak_verification.md:212` | `tileQR_data/out/fig_kurzak_size_exponent.png` | `tileQR_data/figures/fig_kurzak_size_exponent.png` |
| `notes/kurzak_verification_brief.md`（構成図内） | `machines.yaml` | `spec/machines.yaml` |
| `notes/benchmark_protocol.md:32` | `tileQR_data/machines.yaml` | `tileQR_data/spec/machines.yaml` |

`notes/research_workflow.md` の「出典は `git log -- out/fig_xxx.png` だけで辿れる」は
**2026-08-26 の設計判断の記録なので書き換えない**。CHANGELOG と同じ扱い。

`figures/` が Git 管理外である点はユーザー了承済み（図がまだ最終版ではないため）。
確定版ができた時点で `figures_final/` へ移し、vault の参照も差し替える。
この方針を `docs/design/figures.md` に1段落で書き残すこと。

---

## 8. 検証

```bash
python scripts/validate.py                     # エラー0
python scripts/ingest.py                       # docs/COVERAGE.md を書く
diff /tmp/COVERAGE.before.md docs/COVERAGE.md  # 差分なし
python scripts/assemble.py raw_data            # dry-run のみ。--apply 禁止
find raw -name '*.csv' | wc -l                 # 353（作業前と同じ）
wc -l derived/optima.csv                       # 67（作業前と同じ）
git status --short                             # 未追跡は上記4ファイルのみ
```

`assemble.py` の dry-run で「前回の名残」に i3-7100 / i5-7400 の新規ファイルが
出るのは想定内（未取り込みのため）。**`--apply` を付けないこと。**

`make figures` は Phase 4 で実行済み。再実行は不要。

---

## 9. コミット

論理的に分ける。各コミットの時点で `validate.py` が通ること。

1. `spec/` へ YAML 4本を移動（`paths.py` 込み）
2. `docs/` へ文書を移動（`paths.py` / `sync_generated.py` / `Makefile` 込み）
3. `archive/` へ attic と quarantine を移動（参照の書き換えと `archive/README.md` 込み）
4. `out/` を廃止（`paths.py` / `.gitignore` 込み）
5. README を分割し `docs/design/` を新設
6. `docs/CHANGELOG.md` に 0.10.0 を追記（`pyproject.toml` の version も 0.10.0 に）

CHANGELOG の 0.10.0 には最低限これを書く。

- ルート直下の肥大と文書の散逸を解消したこと
- `config/` ではなく `spec/` にした理由（ドメイン語 config との衝突）
- `excluded/` ではなく `archive/` にした理由（curation の exclude と混同する）
- `out/` は 2026-09-01 の図ディレクトリ再編で役割を失っていた残骸だったこと
- vault 側の参照2件を `figures/` に向け直したこと（確定版ができたら `figures_final/` へ）

---

## 10. やらないこと

- **`assemble.py --apply` の実行**。未追跡の新規4ファイルを取り込んでしまう
- `raw_data/` `raw/` `derived/` の中身の変更・移動
- `spec/curation.yaml` のルールの変更
- `docs/CHANGELOG.md` の過去エントリ、完了済み指示書の本文の書き換え
- `curation.py` / `curation.yaml` の docstring・コメントの書き換え
- vault（`tileQR_research`）でのコミット
- `studies/` の移動（9文書から参照されており、現在の位置で機能している）
- ルート直下の YAML を `config/` という名前にすること
