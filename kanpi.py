#!/usr/bin/env python3
# 完コピ練習の「比べる」部分（作業AI・2026-10-15）。流れと合格の線は README-kanpi.md
#   元の場面と、型だけで作り直した場面を、saboranai と同じ測り方（sokutei.py）でコマ単位に比べる。
#   python3 kanpi.py hikaku <元.mp4> <元の開始秒> <作った.mp4> <作ったものの開始秒> <秒数> [--voice 声.wav] [--voice-t0 秒] [--ocr-fps 2] [--out 結果.json]
#     --voice  同じナレーション音声（声だけ）。これに有る立ち上がりは「声」として効果音の比べから外す
#   結果：項目ごとの数字と 合格/不合格（LINE）。ずれの大きい所を秒で出す＝次に直す所
import os, sys, json, glob, shutil, tempfile, subprocess, statistics
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sokutei as S

# ---- 合格の線（README-kanpi.md と同じ。変えたら両方） ----
LINE = dict(
    CUT_TOL_F=2,          # 場面転換は ±2コマ以内なら「同じ所」
    CUT_RECALL=0.90,      # 元の場面転換の 90% 以上が作ったものにもある
    CUT_PRECISION=0.85,   # 作ったものの場面転換の 85% 以上が元にもある（余計な切り替えを入れない）
    CUT_MED_F=1.0,        # 対応した場面転換のずれの中央値は 1コマ以内
    CHG_RATE=0.15,        # 画面の変化（要素の出入り）の回数/分は 元の ±15%
    INTERVAL_MED=0.10,    # 切り替わり間隔の中央値は 元の ±10%
    TELOP_MATCH=0.85,     # 元のテロップの 85% 以上が作ったものにも出る（文字の重なり 60% 以上で同じとみなす）
    TELOP_IN_MED_F=2.0,   # テロップの出のずれの中央値 2コマ以内
    TELOP_IN_P90_F=4.0,   # 90% が 4コマ以内（OCR の刻みより細かくは測れない＝下の注意）
    TELOP_OUT_MED_F=3.0,  # 消えのずれの中央値 3コマ以内
    SE_TOL_F=2,           # 効果音は ±2コマ以内なら「同じ所」
    SE_RECALL=0.85,       # 元の効果音（声に無い立ち上がり）の 85% 以上
    SE_PRECISION=0.80,    # 作ったものの効果音の 80% 以上が元にもある
    COLOR_DE_MED=8.0,     # 毎秒のコマの色差（CIE76・160x90 の画素ごと）の中央値の中央値 8 以内
    LAYOUT_CORR=0.80,     # 構図（輪郭の位置 64x36）の相関の中央値 0.80 以上
)


def seg_fd(mp4, t0, dur):
    return S.framediff(mp4, None, t0, dur)


