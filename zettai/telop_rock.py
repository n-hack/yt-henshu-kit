# 手本の編集者さんの門の項目「テロップの出/分」（2026-10-23 作業AIの判断で追加・実験の記録 ~/rin6/state/mon-yutori-20261023.md 4〜5回目）
#   手本：講義型 youtube.tehon 37本の頭171秒（telop-kougi37-171.json）。ゆとり 0.1＝(最大−最小)×0.1 を両側に足した幅の外は「下」
#   測り方：頭 t1 秒を切り出し、miyasusa-mon＋hyougen-mon にかけ、hyougen-hikaku.kou の「見やすさ：テロップの出/分」（字幕帯の下2割は除く）
#   2回測って揺れ0（v14・zen7・手本5本）。手本の値は171秒の頭で測ったので、頭が120秒より短い試験（30秒）では測らない
import os, sys, json, subprocess, tempfile, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(HERE)
KEY = '見やすさ：テロップの出/分'; NAME = 'テロップの出/分（講義型37本）'

def hakaru(mp4, t1):
    d = tempfile.mkdtemp(prefix='telop-rock-'); mp = os.path.join(d, 'atama.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp4, '-t', str(t1), '-c', 'copy', mp], check=True)
    subprocess.run(['python3', os.path.join(T, 'miyasusa-mon.py'), mp, '--raw', d + '/mr.json', '--out', d + '/mi.json'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(['python3', os.path.join(T, 'hyougen-mon.py'), mp, '--ocr', d + '/mr.json', '--raw', d + '/hr.json', '--out', d + '/hy.json'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    sp = importlib.util.spec_from_file_location('hh', os.path.join(T, 'hyougen-hikaku.py')); hh = importlib.util.module_from_spec(sp)
    av = sys.argv; sys.argv = ['x']; sp.loader.exec_module(hh); sys.argv = av
    v = hh.kou(json.load(open(d + '/mi.json')), json.load(open(d + '/hy.json')))[KEY]
    subprocess.run(['rm', '-rf', d]); return v

def check(mp4, t1, nozoku=None):
    """→ (行, 下か) 。t1 が120秒未満なら (None, False)"""
    if t1 < 120: return None, False
    R = json.load(open(os.path.join(HERE, 'telop-kougi37-171.json')))
    vals = [v for k, v in R['値'].items() if k != nozoku]; lo, hi = min(vals), max(vals); w = (hi - lo) * R['ゆとり']
    x = hakaru(mp4, t1)
    if x < lo - w: h, why = '下', '講義型の最小 %s より少ない（ゆとり込み %s）' % (lo, round(lo - w, 1))
    elif x > hi + w: h, why = '下', '講義型の最大 %s より多い（多すぎ・ゆとり込み %s）' % (hi, round(hi + w, 1))
    else: h, why = '同じ', '講義型の幅 %s〜%s の中（ゆとり込み %s〜%s）' % (lo, hi, round(lo - w, 1), round(hi + w, 1))
    return {'項目': NAME, 'key': 'telop_pm', '自分': x, '手本 最小': lo, '手本 最大': hi, '判定': h, 'わけ': why, '手本の本数': len(vals)}, h == '下'
