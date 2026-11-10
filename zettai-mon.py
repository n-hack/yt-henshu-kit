#!/usr/bin/env python3
# 動画編集の絶対ルール10の門（作業AI・2026-10-19。依頼主 03:1x「全部動画編集の絶対ルールで仕組み化しといて」）
#   正本 tools/yt-henshu/ZETTAI-RULES.md。1つでも外れたら exit 1 と外れた理由。通ったら納品の印（state/nouhin-mon/<sha>.zettai）を付ける
#   この印が無い YouTube の動画は ai-label-check.py の --strip／--mokushi-ok／--gate が止める＝Drive にも Discord にも出ない
#
#   python3 zettai-mon.py <作業フォルダ> [--mp4 書き出した.mp4] [--sozai 素材一覧.json] [--moto 元のナレーション]
#                         [--story story.v5.py] [--kae _head.py=_head.v4.py ...] [--nouhin] [--out 結果の置き場]
#     --story/--kae … 前の版を測るとき、その版の場面表で組み直す（作業フォルダの本物は書き換えない・写しで組む）
#     --nouhin      … 通ったら <名前>.nouhin.mp4 を作る（AIの印を外した写し＝ai-label-check.py --strip）。通らなければ作らない
#   素材一覧（<作業フォルダ>/sozai-ichiran.json）の形は ZETTAI-RULES.md の「素材一覧」の節
import os, sys, json, re, glob, shutil, subprocess, time, hashlib, difflib, argparse
TOOL = os.path.dirname(os.path.abspath(__file__)); LIB = os.path.join(TOOL, 'lib'); sys.path.insert(0, LIB)
import paths
HOME = os.path.expanduser('~')
STAMP = os.path.join(HOME, 'rin6/state/nouhin-mon')
OUTROOT = os.path.join(HOME, 'rin6/state/yt-henshu/zettai-mon')
TAKUTO = {'youtube.tehon', 'sns.tehon', 'instagram_tehon'}              # ルール3：許可済み（依頼主 10/19 02:4x・03:2x）
DEGUCHI = {'公式', '手本の作者さん', '素材サイト', '自作'}                         # ルール3：出どころの4つ
SHURUI7 = ['挿絵', 'イラスト', '図解', '全画面挿絵', '実際の画面']                # ルール7：0本の種類があれば止める
SERVICES = {'chatgpt': 'ChatGPT', 'openai': 'ChatGPT', 'claude': 'Claude', 'anthropic': 'Claude', 'lineapp': 'LINE', 'line_logo': 'LINE', 'utage': 'UTAGE',
            'instagram': 'Instagram', 'insta': 'Instagram', 'youtube': 'YouTube', 'notion': 'Notion', 'gemini': 'Gemini', 'canva': 'Canva',
            'threads': 'Threads', 'discord': 'Discord', 'slack': 'Slack', 'x_logo': 'X', 'twitter': 'X', 'zoom': 'Zoom', 'note_logo': 'note'}
TAKUTO_ICON = {'v1_mascot_line.png': '手本の作者さんの右下の丸いロゴ（座る男の線画）の写し'}   # ルール6：残さない
CHARA_ICON = re.compile(r'chara', re.I)   # ファイル名か置き場（…/vtuber/chara/icon1024.png）に自社キャラ
FPS = 30000 / 1001
SAISEI = re.compile(r'再生数|再生回数|視聴回数|再生が多い|再生の多い|伸びた本|伸びている本|view_?count|\bviews\b', re.I)
ENGINE = paths.ENGINE; SOZAI = os.path.join(ENGINE, 'sozai')


def sh(cmd, **k): return subprocess.run(cmd, capture_output=True, text=True, **k)
def dur(f):
    r = sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]); return float(r.stdout.strip() or 0)
