#!/usr/bin/env python3
# ナレーション音声＋台本 → 動画（作業AI・2026-10-15）
#   python3 make.py <プロジェクト> [--step all|voice|draft|stills|video|check|nouhin|naoshi|jikan] [--drive <フォルダID>] [--t 秒 秒 ...]
#   直し：story.py のその場面を直してから  python3 make.py <P> --step naoshi --at 83.5 90 --memo "1:23 のテロップの数字"（その秒の部品だけ描き直し→質の門）
#   時間：python3 make.py <P> --step jikan（段ごとの機械の時間・作業AIの仕上げの時間・動画1分あたり）
# 入力は2つだけ（依頼主 10/15「ナレーションと台本しか渡さない」「ナレーションはただ録っただけ」）:
#   <プロジェクト>/input/narration.(wav|mp3|m4a)   依頼主が録ったままの粗いナレーション（言い直し・つなぎ言葉・間・速さのばらつき込み）
#   <プロジェクト>/input/daihon.txt                台本（そのままの文章。区間・訴求・【間】は書かなくてよい＝作業AIが台本と声から決める）
#                                                  ※ 前の形（script.md の表・script.txt）も読める
# 作業AIが作るもの:
#   work/kousei.json・kousei.md   区間・訴求・【間】（① 声のあと自動で推し量る → 作業AIが見直す）
#   story.py                      場面表（draft.py の下書き → 作業AIが仕上げる。行ごとのテロップの選び方 sel と理由つき）
#   video_marketing.json          1本の流れ（draft.py の下書き → 作業AIが仕上げる。質の門⑫）
#   <プロジェクト>/work/  out/  check/             作業・書き出し・静止画
# 順番（飛ばせない）：① voice（字ごとの時刻だけ）→ ② story → ③ video（GPU）→ ④ check（質の門）→ ⑤ 動画編集の絶対ルールの門（zettai-mon.py）→ 納品の門（AIの印）→ ⑥ Drive
#   絶対ルール（ZETTAI-RULES.md・依頼主 10/19）：ナレーションはジャンプカット済みで依頼主から来る → ① は声を編集しない（間・速さ・切り詰めを通さない）
#   ④が不合格なら⑤⑥に進まない。⑤は機械の検査＋作業AIの目視（--mokushi-ok）の両方が済んでいないと⑥に進まない
import os, sys, json, subprocess, argparse, shutil, time
TOOL = os.path.dirname(os.path.abspath(__file__)); LIB = os.path.join(TOOL, 'lib'); sys.path.insert(0, LIB)
import paths
ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--step', default='all'); ap.add_argument('--drive'); ap.add_argument('--t', nargs='*', type=float)
ap.add_argument('--force-voice', action='store_true')
ap.add_argument('--at', nargs='*', type=float, help='直し（--step naoshi）の秒。2つ組で 始め 終わり（1つだけならその前後3秒）')
ap.add_argument('--memo', default='', help='直し（--step naoshi）の中身（例「1:23 のテロップの数字が違う」）')
ap.add_argument('--as-is', action='store_true', help='声は編集せず時刻だけ取る（答えを見ない練習 mikai.py 用）')
ap.add_argument('--voice-tts', action='store_true', help='試し用：台本どおりに読んだきれいな声（TTS）を ElevenLabs の強制アライメントで合わせる前の形（本番では使わない）')
K = json.load(open(paths.KIJUN))
A = P = NAME = OUT = WK = None
def log(*a): print('［yt-henshu］', *a, flush=True)
def wait_load():
    """Mac の決まり（~/rin6/state/yt-anime-1014/kata/full/GENDO.md）：メモリの圧力が1（normal）以外の時だけ待つ（load では待たない＝一括処理は最低の優先度で後ろに回る）"""
    import subprocess
    while subprocess.run(['bash', os.path.expanduser('~/rin6/state/night-lock/night-slot.sh'), 'ls'], capture_output=True, text=True).stdout.strip().endswith('いまは待つ状態'):
        log('メモリが詰まっているので待ちます'); time.sleep(60)
