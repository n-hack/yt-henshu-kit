#!/usr/bin/env python3
# 声の文字起こし（単語の時刻つき）：~/rin6/tools/yt-henshu/narration/.venv/bin/python whisper_words.py <作業の場>
#   work/vocals.wav を Whisper large-v3（mlx・GPU）で起こし、work/whisper_words.json に [{"w","s","e"}] で書く。
#   台本と言い回しが違う所でも、実際に話した字で声に貼るため（kotoba_align.py が使う）
import os, sys, json, subprocess
import numpy as np, mlx_whisper
P = sys.argv[1]
x = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(P, 'work', 'vocals.wav'), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True).stdout
a = np.frombuffer(x, np.int16).astype(np.float32) / 32768
r = mlx_whisper.transcribe(a, path_or_hf_repo='mlx-community/whisper-large-v3-mlx', language='ja', word_timestamps=True, condition_on_previous_text=False)
W = [{'w': w['word'].strip(), 's': round(float(w['start']), 3), 'e': round(float(w['end']), 3)} for s in r['segments'] for w in s.get('words', []) if w['word'].strip()]
json.dump(W, open(os.path.join(P, 'work', 'whisper_words.json'), 'w'), ensure_ascii=False)
print('単語 %d ／ %.1f秒' % (len(W), len(a) / 16000))
