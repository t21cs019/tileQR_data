# archive — パイプラインが読まないデータ

`assemble.py` も `ingest.py` も `validate.py` も、このディレクトリの中身を
一切走査しない（コード側に例外は無い。単にどのスクリプトもここを見ない）。

## 2つのサブディレクトリ

- **`attic/`** — 出自が欠けていて `raw/` に上げられない原本（学部時代の
  フルスイープ等）。詳細と目録は `attic/README.md`。
- **`quarantine/`** — 一度は `raw_data/` にあったが、計測条件が無効と
  確定したため丸ごと退避したもの。理由と再利用条件は各サブディレクトリの
  README。例: `quarantine/aoba-b_s1_oversubscribed_2026-06/README.md`。

## どちらに置くか、あるいは `spec/curation.yaml` で足りるかの判断

3方式の使い分けは `docs/design/excluded-data.md` の判断表を参照。
ここでは重複を避けるため詳細を書かない。
