#!/usr/bin/env python3
# 文字起こし（言葉ごとの時刻つき）。どの音声でも同じ。
#   python3 build/mojiokoshi.py <音声または動画> <出力フォルダ> [開始秒 終わり秒]
#   → <出力>/words.json（[開始, 終わり, 言葉] の並び）と <出力>/text.txt（読む用）
#   whisper large-v3-turbo（このMacに入っている・CPUで3分の音声に約5分）。抜けた所は同じ道具で区間だけやり直せる。
import sys, os, json, subprocess, tempfile
src, out = sys.argv[1], sys.argv[2]
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)
wav = os.path.join(out, 'audio16k.wav')
cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', str(t0), '-i', src]
if t1: cmd += ['-t', str(t1 - t0)]
subprocess.run(cmd + ['-vn', '-ac', '1', '-ar', '16000', wav], check=True)
subprocess.run(['/opt/homebrew/bin/whisper', wav, '--model', os.environ.get('WHISPER_MODEL', 'large-v3-turbo'), '--language', 'ja',
                '--word_timestamps', 'True', '--output_format', 'json', '--output_dir', out, '--fp16', 'False'],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = json.load(open(os.path.join(out, 'audio16k.json')))
words = [[round(w['start'] + t0, 3), round(w['end'] + t0, 3), w['word']] for s in d['segments'] for w in s.get('words', [])]
json.dump(words, open(os.path.join(out, 'words.json'), 'w'), ensure_ascii=False)
with open(os.path.join(out, 'text.txt'), 'w') as f:
    for s in d['segments']: f.write('%7.2f %7.2f %s\n' % (s['start'] + t0, s['end'] + t0, s['text']))
# 話しているのに言葉が無い区間（whisper の取りこぼし）を知らせる
gaps = [(a[1], b[0]) for a, b in zip(words, words[1:]) if b[0] - a[1] > 2.5]
print('言葉 %d 個 ／ %.1f〜%.1f秒' % (len(words), words[0][0], words[-1][1]))
for a, b in gaps: print('  2.5秒以上の空き %.1f〜%.1f（取りこぼしなら: mojiokoshi.py で区間だけやり直す）' % (a, b))
