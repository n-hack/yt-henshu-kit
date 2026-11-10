#!/usr/bin/env python3
# 文字起こし → 場面表の【下書き】を自動で作る（どのジャンルでも同じ）。
#   python3 build/daihon_draft.py <words.json> <出力 story.json> --theme themes/xxx.json --audio src/xxx.m4a [--start 0 --end 180]
#   1文ずつ読み、言葉の形で場面の型を選ぶ:
#     数字＋単位（万・%・円・倍・ヶ月・年・人・社…）→ headline（数字を大きく赤く）
#     「〜とか」「、」で2つ以上並ぶ               → list（チェックの並び）
#     「〜しよう」「〜でしょ」など話し言葉の引用  → dialogue（人物＋吹き出し）
#     問いかけ（〜か？ なぜ・どうやって）          → marker（黄色いマーカーの見出し）
#     それ以外                                  → marker と photo を交互（photo は素材の注文も下書きに書く）
#   どの場面も say（話し始めの言葉）で時刻を合わせるので、秒は書かない。字幕は auto。
#   ★下書きは「並べる」まで。見出しの言い回し・強調の場所・絵の選び方は人（作業AI）が直して仕上げる。
import sys, json, re, argparse
ap = argparse.ArgumentParser()
ap.add_argument('words'); ap.add_argument('out')
ap.add_argument('--theme', default='themes/insta-chara.json'); ap.add_argument('--audio', required=True)
ap.add_argument('--start', type=float, default=None); ap.add_argument('--end', type=float, default=None)
ap.add_argument('--min_scene', type=float, default=3.0, help='これより短い文は前の場面にまとめる（秒）')
A = ap.parse_args()
W = json.load(open(A.words))
if A.start is not None: W = [w for w in W if w[0] >= A.start]
if A.end is not None: W = [w for w in W if w[0] < A.end]

FILL = ['えー', 'えっと', 'あの', 'まあ', 'やっぱり', 'ですね', 'ね、', 'っていう', 'というふうに', 'というふうに', 'なんですけど', 'なんですよ',
        'と思います', 'と思うんですけど', 'と思うので', 'んですよね', 'んですね', 'ですけど', '実際に', 'ぶっちゃけ', '今回ね', '本当に']
def clean(s):
    for f in FILL: s = s.replace(f, '')
    s = re.sub(r'[、，]{2,}', '、', s).strip('、。 ')
    return s

def wrap(s, n=14):
    s = s.replace('。', '')
    out = []; cur = ''
    for part in re.split(r'(、)', s):
        if len(cur) + len(part) > n and cur: out.append(cur.rstrip('、')); cur = part.lstrip('、')
        else: cur += part
    if cur: out.append(cur.rstrip('、'))
    lines = []
    for l in out:
        while len(l) > n: lines.append(l[:n]); l = l[n:]
        if l: lines.append(l)
    return '\n'.join(lines[:3])

# 文に分ける
sents = []; cur = [];
for i, w in enumerate(W):
    cur.append(w)
    end = re.search(r'[。！？!?]$', w[2].strip()) or (i + 1 < len(W) and W[i + 1][0] - w[1] > 0.8)
    if end: sents.append(cur); cur = []
if cur: sents.append(cur)
S = [dict(t0=s[0][0], t1=s[-1][1], text=''.join(x[2].strip() for x in s), first=''.join(x[2].strip() for x in s[:4])) for s in sents]
# 短い文は前にまとめる
M = []
for s in S:
    if M and (s['t1'] - s['t0'] < A.min_scene or M[-1]['t1'] - M[-1]['t0'] < A.min_scene):
        M[-1]['text'] += s['text']; M[-1]['t1'] = s['t1']
    else: M.append(dict(s))

NUM = re.compile(r'(\d[\d,\.]*)\s*(万|億|千|%|％|円|倍|ヶ月|か月|カ月|年|日|人|社|件|回|個|本|位|割)')
QUOTE = re.compile(r'(しよう|やろう|でしょ|じゃん|やん|なんで|って言われ|って思)')
QUESTION = re.compile(r'(なぜ|なんで|どうやって|どうすれば|どういう|何を|か[？?]|のか)')
scenes = [{"type": "logo", "at": round(M[0]['t0'] - 0.7, 2) if M[0]['t0'] > 0.7 else 0}] if M and M[0]['t0'] > 0.7 else []
assets = {}
alt = 0
for k, s in enumerate(M):
    say = s['first']; txt = clean(s['text'])
    m = NUM.search(s['text'])
    items = [clean(x) for x in re.split(r'とか[、,]?|、', s['text']) if len(clean(x)) >= 4]
    if m:
        n = m.group(0)
        head = clean(s['text'][:s['text'].find(n)])[-14:]
        scenes.append({"type": "headline", "say": say, "lines": [
            {"text": head or '結論', "say": say, "size": 92, "marker": True},
            {"text": "<hugr>%s</hugr>" % n, "say": n[:2], "size": 120, "pop": True}]})
    elif s['text'].count('とか') >= 2 and len(items) >= 2:
        scenes.append({"type": "list", "say": say, "icon": "check", "items": [{"text": it[:24], "say": it[:4]} for it in items[:5]]})
    elif QUOTE.search(s['text']):
        p = 'p_auto_%d' % (len(assets) + 1)
        assets[p] = {"kind": "person", "prompt": "上半身。この台詞を言っている人：「%s」。年齢・性別・服装は台詞に合わせて自然に。" % txt[:40]}
        scenes.append({"type": "dialogue", "say": say, "rows": [{"person": p, "text": wrap(txt, 16), "color": ["orange", "blue", "green", "purple"][k % 4], "say": say}]})
    elif QUESTION.search(s['text']) or alt % 2 == 0:
        scenes.append({"type": "marker", "say": say, "text": wrap(txt, 12)})
        alt += 1
    else:
        ph = 'ph_auto_%d' % (len(assets) + 1)
        assets[ph] = {"kind": "photo", "prompt": "この話の場面を表す写真：「%s」" % txt[:60]}
        scenes.append({"type": "photo", "say": say, "photo": ph, "subs_hint": txt})
        alt += 1

story = {"_説明": "daihon_draft.py が作った下書き。見出しの言い回し・強調・絵を直して仕上げる",
         "audio": A.audio, "words": A.words, "theme": A.theme,
         "start": A.start if A.start is not None else 0, "end": A.end if A.end is not None else round(W[-1][1] + 1, 2),
         "assets": assets, "scenes": scenes, "subs": "auto"}
json.dump(story, open(A.out, 'w'), ensure_ascii=False, indent=1)
from collections import Counter
print('場面 %d（%s）／ 素材の注文 %d' % (len(scenes), dict(Counter(s['type'] for s in scenes)), len(assets)))