def frames_rgb(mp4, t0, dur, fps=1.0, w=160, h=90):
    b = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t0, '-i', mp4, '-t', '%.3f' % dur, '-vf', 'fps=%g,scale=%d:%d' % (fps, w, h),
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    n = len(b) // (w * h * 3)
    return np.frombuffer(b[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def edges(a):
    g = a.astype(np.float32).mean(-1)
    gx = np.abs(np.diff(g, axis=1))[:-1]; gy = np.abs(np.diff(g, axis=0))[:, :-1]
    e = gx + gy
    H, W = e.shape
    e = e[:H - H % 2, :W - W % 2].reshape(H // 2, 2, W // 2, 2).mean((1, 3))  # 64x36 程度
    return e


def ocr_track(mp4, t0, dur, fps):
    """fps ごとにコマを読み、文字列ごとに出た秒・消えた秒を出す"""
    tmp = tempfile.mkdtemp(prefix='kanpi-')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t0, '-i', mp4, '-t', '%.3f' % dur, '-vf', 'fps=%g,scale=1920:1080' % fps,
                    os.path.join(tmp, 'f%05d.png')])
    ps = sorted(glob.glob(os.path.join(tmp, 'f*.png')))
    rd = {}
    for i in range(0, len(ps), 40):
        rd.update(S.ocr(ps[i:i + 40]))
    seen = []  # [(秒, set(文字列))]
    for k, p in enumerate(ps):
        seen.append((k / fps, {''.join(S.norm_chars(x)) for x in rd.get(p, []) if len(S.norm_chars(x)) >= 2}))
    shutil.rmtree(tmp, ignore_errors=True)
    tracks = {}
    for t, ss in seen:
        for s in ss:
            tr = tracks.setdefault(s, [])
            if tr and abs(tr[-1][1] - (t - 1 / fps)) < 1e-6: tr[-1][1] = t
            else: tr.append([t, t])
    out = []
    for s, lst in tracks.items():
        for a, b in lst: out.append({'text': s, 'in': a, 'out': b + 1 / fps})
    return out


def sim(a, b):
    from collections import Counter
    A, B = Counter(a), Counter(b)
    n = sum((A & B).values())
    return n / max(1, max(len(a), len(b)))


def hikaku(orig, ot0, mine, mt0, dur, voice=None, voice_t0=0.0, ocr_fps=2.0):
    po = S.probe(orig); fps = po['fps']; F = 1.0 / fps
    r = {'fps': fps, 'dur': dur, 'line': LINE, 'th': S.THRESHOLDS}
    # 1 場面転換と変化
    fo, fm = seg_fd(orig, ot0, dur), seg_fd(mine, mt0, dur)
    co, cm = S.cuts_from_diff(fo, fps), S.cuts_from_diff(fm, fps)
    pairs, uo, um = S.match_events(co, cm, LINE['CUT_TOL_F'] * F + 1e-6)
    offs = [abs(d) / F for _, _, d in pairs]
    r['cut'] = {'orig': len(co), 'mine': len(cm), 'matched': len(pairs), 'recall': len(pairs) / max(1, len(co)), 'precision': len(pairs) / max(1, len(cm)),
                'med_off_f': statistics.median(offs) if offs else None, 'missing_s': [round(x, 2) for x in uo[:20]], 'extra_s': [round(x, 2) for x in um[:20]]}
    ho, hm = S.changes_from_diff(fo, fps), S.changes_from_diff(fm, fps)
    io = np.diff(ho) if len(ho) > 1 else np.array([0.0]); im = np.diff(hm) if len(hm) > 1 else np.array([0.0])
    r['change'] = {'orig_per_min': len(ho) / dur * 60, 'mine_per_min': len(hm) / dur * 60,
                   'orig_interval_med': float(np.median(io)), 'mine_interval_med': float(np.median(im)),
                   'orig_interval_max': float(io.max()), 'mine_interval_max': float(im.max())}
    # 2 色と構図（毎秒）
    ro, rm = frames_rgb(orig, ot0, dur), frames_rgb(mine, mt0, dur)
    n = min(len(ro), len(rm)); des, lay = [], []
    for i in range(n):
        de = np.sqrt(((S.rgb2lab(ro[i]) - S.rgb2lab(rm[i])) ** 2).sum(-1))
        des.append(float(np.median(de)))
        eo, em = edges(ro[i]).ravel(), edges(rm[i]).ravel()
        lay.append(float(np.corrcoef(eo, em)[0, 1]) if eo.std() > 1e-6 and em.std() > 1e-6 else (1.0 if eo.std() == em.std() else 0.0))
    worst = sorted(range(n), key=lambda i: -des[i])[:8]
    r['color'] = {'de_med': statistics.median(des) if des else None, 'worst_s': [(i, round(des[i], 1)) for i in worst]}
    worstl = sorted(range(n), key=lambda i: lay[i])[:8]
    r['layout'] = {'corr_med': statistics.median(lay) if lay else None, 'worst_s': [(i, round(lay[i], 2)) for i in worstl]}
    # 3 テロップの出入り
    if ocr_fps > 0:
        to, tm = ocr_track(orig, ot0, dur, ocr_fps), ocr_track(mine, mt0, dur, ocr_fps)
        used = set(); m_in, m_out, miss = [], [], []
        for a in sorted(to, key=lambda x: x['in']):
            cand = [(sim(a['text'], b['text']) - abs(a['in'] - b['in']) / 10, j) for j, b in enumerate(tm)
                    if j not in used and sim(a['text'], b['text']) >= 0.6 and abs(a['in'] - b['in']) <= 3.0]
            if not cand: miss.append((round(a['in'], 2), a['text'][:20])); continue
            _, j = max(cand); used.add(j)
            m_in.append(abs(tm[j]['in'] - a['in']) / F); m_out.append(abs(tm[j]['out'] - a['out']) / F)
        r['telop'] = {'orig': len(to), 'mine': len(tm), 'matched': len(m_in), 'match_rate': len(m_in) / max(1, len(to)),
                      'in_med_f': statistics.median(m_in) if m_in else None, 'in_p90_f': float(np.percentile(m_in, 90)) if m_in else None,
                      'out_med_f': statistics.median(m_out) if m_out else None, 'missing': miss[:20], 'ocr_fps': ocr_fps,
                      'note': 'OCR は %g コマ/秒で読むので、出入りの細かさは ±%.1f コマまで' % (ocr_fps, fps / ocr_fps / 2)}
    # 4 効果音の位置
    ao, am = S.audio(orig, ot0, dur), S.audio(mine, mt0, dur)
    oo, om = S.onsets(ao), S.onsets(am)
    if voice:
        ov = S.onsets(S.audio(voice, voice_t0, dur))
        oo = [t for t in oo if all(abs(t - v) > 0.05 for v in ov)]
        om = [t for t in om if all(abs(t - v) > 0.05 for v in ov)]
    sp, suo, sum_ = S.match_events(oo, om, LINE['SE_TOL_F'] * F + 1e-6)
    r['se'] = {'orig': len(oo), 'mine': len(om), 'matched': len(sp), 'recall': len(sp) / max(1, len(oo)), 'precision': len(sp) / max(1, len(om)),
               'med_off_f': statistics.median([abs(d) / F for _, _, d in sp]) if sp else None, 'voice_removed': bool(voice),
               'missing_s': [round(x, 2) for x in suo[:20]], 'extra_s': [round(x, 2) for x in sum_[:20]]}
    # 判定
    ok = {}
    c = r['cut']; ok['場面転換'] = c['recall'] >= LINE['CUT_RECALL'] and c['precision'] >= LINE['CUT_PRECISION'] and (c['med_off_f'] or 0) <= LINE['CUT_MED_F']
    ch = r['change']
    ok['変化の頻度'] = abs(ch['mine_per_min'] - ch['orig_per_min']) <= LINE['CHG_RATE'] * max(1e-6, ch['orig_per_min']) and \
        abs(ch['mine_interval_med'] - ch['orig_interval_med']) <= LINE['INTERVAL_MED'] * max(1e-6, ch['orig_interval_med'])
    if 'telop' in r:
        t = r['telop']; ok['テロップの出入り'] = t['match_rate'] >= LINE['TELOP_MATCH'] and (t['in_med_f'] or 99) <= LINE['TELOP_IN_MED_F'] and \
            (t['in_p90_f'] or 99) <= LINE['TELOP_IN_P90_F'] and (t['out_med_f'] or 99) <= LINE['TELOP_OUT_MED_F']
    s = r['se']; ok['効果音の位置'] = s['recall'] >= LINE['SE_RECALL'] and s['precision'] >= LINE['SE_PRECISION']
    ok['色'] = (r['color']['de_med'] or 99) <= LINE['COLOR_DE_MED']
    ok['構図'] = (r['layout']['corr_med'] or 0) >= LINE['LAYOUT_CORR']
    r['ok'] = ok; r['pass'] = all(ok.values())
    return r


def main():
    a = sys.argv[1:]
    if not a or a[0] != 'hikaku':
        print(__doc__ or open(__file__).read().split('import os')[0]); return
    opt = {a[i]: a[i + 1] for i in range(6, len(a) - 1) if a[i].startswith('--')}
    r = hikaku(a[1], float(a[2]), a[3], float(a[4]), float(a[5]), opt.get('--voice'), float(opt.get('--voice-t0', 0)), float(opt.get('--ocr-fps', 2)))
    js = json.dumps(r, ensure_ascii=False, indent=1, default=float)
    if opt.get('--out'): open(opt['--out'], 'w').write(js)
    for k, v in r['ok'].items(): print('%s %s' % ('合格' if v else '不合格', k))
    print('場面転換 元%d 作%d 対応%d（拾えた %.0f%%・余計 %.0f%%・ずれ中央 %s コマ）' % (r['cut']['orig'], r['cut']['mine'], r['cut']['matched'], 100 * r['cut']['recall'],
          100 * (1 - r['cut']['precision']), r['cut']['med_off_f']))
    print('変化/分 元%.1f 作%.1f ／ 間隔の中央 元%.2f秒 作%.2f秒 ／ 最長 元%.1f秒 作%.1f秒' % (r['change']['orig_per_min'], r['change']['mine_per_min'], r['change']['orig_interval_med'],
          r['change']['mine_interval_med'], r['change']['orig_interval_max'], r['change']['mine_interval_max']))
    if 'telop' in r:
        t = r['telop']; print('テロップ 元%d 作%d 対応%d（%.0f%%）出のずれ 中央%s・90%%点%s コマ 消えのずれ 中央%s コマ' % (t['orig'], t['mine'], t['matched'], 100 * t['match_rate'], t['in_med_f'], t['in_p90_f'], t['out_med_f']))
    s = r['se']; print('効果音 元%d 作%d 対応%d（拾えた %.0f%%・余計 %.0f%%）声を除いた=%s' % (s['orig'], s['mine'], s['matched'], 100 * s['recall'], 100 * (1 - s['precision']), s['voice_removed']))
    print('色差の中央 %.1f（悪い秒 %s）／構図の相関 %.2f（悪い秒 %s）' % (r['color']['de_med'], r['color']['worst_s'][:4], r['layout']['corr_med'], r['layout']['worst_s'][:4]))
    print('総合', '合格' if r['pass'] else '不合格')


if __name__ == '__main__':
    main()