def newer(a, bs): return os.path.exists(a) and all(os.path.getmtime(a) >= os.path.getmtime(b) for b in bs if os.path.exists(b))
def step_voice():
    ins = [os.path.join(P, 'input', f) for f in os.listdir(os.path.join(P, 'input'))]
    tj = os.path.join(WK, 'timing.json')
    if newer(tj, ins) and not A.force_voice: log('① 声はそのまま（入力が変わっていない）'); return
    if A.voice_tts:      # 試し用（台本どおりのきれいな声）。本番の入口ではない
        import voice
        J = voice.prep(P, K); log('① 声（試し・TTS）：ジャンプカット %d か所・長さ %.1f 秒' % (J['cuts'], J['duration'])); return
    import narr_bridge
    if not A.as_is: log('① 絶対ルール2（依頼主 10/19）：声はジャンプカット済みで来る → 編集しない（時刻だけ取る）')
    A.as_is = True
    J = narr_bridge.prep(P, K, as_is=True, log=log)
    ma = sum(1 for x in J['lines'] if '【間】' in x['text'])
    log('① 声：%s・%d 行・長さ %.1f 秒（元 %s 秒）・消した所 %d・全体の速さ %.2f 倍・【間】%d（作業AIの推定）→ work/kousei.md で区間・訴求・間を見直す'
        % ('編集なし（時刻だけ）' if A.as_is else '言い直し・つなぎ言葉・間を編集', len(J['lines']), J['duration'], J.get('dur_in'), J['cuts'], J['speed'], ma))
def step_draft():
    sp = os.path.join(P, 'story.py')
    if os.path.exists(sp): log('② 場面表あり（story.py）'); return
    subprocess.run([sys.executable, os.path.join(TOOL, 'draft.py'), P], check=True)
    log('② 台本と声から下書きを作りました → story.py（行ごとのテロップの選び方つき）・video_marketing.json（1本の流れ）。作業AIが訴求と流れを見て仕上げる')
def step_story():
    r = subprocess.run([paths.VENV_PY if False else sys.executable, os.path.join(P, 'story.py')], env=dict(os.environ, PROJ=P), capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); raise SystemExit('🔴 場面表（story.py）でエラー')
    log('② 場面表：', r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '')
def step_stills(ts):
    import render
    for p in render.stills(P, ts): log('静止画', p)
def step_video():
    import render
    return render.video(P, os.path.join(OUT, NAME + '.mp4'))
def step_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location('check', os.path.join(TOOL, 'check.py')); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
    ok = C.main(P, os.path.join(OUT, NAME + '.mp4'))
    stamp = time.strftime('%Y%m%d-%H%M')
    shutil.copy(os.path.join(OUT, 'hikaku.tsv'), os.path.join(OUT, 'hikaku-%s.tsv' % stamp))
    if not ok: raise SystemExit('🔴 ④ 質の門：不合格。out/check.json の「外れ」を直してからもう一度')
    log('④ 質の門：合格（out/hikaku.tsv に見本と今回の比較）')
