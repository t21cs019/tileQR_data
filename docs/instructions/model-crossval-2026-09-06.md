# 指示書: 性能モデルの交差検証基盤（第3世代の実装から）

対象リポジトリ: `tileQR_data`
起票日: 2026-09-06
起票理由: 世代間（第2〜第4世代）のモデルを同一の交差検証プロトコルで比較したい。
現状 `kurzak.py` に第4世代のフィットと LOOCV があるが、Kurzak 比較図の土台として
書かれており、モデルを差し替えて比べる器になっていない。

---

## 0. まず読む

### 第3世代は既存の `shape()` の特殊ケースである

`src/tileqr_data/kurzak.py` の `shape()` は第4世代の一般形:

```
x = c2·p^m·nb / (S0·(size/S0)^δ)
```

ここで `m=0.5, δ=1.0` とすると `S0·(size/S0)^1 = size` なので

```
x = c·√p·nb / size
```

となり、これが第3世代（`notes/performance_model.md`）そのもの。
**新しい数式を書き起こしてはならない。** 制約付きフィットとして表現する。
式を別実装すると、第4世代との差が「モデルの差」なのか「実装の差」なのか
分からなくなる。

### 壊してはいけないもの

`figures_src/fig_kurzak_p_exponent.py` と `fig_kurzak_size_exponent.py` が
`kurzak.py` に依存している。共通機械を移設したあと、この2本が**移設前と
同じ数値を出す**ことを確認すること（手順4）。

`scripts/ingest.py` `assemble.py` `validate.py` は触らない。
`derived/qr_sweep.parquet` `ssrfb.parquet` `optima.csv` は読むだけ。

### 作業前にブランチを切る

```bash
git switch -c feat/model-crossval
```

---

## 1. 完了条件

1. `src/tileqr_data/beta.py` が SSRFB から arch ごとの β 表を返す
2. `src/tileqr_data/crossval.py` に分割・指標・CV ループがあり、`kurzak.py` は
   自前で持っていた `observed` / `evaluate` / `_contiguous` / `loocv` を
   これに委譲している（重複実装が無い）
3. `src/tileqr_data/models.py` に第3世代と第4世代が登録され、
   レジストリ経由で取り出せる
4. `scripts/crossval.py` が `derived/crossval.csv` と `docs/MODEL_CROSSVAL.md` を書く
5. `python figures_src/fig_kurzak_p_exponent.py --preset slide` と
   `fig_kurzak_size_exponent.py` が移設前と同じ指数を出す
6. `python scripts/validate.py` がエラー0
7. `python scripts/ingest.py` の出力（`docs/COVERAGE.md`）が作業前と同一

### 作業前に控えを取ること

```bash
cp docs/COVERAGE.md /tmp/COVERAGE.before.md
python figures_src/fig_kurzak_p_exponent.py --preset slide 2>&1 | tee /tmp/kurzak_p.before.txt
python figures_src/fig_kurzak_size_exponent.py --preset slide 2>&1 | tee /tmp/kurzak_size.before.txt
```

---

## 2. 決定事項（ユーザー確認済み・2026-09-06）

| 論点 | 決定 |
|---|---|
| β の与え方 | **SSRFB 実測に固定。** フィットの自由パラメータにしない |
| CV 分割 | **LOO-point と leave-one-arch-out の2つ。** leave-one-size-out は今回やらない |

β を固定するのは、arch ごとの自由 β（現行 `kurzak.fit` の既定）だと
leave-one-arch-out で抜いたはずの機種の情報が β 経由で漏れ、
「未知機種のゼロショット」の主張が成立しないため。

---

## 3. 手順

### 3.1 `src/tileqr_data/beta.py`

`raw/ssrfb` → arch ごとの β を返す。

手続きは `kurzak.py` の既存関数をそのまま使う:

1. `io.load_ssrfb()` を (node, size) で割る
2. 各群を `(nb, ib)` で平均し、`kurzak.ib_rule_slice(g, rho=8.0)` で
   `ib = nb/8` の断面を作る
