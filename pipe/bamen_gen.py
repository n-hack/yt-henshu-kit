#!/usr/bin/env python3
# 場面割り・場面ごとの訴求・部品と音の選び（yt-henshu-pipe・10/19）：AI（claude -p・opus）が章ごとに場面表を書き、機械の検査で直させる
#   ① 場面割り：行（work/timing_fa.json）と台本から章（30〜60秒・訴求つき）を決める → work/bamen/plan.json・bamen.md
#   ② 章ごとに場面表の節を書く（同時4本）→ work/bamen/ch<章>.py（手引き pipe/BAMEN-GUIDE.md・引き出しの要点・字幕の字）
#   ③ 頭（pipe/story_head.py）＋節＋終わり（pipe/story_tail.py）で story.py を組み、走らせて止まった章を直させる（最大4回）
#   ④ pipe/kensa_bamen.py の検査（重なり・字幕帯・間の空き・帯と字幕の食い違い・種類）で直す所がある章を直させる（最大2回）
#   python3 bamen_gen.py <作業フォルダ> [--kind VSL|YouTube] [--replan] [--regen 章,章] [--fix-rounds 2]
import os, sys, json, re, subprocess, time, argparse, glob
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--kind', default='VSL'); ap.add_argument('--replan', action='store_true')
ap.add_argument('--regen', default=''); ap.add_argument('--kaizen', default='', help='作り直すとき、前の版の節を見せて直す方向を書く（v14：前の版の訴求と字は残し、表現の型を増やす）'); ap.add_argument('--fix-rounds', type=int, default=3); ap.add_argument('--model', default='opus')
A = ap.parse_args(); P = os.path.abspath(A.proj); BD = os.path.join(P, 'work', 'bamen'); os.makedirs(BD, exist_ok=True)
def log(*a): print('［場面表］', time.strftime('%H:%M:%S'), *a, flush=True)
J = json.load(open(os.path.join(P, 'work', 'timing_fa.json'))); LINES = J['lines']
DISP = {int(k): v['disp'].replace('｜', '') for k, v in json.load(open(os.path.join(P, 'work', 'jimaku_disp.json'))).items()}
DAI = open(os.path.join(P, 'input', 'daihon.txt'), encoding='utf-8-sig').read()
GAMEN = json.load(open(os.path.join(HERE, 'gamen.json')))
GUIDE = open(os.path.join(HERE, 'BAMEN-GUIDE.md')).read().replace('{GAMEN}', '・'.join('%s（%s）' % (k, v) for k, v in GAMEN.items()))
HK = os.path.expanduser('~/rin6/state/yt-renshu/1018/jiki/hikidashi.md')
HIKI = open(HK).read()[:9000] if os.path.exists(HK) else ''
def ai(prompt, tries=3):
    for k in range(tries):
        r = subprocess.run(['claude', '-p', '--model', A.model, '--output-format', 'text'], input=prompt, capture_output=True, text=True, cwd='/tmp', timeout=1500)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout
        log('AI がこけた（%d回目）：%s' % (k + 1, (r.stderr or r.stdout)[-300:])); time.sleep(20)
    raise SystemExit('AI が返らない')
def table(a, b):
    rows = []
    for ln in LINES:
        if a <= ln['n'] <= b:
            rows.append('%d | %.2f | %.1f | %s | %s' % (ln['n'], ln['start'], ln['end'] - ln['start'], ln['text'], DISP.get(ln['n'], '')))
    return '行 | 始め秒 | 長さ | 声の字（K() に使う字） | 字幕の字（画面に出す正しい字）\n' + '\n'.join(rows)
END = J['duration']
# ① 場面割り
PJ = os.path.join(BD, 'plan.json')
if A.replan or not os.path.exists(PJ):
    pr = ('あなたは %s（話し手自社キャラの1人語り・%.0f秒）の編集者です。マーケ目線で章に分け、章ごとの訴求を決めてください。\n'
          '- 章は話の切れ目で 25〜60 秒（短すぎ・長すぎにしない）。全部の行をどれかの章に入れる（抜け・重なりなし・行番号の順）\n'
          '- title は画面左上の章札に出す 16 字以内の言葉（見る人が今どこを聞いているか分かる言葉。最初のつかみの章は title を空にする）\n'
          '- aim は「見る人に何を感じさせ、何をさせたいか」（1文）。roles はこの章で使う訴求の型（フック・共感・問題提起・具体例・権威・実績・限定・希少・比較・手順・結論・CTA・告知・宣伝 など）\n'
          '- kokuchi は面談・申し込み・特典などの告知・CTA が本格的に始まる章だけ true（1つだけ）\n'
          '- 再生数・再生回数・視聴回数という言葉は書かない\n'
          '返事は JSON だけ：{"chapters": [{"id": "1", "a": 最初の行, "b": 最後の行, "title": "…", "aim": "…", "roles": ["…"], "kokuchi": false}]}\n\n'
          '行の一覧：\n%s\n\n台本（参考）：\n%s\n\n手本の作者さんの動画から取った部品と訴求の引き出し（要点）：\n%s') % (A.kind, END, table(1, 10 ** 6), DAI[:12000], HIKI[:6000])
    out = ai(pr); m = re.search(r'\{.*\}', out, re.S); plan = json.loads(m.group())
    ns = [ln['n'] for ln in LINES]; cov = sorted(n for c in plan['chapters'] for n in range(int(c['a']), int(c['b']) + 1))
    if cov != ns: raise SystemExit('場面割りが行を覆っていない（抜け・重なり）：%s' % (sorted(set(ns) ^ set(cov))[:20]))
    json.dump(plan, open(PJ, 'w'), ensure_ascii=False, indent=1)
    with open(os.path.join(P, 'bamen.md'), 'w') as f:
        f.write('# 場面割りと訴求（pipe/bamen_gen.py・AI が決めた）\n\n| 章 | 行 | 秒 | 章札 | 訴求 | 型 |\n|---|---|---|---|---|---|\n')
        st = {ln['n']: ln['start'] for ln in LINES}
        for c in plan['chapters']: f.write('| %s | %s〜%s | %.0f〜 | %s | %s | %s |\n' % (c['id'], c['a'], c['b'], st[int(c['a'])], c['title'], c['aim'], '・'.join(c.get('roles', []))))
    log('場面割り：%d 章' % len(plan['chapters']))