def step_naoshi():
    """秒を指定した直し（抜けH・外注さんへの Frame.io の直しと同じ形）：
    ① 直しの依頼を work/naoshi.jsonl に残す ② 直す前の静止画を check/naoshi-<日時>/ に ③ 作業AIが story.py のその場面を直す（この段の前に）
    ④ その秒にかかる部品（約20秒単位）だけ描き直して差し込む ⑤ 直した後の静止画 ⑥ 質の門をもう一度（全体）"""
    import render
    at = A.at or []
    if not at: raise SystemExit('--at 秒 [秒] が要る（例 --at 83.5 90）')
    rngs = [(at[i], at[i + 1]) for i in range(0, len(at) - 1, 2)] if len(at) > 1 else [(max(0, at[0] - 3), at[0] + 3)]
    v = os.path.join(OUT, NAME + '.mp4'); stamp = time.strftime('%Y%m%d-%H%M%S'); cd = os.path.join(P, 'check', 'naoshi-' + stamp); os.makedirs(cd, exist_ok=True)
    ts = sorted({round(t, 2) for a, b in rngs for t in (a, (a + b) / 2, b)})
    for t in ts:
        if os.path.exists(v): subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', v, '-frames:v', '1', os.path.join(cd, 'mae_%07.2f.png' % t)])
    rec = {'at': stamp, 'ranges': rngs, 'memo': A.memo, 'story_mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(os.path.join(P, 'story.py'))))}
    out, redone = render.naoshi(P, v, rngs)
    for t in ts: subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', v, '-frames:v', '1', os.path.join(cd, 'ato_%07.2f.png' % t)])
    rec['redone'] = redone
    with open(os.path.join(WK, 'naoshi.jsonl'), 'a') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    log('直し：%s → 描き直し %s ／ 前後の静止画 %s（作業AIが目で比べる）' % (rngs, redone, cd))


def step_jikan():
    """1本にかかる時間（抜けJ）：work/jikan.tsv（段ごとの機械の時間）と、作業AIが場面表を仕上げた時間（story.py の下書き→最後の保存）"""
    jt = os.path.join(WK, 'jikan.tsv')
    if not os.path.exists(jt): raise SystemExit('まだ測った記録が無い（work/jikan.tsv）')
    rows = [l.split('\t') for l in open(jt).read().splitlines()[1:]]
    last = {}
    for r in rows: last[r[1]] = float(r[2])
    dur = float(rows[-1][3]) if rows else 0
    tot = sum(last.values())
    dj = os.path.join(WK, 'draft_plan.json'); sp = os.path.join(P, 'story.py')
    shiage = (os.path.getmtime(sp) - os.path.getmtime(dj)) if os.path.exists(dj) and os.path.exists(sp) and os.path.getmtime(sp) > os.path.getmtime(dj) else 0
    for k, v in last.items(): log('  %-8s %7.0f 秒' % (k, v))
    log('機械の時間 計 %.0f 秒（%.1f 分）・作業AIの仕上げ（下書き→最後の保存）%.0f 分・動画 %.1f 分 → 動画1分あたり 機械 %.1f 分'
        % (tot, tot / 60, shiage / 60, dur / 60, (tot / 60) / max(0.1, dur / 60)))
    return {'machine_s': tot, 'shiage_s': shiage, 'video_s': dur, 'steps': last}


def step_nouhin():
    v = os.path.join(OUT, NAME + '.mp4')
    # ⑤ 動画編集の絶対ルールの門（ZETTAI-RULES.md）：1つでも外れたら納品の写しを作らない・Drive に上げない
    if subprocess.run(['python3', os.path.join(TOOL, 'zettai-mon.py'), P, '--mp4', v]).returncode:
        raise SystemExit('🔴 ⑤ 動画編集の絶対ルールの門：不合格（外れた理由は上・~/rin6/state/yt-henshu/zettai-mon/）')
    r = subprocess.run(['python3', paths.AI_LABEL, v]);
    if r.returncode:
        subprocess.run(['python3', paths.AI_LABEL, '--strip', v], check=True)
        cl = v.replace('.mp4', '.clean.mp4')
        if os.path.exists(cl): shutil.move(cl, v)
        if subprocess.run(['python3', paths.AI_LABEL, v]).returncode: raise SystemExit('🔴 ⑤ AIの印が消えない')
    subprocess.run(['python3', paths.AI_LABEL, '--sheet', v], check=True)
    if subprocess.run(['python3', paths.AI_LABEL, '--gate', v]).returncode:
        raise SystemExit('⏸ ⑤ 納品の門：機械の検査は済み。一覧画像を作業AIが目で見て python3 %s --mokushi-ok %s のあと、もう一度 --step nouhin' % (paths.AI_LABEL, v))
    log('⑤ 納品の門：合格')
    if A.drive:
        r = subprocess.run(['python3', paths.DRIVE_UP, v, A.drive, NAME + '.mp4'], capture_output=True, text=True); print(r.stdout, r.stderr)
        if r.returncode: raise SystemExit('🔴 ⑥ Drive に上げられませんでした')
        log('⑥ Drive に上げました')
    else: log('⑥ Drive のフォルダID（--drive）が無いので上げていません')
if __name__ == '__main__':
    A = ap.parse_args(); P = os.path.abspath(A.proj); NAME = os.path.basename(P.rstrip('/'))
    OUT = os.path.join(P, 'out'); WK = os.path.join(P, 'work'); os.makedirs(OUT, exist_ok=True); os.makedirs(WK, exist_ok=True)
    S = A.step
    (os.getpriority(os.PRIO_PROCESS, 0) < 19 and os.setpriority(os.PRIO_PROCESS, 0, 19)); wait_load()   # 重い一括処理は nice 19（10/15 の決まり）
    def timed(name, fn, *a):
        t0 = time.time(); r = fn(*a); dt = time.time() - t0
        jt = os.path.join(WK, 'jikan.tsv'); new = not os.path.exists(jt)
        tj = os.path.join(WK, 'timing.json'); dur = json.load(open(tj))['duration'] if os.path.exists(tj) else 0
        with open(jt, 'a') as f:
            if new: f.write('日時\t段\t秒\t動画の長さ\n')
            f.write('%s\t%s\t%.1f\t%.1f\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), name, dt, dur))
        return r
    if S in ('all', 'voice'): timed('voice', step_voice)
    if S in ('all', 'draft'): timed('draft', step_draft)
    if S in ('all', 'stills', 'video'): timed('story', step_story)
    if S == 'stills': step_stills(A.t or [2, 10, 30, 60, 90])
    if S in ('all', 'video'): timed('video', step_video)
    if S == 'naoshi': timed('story', step_story); timed('naoshi', step_naoshi)
    if S in ('all', 'video', 'check', 'naoshi'): timed('check', step_check)
    if S in ('all', 'nouhin'): timed('nouhin', step_nouhin)
    if S in ('all', 'jikan'): step_jikan()
