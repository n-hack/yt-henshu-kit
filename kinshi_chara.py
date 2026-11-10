#!/usr/bin/env python3
"""使ってはいけないキャラ（自社キャラの頭＋線の体の「棒人間」）が動画に1コマでも出たら止める。
依頼主 10/20 23:45（#報告の部屋）「この棒人間みたいなやつ、マジで致命的だから本当に一生使わないでください」。
  ① ファイル：門が開いた素材のファイルを kinshi.json の sha256・名前（chara_*／shibai_chara_*）と突き合わせる
  ② 見た目：動画の全コマ（既定は1コマおき）で、顔の見本（kata/kao.png・×の目と笑った口）を大きさを変えて探す
使い方：python3 kinshi_chara.py <mp4> [--step 1] [--out kekka.json]   終わりのコード 0＝出ない／1＝出た
"""
import os, sys, json, hashlib, argparse, subprocess
import numpy as np, cv2

K = os.path.expanduser('~/rin6/state/yt-henshu/kinshi/chara-boujin')
SEN = float(os.environ.get('KINSHI_SEN', '0.80'))   # 似ている度合いの線（試験で決めた・README の試験結果）
KATA_NAMES = ('eri2', 'eri1')   # 10/21：顔の見本（kao・me2）は3Dの自社キャラアイコン（ルール6で使う）も止めたので外し、体（襟とフードのひも）だけで見る
SENS = json.loads(os.environ.get('KINSHI_SENS', '{}')) or {'eri2': 0.65, 'eri1': 0.65}   # 10/21 試験：手本15本（頭171秒）の最大 0.562/0.570・3Dの自社キャラアイコン 0.42（止めない）・部品77本は68本が線を超える（漏れ9本は名前とハッシュの門で止まる）
W, H = 640, 360
_KATA = None


def kata():
    global _KATA
    if _KATA is None:
        out = []
        for nm in KATA_NAMES:   # 顔（×の目と口）・目だけ（口の形は場面で変わる）・襟とフードのひも（体）。⑤の書き出しと部品の見本の両方から切った
            k = cv2.imread(os.path.join(K, 'kata', nm + '.png'), cv2.IMREAD_GRAYSCALE)
            base = k.shape[0] / (3.0 if nm in ('kao', 'me') else 1.9)   # ⑤の見本は 1920 幅から（640 幅で 1/3）・部品の見本は 1220 幅から（1/1.9）
            for s in [0.3 * 1.08 ** i for i in range(31)]:   # 0.3〜3.0 倍を 8% きざみ（きざみが粗いと同じ絵でも似ている度合いが 0.6 台に落ちた・10/21 試験）
                h = int(round(base * s)); w = int(round(k.shape[1] / k.shape[0] * h))
                if h < 10 or w < 14 or h > H - 4 or w > W - 4: continue
                out.append((nm, cv2.resize(k, (w, h), interpolation=cv2.INTER_AREA)))
        _KATA = out
    return _KATA


def kinshi_list():
    p = os.path.join(K, 'kinshi.json')
    return json.load(open(p)) if os.path.exists(p) else {'files': [], 'prefix': ['chara_', 'shibai_chara_']}


def files_check(files):
    """門が開いたファイルの中に禁止の物があるか（sha256 か 名前）"""
    L = kinshi_list(); hs = {f['sha256'] for f in L.get('files', [])}; pre = tuple(L.get('prefix', []))
    bad = []
    for f in files:
        b = os.path.basename(f)
        if (b.startswith(pre) and '/jinbutsu/' in f) or b.startswith(('jimon_chara', 'chara_line', 'chara_flat')): bad.append((f, '名前')); continue
        try:
            if os.path.isfile(f) and os.path.getsize(f) < 400_000_000 and hashlib.sha256(open(f, 'rb').read()).hexdigest() in hs: bad.append((f, 'sha256'))
        except Exception: pass
    return bad


