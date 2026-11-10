#!/usr/bin/env python3
# 書き出し（どの動画でも同じ）。
#   SPEC=stories/xxx.json python3 build/render.py stills 10 30 60   → check/mine_<秒>.png（静止画で確かめる）
#   SPEC=stories/xxx.json python3 build/render.py video [t0 t1] [出力.mp4]
#     → 10本に分けて並列で描き、つなぎ、元の音声を【再エンコードせず】そのまま重ねる
#   SPEC を省くと stories/insta-3min.json。SPEC=scenes_3min のように .json でない名前なら Python の場面表を読む（最初の試作）
import sys, os, subprocess, time, importlib, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
BASE = os.path.dirname(HERE)
SPEC = os.environ.get('SPEC', 'stories/insta-3min.json')
STORY = None
if SPEC.endswith('.json'):
    STORY = json.load(open(SPEC if os.path.isabs(SPEC) else os.path.join(BASE, SPEC)))
    if STORY.get('theme') and not os.environ.get('THEME'): os.environ['THEME'] = STORY['theme']
import anim

def load():
    if STORY is not None:
        import story
        sc, sb, _, _ = story.load_story(SPEC if os.path.isabs(SPEC) else os.path.join(BASE, SPEC))
        return sc, sb
    m = importlib.import_module(SPEC)
    return m.SCENES, m.SUBS

def stills(ts):
    sc, sb = load()
    os.makedirs(os.path.join(BASE, 'check'), exist_ok=True)
    for t in ts:
        p = os.path.join(BASE, 'check', 'mine_%06.2f.png' % t)
        anim.frame_at(sc, sb, t).save(p); print(p)

def chunk(args):
    i, f0, f1, out = args
    sc, sb = load()
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (anim.W, anim.H),
           '-r', '30000/1001', '-i', '-', '-c:v', 'h264_videotoolbox', '-b:v', '16M', '-maxrate', '20M', '-allow_sw', '0', '-pix_fmt', 'yuv420p', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(anim.frame_at(sc, sb, f / anim.FPS).tobytes())
    p.stdin.close(); p.wait()
    return i, p.returncode

def video(t0, t1, out, n=10):
    from multiprocessing import Pool
    f0, f1 = int(round(t0 * anim.FPS)), int(round(t1 * anim.FPS))
    tmp = os.path.join(BASE, 'build', 'tmp'); os.makedirs(tmp, exist_ok=True)
    step = (f1 - f0 + n - 1) // n
    jobs = [(i, f0 + i * step, min(f1, f0 + (i + 1) * step), os.path.join(tmp, 'part%02d.mp4' % i)) for i in range(n) if f0 + i * step < f1]
    st = time.time()
    with Pool(len(jobs)) as pool:
        for i, rc in pool.imap_unordered(chunk, jobs):
            print('part', i, 'rc', rc, '%.0fs' % (time.time() - st), flush=True)
            if rc: raise SystemExit('描画に失敗 part %d' % i)
    lst = os.path.join(tmp, 'list.txt')
    open(lst, 'w').write(''.join("file '%s'\n" % j[3] for j in jobs))
    silent = os.path.join(tmp, 'silent.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', silent], check=True)
    audio = os.path.join(BASE, (STORY or {}).get('audio', 'src/audio_full.m4a'))
    outp = out if os.path.isabs(out) else os.path.join(BASE, out)
    S = STORY or {}
    if not S.get('sfx') and not S.get('bgm'):
        # 音声は再エンコードしない（元の音声のまま）
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-ss', str(t0), '-t', str(t1 - t0), '-i', audio,
                        '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'copy', '-shortest', '-movflags', '+faststart', outp], check=True)
    else:
        # ナレーションだけの音声のとき: 効果音（部品の出る時刻に自動）と BGM を重ねる
        import sfx
        ins = ['-i', silent, '-ss', str(t0), '-t', str(t1 - t0), '-i', audio]; mix = ['[1:a]volume=1.0[a0]']; n = 1; labs = ['[a0]']
        if S.get('sfx'):
            sc, _ = load(); ev = sfx.events_from_scenes(sc, t0, t1)
            ins += ['-i', sfx.render_track(ev, t1 - t0, os.path.join(tmp, 'sfx.wav'), S.get('sfx_gain', 0.5))]; n += 1
            mix.append('[%d:a]volume=1.0[a%d]' % (n, n)); labs.append('[a%d]' % n)
        if S.get('bgm'):
            ins += ['-stream_loop', '-1', '-i', os.path.join(BASE, S['bgm'])]; n += 1
            mix.append('[%d:a]volume=%s[a%d]' % (n, S.get('bgm_gain', 0.12), n)); labs.append('[a%d]' % n)
        fc = ';'.join(mix) + ';' + ''.join(labs) + 'amix=inputs=%d:duration=first:normalize=0[aout]' % len(labs)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', fc, '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '192k', '-t', str(t1 - t0), '-movflags', '+faststart', outp], check=True)
    print(outp, 'total %.0fs' % (time.time() - st))

if __name__ == '__main__':
    if sys.argv[1] == 'stills': stills([float(x) for x in sys.argv[2:]])
    else:
        a = sys.argv[2:]
        d0 = float((STORY or {}).get('start', 0)); d1 = float((STORY or {}).get('end', 180))
        video(float(a[0]) if a else d0, float(a[1]) if len(a) > 1 else d1, a[2] if len(a) > 2 else 'shisaku-3min.mp4')
