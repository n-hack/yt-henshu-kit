# 声は編集せず、文と言葉の時刻だけ取る（答えを見ない練習用：元の動画の声の時間軸のまま演出を決めるため）
#   whisper large-v3 で起こし、台本の文と並べて jikoku.json を書く。henshu.wav は元の声をそのまま 48kHz にしたもの
# 使い方: .venv/bin/python jikoku_only.py 声.wav 台本.txt 出力フォルダ
import json, sys
from pathlib import Path
from common import SR, load, save, kana, split_sentences
import henshu as H

audio, script, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True); cache = out / "cache"; cache.mkdir(exist_ok=True)
x = load(audio); save(out / "henshu.wav", x)
sents = split_sentences(Path(script).read_text())
for s in sents: s["k"] = kana(s["text"])
H.assign_sections(sents)
tm = H.verify(out / "henshu.wav", sents, cache)
json.dump(tm, open(out / "jikoku.json", "w"), ensure_ascii=False, indent=1)
json.dump({"input": audio, "script": script, "dur_in": round(len(x) / SR, 2), "dur_out": round(len(x) / SR, 2), "as_is": True,
           "deleted": [], "speed": {"factor": 1.0}, "missing": [s["text"] for s in tm["sentences"] if not s["found"]]},
          open(out / "kiroku.json", "w"), ensure_ascii=False, indent=1)
print(f"→ {out}/jikoku.json（{len(sents)}文・見つからない {sum(1 for s in tm['sentences'] if not s['found'])}）", file=sys.stderr)
