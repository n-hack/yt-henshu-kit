# ① 声：依頼主から届く「録ったままの粗いナレーション」＋「台本」→ 編集済みの声と、台本の字ごとの時刻（作業AI・2026-10-15）
#   依頼主 10/15 09:25「ナレーションはただ録っただけなので、ジャンプカットしていなかったり、言い直しがあったりと、かなり粗い状態です。そういったカットも含めて対応できるようになっておいてください」
#   声の編集は narration/henshu.py（言い直し・つなぎ言葉・噛みを消す／Whisper large-v3（mlx・GPU）／動画全体で倍率を1つ／間を見本の分布に）
#   ここはその結果を、場面表（lib/henshu.py の Clock）・質の門（check.py）が読む形に直す：
#     work/vocals.wav   編集済みの声
#     work/timing.json  台本の行ごとの区間・訴求・話し始め、字ごとの話し始め・終わり
#     work/kousei.json  作業AIが台本と声から決めた 区間・訴求・【間】（依頼主の台本には書かれていない前提）
#   as_is=True … 声は編集せず時刻だけ取る（答えを見ない練習：元の動画の時間軸のまま演出を決める）
import os, re, json, shutil, subprocess, difflib
import numpy as np
import paths, metrics as HM
import voice as V

NARR = os.path.join(paths.TOOL, 'narration')
NARR_PY = os.path.join(NARR, '.venv', 'bin', 'python')
N = lambda s: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】“”"]', '', s.replace('【間】', ''))
SEC_MAP = {'冒頭': 'フック', '告知': '告知', '本編': '本編', '締め': '締め'}
EMPH = re.compile(r'^(結論|つまり|実は|じつは|なぜなら|ポイントは|大事なのは|重要なのは|答えは|正解は|ズバリ|はっきり言って|一番|最後に)')


def find_inputs(proj):
    d = os.path.join(proj, 'input'); fs = sorted(os.listdir(d))
    na = [os.path.join(d, f) for f in fs if f.startswith('narration')]
    sc = [os.path.join(d, f) for f in fs if re.match(r'(daihon|script)\.(txt|md)$', f)]
    if not na: raise SystemExit('input/narration.(wav|mp3|m4a) がありません')
    if not sc: raise SystemExit('input/daihon.txt（台本）がありません')
    return na[0], sc[0]


def plain_script(src, dst):
    """どんな形の台本でも、henshu.py が読む形（1行1文・空行で段落・【冒頭】などの見出しは任意）にする。
    表の形（| # | 区間 | 台本 | 訴求 |）なら台本の列だけを取り、区間は見出しに直す。【間】は外す（作業AIが声から決める）"""
    out, prev = [], None
    for raw in open(src, encoding='utf-8'):
        s = raw.rstrip('\n')
        m = re.match(r'\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|', s)
        if m:
            sec = next((v for k, v in (('フック', '冒頭'), ('冒頭', '冒頭'), ('告知', '告知'), ('締め', '締め'), ('CTA', '締め')) if k in m.group(2)), '本編')
            if sec != prev: out.append(''); out.append('【%s】' % sec); prev = sec
            out.append(m.group(3).strip().replace('【間】', '')); continue
        if s.startswith('|') or s.startswith('#') or s.startswith('- '): continue
        m2 = re.match(r'\[([^\]]+)\]\s*(.*)', s.strip())
        if m2: s = m2.group(2)
        out.append(s.replace('【間】', ''))
    open(dst, 'w', encoding='utf-8').write('\n'.join(out).strip() + '\n')
    return dst


def run_henshu(inp, script, outdir, as_is=False, log=print):
    """narration/henshu.py を一番低い優先度（nice 19）で走らせる。Whisper は large-v3（mlx・GPU）から下げない"""
    if as_is and os.path.exists(os.path.join(outdir, 'jikoku.json')) and os.path.exists(os.path.join(outdir, 'kiroku.json')):
        log('① 時刻だけ：jikoku.json が先にある（mikai.py が見本の前処理の Whisper large-v3 の結果から作った）ので起こし直さない'); return
    tool = 'jikoku_only.py' if as_is else 'henshu.py'
    cmd = ['nice', '-n', '19', NARR_PY, os.path.join(NARR, tool), inp, script, outdir]
    log('① 声の編集：%s（Whisper large-v3・mlx・GPU・nice 19）' % ('時刻だけ' if as_is else '言い直し・つなぎ言葉・噛み・間・全体の速さ'))
    r = subprocess.run(cmd, cwd=NARR, capture_output=True, text=True)
    open(os.path.join(outdir, 'henshu.log'), 'w').write(r.stdout + r.stderr)
    if r.returncode: raise SystemExit('🔴 ① 声の編集でエラー（%s/henshu.log）\n%s' % (outdir, r.stderr[-1500:]))


