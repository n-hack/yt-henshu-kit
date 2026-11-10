#!/usr/bin/env python3
# 場面ごとの別の目（v14・依頼主 10/19 19:40「人間が見てわかりやすい！！がGOAL」・19:3x「スライドアニメーションじゃない」）
#   EDL の場面1つにつき、部品が出そろった終わり際のコマを1枚ずつ並べ、AI（claude -p）に「初めて見た人が一瞬で意味をつかめるか」を見させる。
#   あわせて機械で「動いているか」を測る：場面の中の3つのコマ（35%・65%・終わり際）の差が、字幕と章札を除いてほぼ0なら「止まった絵」
#   出力 check/bamen-<名前>-<n>.jpg・work/me_shot.json＝{"ok", "n", "tomatta": [...], "wakaranai": [...], "ugoki": {id: 差}}
#   python3 me_shot.py <作業フォルダ> <mp4> [--no-ai]
import os, sys, json, re, subprocess, io, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('mp4'); ap.add_argument('--no-ai', action='store_true'); ap.add_argument('--sen', type=float, default=0.8, help='止まった絵とみなす差（0〜255の平均）')
A = ap.parse_args(); P = os.path.abspath(A.proj); name = os.path.splitext(os.path.basename(A.mp4))[0]
d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', A.mp4], capture_output=True, text=True).stdout)
K = json.load(open(os.path.join(P, 'work', 'kata_v13.json')))
EDL = json.load(open(os.environ.get('PIPE_EDL_PATH') or os.path.join(P, 'work', 'edl.json')))
IMI = {s.get('id'): s for s in EDL['shots']}
sh_ = [x for x in K['kirikae'] if x.get('id')]
shots = []
for i, x in enumerate(sh_):
    t0 = x['t']; t1 = sh_[i + 1]['t'] if i + 1 < len(sh_) else d - 0.05
    shots.append((x['id'], t0, t1))
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 22)
def koma(t, w=640, h=360):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t, '-i', A.mp4, '-frames:v', '1', '-vf', 'scale=%d:%d' % (w, h), '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(r)).convert('RGB')
def mask(im):
    a = np.asarray(im.convert('L'), np.float32); h, w = a.shape
    a = a[int(h * 0.09):int(h * 0.86), :]   # 上の章札の帯と下の字幕帯は除く（字幕は言葉で替わるので「動き」に数えない）
    return a
def one(s):
    sid, t0, t1 = s; L = t1 - t0
    ts = [t0 + L * 0.35, t0 + L * 0.65, max(t0 + 0.05, t1 - 0.12)]
    ims = [koma(t, 320, 180) for t in ts]
    df = max(float(np.abs(mask(ims[0]) - mask(ims[1])).mean()), float(np.abs(mask(ims[1]) - mask(ims[2])).mean()))
    return sid, t0, t1, df, koma(ts[-1])
with ThreadPoolExecutor(8) as ex: R = list(ex.map(one, shots))
tomatta = [{'id': sid, 't': round(t0, 2), 'sa': round(df, 2)} for sid, t0, t1, df, _ in R if df < A.sen and t1 - t0 >= 0.8]
os.makedirs(os.path.join(P, 'check'), exist_ok=True); sheets = []
per = 12
for s in range(0, len(R), per):
    sh = Image.new('RGB', (640 * 4, 430 * 3), 'white'); dr = ImageDraw.Draw(sh)
    for k, (sid, t0, t1, df, im) in enumerate(R[s:s + per]):
        x, y = (k % 4) * 640, (k // 4) * 430; sh.paste(im, (x, y + 64))
        imi = (IMI.get(sid, {}).get('imi') or '')[:26]
        dr.text((x + 6, y + 2), '%s %d:%05.2f  %s' % (sid, int(t0 // 60), t0 % 60, '止' if df < A.sen else ''), fill='black', font=F)
        dr.text((x + 6, y + 32), '意味：' + imi, fill='#444444', font=F)
    fp = os.path.join(P, 'check', 'bamen-%s-%d.jpg' % (name, s // per + 1)); sh.save(fp, quality=85); sheets.append(fp)
print('場面 %d・一覧 %d 枚・止まった絵 %d（%s）' % (len(R), len(sheets), len(tomatta), sheets[0] if sheets else ''))
res = {'n': len(R), 'sheets': sheets, 'tomatta': tomatta, 'ugoki': {sid: round(df, 2) for sid, t0, t1, df, _ in R}, 'wakaranai': []}
if not A.no_ai:
    def ask(group):
        prompt = ('次の画像は、アニメーションの YouTube 動画（VSL）の場面ごとのコマを並べた一覧です。1マスが1場面。上に「場面の番号 分:秒」と「意味：この場面で伝えたいこと」。\n'
                  '画像を全部 Read で開き、1マスずつ見てください：%s\n'
                  '判定：その場面を初めて見た人が、絵だけで「意味：」の中身を一瞬でつかめるか。○＝一瞬で分かる／△＝少し考えないと分からない・絵と意味がずれている／×＝分からない。\n'
                  '分かりにくい例：黒い単色アイコンを並べて文字で説明するだけ・アイコン入りの箱を並べて比べるだけ・アイコン3つを矢印でつなぐだけ。'
                  '分かりやすい例：表情のある色付きの人物（悩む・驚く・喜ぶ）と大きな立体文字で気持ちや状況が一目で分かる。下の紺の帯は字幕なので判定に入れない。\n'
                  '返事は JSON だけ：{"hantei": [{"id": "場面の番号", "kekka": "○|△|×", "riyuu": "△×のときだけ・何が分かりにくく、どう見せれば一瞬で分かるか"}]}') % ' '.join(group)
        r = subprocess.run(['bash', os.path.expanduser('~/rin/scripts/claude-p.sh'), 'rin6', '--model', 'opus', '--allowedTools', 'Read', '--output-format', 'text'], input=prompt, capture_output=True, text=True, cwd='/tmp', timeout=1800)
        m = re.search(r'\{.*\}', r.stdout, re.S)
        try: return json.loads(m.group())['hantei']
        except Exception: return [{'id': '-', 'kekka': '×', 'riyuu': '別の目の返事が読めなかった：' + r.stdout[-200:]}]
    groups = [sheets[i:i + 4] for i in range(0, len(sheets), 4)]
    with ThreadPoolExecutor(3) as ex: H = [h for g in ex.map(ask, groups) for h in g]
    res['hantei'] = H; res['wakaranai'] = [h for h in H if h.get('kekka') != '○']
    res['maru'] = sum(1 for h in H if h.get('kekka') == '○')
res['ok'] = not tomatta and not res['wakaranai']
json.dump(res, open(os.path.join(P, 'work', 'me_shot.json'), 'w'), ensure_ascii=False, indent=1)
print('場面の別の目：', 'OK' if res['ok'] else '止まった絵 %d・分かりにくい %d' % (len(tomatta), len(res['wakaranai'])))
for x in (tomatta + res['wakaranai'])[:30]: print('  ', x)