plan = json.load(open(PJ)); CHS = plan['chapters']
OUTLINE = '\n'.join('章%s 行%s〜%s「%s」%s%s' % (c['id'], c['a'], c['b'], c['title'], c['aim'], '（告知・CTA の始まり）' if c.get('kokuchi') else '') for c in CHS)
def ch_prompt(c, extra=''):
    a, b = int(c['a']), int(c['b'])
    prev = [ln for ln in LINES if ln['n'] == a - 1]
    return (GUIDE + '\n\n# この動画\n種類：%s（%.0f 秒）。章の流れ：\n%s\n\n# あなたが書く章\n章 %s（行 %d〜%d）章札「%s」\n訴求：%s\n型：%s\n%s%s\n\n%s\n%s'
            % (A.kind, END, OUTLINE, c['id'], a, b, c['title'], c['aim'], '・'.join(c.get('roles', [])),
               '最初のつかみの章なので LBL = None のまま（章札を出さない）。\n' if not c['title'] else '',
               'この章で告知・CTA が始まる：最初の行で KOKUCHI_FROM = L(%d) を書く。\n' % a if c.get('kokuchi') else '',
               ('前の章の最後の行：%s\n' % prev[0]['text']) if prev else '', table(a, b)) + extra)
def code_of(out):
    m = re.findall(r'```python\n(.*?)```', out, re.S)
    if not m: raise ValueError('python の節が無い')
    return max(m, key=len).strip() + '\n'
def gen(c, extra=''):
    fp = os.path.join(BD, 'ch%s.py' % c['id'])
    if A.kaizen and not extra and os.path.exists(fp + '.mae'):
        extra = '\n\n# 前の版（この章）\n%s\n\n```python\n%s```' % (A.kaizen, open(fp + '.mae').read())
    for k in range(3):
        try:
            code = code_of(ai(ch_prompt(c, extra)))
            compile(code, fp, 'exec'); open(fp, 'w').write(code); return fp
        except (ValueError, SyntaxError) as ex:
            extra = extra + '\n\n（前の返事は %s で使えなかった。```python … ``` の中に正しい Python だけを書く）' % ex
    raise SystemExit('章 %s の節が書けない' % c['id'])
regen = set(x for x in A.regen.split(',') if x)
if regen == {'all'}: regen = {c['id'] for c in CHS}
if A.kaizen:   # 作り直す章の今の節を .mae に控えて、AI に見せる
    import shutil as _sh
    for c in CHS:
        fp = os.path.join(BD, 'ch%s.py' % c['id'])
        if c['id'] in regen and os.path.exists(fp) and not os.path.exists(fp + '.mae'): _sh.copy(fp, fp + '.mae')
todo = [c for c in CHS if c['id'] in regen or not os.path.exists(os.path.join(BD, 'ch%s.py' % c['id']))]
if todo:
    log('章の節を書く：%s' % ','.join(c['id'] for c in todo))
    with ThreadPoolExecutor(4) as ex: list(ex.map(gen, todo))
HEAD = open(os.path.join(HERE, 'story_head.py')).read(); TAIL = open(os.path.join(HERE, 'story_tail.py')).read()
def assemble():
    parts = [HEAD]; rng = {}; ln = HEAD.count('\n')
    for c in CHS:
        code = open(os.path.join(BD, 'ch%s.py' % c['id'])).read()
        if not code.endswith('\n'): code += '\n'
        rng[c['id']] = (ln + 1, ln + code.count('\n')); parts.append(code); ln += code.count('\n')
    parts.append(TAIL); open(os.path.join(P, 'story.py'), 'w').write(''.join(parts)); return rng
def run_story():
    r = subprocess.run([sys.executable, os.path.join(P, 'story.py')], env=dict(os.environ, PROJ=P), capture_output=True, text=True, cwd=P)
    return r.returncode, r.stdout, r.stderr
