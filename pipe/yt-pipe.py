#!/usr/bin/env python3
# 声＋台本 → 1本の完成動画と報告（yt-henshu-pipe・作業AI 2026-10-19）
#   依頼主は「ナレーション（ジャンプカット済みの声）＋台本」だけを渡す。そこから下の段を順に1本で回す（コマンド1つ）
#     python3 ~/rin6/tools/yt-henshu/pipe/yt-pipe.py --koe <声.wav|mp3|m4a> --daihon <台本.txt> --out <作業フォルダ> [--kind VSL|YouTube]
#                                                   [--name 書き出しの名前] [--drive <Drive のフォルダID>] [--from 段] [--to 段]
#   段（--from で途中から・作った物は作業フォルダに残るので続きから回せる）
#     junbi     声を work/vocals.wav に写す（編集しない＝絶対ルール2）・台本を input/daihon.txt に
#     okoshi    書き起こし（Whisper large-v3・間で切った20秒前後ずつ・抜けは割って起こし直す）        pipe/koe_okoshi.py
#     gyou      台本の文の切れ目で行に分ける → 強制合わせ（MMS_FA）→ 強制合わせの頭と静かな長さで切り直す pipe/gyou_auto.py・align/kotoba_align.py
#     jimaku    字幕に出す字（台本と違う所を AI が「聞き違い／言い換え」で1件ずつ判断）→ 切れ目の表（文節）  pipe/jimaku_ji.py・pipe/kire_auto.py
#     bamen     場面割り・場面ごとの訴求・部品と音（AI が章ごとに書き、機械の検査で直させる）              pipe/bamen_gen.py
#     sozai     素材一覧（出どころ・種類ごとの使った秒）                                               pipe/sozai_auto.py
#     render    GPU 書き出し（h264_videotoolbox・nice 19・同時2本・メモリの圧力が1の時だけ始める）       lib/render.py
#     mon       動画編集の絶対ルール10の門（--nouhin：通れば AI の印を外した納品の写し）               zettai-mon.py
#     kensa     字幕のずれ（全件・1コマ単位）・字幕の割れ・台本との突き合わせ                           pipe/jimaku_koma.py・kire_bunseki・pipe/jimaku_taishou.py
#     me        目視の一覧画像＋別の目（AI）が1コマずつ見る → 通れば ai-label-check --mokushi-ok        pipe/me_ai.py
#     drive     Drive に上げて、見られる人が依頼主と you@ だけか確かめる                                 tools/drive-up.py
#     houkoku   報告（out/<名前>-houkoku.md：数字・例外・残り）
#   依頼主へは送らない（作業AIが確かめてから送る）
import os, sys, json, glob, shutil, subprocess, time, argparse, re
HERE = os.path.dirname(os.path.abspath(__file__)); TOOL = os.path.dirname(HERE)
VPIPE = os.path.join(HERE, '.venv', 'bin', 'python')
VNARR = os.path.join(TOOL, 'narration', '.venv', 'bin', 'python')
VALIGN = os.path.join(TOOL, 'align', '.venv', 'bin', 'python')
STEPS = ['junbi', 'okoshi', 'gyou', 'jimaku', 'bamen', 'sozai', 'render', 'mon', 'kensa', 'me', 'drive', 'houkoku']
ap = argparse.ArgumentParser(); ap.add_argument('--koe'); ap.add_argument('--daihon'); ap.add_argument('--out', required=True)
ap.add_argument('--kind', default='VSL'); ap.add_argument('--name'); ap.add_argument('--drive'); ap.add_argument('--from', dest='frm', default='junbi'); ap.add_argument('--to', default='houkoku')
ap.add_argument('--big-min', type=float, default=15.3, help='門で測る大きな切り替わり/分の下限（v12 の 15.3 を下回らない・作業AI 10/19）')
ap.add_argument('--move-min', type=float, default=0.0, help='門で測る動く要素/分の下限（v14：手本で一番多い本 31.2）')
ap.add_argument('--gpu', type=int, default=2, help='同時に書き出す本数（講義動画の作業員も使うので既定2）')
ap.add_argument('--edl', help='v14：編集の指示書（yt-edl が1文ずつ判断で書いた edl.json）。あれば bamen は AI の場面表でなく、指示書どおりに組む（中身を道具で選び直さない）')
A = ap.parse_args(); P = os.path.abspath(A.out); NAME = A.name or os.path.basename(P.rstrip('/'))
os.makedirs(os.path.join(P, 'input'), exist_ok=True); os.makedirs(os.path.join(P, 'work'), exist_ok=True); os.makedirs(os.path.join(P, 'out'), exist_ok=True)
if A.edl:   # 指示書の写しを作業フォルダに置き、子の処理（story.py・門・別の目）に知らせる
    _e = os.path.join(P, 'work', 'edl.json')
    if os.path.abspath(os.path.expanduser(A.edl)) != _e: shutil.copy(os.path.expanduser(A.edl), _e)
    os.environ['PIPE_EDL'] = '1'; os.environ['PIPE_EDL_PATH'] = _e
    _th = json.load(open(_e)).get('theme')   # 指示書の見た目の名前（例 tehon-shiro）→ 描画エンジンの THEME に渡す
    if _th:
        _tp = os.path.expanduser('~/rin6/state/yt-anime-1014/themes/%s.json' % _th)
        if not os.path.exists(_tp): raise SystemExit('🔴 指示書の theme %s の設定ファイルが無い（%s）' % (_th, _tp))
        os.environ['THEME'] = _tp
