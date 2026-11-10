#!/usr/bin/env python3
# 書き出し：story.py の場面を並列で描いて GPU（h264_videotoolbox）で書き出し、声＋見本の効果音＋BGM を重ねる
import os, sys, time, json, subprocess, importlib.util
LIB = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, LIB)
import paths
sys.path.insert(0, paths.BUILD)
def load_story(proj):
    os.environ['PROJ'] = proj
    spec = importlib.util.spec_from_file_location('story', os.path.join(proj, 'story.py')); S = importlib.util.module_from_spec(spec)
    sys.modules['story'] = S; spec.loader.exec_module(S); return S
def mixer():
    import sfx_plan as P
    SM = {k: v for k, v in json.load(open(os.path.join(paths.TOOL, 'sound_map.json'))).items() if not k.startswith('_')}
    P.LIB = os.path.join(paths.sozai_dir(), 'se')
    P.SOUNDS = {k: (v['file'], v['db'], v['use']) for k, v in SM.items()}
    if os.environ.get('PIPE_EDL'):   # v14：効果音は編集の指示書（EDL）に書いたとおりに全部鳴らす（道具が近い音を間引かない・依頼主 10/19 20:0x）
        _known = set(P.SOUNDS)
        def _sel(events, sparse=()):
            bad = sorted({k for t, k in events if k not in _known})
            if bad: print('🟡 EDL の効果音の名前が手元に無い：%s（鳴らさない）' % '・'.join(bad), flush=True)
            return sorted((t, k) for t, k in events if k in _known)
        P.select = _sel
    P.RANK = {k: v['rank'] for k, v in SM.items()}
    # 音は元の編集者さんのものだけ（依頼主 10/15「外の素材サイトの音は一切使わない」）：素材集の se/ に無い音は止める
    for k, v in SM.items():
        if not os.path.exists(os.path.join(P.LIB, v['file'])): raise SystemExit('🔴 効果音 %s（%s）が元の素材集 %s に無い' % (k, v['file'], P.LIB))
    return P
_S = None
def _chunk(args):
    global _S
    proj, i, f0, f1, out = args
    if _S is None: _S = load_story(proj)
    import anim
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (anim.W, anim.H), '-r', '30000/1001', '-i', '-',
           '-c:v', 'h264_videotoolbox', '-b:v', '18M', '-maxrate', '24M', '-allow_sw', '0', '-pix_fmt', 'yuv420p', out]
    # GPU の書き出し回路が埋まると -12912 で落ちる。30秒おいて最大3回やり直す（GENDO.md・state/pc-spec/gpu-video-20261015.md）
    SLOT = os.path.expanduser('~/rin6/state/night-lock/night-slot.sh')   # GPU の書き出しの枠（10/18 作業AI・yt-hozon：同時本数を全体で数える。出来上がりは変わらない）
    for k in range(4):
        err = out + '.err'
        t0 = time.time()
        T = subprocess.run(['bash', SLOT, 'get', 'gpu-enc-render-%d-%d' % (os.getpid(), i), str(os.getpid())], capture_output=True, text=True).stdout.strip()
        t1 = time.time(); tg = tw = 0.0   # 時刻の記録（10/18 yt-hozon・別の作業AIの依頼：合成と書き出しの内訳。出来上がりは変わらない）
        try:
            with open(err, 'w') as ef:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=ef)
                try:
                    for f in range(f0, f1):
                        a0 = time.time(); buf = _S.frame_at(f / anim.FPS).convert('RGB').tobytes(); a1 = time.time()
                        p.stdin.write(buf); tg += a1 - a0; tw += time.time() - a1
                    p.stdin.close()
                except BrokenPipeError: pass
                a2 = time.time(); p.wait(); te = time.time() - a2
        finally:
            if T: subprocess.run(['bash', SLOT, 'put', T])
        try:
            with open(os.path.join(os.path.dirname(out), 'jikan-parts.jsonl'), 'a') as jf:
                jf.write(json.dumps({'part': i, 'frames': f1 - f0, 'try': k, 'pid': os.getpid(), 'start': time.strftime('%H:%M:%S', time.localtime(t0)),
                                     'slot_wait': round(t1 - t0, 2), 'gousei': round(tg, 2), 'watasu': round(tw, 2), 'owari': round(te, 2), 'cpu': round(time.process_time(), 2)}) + '\n')
        except Exception: pass
        msg = open(err).read(); os.remove(err)
        if p.returncode == 0 or '-12912' not in msg or k == 3:
            if msg: sys.stderr.write(msg)
            return i, p.returncode
        print('part %d：GPU の回路が埋まっている（-12912）ので30秒おいてやり直す（%d回目）' % (i, k + 1), flush=True); time.sleep(30)