def fix_leftovers(J, wav, plain, nd, log=print, lim=0.5):
    """編集後の声の聞き直しで、文の区間（s_edit〜e_edit）の頭や尻に、その文として聞こえない声が lim 秒より長く残っていたら
    （言いかけ・言い直しの1回目の取りこぼし。10/15 粗い声の試しで1か所見つかった）、そこを切って聞き直す。
    切った後に台本の文が1つでも見つからなくなったら切らない（元のまま・作業AIに知らせる）"""
    cut = []
    for s in J['sentences']:
        if not s.get('found') or s.get('s_edit') is None: continue
        if s['s'] - s['s_edit'] > lim: cut.append((s['s_edit'] + 0.02, s['s'] - 0.04, s['text'][:16], '頭'))
        if s['e_edit'] - s['e'] > lim: cut.append((s['e'] + 0.04, s['e_edit'] - 0.02, s['text'][:16], '尻'))
    if not cut: return J, wav, []
    fd = os.path.join(nd, 'nokori'); os.makedirs(fd, exist_ok=True)
    fw = os.path.join(fd, 'henshu_fix.wav')
    sel = '+'.join('between(t,%.3f,%.3f)' % (a, b) for a, b, _, _ in cut)     # 元と同じ 24bit のまま切る（音質を落とさない）
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-af', "aselect='not(%s)',asetpts=N/SR/TB" % sel, '-c:a', 'pcm_s24le', fw], check=True)
    log('① 文の前後に残った声 %d か所（計 %.1f 秒）を切る：%s' % (len(cut), sum(b - a for a, b, _, _ in cut), ' ／ '.join('%s「%s」%.1f秒' % (w, t, b - a) for a, b, t, w in cut)))
    # 時刻は聞き直さず、切った長さだけ後ろを前へずらす（聞き直すと切っていない所で Whisper が文を落とすことがある・10/15 実測）
    cs = sorted((a, b) for a, b, _, _ in cut)
    def mv(t):
        if t is None: return t
        d = 0.0
        for a, b in cs:
            if t >= b: d += b - a
            elif t > a: d += t - a
        return round(t - d, 3)
    J2 = json.loads(json.dumps(J))
    for x in J2['sentences']:
        for k in ('s', 'e', 's_edit', 'e_edit'): x[k] = mv(x.get(k))
        for w in x.get('words') or []: w['s'], w['e'] = mv(w['s']), mv(w['e'])
        if x.get('s') is not None and x.get('s_edit') is not None and x['s'] - x['s_edit'] > lim: x['s_edit'] = x['s']
        if x.get('e') is not None and x.get('e_edit') is not None and x['e_edit'] - x['e'] > lim: x['e_edit'] = x['e']
    json.dump(J2, open(os.path.join(fd, 'jikoku.json'), 'w'), ensure_ascii=False, indent=1)
    rec = [{'s': round(a, 2), 'e': round(b, 2), 'text': t, 'where': w, 'applied': True} for a, b, t, w in cut]
    return J2, fw, rec


def char_times(text, words, s0, e0):
    """台本の1文の字ごとの話し始め・終わり。Whisper の言葉の時刻を字に割り、台本の字と並べる（合わない字は前後から補う）"""
    ref = N(text); said, st, en = '', [], []
    for w in words:
        t = N(w['t'])
        if not t: continue
        d = (w['e'] - w['s']) / len(t)
        for k, ch in enumerate(t): said += ch; st.append(w['s'] + k * d); en.append(w['s'] + (k + 1) * d)
    S = [None] * len(ref); E = [None] * len(ref)
    for b in difflib.SequenceMatcher(None, ref, said, autojunk=False).get_matching_blocks():
        for k in range(b.size): S[b.a + k] = st[b.b + k]; E[b.a + k] = en[b.b + k]
    known = [i for i, v in enumerate(S) if v is not None]
    if not known:
        g = np.linspace(s0, e0, len(ref) + 1); return list(g[:-1]), list(g[1:])
    for i in range(len(ref)):
        if S[i] is not None: continue
        lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
        a = E[lo] if lo is not None else s0; b = S[hi] if hi is not None else e0
        n_lo = lo if lo is not None else -1; n_hi = hi if hi is not None else len(ref)
        m = n_hi - n_lo - 1; k = i - n_lo - 1                     # 合わない字は 前後の合った字の間に等しく並べる
        S[i] = a + (b - a) * k / m; E[i] = a + (b - a) * (k + 1) / m
    for i in range(1, len(ref)): S[i] = max(S[i], S[i - 1])
    return S, E


