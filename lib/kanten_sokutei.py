# 作業AIの1本を、見本の per_full と【同じ道具・同じ式】で測る（作業AI・2026-10-16）
#   見本の数字（numbers.full・first30・selection 以外）は、yoru の前処理（onepass → demucs → resample → Whisper large-v3 → ana1）が作った ana.json から来ている。
#   作業AIの mp4 も同じ順で通して ana.json を作り、kanten.from_per_full と同じ読み方で指標にする（別の式で測って比べない）。
#   measure(mp4, name) → (指標, ana.json の場所)。作業場所は kata/full/raw/rin__<name>/（見本と同じ置き場・名前の頭 rin__ で見本と分ける）
#   重い処理は nice 19・担当の共通の札（night-slot.sh＝メモリの圧力が1以外なら待つ）を1段ごとに取る
import os, sys, json, shutil, subprocess, time
import paths
BASE = paths.ENGINE; FULL = os.path.join(BASE, 'kata', 'full'); Y = os.path.join(FULL, 'yoru')
PY = os.path.join(BASE, '.venv', 'bin', 'python'); OPY = os.path.join(FULL, 'tools0', 'ocrvenv', 'bin', 'python')
SLOT = os.path.expanduser('~/rin6/state/night-lock/night-slot.sh')
LOW = ['nice', '-n', '19']


def _run(tag, cmd, log):
    g = subprocess.run(['bash', SLOT, 'get', 'yt-kanten-%s' % tag, str(os.getpid())], capture_output=True, text=True); slot = g.stdout.strip()
    try:
        for k in range(4):
            t = time.time(); r = subprocess.run(LOW + cmd, cwd=BASE, capture_output=True, text=True)
            log.write('%s %s rc=%d %.0f秒\n%s\n%s\n' % (time.strftime('%H:%M:%S'), tag, r.returncode, time.time() - t, r.stdout[-1500:], r.stderr[-1500:])); log.flush()
            if r.returncode == 0 or '-12912' not in (r.stdout + r.stderr): break
            time.sleep(30)   # GPU の回路が埋まっている → 30秒おいてやり直す（3回まで）
    finally:
        if slot: subprocess.run(['bash', SLOT, 'put', slot])
    if r.returncode != 0: raise SystemExit('🔴 観点の測り %s で失敗（記録 %s）' % (tag, log.name))


def measure(mp4, name, force=False):
    vid = 'rin__' + name; od = os.path.join(FULL, 'raw', vid); os.makedirs(od, exist_ok=True)
    src = os.path.join(od, vid + '.mp4')
    if force or not os.path.exists(src) or os.path.getmtime(src) < os.path.getmtime(mp4):
        for f in os.listdir(od):   # 動画が変わったら前の測りを全部捨てる（古い材料を使い回さない）
            p = os.path.join(od, f); shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)   # 置き場を移した印（symlink）は印だけ消す（10/16）
        st = os.path.join(FULL, 'stems', vid)
        if os.path.islink(st): os.remove(st)   # RAM へ移した印は印だけ消す（10/16）
        elif os.path.exists(st): shutil.rmtree(st)
        shutil.copy2(mp4, src)
    log = open(os.path.join(od, 'kanten_sokutei.log'), 'a')
    if not os.path.exists(os.path.join(od, 'blk.npz')): _run('onepass', [PY, os.path.join(Y, 'onepass.py'), src], log)
    if not os.path.exists(os.path.join(FULL, 'stems', vid, 'done')): _run('demucs', [PY, os.path.join(BASE, 'sozai2', 'tools', 'stems.py'), src], log)
    if not os.path.exists(os.path.join(od, 'vocals16k.wav')): _run('resample', [PY, os.path.join(Y, 'resample.py'), vid], log)
    if not os.path.exists(os.path.join(od, 'words_v3.json')): _run('whisper', [PY, os.path.join(FULL, 'tools0b', 'words3.py'), vid], log)
    if not os.path.exists(os.path.join(od, 'ana.json')): _run('ana1', [OPY, os.path.join(Y, 'ana1.py'), src], log)
    ana = json.load(open(os.path.join(od, 'ana.json')))
    return ana, os.path.join(od, 'ana.json')


def values(od, ana, D):
    """ana.json・ev.json・words_v3.json → 観点の指標（見本の per_full と同じ読み方。場面の役割に頼らない分だけ）"""
    import re, kanten as KT
    ev = json.load(open(os.path.join(od, 'ev.json')))
    wv = json.load(open(os.path.join(od, 'words_v3.json'))); segs = wv['segments'] if isinstance(wv, dict) else wv
    chars = sum(len(re.sub(r'[\s、。,.!?！？「」『』…・]', '', w[2])) for s_ in segs for w in s_['words'])
    sp_s = ana.get('speech_s') or 0
    cps = chars / sp_s if sp_s else None
    sil = [y - x for x, y in ev.get('silences') or []]
    rows = [o.get('visibility') or {} for o in ev.get('telop') or []]
    num = to_numbers(ana)
    import kanten as KT_
    if KT_.YAMA:
        import yama
        num = yama.overlay(num, od)   # 見本と同じく、動き続けを変化の山で切り直した数字（lib/yama.py）
    num['speed'] = {'chars_per_s_speaking': cps, 'whole_speedup_guess': round(cps / 7.5, 2) if cps else None}
    num['4_silence'] = {'pauses_0.3s_plus': [x for x in sil if x >= 0.3]}
    v = KT.from_per_full({'numbers': num, 'duration_s': D, 'scenes': [], 'modes': [], 'base_look': {}, 'video_marketing': {}})
    for k in ('w_modes', 'k_retention_n', 'c_duration_s', 'tr_first_proof_s', 'p_answer_first_s', 'k_cta_first_ratio', 'u_rephrase_pm'):
        v.pop(k, None)   # 場面の記録が無い所で作った値は使わない（作業AIの story_meta から別に出す）
    ph = [r['phone390_height_px'] for r in rows if isinstance(r.get('phone390_height_px'), (int, float))]
    if ph: v['v_small_share'] = sum(1 for x in ph if x < 15) / len(ph)
    ct = [r['contrast_fill_vs_surround'] for r in rows if isinstance(r.get('contrast_fill_vs_surround'), (int, float))]
    if ct: v['v_lowcontrast_share'] = sum(1 for x in ct if x < 3) / len(ct)
    return v


def to_numbers(ana):
    """ana.json → per_full の numbers と同じ形（from_per_full がそのまま読める）"""
    n = {'full': ana.get('full'), 'first30': ana.get('first30'), 'bgm_switch_candidates': ana.get('bgm_switch_candidates') or []}
    b = (ana.get('full') or {}).get('bgm') or {}
    if b.get('voice_minus_bg_db') is not None: n['voice_minus_bg_db'] = {'full': b['voice_minus_bg_db']}
    return n
