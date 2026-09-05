# 使わないデータの扱い

「取ったが使えない」データが出る理由は、メモリチャネル構成の違い、
スレッド数の取り違え、サーマルドリフトなど様々。置き方は3通りある。
次に同じ判断をするときはこの表を見る。

## 判断表

| 状況 | 置き場所 | 実例 |
|---|---|---|
| 出自が欠けていて昇格の判定が要る | `archive/attic/` | 学部時代のフルスイープ（スレッド数不明） |
| 計測条件が無効・不完全と確定し、該当ファイルを丸ごと動かせる | `archive/quarantine/<理由>_<時期>/` | `aoba-b_s1_oversubscribed_2026-06`（NPS4 で16コア）、`i5-7400_single_channel_2026-06`（シングルチャネル） |
| 元ファイルを `raw_data/` から消せない（連結の出所を追える形で残す等）事情がある | `spec/curation.yaml` の `exclude` | ryzen7-5800x の nb404-512 二重取り込み |
| 行の一部だけ落とす／別ファイルの値に置き換える | `spec/curation.yaml` の `exclude`（nb/ib指定）・`replace` | i5-8500 ssrfb の nb32-100 区間、ssrfb コールドスタート点の置換 |

**2026-09-05 の方針転換**: 以前は「特定ファイルだけを丸ごと落とす」場合も
`curation.yaml` の `src:` にファイル名を列挙していた（i5-7400 のメモリ
チャネル問題・ssrfb threads 問題がそうだった）。しかしファイルを
そのまま動かせるなら、列挙するより **`archive/quarantine/` へ物理的に
退避する方が管理しやすい**（列挙が要らない、当たらなくなったルールの
消し忘れを心配しなくてよい）。`curation.yaml` の `exclude` を使うのは、
ryzen7-5800x の例のように元ファイルを `raw_data/` に残す積極的な理由が
あるか、行単位（nb/ib）で絞る必要がある場合。

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
  - id: ryzen7-5800x-qr_sweep-nb404-512-merged
    match:
      kind: qr_sweep
      node: ryzen
      src: [ryzen_size2048_nb404-512_t5_20260901_015640.csv, ...]
    since: 2026-09-04
    reason: nb32-512に手作業で連結済みの元ファイル。残さないと二重取り込みになる。
    remeasure: 不要。連結済みのnb32-512が正。raw_dataの掃除（削除）をするまでの暫定措置
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
除外され続ける**。ルールが広すぎるときも同じことが起きる。i5-7400 の ssrfb
除外ルールが `{kind: ssrfb, node: i5-7400}` とだけ書いていたせいで、
`threads=1` で取り直した正しいデータまで `raw/` に上がらなくなりかけた
（2026-08-31。実際には `threads: 4` を足して絞ったことで防げた。
このルール自体は2026-09-05に `archive/quarantine/i5-7400_ssrfb_threads4_2026-08/`
への物理退避に置き換えて削除済み）。**何が原因で落とすのかを match に
書く**こと。`assemble.py` は1件も当たらなかったルールを「未使用」として
必ず報告する。`make validate` は、除外したはずのデータが `raw/` に残っていたら
エラーにする。

散文（何が起きたか、どう測り直すか）は `docs/TODO_REMEASURE.md`、
機械が守る形が `spec/curation.yaml`、適用結果が `raw/CURATION.md`。

---

## `archive/quarantine/` の実例

### aoba-b_s1_smt-off（計測条件そのものが無効）

2026-06〜09 の計測（`numactl --cpunodebind=0`）が、AOBA-B の NPS4 環境で
16コアしか掴んでおらず、64スレッドを16コアに載せた4倍オーバーサブスク
リプションだったことが 2026-09-05 に判明した。

20ファイル全件が対象で、かつ `raw_data/` に残す個別ファイル単位の
`curation.yaml` 除外リストにすると煩雑になるため、`raw_data/aoba-b_s1_smt-off/`
をディレクトリごと `archive/quarantine/aoba-b_s1_oversubscribed_2026-06/` へ
退避した（削除ではない）。詳細・再利用条件は同ディレクトリの README。

### i5-7400（curation.yamlからの移行例）

i5-7400 のメモリチャネル問題（qr_sweep 4ファイル）と ssrfb threads 取り違え
（4ファイル）は、もともと `curation.yaml` の `src:` 列挙で除外していた
（`i5-7400-qr_sweep-memory-channels` / `i5-7400-ssrfb-threads`）。2026-09-05、
AOBA-B s1 の隔離作業に合わせて `archive/quarantine/i5-7400_single_channel_2026-06/`
と `archive/quarantine/i5-7400_ssrfb_threads4_2026-08/` へ退避し、両ルールは
`curation.yaml` から削除した。対象ファイルが特定できていて `raw_data/` に
残す積極的な理由が無いなら、列挙よりディレクトリ移動の方が管理しやすい
という判断（上の判断表を参照）。

3サイズ（1024/2048/4096）は既に正しい値で再計測済みで `raw/` に入っている。
size8192 の再計測は取得済みだが意図的に未取り込み。詳細は各 quarantine
ディレクトリの README。

### aoba-b_s2_smt-off size8192（不完全データ）

計測条件は無効ではないが、nb の走査範囲が計画（32-512）に届かず
20-508 止まりだった（格子充填率97%）。5トライアルとも揃っており95%帯の
判定も健全だが、格子の穴があるまま「done」扱いにしないため隔離した。
`archive/quarantine/aoba-b_s2_size8192_incomplete_2026-06/` へ退避。
i5-7400 や aoba-b_s1 と違い**測定自体は無効ではない**点に注意
（詳細は同ディレクトリの README）。
