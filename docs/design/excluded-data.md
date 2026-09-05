# 使わないデータの扱い

「取ったが使えない」データが出る理由は、メモリチャネル構成の違い、
スレッド数の取り違え、サーマルドリフトなど様々。置き方は3通りある。
次に同じ判断をするときはこの表を見る。

## 判断表

| 状況 | 置き場所 | 実例 |
|---|---|---|
| 出自が欠けていて昇格の判定が要る | `archive/attic/` | 学部時代のフルスイープ（スレッド数不明） |
| 計測条件が無効と確定し、ディレクトリ全件が対象 | `archive/quarantine/<理由>_<時期>/` | `aoba-b_s1_oversubscribed_2026-06`（NPS4 で16コア） |
| 一部のファイル・一部の行だけ。原本は `raw_data/` に残す | `spec/curation.yaml` の `exclude` | i5-7400 シングルチャネル計測 |

**`spec/curation.yaml` で落としたデータは `archive/` には来ない**（`raw_data/` に残る）。
`archive/` を `excluded/` という名前にしなかったのはこのため。
「除外したものは excluded/ にある」が偽になってしまう。

`archive/attic/` と `archive/quarantine/` の違いは `archive/README.md` を参照。

---

## `spec/curation.yaml` の書き方

**`raw/` から手で消すのではいけない。** `raw/` は `raw_data/` から
`make assemble` で再生成できることが前提のディレクトリなので、
手で消した除外も手で直した1点も、次の assemble で黙って元に戻る。
判断は再生成の**入力側**、つまり `spec/curation.yaml` に置く。

```yaml
exclude:
  - id: i5-7400-qr_sweep-memory-channels
    match:
      kind: qr_sweep
      node: i5-7400
      src: [i5-7400_size1024_nb32-512_t5_20260624_104705.csv, ...]
    since: 2026-09-01
    reason: 2026-06-24 分はシングルチャネルで計測されていた。…
    remeasure: デュアルチャネル構成で size 1024/2048/4096/8192 を各5反復
```

`assemble.py` が自前で持つ除外（プローブ、部分集合の周）は**データの形から
決まる**のでコードにある。`curation.yaml` が持つのは、データを見ても分からない
判断だけ。この2つを混ぜないこと。

### 部分的に使う

`match` に `nb` / `ib` を書くと、トライアル全体ではなく**該当行だけ**に効く。
古い計測のうち一部の nb 区間だけ使いたいときはこれを使う。

```yaml
  - match: {node: i5-8500, kind: ssrfb, nb: [32, 100]}   # この区間だけ落とす
```

| match のキー | 効く単位 |
|---|---|
| `kind` / `node` / `config` / `threads` / `size` / `src` / `trial` | トライアル |
| `nb` / `ib` | 行（＝部分的に使う） |

`nb` は `32`（値）、`[32, 64]`（区間）、`[32, 40, 48]`（3つ以上なら集合）。
`src` は `raw_data` 側のファイル名で glob 可。

未知のキーと空の `match` は読み込み時にエラーになる。`kind` を `kinds` と
書き間違えたルールが黙って全件を除外するのが一番こわいため。

### 1点だけ測り直したとき（replace）

`replace` は別ファイルの値で該当点を置き換える。数値そのものを yaml に
直書きしないのは、「どのファイルの何行をどう畳んだ値か」が失われるため。

```yaml
replace:
  - id: ryzen-ssrfb-coldstart
    match: {kind: ssrfb, node: ryzen, size: 1024, nb: 32, ib: 8}
    from: {file: ryzen7-5800x_s1_smt-on/ryzen_manual_ssrfb_nb32_ib8.csv,
           agg: mean, drop_first: 1}
```

`drop_first` があるのは、手動再計測でも1回目だけコールドスタートで跳ねたため。
何行捨てたかが残るので、後から判断を検証できる。

### 消し忘れと、絞りすぎないルールが一番あぶない

再計測が済んで元データを差し替えたのにルールを残すと、**新しい計測が黙って
除外され続ける**。ルールが広すぎるときも同じことが起きる。`{kind: ssrfb,
node: i5-7400}` と書いていたせいで、`threads=1` で取り直した正しいデータまで
`raw/` に上がらなかった（2026-08-31）。**何が原因で落とすのかを match に
書く**こと。上の例が `threads: 4` や `src` で絞っているのはこのため。`assemble.py` は1件も当たらなかったルールを「未使用」として
必ず報告する。`make validate` は、除外したはずのデータが `raw/` に残っていたら
エラーにする。

散文（何が起きたか、どう測り直すか）は `docs/TODO_REMEASURE.md`、
機械が守る形が `spec/curation.yaml`、適用結果が `raw/CURATION.md`。

---

## `archive/quarantine/` の実例: aoba-b_s1_smt-off

2026-06〜09 の計測（`numactl --cpunodebind=0`）が、AOBA-B の NPS4 環境で
16コアしか掴んでおらず、64スレッドを16コアに載せた4倍オーバーサブスク
リプションだったことが 2026-09-05 に判明した。

20ファイル全件が対象で、かつ `raw_data/` に残す個別ファイル単位の
`curation.yaml` 除外リストにすると煩雑になるため、`raw_data/aoba-b_s1_smt-off/`
をディレクトリごと `archive/quarantine/aoba-b_s1_oversubscribed_2026-06/` へ
退避した（削除ではない）。詳細・再利用条件は同ディレクトリの README。