# ③ 走らせて止まった章を直させる
for k in range(5):
    rng = assemble(); rc, so, se = run_story()
    if rc == 0: log('場面表が通った：', so.strip().splitlines()[-1] if so.strip() else ''); break
    lines_ = [int(x) for x in re.findall(r'story\.py", line (\d+)', se)]
    bad = next((cid for cid, (a, b) in rng.items() for x in reversed(lines_) if a <= x <= b), None)
    msg = se.strip().splitlines()[-1] if se.strip() else so[-300:]
    if bad is None or k == 4: raise SystemExit('場面表が止まる（章を特定できない）：%s\n%s' % (msg, se[-2000:]))
    c = next(c for c in CHS if c['id'] == bad); code = open(os.path.join(BD, 'ch%s.py' % bad)).read()
    log('章 %s で止まった：%s → 直させる' % (bad, msg))
    gen(c, '\n\n# 直してほしいこと\n前に書いた節を走らせたら、次のエラーで止まった。原因の所だけ直した節を全部書き直して返す。\nエラー：%s\n（K() の言葉はその行の「声の字」にそのままある字だけ。行番号もこの章の中だけ）\n\n前の節：\n```python\n%s```' % (msg, code))
# ④ 検査して直させる
def kensa():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'kensa_bamen.py'), P], capture_output=True, text=True)
    if r.returncode: raise SystemExit('検査が止まった：' + r.stderr[-1500:])
    log(r.stdout.strip().splitlines()[0]); return json.load(open(os.path.join(BD, 'kensa.json')))
K_ = kensa(); json.dump(K_, open(os.path.join(BD, 'kensa-0.json'), 'w'), ensure_ascii=False, indent=1)
# 別の目（pipe/me_ai.py）が書き出した動画で見つけた直す所も、秒から章に振り分けて直させる
ME = os.path.join(P, 'work', 'me_ai.json'); ME_DONE = os.path.join(BD, 'me_ai_used.json')
if os.path.exists(ME) and not json.load(open(ME)).get('ok') and (not os.path.exists(ME_DONE) or os.path.getmtime(ME_DONE) < os.path.getmtime(ME)):
    stt = {ln['n']: ln['start'] for ln in LINES}
    for x in json.load(open(ME)).get('mondai', []):
        mm = re.match(r'(\d+):(\d+(?:\.\d+)?)', str(x.get('t', '')))
        if not mm: continue
        sec = int(mm.group(1)) * 60 + float(mm.group(2))
        cid = max((c for c in CHS if stt[int(c['a'])] <= sec + 0.01), key=lambda c: stt[int(c['a'])], default=CHS[0])['id']
        K_['ch'].setdefault(cid, []).append('（書き出した動画を見た別の目）%.1f秒：%s' % (sec, x.get('naiyou', '')))
    open(ME_DONE, 'w').write('1')
for rnd in range(A.fix_rounds):
    chs = {c: v for c, v in K_['ch'].items() if c in {x['id'] for x in CHS}}
    if K_['zentai']:   # 種類が足りないときは、長い章から順に1つずつ受け持たせる
        big = sorted(CHS, key=lambda c: -(int(c['b']) - int(c['a'])))
        for i, z in enumerate(K_['zentai']): chs.setdefault(big[i % len(big)]['id'], []).append(z)
    if not chs: break
    log('直す章（%d回目）：%s' % (rnd + 1, '・'.join('%s(%d)' % (c, len(v)) for c, v in sorted(chs.items()))))
    def fix(cid):
        c = next(x for x in CHS if x['id'] == cid); code = open(os.path.join(BD, 'ch%s.py' % cid)).read()
        gen(c, '\n\n# 直してほしいこと（機械の検査）\n' + '\n'.join('- ' + m for m in chs[cid][:25]) + '\n直す所だけ直し、ほかの場面・訴求・密度は保ったまま、節を全部書き直して返す。\n\n前の節：\n```python\n%s```' % code)
    with ThreadPoolExecutor(4) as ex: list(ex.map(fix, list(chs)))
    for k in range(4):
        rng = assemble(); rc, so, se = run_story()
        if rc == 0: break
        lines_ = [int(x) for x in re.findall(r'story\.py", line (\d+)', se)]; msg = se.strip().splitlines()[-1]
        bad = next((cid for cid, (a, b) in rng.items() for x in reversed(lines_) if a <= x <= b), None)
        if bad is None: raise SystemExit('場面表が止まる：' + msg)
        c = next(c for c in CHS if c['id'] == bad); code = open(os.path.join(BD, 'ch%s.py' % bad)).read()
        gen(c, '\n\n# 直してほしいこと\nエラー：%s\n原因の所だけ直した節を全部返す。\n\n前の節：\n```python\n%s```' % (msg, code))
    K_ = kensa(); json.dump(K_, open(os.path.join(BD, 'kensa-%d.json' % (rnd + 1)), 'w'), ensure_ascii=False, indent=1)
log('おわり：直す所 %d 件・全体 %s' % (K_['kazu']['直す所'], K_['zentai'] or 'なし'))
