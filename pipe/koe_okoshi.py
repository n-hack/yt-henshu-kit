#!/usr/bin/env python3
# 声の書き起こし（単語の時刻つき）を、間で切った20秒前後のかたまりごとに起こす（yt-henshu-pipe・10/19）
#   ~/rin6/tools/yt-henshu/narration/.venv/bin/python koe_okoshi.py <作業フォルダ>
#   通しで起こすと声のある所が抜け、作り事（「ご視聴ありがとうございました」）が出た（10/19 面談前VSL・kiru_zen.py の注）。
#   そこで 0.25秒以上の静かな所で切ったかたまり（最大24秒）ごとに Whisper large-v3（mlx・GPU）で起こし、時刻を足し戻す。
#   声の無い所に置かれた言葉（かたまりの中で、その言葉の時間の声の大きさが −45dB 未満）と、台本に無い決まり文句の作り事は捨てる。
#   出力 work/whisper_words.json＝[{"w","s","e"}]（align/kotoba_align.py と同じ形）
import os, sys, json, re, subprocess
import numpy as np, mlx_whisper
P = sys.argv[1]
SR = 16000
x = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(P, 'work', 'vocals.wav'), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
a = np.frombuffer(x, np.int16).astype(np.float32) / 32768
n10 = len(a) // 160
db = 20 * np.log10(np.sqrt((a[:n10 * 160].reshape(n10, 160) ** 2).mean(1)) + 1e-9)
quiet = db < -40
# 切れ目の候補：0.25秒以上続く静かな所のまん中
cands = []; s = None
for i, q in enumerate(quiet):
    if q and s is None: s = i
    if not q and s is not None:
        if i - s >= 25: cands.append((s + i) // 2)
        s = None
cuts = [0]
for c in cands + [n10]:
    while c - cuts[-1] > 2400:                          # 24秒を超えるなら、その手前の静かな所（無ければ24秒の所）で切る
        prev = [d for d in cands if cuts[-1] + 600 < d < cuts[-1] + 2400]
        cuts.append(prev[-1] if prev else cuts[-1] + 2400)
    if c - cuts[-1] >= 1200 and c < n10: cuts.append(c)   # 12秒を過ぎた最初の静かな所で切る
cuts.append(n10)
HALL = re.compile(r'ご視聴ありがとうございました|チャンネル登録|おやすみなさい|字幕|by H')
daihon = ''
for f in ('daihon.txt', 'daihon-seihon.txt'):
    p = os.path.join(P, 'input', f)
    if os.path.exists(p): daihon = open(p, encoding='utf-8-sig').read(); break
def okosu(c0, c1):
    """かたまり [c0, c1)（10ms 単位）を起こす → (言葉, 捨てた, 声があるのに言葉の無い秒)"""
    seg = a[c0 * 160:c1 * 160]; ws, dr = [], []
    r = mlx_whisper.transcribe(seg, path_or_hf_repo='mlx-community/whisper-large-v3-mlx', language='ja', word_timestamps=True, condition_on_previous_text=False)
    for sg in r['segments']:
        txt = sg.get('text', '')
        if HALL.search(txt) and not HALL.search(daihon): dr.append((round(c0 / 100 + sg['start'], 2), txt)); continue
        for w in sg.get('words', []):
            ww = w['word'].strip()
            if not ww: continue
            s_, e_ = c0 / 100 + float(w['start']), c0 / 100 + float(w['end'])
            i0, i1 = int(s_ * 100), max(int(s_ * 100) + 1, int(e_ * 100))
            if db[i0:i1].max() < -45: dr.append((round(s_, 2), ww)); continue
            ws.append({'w': ww, 's': round(s_, 3), 'e': round(e_, 3)})
    cov = np.zeros(c1 - c0, bool)
    for w in ws: cov[max(0, int(w['s'] * 100) - c0 - 30):max(0, int(w['e'] * 100) - c0 + 30)] = True
    nuke = float(((db[c0:c1] > -32) & ~cov).sum()) / 100   # 声があるのに言葉が無い秒（言葉の前後0.3秒は覆ったとみなす）
    return ws, dr, nuke
def okosu_r(c0, c1, depth=0):
    """抜けが1秒を超えたら、かたまりのまん中に近い静かな所で2つに割って起こし直し、抜けの少ない方を取る（10/19：通しの起こしで 467〜481秒の言葉が抜けた）"""
    ws, dr, nuke = okosu(c0, c1)
    if nuke <= 1.0 or depth >= 3 or c1 - c0 < 400: return ws, dr, nuke
    mid = (c0 + c1) // 2; qs = [d for d in cands if c0 + 150 < d < c1 - 150]
    m = min(qs, key=lambda d: abs(d - mid)) if qs else mid
    w1, d1, n1 = okosu_r(c0, m, depth + 1); w2, d2, n2 = okosu_r(m, c1, depth + 1)
    if n1 + n2 < nuke: return w1 + w2, d1 + d2, n1 + n2
    return ws, dr, nuke
W = []; dropped = []; NUKE = []
for k in range(len(cuts) - 1):
    c0, c1 = cuts[k], cuts[k + 1]
    if c1 - c0 < 15 or db[c0:c1].max() < -40: continue
    ws, dr, nuke = okosu_r(c0, c1)
    W += ws; dropped += dr
    if nuke > 1.0: NUKE.append((c0 / 100, c1 / 100, nuke))
W.sort(key=lambda w: w['s'])
json.dump(W, open(os.path.join(P, 'work', 'whisper_words.json'), 'w'), ensure_ascii=False)
json.dump({'cuts_sec': [c / 100 for c in cuts], 'dropped': dropped, 'nuke': NUKE}, open(os.path.join(P, 'work', 'whisper_kizami.json'), 'w'), ensure_ascii=False)
print('かたまり %d ／ 単語 %d ／ 捨てた %d ／ 抜けが残るかたまり %d（%s）／ %.1f秒' % (len(cuts) - 1, len(W), len(dropped), len(NUKE), NUKE, len(a) / SR))