def sha(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fp:
        for c in iter(lambda: fp.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
N = lambda s: re.sub(r'<[^>]+>|[、。「」『』！？!?,.\s・…（）()【】“”"=〜~\-ー：:；;／/]', '', (s or '').replace('【間】', '')).lower()


# ---------------- 写しで場面表を組んで、実際に読んだ素材・部品・効果音を数える（作業フォルダは書き換えない） ----------------
def sandbox(P, story=None, kae=()):
    sb = os.path.join(OUTROOT, 'sb', os.path.basename(P.rstrip('/')) + '-' + time.strftime('%H%M%S') + '-%d' % os.getpid())
    os.makedirs(os.path.join(sb, 'work'))
    for f in glob.glob(os.path.join(P, '*.py')): shutil.copy(f, sb)
    if os.path.isdir(os.path.join(P, 'input')): shutil.copytree(os.path.join(P, 'input'), os.path.join(sb, 'input'))
    for f in glob.glob(os.path.join(P, 'work', '*')):
        if os.path.isfile(f) and (f.endswith(('.json', '.txt', '.tsv', '.md')) and os.path.getsize(f) < 50 << 20): shutil.copy(f, os.path.join(sb, 'work'))
        elif os.path.isfile(f): os.symlink(f, os.path.join(sb, 'work', os.path.basename(f)))   # 大きい声は読むだけ（書かれない）
    if os.path.isdir(os.path.join(P, 'work', 'jin_cache')): subprocess.run(['cp', '-cR', os.path.join(P, 'work', 'jin_cache'), os.path.join(sb, 'work', 'jin_cache')])   # 人物のコマの作り置きを複製（同じ部品なら同じ絵・作り直しの約40秒を省く）
    if os.path.isdir(os.path.join(P, 'sozai')): os.symlink(os.path.join(P, 'sozai'), os.path.join(sb, 'sozai'))   # 作業フォルダの素材（素材サイトから取った人物など）も写しで読む。無いと写しで部品が出ず、出どころの検査をすり抜けた（10/20 projk ソコスト）
    if story: shutil.copy(story if os.path.isabs(story) else os.path.join(P, story), os.path.join(sb, 'story.py'))
    for kv in kae:
        a, b = kv.split('=', 1); shutil.copy(os.path.join(P, b), os.path.join(sb, a))
    return sb


def trace_main(sb):
    """--_trace：PIL の Image.open と ImageFont.truetype を見張って場面表を組む → 読んだファイル・部品・置いた効果音・BGM"""
    from PIL import Image, ImageFont
    os.environ['PROJ'] = sb
    import render                       # 先に（henshu が build/ を前に足すと build/render.py を拾う・10/19）
    import henshu as _h0, kit as _k   # 道具を先に読む（henshu の頭の DARK＝使わない場面でも読む絵を数えない）→ 覚えた絵を捨ててから見張る
    for _n in dir(_k):
        if hasattr(getattr(_k, _n), 'cache_clear'): getattr(_k, _n).cache_clear()
    _h0._LB.clear()
    seen = set(); o, ft = Image.open, ImageFont.truetype
    def op(fp, *a, **k):
        if isinstance(fp, (str, os.PathLike)): seen.add(os.path.realpath(fp))
        return o(fp, *a, **k)
    def tt(font=None, *a, **k):
        if isinstance(font, (str, os.PathLike)): seen.add(os.path.realpath(font))
        return ft(font, *a, **k)
    Image.open = op; ImageFont.truetype = tt
    os.environ['PROJ'] = sb; os.chdir(sb)
    S = render.load_story(sb)
    H = sys.modules.get('henshu')
    W_, H_ = 1920, 1080
    elems = []
    for sc in getattr(H, 'SCENES', []):
        for e in sc.elems:
            try:
                im = e.image(); x, y = e.pos(im)
                area = max(0, min(W_, x + im.width) - max(0, x)) * max(0, min(H_, y + im.height) - max(0, y)) / (W_ * H_)
                elems.append({'t': round(getattr(e, 't_plan', e.ts), 3), 'text': im.info.get('text', ''), 'area': round(area, 3), 'anim': e.anim})
            except Exception: pass
    P_ = render.mixer()
    ev = P_.select([(t, k) for t, k in S.SFX], getattr(S, 'SFX_SPARSE', ()))
    kinds = sorted({k for _, k in ev})
    # ルール10：BGM だけの音を書き出しと同じ式（sfx_plan.mix の BGM の段）で作り、声と並べて測る
    import numpy as np
    sys.path.insert(0, os.path.join(TOOL, 'zettai')); import bgm_hakari
    v = P_.dec(os.path.join(sb, 'work', 'vocals.wav')); SR_ = P_.SR
    vrms = float(np.sqrt(np.mean(v[np.abs(v) > 0.01] ** 2))) if (np.abs(v) > 0.01).any() else 0.0
    bgt = np.zeros(len(v), np.float32); sec = 0.0
    for a, b, f, off, gdb in S.BGM:
        a, b = max(a, 0), min(b, S.END)
        if b <= a: continue
        fp = f if os.path.isabs(f) else os.path.join(paths.sozai_dir(), f)
        m = P_.dec(fp, off, b - a + 0.1)[:int((b - a) * SR_)]
        m = m / (np.sqrt(np.mean(m ** 2)) + 1e-9) * vrms * 10 ** (gdb / 20)
        fi, fo = int(0.25 * SR_), int(1.2 * SR_); env = np.ones(len(m), np.float32); env[:fi] = np.linspace(0, 1, fi)[:len(m)]; env[-fo:] = np.linspace(1, 0, min(fo, len(m)))
        i = int(a * SR_); k = min(len(m), len(bgt) - i); bgt[i:i + k] += (m * env)[:k]; sec += b - a
    st = bgm_hakari.stats(v[::3], bgt[::3]) if len(S.BGM) else None
    # この場面表から音を作り直す（書き出しと同じ式）→ 動画の音と比べ、場面表が本当にこの動画を作ったかを確かめる（素材・BGM の項目の裏づけ）
    P_.mix(os.path.join(sb, 'work', 'vocals.wav'), S.SFX, [(a, b, os.path.join(paths.sozai_dir(), f) if not os.path.isabs(f) else f, o, g) for a, b, f, o, g in S.BGM],
           0.0, S.END, os.path.join(sb, 'work', 'remix.wav'), getattr(S, 'SFX_SPARSE', ()))
    ring = [round(s.t0, 2) for s in getattr(H, 'SCENES', []) if getattr(s, 'ring', False)]
    JM = next((getattr(m, 'JIMAKU') for m in (sys.modules.get('ki1'), S) if m is not None and getattr(m, 'JIMAKU', None)), [])   # 右下の丸いロゴ（kit.ring_logo＝手本の作者さんのロゴの写し）が出る場面
    out = {'files': sorted(seen), 'elems': elems, 'ring_scenes': ring, 'jimaku': [[float(a), float(b), str(t)] for a, b, t in JM], 'scenes': [round(s.t0, 3) for s in getattr(H, 'SCENES', [])], 'end': S.END,
           'sfx_placed': ev, 'sfx_files': {k: os.path.join(P_.LIB, P_.SOUNDS[k][0]) for k in kinds if k in P_.SOUNDS},
           'bgm': [b[2] if os.path.isabs(b[2]) else os.path.join(paths.sozai_dir(), b[2]) for b in S.BGM],
           'bgm_sec': round(sec, 2), 'bgm_stats': st}
    json.dump(out, sys.stdout, ensure_ascii=False)


# ---------------- 出どころの帳簿（記録があるものは自動で引く・無いものは素材一覧に要る） ----------------
def ledger():
    L = {}
    def tsv(p):
        if not os.path.exists(p): return []
        rows = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')]
        return [dict(zip(rows[0], r)) for r in rows[1:]]
    for r in tsv(os.path.join(SOZAI, 'se', 'index.tsv')):
        L[os.path.realpath(os.path.join(SOZAI, 'se', r['ファイル']))] = {'deguchi': '手本の作者さん' if r['チャンネル'] in TAKUTO else '不許可',
                                                                   'moto': '%s %s %s秒' % (r['チャンネル'], r['動画'], r['秒']), 'ch': {r['チャンネル']}, 'shurui': '効果音'}
    for r in tsv(os.path.join(SOZAI, 'bgm', 'index.tsv')):
        chs = set(re.findall(r'(youtube\.tehon|sns\.tehon|instagram_tehon|gaibu_x|gaibu_note)', r.get('出どころ（動画・チャンネル・秒・長さ）', '')))
        L[os.path.realpath(os.path.join(SOZAI, 'bgm', r['ファイル']))] = {'deguchi': '手本の作者さん' if chs and chs <= TAKUTO else '不許可' if chs else '不明',
                                                                    'moto': ' / '.join(sorted(chs)) or '記録なし', 'ch': chs, 'shurui': 'BGM'}
        if not chs and 'Audiostock' in r.get('出どころ（動画・チャンネル・秒・長さ）', ''):   # 素材サイトで取った曲（Afterglow・定額制スタンダード 10/20）
            L[os.path.realpath(os.path.join(SOZAI, 'bgm', r['ファイル']))] = {'deguchi': '素材サイト', 'moto': r.get('説明', ''), 'license': 'Audiostock 定額制スタンダード（YouTube・Web広告可）', 'ch': set(), 'shurui': 'BGM'}
    for r in tsv(os.path.join(SOZAI, 'index.tsv')):
        L[os.path.realpath(os.path.join(SOZAI, r['種類'], r['名前'] + '.png'))] = {'deguchi': '手本の作者さん' if r['チャンネル'] in TAKUTO else '不許可',
                                                                              'moto': '%s %s %s秒' % (r['チャンネル'], r['動画'], r['秒']), 'ch': {r['チャンネル']},
                                                                              'shurui': 'イラスト' if r['種類'] == 'jinbutsu' else '写真'}
    A = os.path.join(ENGINE, 'assets')
    for f in glob.glob(os.path.join(A, 'chara_*.png')): L[os.path.realpath(f)] = {'deguchi': '自作', 'moto': '自社キャラのアイコン（自社のキャラ）', 'shurui': '話し手アイコン'}
    for f in glob.glob(os.path.join(A, 'p_*.png')) + glob.glob(os.path.join(A, 'ph_*.png')):
        L[os.path.realpath(f)] = {'deguchi': '自作', 'moto': '画像生成で作った（assets/gen2.log）', 'shurui': 'イラスト'}
    for f, why in TAKUTO_ICON.items(): L[os.path.realpath(os.path.join(A, f))] = {'deguchi': '手本の作者さん', 'moto': why, 'shurui': '手本の作者さんのアイコン'}
    return L


def font_ok(f):
    b = os.path.basename(f)
    if f.startswith(os.path.join(ENGINE, 'build', 'fonts')): return 'Google Fonts（OFL／Material Symbols は Apache 2.0）'
    if f.startswith('/System/Library/'): return 'macOS 付属の字（' + b + '）'
    return None


# ---------------- 9つを測る ----------------
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--mp4'); ap.add_argument('--sozai'); ap.add_argument('--moto')
    ap.add_argument('--story'); ap.add_argument('--kae', nargs='*', default=[]); ap.add_argument('--nouhin', action='store_true'); ap.add_argument('--out')
    ap.add_argument('--no-ocr', action='store_true', help='試験用：ルール5の字幕帯の読み取りを省く（省いたらルール5は外れ扱い）')
    A = ap.parse_args()
    P = os.path.abspath(A.proj); name = os.path.basename(P.rstrip('/'))
    mp4 = os.path.abspath(A.mp4) if A.mp4 else os.path.join(P, 'out', name + '.mp4')
    if not os.path.exists(mp4): sys.exit('🔴 動画が無い：' + mp4)
    out = A.out or os.path.join(OUTROOT, name + '-' + os.path.splitext(os.path.basename(mp4))[0]); os.makedirs(out, exist_ok=True)
    NG = {i: [] for i in range(1, 11)}; DATA = {i: {} for i in range(1, 11)}; NOTE = []
    def ng(i, m): NG[i].append(m)

    # 素材一覧
    sp = A.sozai or os.path.join(P, 'sozai-ichiran.json')
    SL = json.load(open(sp)) if os.path.exists(sp) else None
    items = (SL or {}).get('sozai', [])
    if SL is None:
        for i in (1, 3, 7, 8): ng(i, '素材一覧が無い（%s）。素材ごとの出どころ・種類・使った秒が要る' % sp)
    byfile = {os.path.realpath(x['file']): x for x in items if x.get('file')}

    # 写しで組む
    sb = sandbox(P, A.story, A.kae)
    for _d in sorted((d for d in glob.glob(os.path.join(OUTROOT, 'sb', '*')) if d != sb and os.path.isdir(d)), key=os.path.getmtime, reverse=True)[2:]:   # 途中で止まった門の写しが溜まらないように：いまの写しのほか新しい2つを残し、それより古く1時間より前のものを消す
        if os.path.getmtime(_d) < time.time() - 3600: shutil.rmtree(_d, ignore_errors=True)
    from concurrent.futures import ThreadPoolExecutor
    BG = ThreadPoolExecutor(2)   # 写しで組む間に、動画だけで測れるもの（ルール9の手本の数字・ルール5の言葉ごとのコマ読み）を先に始める。外れの判定は元の場所で行う
    def _r9():
        import importlib.util
        spec = importlib.util.spec_from_file_location('sekisho', os.path.join(TOOL, 'sekisho.py')); SK = importlib.util.module_from_spec(spec); spec.loader.exec_module(SK)
        d_ = dur(mp4); TT = 171 if d_ < 400 else 600
        return SK.measure(SK.frames(mp4, 0, min(TT, d_)))
    F9 = BG.submit(_r9)
    def grab(jb): subprocess.run(['nice', '-n', '19', 'ffmpeg', '-v', 'error', '-y', '-ss', '%.3f' % jb[2], '-i', mp4, '-frames:v', '1', '-vf', 'scale=1280:-2', jb[1]])
    def ocr(ch): return subprocess.run([os.path.join(TOOL, 'ocr')] + ch, capture_output=True, text=True).stdout
    def grab_ocr(jobs_):
        R_ = {}
        with ThreadPoolExecutor(12) as ex: list(ex.map(grab, jobs_))
        ims_ = [j[1] for j in jobs_]
        with ThreadPoolExecutor(8) as ex:
            for o in ex.map(ocr, [ims_[i:i + 40] for i in range(0, len(ims_), 40)]):
                for l in o.splitlines():
                    try: d = json.loads(l); R_[d['p']] = d['r'] or []
                    except Exception: pass
        return R_
    def _r5a():
        TJ_ = json.load(open(os.path.join(P, 'work', 'timing.json')))
        ls_ = [x for x in TJ_['lines'] if N(x['text']) and x['end'] > x['start']]
        vd_ = dur(mp4); ls_ = [x for x in ls_ if x['start'] < vd_ - 0.05]
        fd_ = os.path.join(out, 'ocr'); shutil.rmtree(fd_, ignore_errors=True); os.makedirs(fd_)
        jobs_ = []
        for k, x in enumerate(ls_):
            a, b = x['start'], x['end']
            for j, t in enumerate(sorted({min(b, a + 0.15), (a + b) / 2, max(a, b - 0.1)})): jobs_.append((k, os.path.join(fd_, '%04d_%d.png' % (k, j)), t))
        return jobs_, grab_ocr(jobs_)
    F5 = None if A.no_ocr else BG.submit(_r5a)
    r = subprocess.run(['nice', '-n', '19', sys.executable, os.path.abspath(__file__), '--_trace', sb], capture_output=True, text=True, env=dict(os.environ, PROJ=sb))
    if r.returncode:
        open(os.path.join(out, 'trace-err.txt'), 'w').write(r.stderr[-20000:])
        sys.exit('🔴 場面表を組めなかった（%s/trace-err.txt）' % out)
    T = json.loads(r.stdout[r.stdout.index('{"files"'):])
    json.dump(T, open(os.path.join(out, 'trace.json'), 'w'), ensure_ascii=False, indent=1)
    LG = ledger()
    # 場面表と動画の音の一致（同じなら差は −38dB 前後・BGM が抜けると −26dB・効果音が違うと −14dB＝10/19 試験で測った）
    sys.path.insert(0, os.path.join(TOOL, 'zettai')); import bgm_hakari, numpy as _np
    ra, rb = bgm_hakari.dec(mp4), bgm_hakari.dec(os.path.join(sb, 'work', 'remix.wav')); n_ = min(len(ra), len(rb))
    sa = float(20 * _np.log10(_np.sqrt(_np.mean((ra[:n_] - rb[:n_]) ** 2)) / (_np.sqrt(_np.mean(ra[:n_] ** 2)) + 1e-12) + 1e-12))
    AUDIO_OK = sa <= -32
    if not AUDIO_OK:
        for i in (3, 8, 10): ng(i, '場面表から作り直した音と動画の音が合わない（差 %.1f dB・合う線 −32 dB）＝この動画の素材・効果音・BGM を場面表から確かめられない（場面表を書き出した版に合わせる）' % sa)

    # 使った物の出どころ（ルール1・3・6・8）
    rows = []
    used = [f for f in T['files'] if f.startswith(('/Users/', '/System/', '/Library/'))] + list(T['sfx_files'].values()) + T['bgm']
    for f in sorted(set(os.path.realpath(x) for x in used)):
        if f.endswith(('.codepoints',)): continue
        fo = font_ok(f) if f.endswith(('.ttf', '.otf', '.ttc')) else None
        it = byfile.get(f); lg = LG.get(f)
        if fo: d = {'deguchi': '公式' if '付属' in fo else '素材サイト', 'moto': fo, 'shurui': 'フォント'}
        elif it: d = {'deguchi': it.get('deguchi', ''), 'moto': it.get('moto', ''), 'shurui': it.get('shurui', ''), 'license': it.get('license', ''), 'kakin': it.get('kakin')}
        elif lg: d = dict(lg)
        elif CHARA_ICON.search(f) and f.endswith(('.png', '.jpg', '.webp')): d = {'deguchi': '自作', 'moto': '自社キャラのアイコン（自社のキャラ）', 'shurui': '話し手アイコン'}
        elif '/e/gamen/' in f: d = {'deguchi': '自作', 'moto': 'うちの画面録画（seminar-canva-douga）の1コマ', 'shurui': '実際の画面'}
        elif '/work/jin_cache/' in f or '/state/yt-henshu/jinbutsu/' in f: d = {'deguchi': '自作', 'moto': '動く人物の部品（yt-jinbutsu が jinbutsu.py で描いた・README の出どころ）', 'shurui': 'イラスト'}
        else: d = {'deguchi': '', 'moto': '', 'shurui': ''}
        d['file'] = f; rows.append(d)
        b = os.path.basename(f).lower()
        gaibu = 'gaibu_x' in (d.get('moto') or '') or 'gaibu_x' in (lg or {}).get('ch', set())
        if gaibu: ng(3, 'gaibu_x 由来（許可なし）：%s（%s）' % (b, d.get('moto')))
        elif d['deguchi'] not in DEGUCHI: ng(3, '出どころが分からない／許可が無い：%s（%s）' % (f, d.get('moto') or '記録なし'))
        if d['deguchi'] == '素材サイト' and d['shurui'] != 'フォント' and not d.get('license'): ng(3, '素材サイトのライセンスが空：%s' % b)
        tok = set(re.split(r'[_\-\.\s]+', b))   # 名前の区切りごとに見る（mascot_line の line を LINE と読んだ・10/19 試験）
        svc = [v for k, v in SERVICES.items() if (k in b if '_' in k else k in tok)]
        if svc and d['deguchi'] != '公式': ng(1, '%s のロゴ・画面なのに公式素材でない：%s（出どころ %s）' % (svc[0], b, d['deguchi'] or '空'))
        if b in TAKUTO_ICON: ng(6, '手本の作者さんのアイコンが残っている：%s（%s）' % (b, TAKUTO_ICON[b]))
        if d['shurui'] in ('効果音', 'BGM') and (d['deguchi'] not in DEGUCHI or gaibu): ng(8, '%s が %s：%s' % (d['shurui'], 'gaibu_x 由来（許可なし）' if gaibu else '出どころ不明', b))
    for it in items:   # 一覧に書いた物（ファイルの無い図解なども）
        if it.get('deguchi') not in DEGUCHI: ng(3, '素材一覧の出どころが空・不明：%s' % (it.get('name') or it.get('file')))
        if it.get('service') and it.get('deguchi') != '公式': ng(1, '%s を見せる素材が公式でない：%s（%s）' % (it['service'], it.get('name') or it.get('file'), it.get('deguchi')))
        if it.get('kakin') and it.get('kounyuu') != '済': ng(8, '課金が要る素材（依頼主へ・作業AIは買わない）：%s（%s %s）' % (it.get('name') or it.get('file'), it.get('moto', ''), it.get('kakaku', '')))
    sys.path.insert(0, TOOL); import kinshi_chara as KC   # 依頼主 10/20 23:45「この棒人間みたいなやつ…一生使わないで」：ファイル（sha256・名前）と見た目の両方で、1コマでも出たら止める
    for f_, how in KC.files_check([x['file'] for x in rows]): ng(3, '使ってはいけないキャラ（棒人間）の素材を使った：%s（%s で一致）' % (f_, how))
    _kc = KC.video_check(mp4, 2)
    if _kc['deta']: ng(3, '使ってはいけないキャラ（棒人間）が動画の %d コマに出る（%s 秒〜・似ている度合い %s）' % (len(_kc['deta']), _kc['deta'][0][0], _kc['mihon_betsu']))
    _jc = KC.jimon_check(mp4, 15)
    if _jc['deta']: ng(3, '使ってはいけないキャラ（棒人間）の線画が地（背景）に入っている：%s' % {k: v for k, v in _jc.items() if k != 'deta'})
    DATA[3]['地の線画'] = _jc
    DATA[3]['使ってはいけないキャラ'] = {'deta_koma': len(_kc['deta']), 'mihon_betsu': _kc['mihon_betsu'], 'sen': _kc['sen']}
    DATA[3]['使った物'] = len(rows); DATA[3]['出どころ別'] = {k: sum(1 for x in rows if x['deguchi'] == k) for k in sorted({x['deguchi'] or '空' for x in rows})}
    DATA[8]['置いた効果音'] = len(T['sfx_placed']); DATA[8]['効果音の種類'] = {k: os.path.basename(v) for k, v in T['sfx_files'].items()}; DATA[8]['BGM'] = [os.path.basename(b) for b in T['bgm']]
    with open(os.path.join(out, 'sozai-deguchi.tsv'), 'w') as fp:
        fp.write('種類\t出どころ\t元\tライセンス\tファイル\n')
        for x in rows: fp.write('%s\t%s\t%s\t%s\t%s\n' % (x.get('shurui', ''), x.get('deguchi') or '空', x.get('moto', ''), x.get('license', ''), x['file']))
    kk = [it for it in items if it.get('kakin') and it.get('kounyuu') != '済']
    if kk:
        with open(os.path.join(out, 'kakin-ichiran.md'), 'w') as fp:
            fp.write('# 課金が要る素材（依頼主へ・作業AIは買わない）\n\n| 素材 | 置き場 | 値段 | 何に使うか |\n|---|---|---|---|\n')
            for it in kk: fp.write('| %s | %s | %s | %s |\n' % (it.get('name') or it.get('file'), it.get('moto', ''), it.get('kakaku', ''), it.get('shurui', '')))

    # ルール1（その2）：声で名前が出たサービス → 公式の素材が一覧にあるか（無ければ要確認として残す）
    TJ = json.load(open(os.path.join(P, 'work', 'timing.json')))
    said_all = ''.join(x['text'] for x in TJ['lines']).lower()
    named = sorted({v for k, v in SERVICES.items() if len(k) > 3 and k in said_all} | ({'Claude'} if 'クロード' in said_all else set()) |
                   ({'ChatGPT'} if 'チャットgpt' in said_all or 'チャットジーピーティー' in said_all else set()) | ({'LINE'} if 'ライン' in said_all else set()) |
                   ({'UTAGE'} if 'うたげ' in said_all or 'ウタゲ' in said_all else set()) | ({'Instagram'} if 'インスタ' in said_all else set()))
    have = {it.get('service') for it in items if it.get('deguchi') == '公式'}
    DATA[1]['声に出たサービス'] = named; DATA[1]['公式素材あり'] = sorted(x for x in named if x in have)
    miss = [x for x in named if x not in have]
    if miss: NOTE.append('ルール1 要確認：声に出たサービスで公式素材が一覧に無い → %s（見せていないなら問題なし。見せるなら公式のロゴ・画面を）' % '・'.join(miss))

    # ルール2：比べる相手は依頼主から受け取ったナレーション（ジャンプカット済みの mp3/wav）。区間を切り出すだけなら通す（koe_kukan.json）・区間の中の間は触らない
    import numpy as np
    vo = os.path.join(P, 'work', 'vocals.wav')
    KK = json.load(open(os.path.join(P, 'koe_kukan.json'))) if os.path.exists(os.path.join(P, 'koe_kukan.json')) else None
    cand = [(KK or {}).get('moto'), A.moto, (SL or {}).get('narration_moto')] + sorted(glob.glob(os.path.join(P, 'input', 'narration.*'))) + [os.path.join(P, 'work', 'henshu_full.wav')]
    moto = next((c for c in cand if c and os.path.exists(c)), None)
    def dec8(f, ss=None, t=None):
        cmd = ['ffmpeg', '-v', 'error'] + (['-ss', '%.3f' % ss] if ss is not None else []) + ['-i', f] + (['-t', '%.3f' % t] if t else []) + ['-ac', '1', '-ar', '8000', '-f', 'f32le', '-']
        return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)
    def env(y):
        n = len(y) // 80; return np.sqrt((y[:n * 80].reshape(n, 80) ** 2).mean(1))
    kukan = [(float(a), float(b)) for a, b in (KK or {}).get('kukan', [])]
    dv, dmp4 = dur(vo), dur(mp4)
    dm = (sum(b - a for a, b in kukan) if kukan else dur(moto)) if moto else 0
    DATA[2] = {'元のナレーション': moto, '区間（koe_kukan.json）': kukan or 'なし（全部をそのまま使う）', '元の長さ（区間の合計）': round(dm, 3), '使った声': vo,
               '使った声の長さ': round(dv, 3), '動画の長さ': round(dmp4, 3), 'speed': TJ.get('speed')}
    if not moto: ng(2, '元のナレーションが分からない（koe_kukan.json の moto・素材一覧の narration_moto・input/narration.* のどれか）')
    elif KK is not None and not kukan: ng(2, 'koe_kukan.json に区間が無い')
    elif abs(dv - dm) > 1 / FPS * max(1, len(kukan)):
        ng(2, '声の長さが元と違う：元 %.2f 秒%s → 使った声 %.2f 秒（差 %+.2f 秒）。間を詰めた・伸ばした・切った' % (dm, '（区間 %d 個の合計）' % len(kukan) if kukan else '', dv, dv - dm))
    else:
        want = np.concatenate([dec8(moto, a, b - a) for a, b in kukan]) if kukan else dec8(moto)
        a, b = env(dec8(vo)), env(want); n = min(len(a), len(b)); c = float(np.corrcoef(a[:n], b[:n])[0, 1]) if n > 10 else 0
        DATA[2]['声の形の一致（10ms の大きさの相関）'] = round(c, 4)
        if c < 0.98: ng(2, '声の長さは同じだが中身が元と違う（相関 %.3f）＝区間の中で間を詰めた・伸ばした・入れ替えた' % c)
    if TJ.get('speed') not in (None, 1, 1.0): ng(2, '声の速さを変えている（speed %s）' % TJ.get('speed'))
    kiri = [os.path.basename(f) for f in glob.glob(os.path.join(P, 'work', 'kiri*.json'))]
    if kiri and NG[2]: ng(2, '声を切った記録がある：%s（区間だけを切るなら koe_kukan.json に書く・つなぎ目に間を入れない）' % '・'.join(kiri))
    if dmp4 + 0.05 < dv: ng(2, '動画が声より短い（%.2f＜%.2f 秒）＝声の終わりが切れる' % (dmp4, dv))

    # ルール4：手本は3チャンネル・編集の判断に再生数を使わない
    hits = []
    for f in [os.path.join(P, x) for x in ('intent.json', 'bamen.md', 'video_marketing.json')] + glob.glob(os.path.join(sb, '*.py')):
        if not os.path.exists(f): continue
        if os.path.basename(f) == 'intent.json':   # selection の dropped・shown は語りの文字起こし（編集の判断ではない）ので数えない（team-lead 10/23・Muntri k11 の「再生数が10万再生」で誤検知）
            try: IJ = json.load(open(f, encoding='utf-8'))
            except Exception: IJ = None
            if IJ is not None:
                def _iter(o, pth):
                    if isinstance(o, dict):
                        for k_, v_ in o.items():
                            if pth.endswith('selection') and k_ in ('dropped', 'shown'): continue
                            yield from _iter(v_, pth + '.' + k_)
                    elif isinstance(o, list):
                        for i_, v_ in enumerate(o): yield from _iter(v_, '%s[%d]' % (pth, i_))
                    elif isinstance(o, str): yield pth, o
                for pth, body in _iter(IJ, ''):
                    if SAISEI.search(body): hits.append('intent.json:%s %s' % (pth.lstrip('.'), body.strip()[:80]))
                continue
        for k, ln in enumerate(open(f, encoding='utf-8', errors='ignore'), 1):
            body = ln.split('#', 1)[1] if f.endswith('.py') and '#' in ln else ln if not f.endswith('.py') else ''
            if SAISEI.search(body): hits.append('%s:%d %s' % (os.path.basename(f), k, body.strip()[:80]))
    for h in hits: ng(4, '編集の判断に再生数を使っている：' + h)
    teh = (SL or {}).get('tehon', [])
    chs = {}
    for c in TAKUTO:
        p = os.path.join(ENGINE, 'channels', c + '.tsv')
        if os.path.exists(p):
            for l in open(p, encoding='utf-8'): chs[re.split(r'\\t|\t', l, maxsplit=1)[0].strip()] = c   # この一覧は区切りが「\t」の2文字（10/19 試験で0件になった）
    DATA[4] = {'手本': {t: chs.get(t, '3チャンネルの外') for t in teh}, '再生数の語': len(hits)}
    for t in teh:
        if t not in chs: ng(4, '手本が手本の作者さんの3チャンネルの外：%s' % t)
    if not teh: ng(4, '素材一覧に手本（tehon：比べた手本の動画ID）が無い＝3チャンネルの手本か確かめられない')

    # ルール5：全部の言葉にテロップ（下の字幕帯）＋ 1コマ単位のずれ
    zp = os.path.join(sb, 'work', 'zure-plan.json')
    ZK = subprocess.Popen(['nice', '-n', '19', sys.executable, os.path.join(TOOL, 'zure-kensa.py'), sb, mp4], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) if os.path.exists(zp) and os.path.getmtime(zp) > time.time() - 3600 else None   # 字幕の読みと同時に走らせる
    lines = [x for x in TJ['lines'] if N(x['text']) and x['end'] > x['start']]
    _vd = dur(mp4)   # 頭だけ切り出した版（頭3分など）は動画の外の行を数えない。動画が声より短いことはルール2が別に止める
    lines = [x for x in lines if x['start'] < _vd - 0.05]
    # 比べる相手：字幕として出した字（作業フォルダの jimaku.json か、場面表の JIMAKU＝聞き違いを直した後の字）。無ければ台本の行の字
    jp = next((f for f in (os.path.join(P, 'jimaku.json'), os.path.join(P, 'work', 'jimaku.json')) if os.path.exists(f)), None)
    JI = [tuple(x) for x in (json.load(open(jp)) if jp else T.get('jimaku') or [])]
    DATA[5]['比べた字'] = ('字幕の表 %s（%d 枚）' % (jp, len(JI)) if jp else '場面表の字幕の表 JIMAKU（%d 枚）' % len(JI)) if JI else '台本の行の字（字幕の表が無い）'
    if A.no_ocr: ng(5, '字幕帯の読み取りを省いた（--no-ocr）')
    else:
        fd = os.path.join(out, 'ocr')
        jobs, R = F5.result()
        assert [j[0] for j in jobs] == [k for k, x in enumerate(lines) for _ in sorted({min(x['end'], x['start'] + 0.15), (x['start'] + x['end']) / 2, max(x['start'], x['end'] - 0.1)})]   # 先に読んだ行と同じ行か
        res = []
        if JI:   # 字幕の1枚ごとに、出ているはずの字が字幕帯に読めるか（まん中のコマ）＋声の行が字幕の時間で覆われているか
            fd2 = os.path.join(out, 'ocr2'); os.makedirs(fd2, exist_ok=True)
            jobs2 = [(k, os.path.join(fd2, '%05d.png' % k), (a + b) / 2) for k, (a, b, _t) in enumerate(JI)]
            R.update(grab_ocr(jobs2))
            shutil.rmtree(fd2, ignore_errors=True)
        for k, x in enumerate(lines):
            if JI:
                a0, b0 = x['start'], x['end']; tot = max(0.01, b0 - a0)
                covt = sum(max(0, min(b0, b) - max(a0, a)) for a, b, _t in JI) / tot
                ks = [i for i, (a, b, _t) in enumerate(JI) if a < b0 and b > a0]
                want = ''.join(JI[i][2] for i in ks)
                band = ''.join(r_[0] for i in ks for r_ in R.get(jobs2[i][1], []) if r_[2] + r_[4] / 2 >= 0.70)
                s_ = N(want); c_ = sum(m.size for m in difflib.SequenceMatcher(None, s_, N(band), autojunk=False).get_matching_blocks()) / max(1, len(s_)) if s_ else 0
                res.append({'n': x['n'], 'start': a0, 'end': b0, 'text': want or x['text'], '字幕帯': round(min(c_, 1.0) if covt >= 0.9 else 0.0, 2), '画面のどこか': round(covt, 2)})
                continue
            band = ''.join(r_[0] for jb in jobs if jb[0] == k for r_ in R.get(jb[1], []) if r_[2] + r_[4] / 2 >= 0.70)
            anyw = ''.join(r_[0] for jb in jobs if jb[0] == k for r_ in R.get(jb[1], []))
            s = N(x['text'])
            cov = lambda shown: sum(m.size for m in difflib.SequenceMatcher(None, s, N(shown), autojunk=False).get_matching_blocks()) / max(1, len(s))
            res.append({'n': x['n'], 'start': x['start'], 'end': x['end'], 'text': x['text'], '字幕帯': round(cov(band), 2), '画面のどこか': round(cov(anyw), 2)})
        shutil.rmtree(fd, ignore_errors=True)
        with open(os.path.join(out, 'telop.tsv'), 'w') as fp:
            fp.write('行\t始め\t終わり\t字幕帯の覆い\t%s\t%s\n' % (('字幕の時間で覆えた割合', '出した字幕') if JI else ('画面のどこかの覆い', '台本')))
            for x in res: fp.write('%s\t%.2f\t%.2f\t%.2f\t%.2f\t%s\n' % (x['n'], x['start'], x['end'], x['字幕帯'], x['画面のどこか'], x['text']))
        bad = [x for x in res if x['字幕帯'] < 0.7]
        DATA[5] = {'行': len(res), '字幕帯で覆えた行（0.7以上）': len(res) - len(bad), '画面のどこかで覆えた行': sum(1 for x in res if x['画面のどこか'] >= 0.7),
                   '字幕帯の覆い（中央値）': sorted(x['字幕帯'] for x in res)[len(res) // 2] if res else 0}
        if bad:
            sec = sum(x['end'] - x['start'] for x in bad)
            ng(5, 'テロップ（下の字幕帯）の無い言葉：%d / %d 行・計 %.1f 秒（例 %s）→ telop.tsv' % (len(bad), len(res), sec,
               '／'.join('%.1f秒「%s」' % (x['start'], x['text'][:14]) for x in bad[:3])))
    if ZK:
        _o, _e = ZK.communicate(); z = subprocess.CompletedProcess(ZK.args, ZK.returncode, _o, _e)
        open(os.path.join(out, 'zure.tsv'), 'w').write(z.stdout)
        last = (z.stdout.strip().splitlines() or [''])[-1]; DATA[5]['1コマのずれ'] = last
        if z.returncode:
            # 1コマ超は、同じ場所に直前の部品が先に出ていると「早く出た」と数える取り違えがある（10/19 v12 140.35秒・#694）。
            #   言葉の頭のコマの前後で、その部品の範囲が「直前まで止まっていて頭で変わる」かを見直す（zure-saiken.py）。本当のずれが1件でもあれば止める
            zs = sh(['nice', '-n', '19', sys.executable, os.path.join(TOOL, 'zure-saiken.py'), sb, mp4, os.path.join(out, 'zure.tsv')])
            open(os.path.join(out, 'zure-saiken.txt'), 'w').write(zs.stdout)
            sl = (zs.stdout.strip().splitlines() or [''])[-1]; DATA[5]['1コマ超の見直し'] = sl
            if zs.returncode: ng(5, '言葉の頭と字の出が1コマを超えてずれる：' + last + '（見直し：' + sl + '）')
    else: ng(5, '1コマ単位のずれを測れない（場面表が work/zure-plan.json を出していない）')

    # ルール6：話し手は自社キャラのアイコン
    mar = [f for f in T['files'] if CHARA_ICON.search(f) and f.endswith(('.png', '.jpg', '.webp'))] + [it.get('file') or it.get('name') for it in items if it.get('shurui') == '話し手アイコン' and CHARA_ICON.search((it.get('file') or '') + (it.get('name') or ''))]
    DATA[6] = {'自社キャラのアイコン': [os.path.basename(x) for x in mar], '手本の作者さんのアイコン': [os.path.basename(f) for f in T['files'] if os.path.basename(f) in TAKUTO_ICON]}
    if not mar: ng(6, '話し手のアイコン（自社キャラ）が1つも無い')
    if T.get('ring_scenes'): ng(6, '右下の丸いロゴ（手本の作者さんのロゴの写し・kit.ring_logo）が %d 場面に出る（場面の ring=True・頭 %s 秒〜）' % (len(T['ring_scenes']), T['ring_scenes'][0]))
    DATA[6]['右下のロゴが出る場面'] = len(T.get('ring_scenes', []))

    # ルール7：挿絵・イラスト・図解・全画面挿絵・実際の画面（種類ごとの本数）
    cnt = {k: 0 for k in SHURUI7}
    for it in items:
        if it.get('shurui') in cnt: cnt[it['shurui']] += len(it.get('basho') or []) or 1
    auto_gamen = len({f for f in T['files'] if '/gamen/' in f or '/screen' in f})
    auto_full = sum(1 for e in T['elems'] if not e['text'] and e['area'] >= 0.8 and e['anim'] != 'none')
    cnt['実際の画面'] = max(cnt['実際の画面'], auto_gamen); cnt['全画面挿絵'] = max(cnt['全画面挿絵'], auto_full)
    DATA[7] = {'本数': cnt, '自動で数えた（実際の画面の絵の数／全画面の絵の出）': [auto_gamen, auto_full],
               '文字の無い部品の出（参考）': sum(1 for e in T['elems'] if not e['text'] and e['anim'] != 'none')}
    for k, v in cnt.items():
        if v == 0: ng(7, '%s が0本' % k)

    # ルール9：GPU で書き出し ＋ 手本と数字で比べる
    b = open(mp4, 'rb').read(); x264 = b.count(b'x264 - core')
    pj = os.path.join(os.path.dirname(mp4), 'tmp', 'parts.json'); enc = None
    if os.path.exists(pj) and json.load(open(pj)).get('out') == mp4:
        p0 = json.load(open(pj))['parts'][0][3]
        if os.path.exists(p0): enc = sh(['ffprobe', '-v', 'error', '-show_entries', 'stream_tags=encoder', '-of', 'csv=p=0', p0]).stdout.strip()
    DATA[9]['CPU の印（x264）'] = x264; DATA[9]['部品の書き出し'] = enc or '（この版の部品は残っていない）'
    if x264: ng(9, 'CPU（libx264）で書き出している（x264 の印 %d 個）' % x264)
    if enc and 'videotoolbox' not in enc: ng(9, '部品が GPU で書き出されていない（%s）' % enc)
    sys.path.insert(0, TOOL)
    import importlib.util
    spec = importlib.util.spec_from_file_location('sekisho', os.path.join(TOOL, 'sekisho.py')); SK = importlib.util.module_from_spec(spec); spec.loader.exec_module(SK)
    TT = 171 if dmp4 < 400 else 600
    mine = F9.result()
    ref = [json.loads(l)['r'] for l in open(os.path.join(TOOL, 'zettai', 'tehon15.jsonl')) if json.loads(l)['T'] == TT]
    import statistics as st
    MEI = {'a_diff': '絵の差（動き）', 'b_fill': '埋まり方（字・絵の量）', 'c_big_pm': '大きな切り替わり/分', 'd_move_pm': '動く要素/分'}
    cmp_ = {}
    for k, nm in MEI.items():
        md = st.median(r_[k] for r_ in ref); cmp_[nm] = {'今回': mine[k], '手本15本の中央値': round(md, 3), '線（中央値×0.9）': round(md * 0.9, 3)}
        if mine[k] < md * 0.9: ng(9, '手本に届かない：%s 今回 %s ＜ 線 %.3f（手本15本の中央値 %.3f）' % (nm, mine[k], md * 0.9, md))
    cmp_['色の種類（参考）'] = {'今回': mine.get('e_colors'), '手本15本の中央値': st.median(r_['e_colors'] for r_ in ref)}
    DATA[9]['手本と比べた（頭 %d 秒）' % TT] = cmp_

    # ルール10：YouTube・VSL は BGM を必ず入れる（依頼主 03:3x）。長さ8割以上・声に対する大きさは手本の幅の中
    BK = json.load(open(os.path.join(TOOL, 'zettai', 'bgm_kijun.json'))) if os.path.exists(os.path.join(TOOL, 'zettai', 'bgm_kijun.json')) else None
    st = T.get('bgm_stats'); cov_sec = T.get('bgm_sec', 0) / max(0.1, T['end'])
    DATA[10] = {'BGM の区間': len(T['bgm']), 'BGM の長さ（場面表の区間・全体比）': round(cov_sec, 3), '測り': st, '線': (BK or {}).get('止める線')}
    if not T['bgm']: ng(10, 'BGM の音の筋が無い（場面表の BGM が空）')
    else:
        if cov_sec < 0.8: ng(10, 'BGM が全体の %d%% の長さにしか無い（8割以上が要る）' % round(cov_sec * 100))
        if st and st['BGMのある長さ'] < 0.8: ng(10, '聞こえる BGM が声の範囲の %d%% にしか無い（8割以上が要る・声の中央値−40dB より大きい所）' % round(st['BGMのある長さ'] * 100))
        if not BK: ng(10, '手本の線（zettai/bgm_kijun.json）が無い → python3 zettai/bgm_hakari.py kijun')
        elif st:
            L = BK['止める線']; d = st['声−BGM（dB）']
            if d < L['声−BGM_下限']: ng(10, 'BGM が大きすぎる：声−BGM %.1f dB ＜ 手本の下限 %.1f dB（手本の5%%点）' % (d, L['声−BGM_下限']))
            if d > L['声−BGM_上限']: ng(10, 'BGM が小さすぎる：声−BGM %.1f dB ＞ 手本の上限 %.1f dB（手本の95%%点）' % (d, L['声−BGM_上限']))

    # 例外の記録（作業フォルダの reigai.json）：項目・理由・決めた人・日時が全部あるときだけ、その項目を「例外で通過」にする（外れの中身は消さずに残す）
    REIGAI = []
    rp = os.path.join(P, 'reigai.json')
    if os.path.exists(rp):
        try: RG = json.load(open(rp)); RG = RG if isinstance(RG, list) else [RG]
        except Exception as e: RG = []; NOTE.append('reigai.json が読めない（%s）' % e)
        for r_ in RG:
            ks = ('項目', '理由', '決めた人', '日時')
            try: no = int(str(r_.get('項目', '')).replace('ルール', '').strip())
            except Exception: no = None
            if no not in NG or not all(str(r_.get(k, '')).strip() for k in ks):
                tgt = no if no in NG else 1
                ng(tgt, '例外の記録が足りない（reigai.json に 項目・理由・決めた人・日時 の4つが全部要る）：%s' % json.dumps(r_, ensure_ascii=False)); continue
            if NG[no]:
                REIGAI.append({'項目': no, '理由': r_['理由'], '決めた人': r_['決めた人'], '日時': r_['日時'], '例外で通した外れ': NG[no]}); NG[no] = []
    # まとめ
    ok = not any(NG.values())
    DATA[3]['場面表と動画の音の差（dB）'] = round(sa, 2)
    res = {'作業フォルダ': P, '動画': mp4, '動画のsha256': sha(mp4), '測った時刻': time.strftime('%Y-%m-%d %H:%M:%S'), '合格': ok,
           '外れ': {str(i): v for i, v in NG.items() if v}, 'データ': {str(i): v for i, v in DATA.items()}, '要確認': NOTE, '素材一覧': sp if SL else None,
           '場面表': A.story or 'story.py', '差し替え': A.kae, '例外で通過': REIGAI,
           '依頼主への報告に書く行': ['例外あり：ルール%d（%s・%s %s）' % (r_['項目'], r_['理由'], r_['決めた人'], r_['日時']) for r_ in REIGAI]}
    json.dump(res, open(os.path.join(out, 'kekka.json'), 'w'), ensure_ascii=False, indent=1, default=list)
    TITLE = {1: '公式素材を先に', 2: '声の間を触らない', 3: '出どころ（gaibu_x・不明は使わない）', 4: '手本は3チャンネル・再生数で決めない', 5: '全部の言葉にテロップ・1コマ',
             6: '話し手は自社キャラのアイコン', 7: '挿絵・図解・全画面・実際の画面', 8: 'BGM・効果音の出どころと課金', 9: 'GPU・手本と数字で比べる',
             10: 'BGM を必ず入れる（8割以上・手本の大きさ）'}
    for i in range(1, 11):
        ex = [r_ for r_ in REIGAI if r_['項目'] == i]
        print(('🟠' if ex else '✅' if not NG[i] else '🔴') + ' %d %s' % (i, TITLE[i]) + ('（例外で通過：%s／決めた人 %s／%s）' % (ex[0]['理由'], ex[0]['決めた人'], ex[0]['日時']) if ex else ''))
        for r_ in ex:
            for m in r_['例外で通した外れ']: print('    ・（例外）' + m)
        for m in NG[i]: print('    ・' + m)
    for m in NOTE: print('🟡 ' + m)
    if REIGAI: print('🟠 例外あり %d 項目。依頼主への報告に必ず書く：%s' % (len(REIGAI), ' ／ '.join(res['依頼主への報告に書く行'])))
    print('結果：%s（外れ %d 項目・%d 件）→ %s' % (('合格（例外あり）' if REIGAI else '合格') if ok else '不合格', sum(1 for v in NG.values() if v), sum(len(v) for v in NG.values()), out))
    shutil.rmtree(sb, ignore_errors=True)
    if not ok: sys.exit(1)
    os.makedirs(STAMP, exist_ok=True)
    open(os.path.join(STAMP, res['動画のsha256'] + '.zettai'), 'w').write('%s %s %s%s\n' % (res['測った時刻'], mp4, os.path.join(out, 'kekka.json'), ' 例外あり：' + ' ／ '.join(res['依頼主への報告に書く行']) if REIGAI else ''))
    if A.nouhin:
        AL = os.path.join(HOME, 'rin6/tools/ai-label-check.py')
        nou = mp4[:-4] + '.nouhin.mp4'
        if subprocess.run(['python3', AL, mp4]).returncode:
            subprocess.run(['python3', AL, '--strip', mp4])
            cl = mp4[:-4] + '.clean.mp4'
            if not os.path.exists(cl) or subprocess.run(['python3', AL, cl]).returncode: sys.exit('🔴 AIの印が消えない')
            shutil.move(cl, nou)
        else: shutil.copy(mp4, nou)
        if subprocess.run(['python3', AL, nou]).returncode: sys.exit('🔴 納品の写しに AI の印が残っている')
        s2 = sha(nou)
        if not os.path.exists(os.path.join(STAMP, s2 + '.zettai')):
            open(os.path.join(STAMP, s2 + '.zettai'), 'w').write('%s %s（%s の写し）\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), nou, mp4))
        subprocess.run(['python3', AL, '--sheet', nou])
        print('納品の写し：%s（次は一覧画像を目で見て ai-label-check.py --mokushi-ok）' % nou)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--_trace': trace_main(sys.argv[2])
    else: main()
