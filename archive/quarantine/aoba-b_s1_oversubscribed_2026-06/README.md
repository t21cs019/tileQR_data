# aoba-b_s1_smt-off — 2026-06〜09計測分（16コアへのオーバーサブスクリプション）

## 何のデータか

AOBA-B（AMD EPYC 7702、`aoba-b` architecture）の `aoba-b_s1_smt-off` 系列。
qr_sweep（PLASMA dgeqrf の nb×ib スイープ）、size 2048 / 4096 / 8192 / 16384、
2026-06〜09 に計測。`raw_data/aoba-b_s1_smt-off/` にあったファイルをそのまま
このディレクトリへ退避した（`git mv`、削除はしていない）。

## なぜ隔離したか

計測コマンドは次のとおりで、`--threads 64` を指定していた。

```bash
numactl --cpunodebind=0 --membind=0 \
    bash run_benchmark.sh --size ... --threads 64
```

AOBA-B の計算ノードは NUMA が **NPS4**（2ソケット x 8 NUMAノード、
1ノード=16コア）で構成されている。`--cpunodebind=0` は NPS4 では
**NUMAノード0 = CPU 0-15 の16コア**しか割り当てない。つまりこの計測は
64スレッドを16コアに載せた**4倍オーバーサブスクリプション**状態だった。

ファイル名・CSVの `threads` 列の `64` は「起動したスレッド数」であって
「使用した物理コア数」ではない。この区別が無かったことが発覚を遅らせた。

保存されていた `lscpu.txt`（NUMAノード数2）は**ログインノード**のもので、
計算ノードの構成ではない。ログインノードは NPS1、計算ノードは NPS4。
これを計算ノードのものと誤読したことが発見をさらに遅らせた。

### 検証（2026-09-05, par057）

同一ノードで3通りのバインドを比較（size=4096, threads=64, nb=264）。

| 指定 | 実際に掴んだコア | ピーク GFlops |
|---|---|---|
| `--cpunodebind=0`（6月と同じ） | **16** | 316.2 |
| `--cpunodebind=0-3` | 64 | 461.0 |
| `numactl` なし | 64スレッドを128コアに分散 | 458.8 |

`numactl --cpunodebind=0 --membind=0 --show` の出力が `physcpubind: 0 1 ... 15`
であることを直接確認済み。

6月の5ノード（par001/002/003/004/006）の size=4096 ピークは 297.98〜316.94。
今日の16コア版 316.2 と一致する。nb=264 における ib プロファイル16点すべてで
比が 1.04〜1.14（ノード個体差 +7% の範囲内）。64コア版とは1.5〜1.6倍離れている。

## 影響しないもの

- `aoba-b_s2_smt-off`（threads=128）は `numactl` を使わず128コアに128スレッド。**有効**。
- ssrfb / kernel_dtsmqr の計測は threads=1 なので**無関係**。
- AOBA以外の全機材は無関係。

## 再利用の条件

p（物理コア数）を **16** として扱うなら分析に使える可能性はある。ただし
4倍オーバーサブスクリプションは通常の p=16 実行（1スレッド/コア）とは
別条件であり、そのまま `p=16` のデータとして混ぜてはならない。使う場合は
必ず「oversubscribed 4x」であることを明示すること。

参考: p=16 と置いて s1/s2 の nb_opt 比から m を逆算すると、size 8192 で
m ≈ 0.235、size 4096 で m ≈ 0.32 となり、現行フィット値 0.240 と整合する。
この一致自体が16コア説の傍証になっている。

## 再取り込みする場合

`raw_data/` は `scripts/assemble.py raw_data` で1階層下（`raw_data/*/*.csv`）
しか走査しないため、このディレクトリはそのままでは対象に入らない。再利用する
際は `raw_data/` 直下にコピーし直すか、`assemble.py` の呼び出し元を明示的に
このディレクトリへ向けること。その際は必ず本 README の「再利用の条件」を
読み、config 名を `aoba-b_s1_smt-off` と混同しないこと（訂正後の
`aoba-b_s1_smt-off` は `--cpunodebind=0-3` の64コア版であり別条件）。

## 経緯

- 起票: 2026-09-05
- 訂正後の `aoba-b_s1_smt-off`（`spec/machines.yaml`）は `numactl: "--cpunodebind=0-3 --membind=0"`、
  `cores_effective: 64` に更新済み。
- **2026-09-05: size1024/2048/4096/8192 の再計測完了。** 正しい構成
  （`--cpunodebind=0-3`、64コア）でNQSVジョブを実行し、`raw/` に反映済み
  （`docs/COVERAGE.md` で該当4サイズが `done`）。
- **2026-09-06: size16384 も完了。** `aoba-b_s1_smt-off` は全5サイズ
  解消済み（正しい構成で再計測しdocs/COVERAGE.mdで5/5）。
- 再計測項目は `docs/TODO_REMEASURE.md` を参照。