ROLE_INTENT = [
    ('行動', lambda t: re.search(r'(LINE|ライン|概要欄|コメント|チャンネル登録|高評価|フォロー|受け取)', t), '行動を1つに絞って迷わせない'),
    ('問い', lambda t: t.rstrip('。').endswith(('？', '?', 'か', 'のか', 'でしょうか', 'ませんか')), '問いで自分ごとにして、答えを待たせる'),
    ('数字', lambda t: re.search(r'[0-9０-９]|[一二三四五六七八九十百千万億]+(人|社|件|円|倍|分|時間|日|か月|ヶ月|年|%|割|本|回|つ)', t), '数字で「本当にできる」と信じさせる'),
    ('結論', lambda t: EMPH.search(t), '結論を強く刻む（ここは覚えて帰ってほしい）'),
    ('理由', lambda t: re.search(r'(なぜなら|理由は|だから|というのも|からです)', t), '理由で腹落ちさせる'),
    ('具体例', lambda t: re.search(r'(たとえば|例えば|実際に|実例|ケース)', t), '具体例で絵を浮かばせる'),
    ('言い切り', lambda t: re.search(r'(ません|ない|違う|間違い|ダメ)[。！]?$', t.rstrip()), '常識を覆して続きを聞かせる'),
]
SEC_INTENT = {'フック': '「自分のことだ」と止まらせ、最後まで見る理由を渡す', '告知': '空気を変えて、最後まで見る理由（特典）を作る',
              '本編': '言った順に足して理解させる', '締め': '要点を1つ持ち帰らせ、行動に移させる'}


def kousei(lines, gaps):
    """区間・訴求・【間】を台本と声から決める（作業AIの推定。依頼主の台本には書かれていない前提）
    【間】… 編集済みの声で 0.45秒以上の間が残り、次の文が強調・結論・区間の変わり目のところ（大きい順に4つまで・見本も山場の前だけ）"""
    out = []
    for i, x in enumerate(lines):
        t = x['text']
        role, intent = '説明', SEC_INTENT[x['sec']]
        for r, f, it in ROLE_INTENT:
            if f(t): role, intent = r, it; break
        if i == 0: role, intent = 'つかみ', '「自分のことだ」と止まらせる（題名の先出し）'
        out.append({'n': x['n'], 'sec': x['sec'], 'text': t, 'role': role, 'intent': intent, 'ma': False, 'gap_after': round(gaps[i], 3)})
    cand = [i for i in range(len(out) - 1) if gaps[i] >= 0.45 and (EMPH.search(out[i + 1]['text']) or out[i + 1]['sec'] != out[i]['sec'] or out[i + 1]['role'] in ('結論', '数字'))]
    for i in sorted(cand, key=lambda i: -gaps[i])[:4]: out[i]['ma'] = True
    return out