3. `kurzak.fit_E(nb, GFlops)` で `A·nb/(nb+β)` をフィットし β を得る
4. node → arch は `machines.yaml` の `nodes` から引く
5. **E 形に乗らない曲線を除外し、残りをアーキテクチャごとに平均する**

**除外基準（重要）。** 手順3のフィット残差 `|A·nb/(nb+β) / y - 1|` の平均（MRE）が
**5% を超える曲線を落とす**。全44曲線で見ると、健全な41本は MRE 1.9〜3.1% に
収まり、壊れている3本は 8.2 / 11.5 / 16.6% で、両者の間にきれいなギャップがある。

| 落ちる曲線 | MRE | β | 理由 |
|---|---|---|---|
| epyc size4096 | 11.5% | 342.7 | 曲線が非単調に暴れている（下記） |
| ryzen size1024 | 8.2% | 531.0 | 低 nb 側が崩れている |
| ryzen size8192 | 16.6% | 111.9 | nb=276 で走査打ち切り、n=54 |

**中央値で吸収してはならない。** 各サイズ1本の計測しかない（例外は epyc size4096、
i3-7100、par043 が5反復）ので、サイズ4点の中央値は「外れ値を1個捨てる」のと
ほぼ同義でしかなく、なぜ捨てたかが記録に残らない。MRE で落とせば判定理由が残る。

**epyc size4096 はノイズではない。** 5反復の β が 342.6 / 342.7 / 343.0 / 341.3 /
343.6 で完全に再現する。曲線を直接見ると、同一ノードの他3サイズが互いに 1% 以内で
一致してなめらかなのに対し、4096 だけが上下に飛んでいる（ib=nb/8 断面、GFlops）:

| nb | 1024 | 2048 | **4096** | 8192 |
|---|---|---|---|---|
| 64 | 15.08 | 14.94 | **8.35** | 15.01 |
| 128 | 26.03 | 26.29 | **20.35** | 26.16 |
| 192 | 32.00 | 31.64 | **34.62** | 31.90 |
| 256 | 35.54 | 35.53 | **27.18** | 35.84 |
| 448 | 42.78 | 42.64 | **34.62** | 42.57 |

ib グリッドも `ib_rule_slice` が選ぶ ib も4サイズで同一なので、断面の取り方の
問題ではない。**計測そのものが壊れている。**

**現行 `kurzak.BETA_MEASURED` の epyc = 342.7 はこの壊れた曲線から来ている。**
`notes/performance_model.md`「データ品質の注意」には i5-7400 の SSRFB 汚染しか
挙がっていないので、epyc size4096 と ryzen の2サイズを追記すること
（`tileQR_research` 側の作業。数値が確定してから）。

β 表（2026-09-06、MRE 5% 基準で除外後の平均。**ハードコードしない**）:

| arch | β |
|---|---|
| aoba-b | 186.6 |
| broadwell-e-i7-6900k | 204.7 |
| coffeelake-i5-8500 | 166.5 |
| cometlake-i3-10100 | 159.6 |
| epyc-7543 | 184.3 |
| kabylake-i3-7100 | 140.5 |
| kabylake-i5-7400 | 159.0 |
| kabylake-i7-7700 | 174.5 |
| xeon-silver-4214 | 111.5 |
| zen3-ryzen7-5800x | 182.1 |
| zen4-ryzen5-7400f | 75.9 |

`i5-7400` は `notes/performance_model.md`「データ品質の注意」でマルチスレッド
条件の汚染が疑われている。**除外はしない**が、`beta.py` が返す表に
`suspect: True` の印を持たせ、`docs/MODEL_CROSSVAL.md` の脚注に出すこと。

**`coffeelake-i3-8100` には SSRFB 計測が無い。** β 固定では扱えないので
CV 対象から落とす。落としたことを標準出力と生成文書に明示すること
（黙って 61 群が 56 群になるのが一番よくない）。`docs/TODO_REMEASURE.md` に
「i3-8100 の SSRFB 計測」を積む。

### 3.2 `src/tileqr_data/crossval.py`

