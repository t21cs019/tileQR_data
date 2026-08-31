"""
コンソール出力の文字コード。

Windows のコンソールは既定で cp932 になる。このリポジトリのスクリプトは
出力もコメントも日本語で、表に `—` や `▶` を使うため、そのままだと
`UnicodeEncodeError` で落ちる。しかも落ちるのは処理が全部終わって
print する段なので、「動いたのに最後だけ失敗する」という分かりにくい壊れ方をする。

各スクリプトに同じ4行を貼ると、新しいスクリプトで貼り忘れて同じことが起きる。
ここ1箇所に置いて `use_utf8()` を呼ぶ。

副作用をモジュール読み込み時ではなく関数呼び出しにしてあるのは、
ライブラリとして import しただけで標準出力の設定が変わるのを避けるため。
"""

from __future__ import annotations

import sys


def use_utf8() -> None:
    """標準出力・標準エラーを UTF-8 に固定する。スクリプトの先頭で呼ぶ。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
