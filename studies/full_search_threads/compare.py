#!/usr/bin/env python3
"""
archive/attic/Full_search_dgeqrf/（学部時代・スレッド数不明）を
2026-08-30 の dogwood th=8 実測と突き合わせ、当時のスレッド数を推定する。

--- 位置づけ ----------------------------------------------------------

**参考情報であって証明ではない。** 当時の PLASMA ビルド・BLAS・メモリ構成が
違う可能性があり、GFlops の水準比較はそれらと交絡する。i5-7400 で
「形状は健全に見えるが記録が無いので落とす」とした基準はここでも変えない。
この結果がどちらに転んでも、archive/attic のデータを raw/ に上げる根拠にはしない。

--- 判定の材料 --------------------------------------------------------

i7-6900K は 8C/16T。候補は th=8（SMT 不使用相当）か th=16（SMT 使用）。

1. GFlops の水準  th8 実測との比。SMT の有無は tile QR の到達性能を
   1〜2割動かすのが相場なので、比が 1 に近ければ th8 寄り。
2. 曲線の形      nb ごとに ib 最適化した曲線の相関と、最適 nb の位置。
   スレッド数が違うと並列度が変わり、最適 nb がずれる。

使い方:
    python studies/full_search_threads/compare.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tileqr_data import console  # noqa: E402

console.use_utf8()

OLD = ROOT / "archive" / "attic" / "Full_search_dgeqrf" / "benchmark_dtsmqr_4096.csv"
NEW_DIR = ROOT / "raw" / "qr_sweep" / "dogwood_s1_smt-off"


def best_over_ib(df: pd.DataFrame) -> pd.Series:
    """各 nb について ib を最適化した GFlops。index=nb。"""
    return df.groupby("nb")["GFlops"].max()


def main() -> int:
    old = pd.read_csv(OLD)  # size,nb,ib,GFlops（threads 列なし）

    news = sorted(NEW_DIR.glob("dogwood_size4096_t8_*.csv"))
    if not news:
        print(f"エラー: {NEW_DIR} に th8 size4096 の実測が無い", file=sys.stderr)
        return 1
    new = pd.concat([pd.read_csv(p) for p in news], ignore_index=True)
    # 反復は平均で畳む（ingest.py と同じ方針。最大だと上振れを拾う）
    new = new.groupby(["nb", "ib"], as_index=False)["GFlops"].mean()

    old_curve = best_over_ib(old)
    new_curve = best_over_ib(new)

    common = sorted(set(old_curve.index) & set(new_curve.index))
    o = old_curve.loc[common]
    n = new_curve.loc[common]
    ratio = o / n

    print(f"旧: {OLD.relative_to(ROOT)}  ({len(old):,} 点, "
          f"nb {old['nb'].min()}-{old['nb'].max()})")
    print(f"新: dogwood th8 size4096 x {len(news)} 本の平均 "
          f"(nb {new['nb'].min()}-{new['nb'].max()})")
    print(f"共通 nb: {len(common)} 点 ({common[0]}-{common[-1]})\n")

    print("--- ib 最適化後の曲線の比較（旧 / 新th8） ---")
    print(f"  比の中央値   : {ratio.median():.3f}")
    print(f"  比の範囲     : {ratio.min():.3f} - {ratio.max():.3f}")
    print(f"  ピーク GFlops: 旧 {o.max():.1f} (nb={o.idxmax()})  /  "
          f"新th8 {n.max():.1f} (nb={n.idxmax()})")
    print(f"  形の相関     : {o.corr(n):.4f}")

    # nb の帯域ごとの比。スレッド数が違うと nb 依存の形で割れるはず
    print("\n--- nb 帯域ごとの比の中央値 ---")
    for lo, hi in [(32, 128), (132, 256), (260, 384), (388, 512)]:
        band = ratio[(ratio.index >= lo) & (ratio.index <= hi)]
        if len(band):
            print(f"  nb {lo:3d}-{hi:3d}: {band.median():.3f}  ({len(band)} 点)")

    print(
        "\n※ 参考情報。当時の PLASMA ビルド / BLAS / メモリ構成が違う可能性が\n"
        "   あり、水準の比較はそれらと交絡する。raw/ への昇格根拠にはしない。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