def video_check(mp4, step=2, t0=0.0, t1=None):
    """全コマ（step おき）で顔を探す。見つかったコマの秒と似ている度合いを返す"""
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', mp4] + (['-t', str(t1 - t0)] if t1 else []) + ['-vf', 'scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=gray,format=gray' % (W, H, W, H), '-f', 'rawvideo', '-']
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    fps = float(eval(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout.strip() or '30'))
    hits, best, n, mx = [], 0.0, 0, {}
    while True:
        buf = pr.stdout.read(W * H)
        if len(buf) < W * H: break
        if n % step == 0:
            fr = np.frombuffer(buf, np.uint8).reshape(H, W)
            per = {}
            for nm, tp in kata():
                r = cv2.matchTemplate(fr, tp, cv2.TM_CCOEFF_NORMED); v = float(r.max())
                if v > per.get(nm, 0.0): per[nm] = v
            for k, v in per.items(): mx[k] = max(mx.get(k, 0.0), v)
            # どの見本も0以下（無地のコマなど）なら per は空＝出ていない（yt-edl 10/21 KTbQ の明るい地で max() が空で止まった）
            m = max((v - SENS.get(k, SEN) for k, v in per.items()), default=-1.0)   # 見本ごとの線を超えた分（0以上で出た）
            best = max(best, max(per.values(), default=0.0))
            if m >= 0: hits.append((round(t0 + n / fps, 3), {k: round(v, 3) for k, v in per.items()}))
        n += 1
    pr.wait()
    return {'koma': n, 'mita': (n + step - 1) // step, 'step': step, 'saidai': round(best, 3), 'mihon_betsu': {k: round(v, 3) for k, v in mx.items()}, 'sen': SENS, 'deta': hits}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mp4'); ap.add_argument('--step', type=int, default=2); ap.add_argument('--out'); ap.add_argument('--t1', type=float)
    A = ap.parse_args()
    r = video_check(A.mp4, A.step, 0.0, A.t1)
    if A.out: json.dump(r, open(A.out, 'w'), ensure_ascii=False, indent=1)
    d = r['deta']
    print(('🔴 使ってはいけないキャラ（棒人間）が %d コマに出る（%s 秒〜・似ている度合い %s・線 %s）' % (len(d), d[0][0], r['mihon_betsu'], SENS)) if d else ('✅ 使ってはいけないキャラは出ない（%d コマを見た・似ている度合いの最大 %s ＜ 線 %s）' % (r['mita'], r['mihon_betsu'], SENS)))
    sys.exit(1 if d else 0)


# ---------- 地の線画（ki1.py の明るい地・暗い地に薄く描いていた chara_line_mask と、テーマの地紋 jimon_chara_line_white）----------
# 置き場と大きさが決まっていたので、その形の線の上だけが周りより明るいかで見る（10/21）
def _jimon_masks():
    out = []
    p1 = os.path.join(K, 'files', 'assets', 'chara_line_mask.png')
    if os.path.exists(p1):   # ki1.py：高さ 0.9H・左右まん中・下ぞろえ
        from PIL import Image
        m = Image.open(p1).split()[-1]; h = int(1080 * 0.9); m = m.resize((int(m.width * h / m.height), h))
        c = Image.new('L', (1920, 1080), 0); c.paste(m, (int(960 - m.width / 2), 1080 - h)); out.append(('haikei', np.array(c.resize((W, H)))))
    p2 = os.path.join(K, 'files', 'assets', 'jimon_chara_line_white.png')
    if os.path.exists(p2):   # テーマの地紋：高さ 820・中心 (960,560)
        from PIL import Image
        m = Image.open(p2).split()[-1]; h = 820; m = m.resize((int(m.width * h / m.height), h))
        c = Image.new('L', (1920, 1080), 0); c.paste(m, (int(960 - m.width / 2), int(560 - h / 2))); out.append(('jimon', np.array(c.resize((W, H)))))
    res = []
    for nm, a in out:
        line = a > 60
        ring = cv2.dilate(line.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~cv2.dilate(line.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        res.append((nm, line, ring))
    return res


def jimon_check(mp4, step=15, t1=None, sen=3.0):
    """線の上の明るさ − すぐ外の明るさ（0〜255）の中央値。sen を超えるコマが3割以上なら『出た』"""
    ms = _jimon_masks()
    cmd = ['ffmpeg', '-v', 'error', '-i', mp4] + (['-t', str(t1)] if t1 else []) + ['-vf', 'scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=gray,format=gray' % (W, H, W, H), '-f', 'rawvideo', '-']
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE); n = 0; sc = {nm: [] for nm, _, _ in ms}
    while True:
        buf = pr.stdout.read(W * H)
        if len(buf) < W * H: break
        if n % step == 0:
            fr = np.frombuffer(buf, np.uint8).reshape(H, W).astype(np.float32)
            for nm, line, ring in ms: sc[nm].append(float(np.median(fr[line]) - np.median(fr[ring])))
        n += 1
    pr.wait()
    out = {}
    for nm, v in sc.items():
        v = np.array(v) if v else np.zeros(1); out[nm] = {'koma': len(v), 'chuuou': round(float(np.median(v)), 2), 'koeta_wariai': round(float((v > sen).mean()), 3)}
    out['deta'] = any(x['koeta_wariai'] >= 0.3 for x in out.values() if isinstance(x, dict))
    return out