MP4 = os.path.join(P, 'out', NAME + '.mp4'); NOUHIN = MP4.replace('.mp4', '.nouhin.mp4')
JIKAN = os.path.join(P, 'work', 'pipe-jikan.tsv')
def log(*a): print('［yt-pipe］', time.strftime('%H:%M:%S'), *a, flush=True)
def run(cmd, **k):
    log('$', ' '.join(os.path.basename(c) if i < 2 else c for i, c in enumerate(cmd)))
    r = subprocess.run(cmd, cwd=P, **k)
    if r.returncode: raise SystemExit('🔴 止まった：%s（rc=%d）' % (' '.join(cmd[:3]), r.returncode))
    return r
def nice(cmd): return ['nice', '-n', '19'] + cmd
def wait_mem():
    while subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], capture_output=True, text=True).stdout.strip() != '1':
        log('メモリの圧力が1（通常）でないので、始めずに待つ'); time.sleep(60)
def step_junbi():
    if not A.koe or not A.daihon: raise SystemExit('--koe と --daihon が要る')
    ext = os.path.splitext(A.koe)[1].lower(); dst = os.path.join(P, 'input', 'narration' + ext)
    if os.path.abspath(A.koe) != dst: shutil.copy(A.koe, dst)
    shutil.copy(A.daihon, os.path.join(P, 'input', 'daihon.txt')) if os.path.abspath(A.daihon) != os.path.join(P, 'input', 'daihon.txt') else None
    # 声は編集しない（絶対ルール2）：wav に写すだけ。サンプルの数は変えない（48k/44.1k はそのまま）
    run(['ffmpeg', '-v', 'error', '-y', '-i', dst, '-c:a', 'pcm_s16le', os.path.join(P, 'work', 'vocals.wav')])
    a, b = [float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout) for f in (dst, os.path.join(P, 'work', 'vocals.wav'))]
    if abs(a - b) > 0.034: raise SystemExit('🔴 声の写しの長さが元と違う（%.3f → %.3f）' % (a, b))
    log('声 %.2f 秒（編集なし）' % b)
    yousou_check()
YOUSO = ['~/rin6/tools/yt-henshu/pipe/sozai/chara_icon1024.png', '~/rin6/state/yt-evervsl-1019/e/logo/openai_blossom.png',
         '~/rin6/state/yt-anime-1014/sozai/bgm/honpen_gray.wav', '~/rin6/state/yt-anime-1014/sozai/bgm/honpen_gray_b.wav', '~/rin6/state/yt-anime-1014/sozai/bgm/kokuchi.wav', '~/rin6/state/yt-anime-1014/sozai/bgm/afterglow.wav',
         '~/rin6/state/yt-anime-1014/sozai/se/index.tsv', '~/rin6/state/yt-anime-1014/sozai/jinbutsu/hito_banzai.png', '~/rin6/state/yt-anime-1014/sozai/shashin/photo_kaku.png']