def audio(proj, S, out):
    P = mixer()
    for a, b, f, o, g in S.BGM:
        fp = f if os.path.isabs(f) else os.path.join(paths.sozai_dir(), f)
        if not os.path.realpath(fp).startswith(os.path.realpath(paths.sozai_dir())): raise SystemExit('🔴 BGM %s が元の素材集の外' % f)
    json.dump({'se_dir': P.LIB, 'se': {k: v[0] for k, v in P.SOUNDS.items()}, 'bgm': [b[2] for b in S.BGM], 'sozai': paths.sozai_dir()},
              open(os.path.join(proj, 'work', 'sound_used.json'), 'w'), ensure_ascii=False)
    ev = P.select([(t, k) for t, k in S.SFX], getattr(S, 'SFX_SPARSE', ()))
    json.dump(ev, open(os.path.join(proj, 'work', 'sfx_placed.json'), 'w'))
    return P.mix(os.path.join(proj, 'work', 'vocals.wav'), S.SFX, [(a, b, os.path.join(paths.sozai_dir(), f) if not os.path.isabs(f) else f, o, g) for a, b, f, o, g in S.BGM],
                 0.0, S.END, out, getattr(S, 'SFX_SPARSE', ()))
def stills(proj, ts):
    S = load_story(proj); d = os.path.join(proj, 'check'); os.makedirs(d, exist_ok=True); out = []
    for t in ts:
        p = os.path.join(d, 'mine_%06.2f.png' % t); S.frame_at(t).convert('RGB').save(p); out.append(p)
    return out
PART = 600   # 1つの部品の長さ（コマ・約20秒）。直し（naoshi）はこの単位で作り直す


def _parts(f1, n):
    step = min(PART, (f1 + n - 1) // n)
    return [(i, i * step, min(f1, (i + 1) * step)) for i in range((f1 + step - 1) // step)]


def _join(proj, S, tmp, jobs, out):
    lst = os.path.join(tmp, 'list.txt'); open(lst, 'w').write(''.join("file '%s'\n" % j[4] for j in jobs))
    silent = os.path.join(tmp, 'silent.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', silent], check=True)
    mix = audio(proj, S, os.path.join(tmp, 'mix.wav'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-shortest', '-movflags', '+faststart', '-map_metadata', '-1', out], check=True)


def _pool(proj, S, k):
    """描く人を k 人。親で組んだ場面表をそのまま分けて渡す（fork）：子が story を組み直さない（組むのに数分・メモリ数十GB × 人数かかっていた・10/20 yt-hayasa）。
    描く式は同じなので出来上がりの画素は変わらない。RENDER_SPAWN=1 で元の形（子ごとに組み直す）に戻す"""
    global _S
    import multiprocessing as mp
    if os.environ.get('RENDER_SPAWN') == '1': return mp.Pool(k)
    _S = S; return mp.get_context('fork').Pool(k)


def video(proj, out, n=8):   # GPU の書き出しは同時8本が最速（kata/full/GENDO.md・10/15 19:15 依頼主）
    import anim
    S = load_story(proj); f1 = int(round(S.END * anim.FPS)); tmp = os.path.join(proj, 'out', 'tmp'); os.makedirs(tmp, exist_ok=True)
    jobs = [(proj, i, a, b, os.path.join(tmp, 'part%03d.mp4' % i)) for i, a, b in _parts(f1, n)]
    st = time.time()
    with _pool(proj, S, min(n, len(jobs))) as pool:
        for i, rc in pool.imap_unordered(_chunk, jobs):
            if rc: raise SystemExit('描画に失敗 part %d' % i)
    _join(proj, S, tmp, jobs, out)
    json.dump({'end': S.END, 'f1': f1, 'parts': [j[1:] for j in jobs], 'out': out, 'at': time.strftime('%Y-%m-%d %H:%M:%S')},
              open(os.path.join(tmp, 'parts.json'), 'w'), ensure_ascii=False)
    print(out, '書き出し %.0f 秒' % (time.time() - st)); return out


def naoshi(proj, out, ranges, n=8):
    """秒を指定した直し（抜けH）：story.py を直したあと、指定の秒にかかる部品（約20秒単位）だけ描き直して差し込む。
    ranges … [(t0, t1), ...]。声の長さ（END）が変わっていたら、全部の時刻がずれるので全体を書き出し直す"""
    import anim
    S = load_story(proj); f1 = int(round(S.END * anim.FPS)); tmp = os.path.join(proj, 'out', 'tmp')
    mp = os.path.join(tmp, 'parts.json')
    M = json.load(open(mp)) if os.path.exists(mp) else None
    if not M or M['f1'] != f1 or not all(os.path.exists(p[3]) for p in M['parts']):
        print('前の書き出しの部品が無いか、声の長さが変わった → 全体を書き出し直す', flush=True)
        return video(proj, out, n), 'all'
    redo = sorted({tuple(p) for p in M['parts'] for t0, t1 in ranges if p[1] < (t1 + 0.5) * anim.FPS and p[2] > (t0 - 0.5) * anim.FPS})
    st = time.time()
    jobs = [(proj, i, a, b, path) for i, a, b, path in redo]
    with _pool(proj, S, min(n, max(1, len(jobs)))) as pool:
        for i, rc in pool.imap_unordered(_chunk, jobs):
            if rc: raise SystemExit('描画に失敗 part %d' % i)
    all_jobs = [(proj, i, a, b, path) for i, a, b, path in M['parts']]
    _join(proj, S, tmp, all_jobs, out)
    M['at'] = time.strftime('%Y-%m-%d %H:%M:%S'); json.dump(M, open(mp, 'w'), ensure_ascii=False)
    print(out, '直し：部品 %d / %d を描き直し %.0f 秒' % (len(jobs), len(all_jobs), time.time() - st))
    return out, [(a / anim.FPS, b / anim.FPS) for _, a, b, _ in redo]