`kurzak.py` から以下を**移設**する（コピーではなく移動。`kurzak.py` 側は
`from .crossval import ...` で再輸出するか、呼び出し側を書き換える）:

- `BAND` / `THR` / `_contiguous` / `observed` / `evaluate` / `loocv`
- `fit()` の中の「群ごとに振幅 A を解析消去する重み付き最小二乗」の部分

`fit()` はモデルごとにパラメータの数と束縛が違うので、
**残差の作り方だけを共通化**し、パラメータの pack/unpack はモデル側に持たせる。

追加するもの:

```python
def split_loo_point(df) -> Iterator[key]      # (config, size) を1つずつ
def split_loo_arch(df)  -> Iterator[arch]     # arch を1つずつ（その arch の全群を抜く）
def run(model, df, split, beta) -> DataFrame  # 1行 = 抜いた群1つ
```

`run()` は各フォールドで「残りで fit → 抜いた群を予測 → `evaluate()`」を回す。
評価指標は既存 `evaluate()` の5つ（`perf` / `nb_relerr` / `hit` / `recall` / `width`）
をそのまま使う。**判定規則を変えないこと。** 変えると過去の数値と比較できない。

`perf`（予測 nb での実測性能 ÷ ピーク）を主指標とする。これは点予測しか
出さないモデル（第2世代の min モデル）でも定義できる唯一の指標で、
次の指示書で第2世代を入れるときに表の軸を変えずに済む。

### 3.3 `src/tileqr_data/models.py`

レジストリ。第3・第4世代を登録する。

```python
GEN3 = CurveModel(
    name="gen3",
    doc="乗算モデル (2026-08-02). x = c·√p·nb/size",
    fixed={"m": 0.5, "delta": 1.0, "ke": 0.0},
    free=["c2", "k0"],
)
GEN4 = CurveModel(
    name="gen4",
    doc="改善C (2026-08-27). 崖位置が size^δ でスケール",
    fixed={"ke": 0.0},
    free=["c2", "m", "delta", "k0"],
)
```

第1・第2世代は点予測モデルで帯を持たないため、インタフェースが分かれる。
**今回は入れない**が、`CurveModel` を唯一の型として書かないこと。
`predict_curve` を持つものと `predict_nb` しか持たないものが並ぶ前提で設計する。

### 3.4 `scripts/crossval.py`

```bash
python scripts/crossval.py                    # 全モデル × 全分割
python scripts/crossval.py --model gen3       # 第3世代だけ
```

出力:

- `derived/crossval.csv` — 1行 = (model, split, 抜いた群, 各指標)。コミットする
- `docs/MODEL_CROSSVAL.md` — 集計表。自動生成。冒頭に生成コマンドを書く

表の形（`docs/COVERAGE.md` の書式に合わせる）:

| model | split | n | perf 平均 | perf 最悪 | 帯命中率 | recall 平均 | recall 最悪 | 探索幅比 |
|---|---|---|---|---|---|---|---|---|

---

## 4. 検証

### 4.1 図が壊れていないこと

```bash
python figures_src/fig_kurzak_p_exponent.py --preset slide 2>&1 | diff - /tmp/kurzak_p.before.txt
python figures_src/fig_kurzak_size_exponent.py --preset slide 2>&1 | diff - /tmp/kurzak_size.before.txt
python scripts/ingest.py && diff docs/COVERAGE.md /tmp/COVERAGE.before.md
```

3本とも差分が出ないこと。

### 4.2 当たり確認（2026-09-06 に既存 `kurzak.fit` で実測した値）

**実装が正しければ再現する。** 再現しなければ実装を疑うこと。
β は 3.1 の基準（MRE 5% 除外→平均）、対象は 56 群 / 10 arch。

全点フィットの定数:

| モデル | 定数 | rms |
|---|---|---|
| gen3 | `c = 2.919`, `k = 1.207`（m=0.5, δ=1.0 は固定） | 0.1006 |
| gen4 | `c2 = 6.448`, `m = 0.093`, `δ = 0.786`, `k0 = 1.711` | 0.0748 |

