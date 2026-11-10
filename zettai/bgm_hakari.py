#!/usr/bin/env python3
# BGM の測り（絶対ルール10・作業AI 2026-10-19）。手本と作業AIの1本を同じ式で測る
#   声と「声以外」を 0.4 秒の窓（0.1 秒おき）の大きさ（dB）にし、声が出ている窓だけで
#     声の大きさ（中央値）−「声以外」の大きさ（中央値）＝ 声に対する BGM の小ささ（dB・大きいほど BGM が小さい）
#   効果音は短くまばらなので、中央値なら BGM の床（ずっと鳴っている音）の大きさになる
#   BGM のある長さ … 声のある範囲の窓のうち、「声以外」が 声の中央値−40dB より大きい窓の割合
#   手本は demucs で分けた stems（kata/full/stems/<id>/vocals.wav・bg.wav）、作業AIの1本は書き出しと同じ式で作った BGM だけの音と work/vocals.wav
#   python3 bgm_hakari.py kijun   → 手本を全部測って zettai/bgm_kijun.json（止める線と根拠）
import os, sys, json, glob, subprocess
import numpy as np
SR = 16000
HERE = os.path.dirname(os.path.abspath(__file__))
KIJUN = os.path.join(HERE, 'bgm_kijun.json')


def dec(p, t=None):
    cmd = ['ffmpeg', '-v', 'error', '-i', p, '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    if t: cmd[3:3] = ['-t', str(t)]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


def win_db(y):
    w, h = int(0.4 * SR), int(0.1 * SR)
    if len(y) < w: return np.array([])
    n = 1 + (len(y) - w) // h
    c = np.concatenate([[0.0], np.cumsum(y.astype(np.float64) ** 2)])
    e = (c[np.arange(n) * h + w] - c[np.arange(n) * h]) / w
    return 10 * np.log10(e + 1e-12)


def stats(voice, bg):
    v, b = win_db(voice), win_db(bg); n = min(len(v), len(b)); v, b = v[:n], b[:n]
    if n == 0: return None
    on = v > np.percentile(v, 90) - 20                       # 声が出ている窓
    if on.sum() < 10: return None
    vm = float(np.median(v[on])); bm = float(np.median(b[on]))
    idx = np.where(on)[0]; span = slice(idx[0], idx[-1] + 1)  # 声の最初から最後まで
    cover = float((b[span] > vm - 40).mean())
    return {'声の中央値dB': round(vm, 2), 'BGMの中央値dB': round(bm, 2), '声−BGM（dB）': round(vm - bm, 2), 'BGMのある長さ': round(cover, 3)}


def kijun():
    """手本（手本の作者さんの3チャンネル・stems のそろった本）を頭 600 秒で測る → 止める線"""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'lib')); import paths
    ch = {}
    for c in ('youtube.tehon', 'sns.tehon', 'instagram_tehon'):
        p = os.path.join(paths.ENGINE, 'channels', c + '.tsv')
        if os.path.exists(p):
            import re
            for l in open(p, encoding='utf-8'): ch[re.split(r'\\t|\t', l, maxsplit=1)[0].strip()] = c
    # 手本は固定の15本（tehon15.jsonl・記憶 youtube-tehon-fixed-15）。stems は Drive に逃がしてあり1本2分かかるので全190本は測らない
    ids = sorted({json.loads(l)['r']['hon'][:-4] for l in open(os.path.join(HERE, 'tehon15.jsonl'))})
    ds = [d for d in (os.path.join(paths.ENGINE, 'kata', 'full', 'stems', i) for i in ids) if os.path.exists(os.path.join(d, 'vocals.wav')) and os.path.exists(os.path.join(d, 'bg.wav'))]
    print('手本15本のうち stems がある本', len(ds), flush=True)
    rows = []
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(15) as ex:
        for d, s in zip(ds, ex.map(_one, ds)):
            if s: rows.append(dict(s, id=os.path.basename(d), ch=ch.get(os.path.basename(d), '不明')))
    rows = [r for r in rows if r['ch'] != '不明']
    has = [r for r in rows if r['BGMのある長さ'] >= 0.8]
    q = lambda k, p, R: round(float(np.percentile([r[k] for r in R], p)), 2)
    K = {'測った本': len(rows), 'BGMが8割以上の本': len(has),
         '声−BGM（dB）の幅（BGMが8割以上の本）': {'5%': q('声−BGM（dB）', 5, has), '10%': q('声−BGM（dB）', 10, has), '中央値': q('声−BGM（dB）', 50, has),
                                       '90%': q('声−BGM（dB）', 90, has), '95%': q('声−BGM（dB）', 95, has), '最小': q('声−BGM（dB）', 0, has), '最大': q('声−BGM（dB）', 100, has)},
         'BGMのある長さ（全部の本）': {'10%': q('BGMのある長さ', 10, rows), '中央値': q('BGMのある長さ', 50, rows)}}
    lo, hi = K['声−BGM（dB）の幅（BGMが8割以上の本）']['5%'], K['声−BGM（dB）の幅（BGMが8割以上の本）']['95%']
    K['止める線'] = {'声−BGM_下限': lo, '声−BGM_上限': hi,
                 '根拠': '手本（固定の15本のうち stems のそろった %d 本のうち BGM が8割以上ある %d 本）の 声−BGM の 5%%〜95%%。'
                       'この外は手本の20本に1本も無い大きさ＝「大きく外れた」とする。下限より小さい＝BGM が大きすぎて声が埋もれる／上限より大きい＝BGM が小さすぎて聞こえない' % (len(rows), len(has))}
    K['1本ずつ'] = sorted(rows, key=lambda r: r['id'])
    json.dump(K, open(KIJUN, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in K.items() if k != '1本ずつ'}, ensure_ascii=False, indent=1))


def _one(d):
    try: return stats(dec(os.path.join(d, 'vocals.wav'), 600), dec(os.path.join(d, 'bg.wav'), 600))
    except Exception: return None


if __name__ == '__main__' and sys.argv[1:2] == ['kijun']:
    os.setpriority(os.PRIO_PROCESS, 0, 19); kijun()