def prep(proj, kijun, as_is=False, log=print):
    W = os.path.join(proj, 'work'); os.makedirs(W, exist_ok=True)
    inp, sc = find_inputs(proj)
    plain = plain_script(sc, os.path.join(W, 'daihon_plain.txt'))
    nd = os.path.join(W, 'narr'); os.makedirs(nd, exist_ok=True)
    run_henshu(inp, plain, nd, as_is=as_is, log=log)
    J = json.load(open(os.path.join(nd, 'jikoku.json'))); K = json.load(open(os.path.join(nd, 'kiroku.json')))
    src_wav = os.path.join(nd, 'henshu.wav')
    if not as_is:
        J, src_wav, K['nokori'] = fix_leftovers(J, src_wav, plain, nd, log)
        json.dump(K['nokori'], open(os.path.join(nd, 'nokori.json'), 'w'), ensure_ascii=False, indent=1)
    shutil.copy(src_wav, os.path.join(W, 'vocals.wav'))
    y = V.load(os.path.join(W, 'vocals.wav')); sr = V.SR
    on_line = HM.voice_onsets(y, sr); on = V.onsets(y)
    sents = [s for s in J['sentences']]
    lost = [s['text'] for s in sents if not s.get('found')]
    if lost: raise SystemExit('🔴 ① 編集した声に 台本の文が見つからない（%d文）：%s … 声と台本が合っているか確かめる' % (len(lost), ' ／ '.join(lost[:3])))
    if not as_is:
        # 「見つかった」でも残った声が字数に比べて短すぎる文＝話した言葉が消えている（10/16 HBg：8秒の本文を〔声〕として消していた）
        import importlib.util as IU
        sp = IU.spec_from_file_location('narr_common', os.path.join(NARR, 'common.py')); NC = IU.module_from_spec(sp); sp.loader.exec_module(NC)
        short = NC.short_sentences(J)
        if short: raise SystemExit('🔴 ① 編集した声で 台本の文が短すぎる（落とした文 %d）：%s' % (len(short), ' ／ '.join('文%d %s秒（見込み%s秒）' % (x['i'], x['dur'], x['expect']) for x in short[:3])))
    lines, REF, LINE0, ST, EN = [], '', {}, [], []
    for k, s in enumerate(sents):
        n = k + 1; s0 = s['s_edit'] if s.get('s_edit') is not None else s['s']; e0 = s['e_edit'] if s.get('e_edit') is not None else s['e']
        cs, ce = char_times(s['text'], s.get('words') or [], s0, e0)
        # 行の頭：声の実際の立ち上がり（質の門①と同じ式）に合わせる。字の頭：近くの立ち上がりへ吸着（0.08秒以内）
        c = [u for u in on_line if abs(u - cs[0]) <= 0.2] if len(cs) else []
        if c: cs[0] = float(min(c, key=lambda u: abs(u - cs[0])))
        for j in range(1, len(cs)):
            kk = np.searchsorted(on, cs[j]); cc = [on[q] for q in (kk - 1, kk) if 0 <= q < len(on) and abs(on[q] - cs[j]) <= 0.08]
            if cc: cs[j] = max(cs[j - 1], float(min(cc, key=lambda u: abs(u - cs[j]))))
        LINE0[n] = len(REF); REF += N(s['text']); ST += cs; EN += ce
        lines.append({'n': n, 'sec': SEC_MAP.get(s.get('sec') or '本編', '本編'), 'text': s['text'], 'start': round(cs[0], 3) if cs else round(s0, 3), 'end': round(e0, 3)})
    gaps = [lines[i + 1]['start'] - lines[i]['end'] for i in range(len(lines) - 1)] + [0.0]
    KS = kousei(lines, gaps)
    for x, k in zip(lines, KS):
        x['intent'] = k['intent']; x['role'] = k['role']
        if k['ma']: x['text'] = x['text'] + '【間】'
    json.dump({'by': '作業AIの推定（台本と声から・依頼主の台本には区間・訴求・間は無い前提）', 'lines': KS}, open(os.path.join(W, 'kousei.json'), 'w'), ensure_ascii=False, indent=1)
    with open(os.path.join(W, 'kousei.md'), 'w') as f:
        f.write('| # | 区間 | 台本 | 訴求（作業AIの推定） | 役割 | 間 |\n|---|---|---|---|---|---|\n')
        for k in KS: f.write('| %d | %s | %s | %s | %s | %s |\n' % (k['n'], k['sec'], k['text'], k['intent'], k['role'], '【間】' if k['ma'] else ''))
    sp = K.get('speed') or {}
    out = {'lines': lines, 'ref': REF, 'line0': LINE0, 'starts': [round(t, 3) for t in ST], 'ends': [round(t, 3) for t in EN], 'fa_bias': 0.0,
           'duration': round(len(y) / sr, 3), 'cuts': len(K.get('deleted') or []), 'speed': sp.get('factor', 1.0) if isinstance(sp, dict) else 1.0,
           'dur_in': K.get('dur_in'), 'source': inp, 'script': sc, 'as_is': as_is, 'narr': nd}
    json.dump(out, open(os.path.join(W, 'timing.json'), 'w'), ensure_ascii=False)
    return out
