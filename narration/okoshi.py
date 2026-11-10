# 声だけを Whisper large-v3（mlx・GPU）で起こして、台本の形（1行1文）にする（答えを見ない練習で「台本」の代わりに使う）
# 使い方: .venv/bin/python okoshi.py 声.wav 出力.txt
import sys
from pathlib import Path
from common import load
import henshu as H

x = load(sys.argv[1]); out = Path(sys.argv[2]); cache = out.parent / "cache"; cache.mkdir(parents=True, exist_ok=True)
words = H.transcribe(x, cache, prompt="")          # 呼び水なし（無い「えっと」を書かせない）
out.write_text(H.words_to_script(words))
print(f"→ {out}（{len(words)}語）", file=sys.stderr)
