#!/usr/bin/env python3
# 目視の一覧画像と「別の目」（yt-henshu-pipe・10/19）：書き出した動画から等間隔のコマを並べた一覧を作り、AI（claude -p）に1枚ずつ見させる
#   見ること：部品の重なり・字の切れ・字幕帯へのかぶり・読めない字・空っぽの画面・AI の透かしやロゴ・字の誤り
#   出力 <作業フォルダ>/check/ichiran-<名前>-<n>.jpg・work/me_ai.json＝{"ok": bool, "mondai": [{"t": 秒, "naiyou": …}]}
#   python3 me_ai.py <作業フォルダ> <mp4> [--n 60]
import os, sys, json, re, subprocess, io, argparse
from PIL import Image, ImageDraw, ImageFont
ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('mp4'); ap.add_argument('--n', type=int, default=60); ap.add_argument('--per-min', type=float, default=20.0); ap.add_argument('--no-ai', action='store_true'); ap.add_argument('--trace', default=None); ap.add_argument('--atama', action='store_true')
A = ap.parse_args(); P = os.path.abspath(A.proj); name = os.path.splitext(os.path.basename(A.mp4))[0]
d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', A.mp4], capture_output=True, text=True).stdout)
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 26)
A.n = max(A.n, int(-(-d * A.per_min // 60)))   # 長さに合わせて増やす：1分あたり20コマ以上（頭3分の60コマと同じ密度・team-lead 10/20）
ts = [round(d * (i + 0.5) / A.n, 2) for i in range(A.n)]
# 部品が出る途中のコマを見せない（作業AI 10/20：字が拭くように出る途中を「切れている」と数えていた）：直前0.5秒以内に出始めた部品があれば、その出始め＋0.5秒へずらす
#   出始めは門の記録（trace.json の elems）。同じ動画の記録か sha256 で確かめ、違えば・無ければずらさない（--atama で前の形）
import glob, hashlib
SHIFT = []
if not A.atama:
    tp = A.trace or next(iter(glob.glob(os.path.expanduser('~/rin6/state/yt-henshu/zettai-mon/%s-%s/trace.json' % (os.path.basename(P), name.replace('.nouhin', ''))))), None)
    kp = os.path.join(os.path.dirname(tp), 'kekka.json') if tp else None
    ok_ = False
    if tp and os.path.exists(tp) and kp and os.path.exists(kp):
        h_ = hashlib.sha256()
        with open(A.mp4, 'rb') as f_:
            for c_ in iter(lambda: f_.read(1 << 22), b''): h_.update(c_)
        ok_ = json.load(open(kp)).get('動画のsha256') == h_.hexdigest() or bool(A.trace)
    if ok_:
        st_ = sorted(x['t'] for x in json.load(open(tp))['elems'] if x.get('anim') not in (None, 'none'))
        for i, t in enumerate(ts):
            t2 = t
            for _ in range(2):   # ずらした先でまた出始めにかかれば、もう一度だけ
                near = [x for x in st_ if x <= t2 < x + 0.5]
                if not near: break
                t2 = round(max(near) + 0.5, 2)
            if t2 != t and t2 < d - 0.05: SHIFT.append((t, t2)); ts[i] = t2
        print('出る途中を避けてずらした %d / %d コマ' % (len(SHIFT), len(ts)))
    else: print('🟡 出始めの記録が無い・別の動画のもの → コマはずらさない')
def koma(t):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t, '-i', A.mp4, '-frames:v', '1', '-vf', 'scale=640:360', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(r)).convert('RGB')
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(8) as ex: ims = list(ex.map(koma, ts))
os.makedirs(os.path.join(P, 'check'), exist_ok=True); sheets = []
per = 12   # 1枚に 4×3（字が読める大きさ）
for s in range(0, len(ims), per):
    sh = Image.new('RGB', (640 * 4, 396 * 3), 'white'); dr = ImageDraw.Draw(sh)
    for k, (im, t) in enumerate(zip(ims[s:s + per], ts[s:s + per])):
        x, y = (k % 4) * 640, (k // 4) * 396; sh.paste(im, (x, y + 36)); dr.text((x + 8, y + 4), '%d:%05.2f' % (int(t // 60), t % 60), fill='black', font=F)
    fp = os.path.join(P, 'check', 'ichiran-%s-%d.jpg' % (name, s // per + 1)); sh.save(fp, quality=85); sheets.append(fp)
print('一覧 %d 枚：%s' % (len(sheets), sheets[0]))
if A.no_ai: sys.exit(0)
DP = os.path.join(P, 'input', 'daihon.txt'); DAI = open(DP, encoding='utf-8-sig').read()[:12000].replace('%', '%%') if os.path.exists(DP) else '（台本なし）'
def tanomu(shs):
  prompt = ('次の画像は、YouTube型の VSL 動画（話し手自社キャラの1人語り・アニメーションの装飾）から等間隔に取ったコマの一覧です。左上に「分:秒」。\n'
          '画像を全部 Read で開いて、1コマずつ見てください：%s\n'
          '見ること：①部品どうしが重なって字が読めない ②字が画面の端で切れている ③下の紺の字幕帯に部品がかぶっている ④字がつぶれて読めない ⑤背景だけで何も無い画面 '
          '⑥AI の透かし・生成ツールのロゴ ⑦明らかな字の誤り（同じ字の重なり・意味の通らない字）。下の紺の帯は字幕なので、それ自体は問題ではない。\n'
          '字幕の字は台本に合わせてある。台本と同じ言い回し（例「時間だけ溶けます」のような言い方）は誤りとしない。台本：\n' + DAI + '\n'
          '問題が無ければ ok を true。返事は JSON だけ：{"ok": true/false, "mondai": [{"t": "分:秒", "naiyou": "何が問題か"}]}') % ' '.join(shs)
  r = subprocess.run(['bash', os.path.expanduser('~/rin/scripts/claude-p.sh'), 'rin6', '--model', 'opus', '--allowedTools', 'Read', '--output-format', 'text'], input=prompt, capture_output=True, text=True, cwd='/tmp', timeout=1500)
  m = re.search(r'\{.*\}', r.stdout, re.S)
  try: return json.loads(m.group()) if m else None
  except Exception: return None
# 1回に見せるのは一覧5枚（60コマ）まで。長い動画は分けて並べて頼む（1回の見る量を頭3分と同じにする）
KUMI = [sheets[i:i + 5] for i in range(0, len(sheets), 5)]
# AI の判定は回すたびに揺れるので、同じ一覧を2回見せて、どちらかに出た指摘を全部拾う（作業AI 10/20・質を下げない方・AI代は2倍）
KAI = 2
with ThreadPoolExecutor(min(8, len(KUMI) * KAI)) as ex: kekka = list(ex.map(tanomu, KUMI * KAI))
def _sec(t):
    try: return sum(float(x) * 60 ** i for i, x in enumerate(reversed(str(t).split(':'))))
    except Exception: return -1
res = {'ok': True, 'mondai': []}; kaime = [[] for _ in range(KAI)]
for j, (shs, k) in enumerate(zip(KUMI * KAI, kekka)):
    if k is None: res['ok'] = False; res['mondai'].append({'t': '-', 'naiyou': '別の目の返事が読めなかった（%s・%d回目）' % (os.path.basename(shs[0]), j // len(KUMI) + 1)}); continue
    kaime[j // len(KUMI)] += k.get('mondai', [])
# 2回の指摘を秒（±1秒）で突き合わせる：両方に出た件は1件にまとめ、片方だけの件もそのまま残す
used = set(); ryou, kata = 0, [0] * KAI
for i, m in enumerate(kaime[0]):
    hit = next((jj for jj, m2 in enumerate(kaime[1]) if jj not in used and abs(_sec(m.get('t')) - _sec(m2.get('t'))) <= 1.0), None)
    if hit is None: kata[0] += 1; res['mondai'].append(dict(m, kai='1回目だけ'))
    else: used.add(hit); ryou += 1; res['mondai'].append(dict(m, kai='両方', naiyou2=kaime[1][hit].get('naiyou')))
for jj, m2 in enumerate(kaime[1]):
    if jj not in used: kata[1] += 1; res['mondai'].append(dict(m2, kai='2回目だけ'))
res['ok'] = res['ok'] and not res['mondai']
res['kasanari'] = {'1回目': len(kaime[0]), '2回目': len(kaime[1]), '両方': ryou, '1回目だけ': kata[0], '2回目だけ': kata[1]}
res['sheets'] = sheets; res['n'] = A.n; res['kai'] = len(KUMI); res['zurashi'] = SHIFT
json.dump(res, open(os.path.join(P, 'work', 'me_ai.json'), 'w'), ensure_ascii=False, indent=1)
print('別の目：', 'OK' if res.get('ok') else '直す所 %d' % len(res.get('mondai', [])))
print('別の目の2回の重なり：', json.dumps(res['kasanari'], ensure_ascii=False))
for x in res.get('mondai', [])[:20]: print('  ', x.get('t'), x.get('naiyou'))