交差検証:

| split | model | n | perf 平均 | perf 最悪 | 帯命中率 | recall 平均 | 探索幅比 | nb 相対誤差 |
|---|---|---|---|---|---|---|---|---|
| loo_point | gen3 | 56 | 0.9531 | 0.5752 | 0.750 | 0.9070 | 0.452 | 0.201 |
| loo_point | gen4 | 56 | 0.9651 | 0.8208 | 0.714 | 0.9250 | 0.414 | 0.166 |
| loo_arch | gen3 | 56 | 0.9373 | 0.4642 | 0.696 | 0.8456 | 0.442 | 0.225 |
| loo_arch | gen4 | 56 | 0.9582 | 0.7018 | 0.714 | 0.8769 | 0.393 | 0.190 |

### 4.3 実装時に文書へ書くこと

- **第3世代の c は 2.92 で、notes の「c ≈ 2.1 が3機種で一致」と合わない。**
  当時は3機種・β の推定も別だった。10 arch・β 固定に広げると 2.9 に寄る。
- **δ = 0.786 は極めて安定。** leave-one-arch-out の10フォールドすべてで
  0.748〜0.832。notes の 0.715 とも近い。**β の与え方を変えても動かない。**
  δ が本物の効果である強い傍証になる。
- **`m`（コア数の指数）は安定しない。** 全点で 0.093 だが、aoba-b を抜くと
  0.319 に跳ね、他の9フォールドでは 0.077〜0.096。
  **p の指数は事実上 AOBA 1機種だけで決まっている**（p=64/128 は他の全機種の
  4〜32 から大きく離れており、これを抜くと高 p 側のデータが消える）。
  中間発表で p の指数を主張するなら、この一点依存を明示すること。
- **第3世代の失敗は AOBA に集中する。** leave-one-arch-out で aoba-b を抜いたとき、
  gen3 の perf は 0.787（9群平均）、最悪は size1024 で 0.464
  （予測 nb=36 に対し実測最適 nb=100）。gen3 は m=0.5（√p）を強制するので、
  p=8 から p=128 へ外挿すると崖位置を √16 = 4 倍ずれて手前に置いてしまう。
  **これが第4世代が m を自由にした理由の実測的な裏づけ**であり、
  「なめらかな積にした」だけでは足りなかったことを示す。
- **帯命中率（hit）は 0.70〜0.75 しかない。** notes が主指標に据えている
  recall（0.85〜0.93）とは別物で、こちらは「予測点が実測95%帯に入るか」。
  両方を並べて出すこと。片方だけ出すと過大にも過小にも見える。

> [!warning] 帯の指標の比較は公平でない
> `THR = 0.92` は第4世代のモデルで36点から較正した値。これを第3世代にも
> 適用しているので、`recall` と `width` の比較は第4世代に有利に働いている。
> **`perf` と `nb_relerr` は THR に依存しない**ので、世代間比較はこの2つで
> 述べること。THR の入れ子較正は5節（範囲外）。

## 5. 今回の範囲外（次の指示書）

- 第1・第2世代（点予測モデル）の登録
- leave-one-size-out
- **探索範囲しきい値 thr=0.92 の入れ子較正。** `notes/performance_model.md`
  「残る限界」にある通り、thr は現状 CV の外で全点から決めた大域ハイパー
  パラメータ。訓練フォールド側で thr を決める入れ子にすれば解消できるが、
  今回の器ができてからにする
- `tileQR_research` 側 notes の更新（数値が出てから）

---

## 6. 迷ったら

- 判定規則（`BAND=0.95`、`THR=0.92`、`observed` のピークと帯の取り方）は
  **変えない。** `scripts/ingest.py` と同じであることが前提になっている
- 最適 nb の定義は `scripts/ingest.py` だけが持つ。ここには書かない
- 除外データ（`kurzak.EXCLUDE_CONFIG` / `EXCLUDE_POINTS`）はそのまま使う。
  根拠は `notes/performance_model.md`「データ品質の注意」
