#!/usr/bin/env python3
# 音量の合格線（抜けE）を見本から作る：stems（声／声以外）がそろった見本を全部測り、kijun.json の loudness に入れる（作業AI・2026-10-15）
#   python3 kijun_loud.py   → kata/full/loud_samples.tsv（1本ずつ）・kijun.json の loudness（10〜90% の幅）
import os, sys, json, glob
import numpy as np
TOOL = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(TOOL, 'lib'))
import paths, loud
(os.getpriority(os.PRIO_PROCESS, 0) < 19 and os.setpriority(os.PRIO_PROCESS, 0, 19))
STEMS = os.path.join(paths.ENGINE, 'kata', 'full', 'stems')
def one(d):
    try: m = loud.measure_sample(d)
    except Exception as e: return os.path.basename(d), None, str(e)
    return os.path.basename(d), m, ''
if __name__ == '__main__':
    ds = [d for d in sorted(glob.glob(os.path.join(STEMS, '*'))) if os.path.exists(os.path.join(d, 'vocals.wav')) and os.path.exists(os.path.join(d, 'bg.wav'))]
    rows = []
    from multiprocessing import Pool
    with Pool(8) as pool:                        # 1本ずつは ffmpeg が1コア。8本ずつ並べる（nice 19 のまま）
        for v, m, err in pool.imap_unordered(one, ds):
            if m is None or None in (m['I'], m['diff']): print('測れない', v, err or m, flush=True); continue
            rows.append((v, m)); print(v, m, flush=True)
    rows.sort()
    tsv = os.path.join(paths.ENGINE, 'kata', 'full', 'loud_samples.tsv')
    with open(tsv, 'w') as f:
        f.write('id\tI\tvoice\tbg\tdiff\tpeak\n')
        for v, m in rows: f.write('%s\t%s\t%s\t%s\t%s\t%s\n' % (v, m['I'], m['voice'], m['bg'], m['diff'], m['peak']))
    q = lambda k, p: round(float(np.percentile([m[k] for _, m in rows], p)), 2)
    K = json.load(open(paths.KIJUN))
    K['loudness'] = {'I_min': q('I', 10), 'I_max': q('I', 90), 'I_median': q('I', 50), 'diff_min': q('diff', 10), 'diff_max': q('diff', 90), 'diff_median': q('diff', 50),
                     'peak_max': -1.0, 'n': len(rows),
                     '_': '音量（抜けE）。見本 %d 本の stems（声／声以外＝BGM＋効果音）を ffmpeg ebur128 で測った 10〜90%% の幅。I＝1本全体の LUFS・diff＝声−声以外（dB）・peak は全体のピーク dBFS（-1 以下＝割れない）。作業AIの1本は mp4 から編集後の声を最小二乗で引いて同じ分け方で測る（lib/loud.py）' % len(rows)}
    json.dump(K, open(paths.KIJUN, 'w'), ensure_ascii=False, indent=1)
    print('kijun.json loudness', K['loudness'])