def yousou_check():
    """使う素材が手元で読めるか（内蔵を空ける作業で Drive へ移ると読めなくなる・10/19 自社キャラのアイコンで止まった）"""
    G = json.load(open(os.path.join(HERE, 'gamen.json')))
    fs = [os.path.expanduser(f) for f in YOUSO] + [os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/gamen/%s.png' % k) for k in G]
    bad = [f for f in fs if not (os.path.exists(f) and os.path.getsize(f) > 0)]
    if bad: raise SystemExit('🔴 素材が読めない（Drive へ移った？）：' + '・'.join(bad))
    log('素材 %d 本が読める' % len(fs))
def step_okoshi(): wait_mem(); run(nice([VNARR, os.path.join(HERE, 'koe_okoshi.py'), P]))
def step_gyou():
    run([VPIPE, os.path.join(HERE, 'gyou_auto.py'), P]); wait_mem()
    run(nice([VALIGN, os.path.join(TOOL, 'align', 'kotoba_align.py'), P]))
    run([VPIPE, os.path.join(HERE, 'gyou_auto.py'), P, '--fa'])
def step_jimaku():
    run(['python3', os.path.join(HERE, 'jimaku_ji.py'), P]); run([VPIPE, os.path.join(HERE, 'kire_auto.py'), P])
    shutil.copy(os.path.join(HERE, 'ki1.py'), os.path.join(P, 'ki1.py'))
def step_bamen():
    shutil.copy(os.path.join(HERE, 'ki1.py'), os.path.join(P, 'ki1.py'))   # bamen から始めても道具の ki1.py を写す（古い写しで公式ロゴが無いまま組んだ・10/23 KMXS k3）
    if not A.edl: return run(['python3', os.path.join(HERE, 'bamen_gen.py'), P, '--kind', A.kind])
    # v14：頭＋「指示書どおりに組む」1行＋終わり で story.py を作り、1回走らせて組めるかを確かめる
    mid = ("\n# ===== 中身＝編集の指示書（work/edl.json・yt-edl が1文ずつ判断で書いた）を pipe/edl_kumi.py が書いてあるとおりに組む =====\n"
           "from edl_kumi import kumitate as _kumitate\n_EDL_LOG = _kumitate(globals(), os.path.join(PROJ, 'work', 'edl.json'))\n")
    open(os.path.join(P, 'story.py'), 'w').write(open(os.path.join(HERE, 'story_head.py')).read() + mid + open(os.path.join(HERE, 'story_tail.py')).read())
    run(['python3', os.path.join(P, 'story.py')], env=dict(os.environ, PROJ=P))
    L = json.load(open(os.path.join(P, 'work', 'edl_kumi.json')))
    log('指示書どおりに組んだ：場面 %d・部品 %d・動く人物 %d・動き続ける部品 %d・カメラ %d・部品が無い %d・言葉が場面の外 %d' % (L['shots'], L['parts'], L['jinbutsu'], L['ugoku_bubun'], L['camera'], len(L['buhin_nashi']), len(L['mitsukaranai'])))
    if L.get('hoshii'): log('🟡 欲しかった絵（手元に無い素材）%d件：%s（work/edl_kumi.json の hoshii）' % (len(L['hoshii']), '・'.join('%s「%s」' % (h.get('shurui'), h.get('mono')) for h in L['hoshii'][:8])))
    if L['buhin_nashi']: log('🟡 指示書の部品が手元に無い %d件（work/edl_kumi.json の buhin_nashi）→ その部品だけ外して組んだ。yt-jinbutsu に頼む／指示書を直す' % len(L['buhin_nashi']))
def step_sozai(): run(['python3', os.path.join(HERE, 'sozai_auto.py'), P])
def step_render():
    yousou_check()
    wait_mem(); shutil.rmtree(os.path.join(P, 'out', 'tmp'), ignore_errors=True)
    code = "import os,sys;sys.path.insert(0,os.path.expanduser('~/rin6/tools/yt-henshu/lib'));import render;render.video(%r,%r,n=%d)" % (P, MP4, A.gpu)
    t0 = time.time(); run(nice(['python3', '-c', code]), env=dict(os.environ, PROJ=P)); log('書き出し %.0f 秒' % (time.time() - t0))
def step_mon():
    r = subprocess.run(['python3', os.path.join(TOOL, 'zettai-mon.py'), P, '--mp4', MP4, '--nouhin'], cwd=P)
    if r.returncode: raise SystemExit('🔴 動画編集の絶対ルールの門：不合格（~/rin6/state/yt-henshu/zettai-mon/%s-%s/kekka.json）' % (os.path.basename(P), NAME))
    rk = os.path.join(P, 'work', 'rock-mon.json')   # 最低ラインは手本の編集者さん（依頼主 10/20 14:4x 絶対ルール）：手本15本と並べて1項目でも下なら止める
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', MP4], capture_output=True, text=True).stdout)
    mado = sorted(int(re.search(r'rock15-(\d+)\.json', f).group(1)) for f in glob.glob(os.path.join(TOOL, 'zettai', 'rock15-*.json')))
    t1 = max([m for m in mado if m <= dur + 0.5] or mado[:1])   # 動画の長さに合わせて手本の頭の窓を選ぶ（10/21 team-lead：30秒の試験を頭171秒の手本と比べて MJrC k1 が外れていた）
    log('手本の編集者さんの門：動画 %.1f 秒 → 手本の頭 %d 秒と比べる' % (dur, t1))
    r = subprocess.run(['python3', os.path.join(TOOL, 'rock-mon.py'), MP4, '--t1', str(t1), '--out', rk])
    if r.returncode: raise SystemExit('🔴 最低ラインは手本の編集者さんの門：不合格（%s）' % rk)
    if dur >= 300:   # 全編だけ：見やすさの門と、動き・見せ方・全画面挿絵の門（依頼主 10/22 20:33〜20:37・手本15本全編の範囲＝zettai/miyasusa-sen.json・hyougen15.json）
        mr, mo, hr, ho = (os.path.join(P, 'work', x) for x in ('miyasusa-raw.json', 'miyasusa.json', 'hyougen-raw.json', 'hyougen.json'))
        for f in (mr, hr):
            if os.path.exists(f) and os.path.getmtime(f) < os.path.getmtime(MP4): os.remove(f)   # 書き出し直した動画は測り直す
        r = subprocess.run(['python3', os.path.join(TOOL, 'miyasusa-mon.py'), MP4, '--raw', mr, '--out', mo, '--sheet', os.path.join(P, 'out', 'miyasusa'), '--mon'])
        if r.returncode: raise SystemExit('🔴 見やすさの門：不合格（%s・並べシート out/miyasusa/）' % mo)
        subprocess.run(['python3', os.path.join(TOOL, 'hyougen-mon.py'), MP4, '--ocr', mr, '--raw', hr, '--out', ho], stdout=subprocess.DEVNULL)
        r = subprocess.run(['python3', os.path.join(TOOL, 'hyougen-hikaku.py'), '--mon', mo, ho])
        if r.returncode: raise SystemExit('🔴 動き・見せ方・全画面挿絵の門：不合格（%s）' % ho)
    kj = os.path.expanduser('~/rin6/state/yt-henshu/zettai-mon/%s-%s/kekka.json' % (os.path.basename(P), NAME))
    big = next((v['大きな切り替わり/分']['今回'] for k, v in (json.load(open(kj)).get('データ', {}).get('9', {}) or {}).items() if '手本と比べた' in k), None) if os.path.exists(kj) else None
    mv = next((v['動く要素/分']['今回'] for k, v in (json.load(open(kj)).get('データ', {}).get('9', {}) or {}).items() if '手本と比べた' in k), None) if os.path.exists(kj) else None
    log('門の測り：大きな切り替わり/分 %s（下限 %.1f）・動く要素/分 %s（下限 %.1f）' % (big, A.big_min, mv, A.move_min))
    if mv is not None and mv < A.move_min: raise SystemExit('🔴 動く要素/分 %.1f ＜ 下限 %.1f → 場面表の部品を足して --from bamen' % (mv, A.move_min))
    if big is not None and big < A.big_min: raise SystemExit('🔴 大きな切り替わり/分 %.1f ＜ 下限 %.1f（v12 を下回る）→ kensa_bamen.py の BIG_PM を上げて --from bamen' % (big, A.big_min))
def step_kensa():
    K = {}
    r = subprocess.run(['python3', os.path.join(HERE, 'jimaku_koma.py'), P, MP4, os.path.join(P, 'work', 'koma.tsv')], capture_output=True, text=True, env=dict(os.environ, PROJ=P))
    print(r.stdout); K['koma'] = r.stdout.strip()
    if r.returncode: raise SystemExit('🔴 jimaku_koma.py が止まった：\n' + r.stderr[-1500:])
    rows = [l.split('\t') for l in open(os.path.join(P, 'work', 'koma.tsv')).read().splitlines()[1:]]
    d = [int(x[4]) for x in rows]; K['koma_n'] = len(d); K['koma_0'] = sum(1 for x in d if x == 0); K['koma_over1'] = sum(1 for x in d if abs(x) > 1); K['koma_max'] = max(abs(x) for x in d) if d else 0
    code = ("import os,sys,json;sys.path.insert(0,%r);os.environ['PROJ']=%r;sys.path.insert(0,%r);import ki1;"
            "J=ki1.build_jimaku(os.path.join(%r,'work','timing_fa.json'),99999);json.dump([s for a,b,s in J],open(os.path.join(%r,'work','fuda.json'),'w'),ensure_ascii=False)") % (P, P, os.path.expanduser('~/rin6/tools/yt-henshu/lib'), P, P)
    run(['python3', '-c', code])
    r = subprocess.run([VPIPE, os.path.expanduser('~/rin6/state/yt-evervsl-1019/v12/wari_kazoe.py'), os.path.join(P, 'work', 'fuda.json'), os.path.join(P, 'work', 'wari.tsv')], capture_output=True, text=True, cwd=HERE)
    print(r.stdout); K['wari'] = r.stdout.strip()
    r = subprocess.run(['python3', os.path.join(HERE, 'jimaku_taishou.py'), os.path.join(P, 'work', 'taishou.tsv')], capture_output=True, text=True, env=dict(os.environ, PROJ=P))
    print(r.stdout); K['taishou'] = r.stdout.strip()
    r = subprocess.run(['python3', os.path.join(HERE, 'jimaku_bunmatsu.py'), P], capture_output=True, text=True)   # 1枚の字幕が文の切れ目をまたいでいないか（作業AI 10/20）
    print(r.stdout); K['bunmatsu'] = r.stdout.strip().splitlines()[0] if r.stdout.strip() else r.stderr[-300:]
    json.dump(K, open(os.path.join(P, 'work', 'kensa-go.json'), 'w'), ensure_ascii=False, indent=1)
    if r.returncode: raise SystemExit('🔴 字幕が文の切れ目をまたぐ：%s（work/bunmatsu.tsv）' % K['bunmatsu'])
    if K['koma_over1']: raise SystemExit('🔴 字幕が言葉の頭から1コマを超えてずれる：%d 枚（work/koma.tsv）' % K['koma_over1'])
    if not re.search(r'A形態素の途中 0 B助詞で始まる 0 C名詞の続き 0', K['wari']): raise SystemExit('🔴 字幕の切れ目で言葉が割れる：%s（work/wari.tsv）' % K['wari'])
def step_me():
    if os.path.exists(os.path.join(P, 'work', 'kata_v13.json')): run(['python3', os.path.join(HERE, 'kirikae_sheet.py'), P, NOUHIN if os.path.exists(NOUHIN) else MP4])   # 切り替えの途中のコマ（v13）
    run(['python3', os.path.join(HERE, 'me_ai.py'), P, NOUHIN if os.path.exists(NOUHIN) else MP4])
    R = json.load(open(os.path.join(P, 'work', 'me_ai.json')))
    # 別の目の例外（作業AI 10/20）：proj/me_reigai.json に書いた1件ずつだけ外す。秒（±1秒）と、その件の中身に含まれる語の両方が合うものだけ。理由・決めた人・日時が無い行は止める
    _rp = os.path.join(P, 'me_reigai.json')
    if os.path.exists(_rp):
        _rg = json.load(open(_rp)); _sec = lambda t: sum(float(x) * 60 ** i for i, x in enumerate(reversed(str(t).split(':'))))
        for g in _rg:
            if not all(g.get(k) for k in ('t', 'kotoba', '理由', '決めた人', '日時')): raise SystemExit('🔴 me_reigai.json の行に t・kotoba・理由・決めた人・日時 のどれかが無い：%s' % json.dumps(g, ensure_ascii=False))
        nokori, hazushi = [], []
        for m in R.get('mondai', []):
            g = next((g for g in _rg if abs(_sec(m.get('t', '0')) - _sec(g['t'])) <= 1.0 and g['kotoba'] in (m.get('naiyou', '') + m.get('naiyou2', ''))), None)
            (hazushi if g else nokori).append(dict(m, reigai=g) if g else m)
        if hazushi:
            R['mondai'] = nokori; R['reigai'] = hazushi; R['ok'] = not nokori
            json.dump(R, open(os.path.join(P, 'work', 'me_ai.json'), 'w'), ensure_ascii=False, indent=1)
            log('別の目の例外で外した %d件：%s' % (len(hazushi), '・'.join('%s %s' % (h['t'], h['reigai']['理由']) for h in hazushi)))
    if A.edl:   # v14：場面ごとに「一瞬で分かるか」と「止まった絵がないか」。直すのは指示書を書く側なので、ここでは止めて知らせる（自動で書き直さない）
        run(['python3', os.path.join(HERE, 'me_shot.py'), P, NOUHIN if os.path.exists(NOUHIN) else MP4])
        S = json.load(open(os.path.join(P, 'work', 'me_shot.json')))
        if not (R.get('ok') and S.get('ok')): raise SystemExit('🔴 別の目：直す所 %d・止まった絵 %d・一瞬で分からない %d（work/me_ai.json・work/me_shot.json）→ 指示書を直して --from bamen' % (len(R.get('mondai', [])), len(S.get('tomatta', [])), len(S.get('wakaranai', []))))
    elif not R.get('ok'): raise SystemExit('⏸ 別の目が直す所を出した（work/me_ai.json）。場面表を直して --from bamen か render から回す')
    run(['python3', os.path.expanduser('~/rin6/tools/ai-label-check.py'), '--mokushi-ok', NOUHIN])
def step_drive():
    if not A.drive: log('Drive のフォルダID（--drive）が無いので上げない'); return
    r = run(['python3', os.path.expanduser('~/rin6/tools/drive-up.py'), NOUHIN, A.drive, NAME + '.mp4'], capture_output=True, text=True); print(r.stdout)
    m_ = re.search(r'^(\S+) (https://drive\.google\.com/\S+)', r.stdout, re.M)   # 1行目は門の「✅ 納品OK」なので、ID とリンクの行を探す
    fid, link = m_.group(1), m_.group(2)
    code = ("import os;from google.oauth2 import service_account;from googleapiclient.discovery import build;"
            "c=service_account.Credentials.from_service_account_file(os.path.expanduser('~/rin/gateway/google-service-account.json'),scopes=['https://www.googleapis.com/auth/drive']).with_subject('you@example.com');"
            "D=build('drive','v3',credentials=c);import json;print(json.dumps(D.permissions().list(fileId=%r,supportsAllDrives=True,fields='permissions(type,role,emailAddress,domain)').execute()['permissions']))") % fid
    perms = json.loads(subprocess.run(['python3', '-c', code], capture_output=True, text=True).stdout)
    who = sorted({p.get('emailAddress') or p.get('domain') or p['type'] for p in perms})
    json.dump({'id': fid, 'link': link, 'perms': perms}, open(os.path.join(P, 'work', 'drive.json'), 'w'), ensure_ascii=False, indent=1)
    if any(p['type'] in ('anyone', 'domain') for p in perms) or not set(who) <= {'you@example.com', 'owner@example.com'}:
        raise SystemExit('🔴 見られる人が依頼主と you@ だけでない：%s（すぐ外す）' % who)
    log('Drive：%s（見られる人 %s）' % (link, '・'.join(who)))
def step_houkoku():
    kj = glob.glob(os.path.expanduser('~/rin6/state/yt-henshu/zettai-mon/%s-%s/kekka.json' % (os.path.basename(P), NAME)))
    Z = json.load(open(kj[0])) if kj else {}
    K = json.load(open(os.path.join(P, 'work', 'kensa-go.json'))) if os.path.exists(os.path.join(P, 'work', 'kensa-go.json')) else {}
    B = json.load(open(os.path.join(P, 'work', 'bamen', 'kensa.json'))) if os.path.exists(os.path.join(P, 'work', 'bamen', 'kensa.json')) else {}
    M = json.load(open(os.path.join(P, 'work', 'me_ai.json'))) if os.path.exists(os.path.join(P, 'work', 'me_ai.json')) else {}
    D = json.load(open(os.path.join(P, 'work', 'drive.json'))) if os.path.exists(os.path.join(P, 'work', 'drive.json')) else {}
    tm = [l.split('\t') for l in open(JIKAN).read().splitlines()] if os.path.exists(JIKAN) else []
    out = ['# %s（yt-pipe の報告・%s）' % (NAME, time.strftime('%Y-%m-%d %H:%M')), '',
           '- 動画：%s（納品の写し %s）' % (MP4, NOUHIN), '- Drive：%s' % (D.get('link') or '上げていない'),
           '- 門：%s・外れ %s・例外 %d' % ('合格' if Z.get('合格') else '不合格', list((Z.get('外れ') or {}).keys()) or 'なし', len(Z.get('例外で通過') or [])),
           '- 字幕のずれ：%s' % K.get('koma', ''), '- 字幕の割れ：%s' % K.get('wari', ''), '- 台本との突き合わせ：%s' % K.get('taishou', ''),
           '- 場面表の検査：%s' % json.dumps(B.get('kazu', {}), ensure_ascii=False), '- 別の目：%s（直す所 %d・例外 %d）' % ('OK' if M.get('ok') else 'NG', len(M.get('mondai', [])), len(M.get('reigai', []))) + '・2回の重なり %s' % json.dumps(M.get('kasanari', {}), ensure_ascii=False),
           '- 手本との比べ（門のルール9）：%s' % json.dumps((Z.get('データ') or {}).get('9', {}), ensure_ascii=False)[:600],
           '- 段ごとの時間：%s' % '・'.join('%s %s秒' % (r[1], r[2]) for r in tm[-12:] if len(r) > 2), '', '依頼主へは送っていない（作業AIが確かめてから送る）']
    fp = os.path.join(P, 'out', NAME + '-houkoku.md'); open(fp, 'w').write('\n'.join(out) + '\n'); log('報告：', fp)
FN = {s: globals()['step_' + s] for s in STEPS}
i0, i1 = STEPS.index(A.frm), STEPS.index(A.to)
# 作業フォルダの ki1.py の写しが古い（棒人間の線画・自社キャラの地紋を読む）なら、共有の新しい ki1.py に差し替える（依頼主 10/20 23:45・古い写しから戻ってこないように 10/21）
_k1 = os.path.join(P, 'ki1.py')
if os.path.exists(_k1):
    sys.path.insert(0, HERE); import ki1_kinshi as _KK
    _t, _ch = _KK.kesu(open(_k1).read())
    if _ch: shutil.copy(_k1, _k1 + '.bak-kinshi'); open(_k1, 'w').write(_t); log('作業フォルダの ki1.py の写しから棒人間の地の線画の部分だけ外した（写しの直しは残す・控え ki1.py.bak-kinshi）')
    if _KK.nokori(open(_k1).read()): raise SystemExit('🔴 作業フォルダの ki1.py に棒人間の線画を読む行が残っている：' + _k1)
try: os.setpriority(os.PRIO_PROCESS, 0, 19)
except PermissionError: pass  # 2dai-run.sh から起動すると既に下げてあり EPERM になる
class MeNG(Exception): pass
def step_me_wrap():
    try: step_me()
    except SystemExit as e:
        if str(e).startswith('⏸'): raise MeNG(str(e))
        raise
FN['me'] = step_me_wrap
seq = STEPS[i0:i1 + 1]; k = 0; ME_MAX = 3   # 別の目が直す所を出したら、場面表を直させて書き出しから見直すまでを最大3回
# 10/20 r10：門が不合格で流れが止まり、字幕の検査と別の目が回らないまま1時間以上気づかれなかった（作業AI 04:3x「不合格でも検査と別の目は続けて回し、終わったら1行」）
#   → 門・検査・別の目は不合格でも次へ進む（不合格は NG に貯める）。NG があれば drive（納品・Drive）には進まない。
#   → 終わったとき・止まったときは必ず houkoku に1行足し、out/<名前>-owari.txt に書く（作業員はこれを見張って team-lead へ送る）
TSUZUKE = ('mon', 'kensa', 'me'); NG = []
HOUKOKU = os.path.expanduser('~/rin6/state/workers/houkoku/yt-henshu-pipe.log')
def owari(msg):
    line = '%s [yt-pipe 自動] %s %s：%s' % (time.strftime('%Y-%m-%d %H:%M'), os.path.basename(os.path.dirname(P.rstrip('/'))) + '/' + os.path.basename(P.rstrip('/')), NAME, msg)
    try:
        with open(HOUKOKU, 'a') as f: f.write(line + '\n')
        open(os.path.join(P, 'out', NAME + '-owari.txt'), 'w').write(line + '\n')
    except Exception: pass
    log(line)
import atexit
_owari_done = []
def _owari_exit():
    if not _owari_done: owari('途中で止まった（最後の段 %s）／不合格 %s' % (seq[k] if k < len(seq) else '?', '・'.join(NG) or 'なし'))
atexit.register(_owari_exit)
while k < len(seq):
    s = seq[k]; t0 = time.time(); log('── %s' % s)
    if s == 'drive' and NG:
        log('不合格があるので drive（納品・Drive）には進まない：' + '／'.join(NG)); k += 1; continue
    try: FN[s]()
    except SystemExit as e:
        if s not in TSUZUKE: raise
        NG.append('%s（%s）' % (s, str(e)[:160].replace('\n', ' '))); log('不合格でも次の段へ進む：%s' % s)
    except MeNG as e:
        ME_MAX -= 1
        if ME_MAX <= 0: raise SystemExit(str(e) + '（3回直しても残った → 作業AIが目で見て決める）')
        log('別の目の直す所を場面表に戻して、書き出しからやり直す（残り %d 回）' % ME_MAX)
        shutil.copy(MP4, MP4.replace('.mp4', '.me%d.mp4' % (3 - ME_MAX)))
        seq = seq[:k] + ['bamen', 'sozai', 'render', 'mon', 'kensa', 'me'] + seq[k + 1:]; continue   # k はそのまま＝次は bamen
    with open(JIKAN, 'a') as f: f.write('%s\t%s\t%.0f\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), s, time.time() - t0))
    k += 1
_owari_done.append(1)
owari('おわり %s／不合格 %s' % (NOUHIN if os.path.exists(NOUHIN) else MP4, '・'.join(NG) or 'なし'))
if NG: sys.exit(1)
