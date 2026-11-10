#!/usr/bin/env python3
# 答えを見ない練習（作業AI・2026-10-15）
#   依頼主 10/15 09:25「これからはトレースするものがない状態で作る」・09:27「あくまでトレースの練習しかできていない」
#   元の動画の【声だけ】から作業AIが演出を決め、そのあとで元の編集（per_full＝全編を1コマずつ見た記録）と比べて点数を出す。
#   決める段（prep）では per_full も映像も開かない。答えを開くのは score だけ。
#
#   python3 mikai.py list                 練習に使える動画（声の切り出し stems と per_full の両方がある）
#   python3 mikai.py prep  <id>           声だけ → 練習の場 mikai/<id>/（台本＝声の文字起こし・① 時刻だけ・② 下書き）
#        → 作業AIが mikai/<id>/story.py を仕上げる（ここで per_full・元の映像を見ない）
#   python3 mikai.py score <id> [--label 作業AIの仕上げ]   作業AIの story を動かして、元の編集と比べる → mikai/<id>/score.json・mikai/kiroku.tsv
#   python3 mikai.py run   <id>           prep → 下書きのまま score（道具だけの実力＝最初の点数）
#
#   比べる中身（合格の線は kijun.json の mikai）
#     ① テロップの言葉 … 元が出した文字と作業AIが出した文字の重なり（時刻が近い所どうし・2字の切れ端で F1）＋「出す／出さない」の一致
#     ② 切り替えの秒 …… 元の場面の頭と作業AIの場面の頭（±mikai.cut_tol 秒で1対1に当てて F1）
#     ③ 効果音の位置 …… 元の効果音と作業AIの効果音（±mikai.sfx_tol 秒で1対1に当てて F1）
#     ④ 絵の意図 ……… 0.5秒ごとに 元の絵の種類 と 作業AIの絵の種類（文字／絵・人物／図解／写真・画面／告知・特典）が同じ割合
#     ⑤ 1本の流れ …… 区間の切れ目（F1）・0.5秒ごとの区間の役割の一致・山場の位置（元の per_full に video_marketing がある本だけ。無い本は合格にしない）
import os, sys, json, re, glob, shutil, subprocess, time, datetime
TOOL = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(TOOL, 'lib'))
import paths
BASE = paths.ENGINE
STEMS = os.path.join(BASE, 'kata', 'full', 'stems'); PER = os.path.join(BASE, 'kata', 'per_full')
HOME_M = os.path.join(BASE, 'mikai'); KIROKU = os.path.join(HOME_M, 'kiroku.tsv')
NARR_PY = os.path.join(TOOL, 'narration', '.venv', 'bin', 'python')
K = json.load(open(paths.KIJUN)); MK = K['mikai']
N = lambda s: re.sub(r'[^ぁ-んァ-ヶー一-龠々0-9０-９A-Za-zＡ-Ｚａ-ｚ]', '', s or '')

def avail():
    return sorted(v for v in os.listdir(STEMS) if os.path.exists(os.path.join(STEMS, v, 'vocals.wav')) and os.path.exists(os.path.join(PER, v + '.json')))

def wait_mem():
    while subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], capture_output=True, text=True).stdout.strip() not in ('1', ''):
        print('メモリの圧力が通常でないので待ちます', flush=True); time.sleep(60)

def jikoku_from_words(vid, P):
    """見本の前処理（yoru：tools0b/words3.py＝Whisper large-v3・mlx）で起こし済みの words_v3.json から、台本の代わり（daihon.txt）と
    時刻（work/narr/jikoku.json・kiroku.json・henshu.wav）を作る。声を起こし直さない（同じモデルの結果・重い Whisper を二度回さない）。
    読むのは words_v3.json と声だけ。raw/<id>/ のほかの物（画面の測り・シート・tl.txt）は答えなので開かない"""
    wp = os.path.join(BASE, 'kata', 'full', 'raw', vid, 'words_v3.json')
    if not os.path.exists(wp): return False
    segs = json.load(open(wp)); segs = segs['segments'] if isinstance(segs, dict) else segs
    sents, cur = [], None
    for sg in segs:
        ws = [{'t': w[2], 's': float(w[0]), 'e': float(w[1])} for w in sg['words'] if N(w[2])]
        if not ws: continue
        if cur and (len(N(cur['text'])) < 10 or ws[0]['s'] - cur['e'] < 0.05) and len(N(cur['text'])) + len(N(sg['text'])) <= 60:
            cur['words'] += ws; cur['text'] += sg['text'].strip(); cur['e'] = ws[-1]['e']
        else:
            if cur: sents.append(cur)
            cur = {'text': sg['text'].strip(), 'words': ws, 's': ws[0]['s'], 'e': ws[-1]['e']}
    if cur: sents.append(cur)
    I = os.path.join(P, 'input'); nd = os.path.join(P, 'work', 'narr'); os.makedirs(nd, exist_ok=True)
    open(os.path.join(I, 'daihon.txt'), 'w').write('\n'.join(x['text'].rstrip('。') + '。' for x in sents) + '\n')
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(I, 'narration.wav')], capture_output=True, text=True).stdout.strip())
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(I, 'narration.wav'), '-ac', '1', '-ar', '48000', os.path.join(nd, 'henshu.wav')], check=True)
    J = {'sentences': [{'i': k + 1, 'text': x['text'].rstrip('。') + '。', 'sec': '本編', 'found': True, 'sim': 1.0, 'hits': 1, 's': round(x['s'], 3), 'e': round(x['e'], 3),
                        's_edit': None, 'e_edit': None, 'words': x['words']} for k, x in enumerate(sents)], 'not_in_script': [], 'dur': round(dur, 2)}
    json.dump(J, open(os.path.join(nd, 'jikoku.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump({'input': os.path.join(I, 'narration.wav'), 'script': os.path.join(I, 'daihon.txt'), 'dur_in': round(dur, 2), 'dur_out': round(dur, 2), 'as_is': True,
               'deleted': [], 'speed': {'factor': 1.0}, 'missing': [], 'from': wp}, open(os.path.join(nd, 'kiroku.json'), 'w'), ensure_ascii=False, indent=1)
    print('台本の代わりと時刻：見本の前処理の Whisper large-v3（words_v3.json）から %d文' % len(sents), flush=True)
    return True

def prep(vid):
    """声だけで練習の場を作る（per_full・元の映像は開かない）"""
    P = os.path.join(HOME_M, vid); I = os.path.join(P, 'input'); os.makedirs(I, exist_ok=True)
    src = os.path.join(STEMS, vid, 'vocals.wav')
    if not os.path.exists(src): src = os.path.join(BASE, 'kata', 'full', 'raw', vid, 'vocals16k.wav')   # yoru の前処理の声（demucs の声を16kHzにしたもの）
    if not os.path.exists(os.path.join(I, 'narration.wav')): shutil.copy(src, os.path.join(I, 'narration.wav'))
    wait_mem()
    if not os.path.exists(os.path.join(I, 'daihon.txt')): jikoku_from_words(vid, P)
    if not os.path.exists(os.path.join(I, 'daihon.txt')):
        print('台本の代わり：声を Whisper large-v3 で起こす', flush=True)
        subprocess.run(['nice', '-n', '19', NARR_PY, os.path.join(TOOL, 'narration', 'okoshi.py'), os.path.join(I, 'narration.wav'), os.path.join(I, 'daihon.txt')],
                       cwd=os.path.join(TOOL, 'narration'), check=True)
    mk = [sys.executable, os.path.join(TOOL, 'make.py'), P]
    subprocess.run(mk + ['--step', 'voice', '--as-is'], check=True)      # 元の時間軸のまま（声は編集しない）
    subprocess.run(mk + ['--step', 'draft'], check=True)
    print('→ %s/story.py を作業AIが仕上げる（per_full・元の映像は見ない）。終わったら python3 mikai.py score %s' % (P, vid))
    return P

def run_story(P):
    r = subprocess.run([sys.executable, os.path.join(P, 'story.py')], env=dict(os.environ, PROJ=P), capture_output=True, text=True)
    if r.returncode: print(r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit('🔴 story.py でエラー')
    return json.load(open(os.path.join(P, 'work', 'story_meta.json')))

def match_f1(a, b, tol):
    """2つの時刻の並びを ±tol で1対1に当てる（近い順に貪欲）→ 適合・再現・F1・当たった組のずれ"""
    a = sorted(a); b = sorted(b); pairs = sorted((abs(x - y), i, j) for i, x in enumerate(a) for j, y in enumerate(b) if abs(x - y) <= tol)
    ua, ub, d = set(), set(), []
    for dd, i, j in pairs:
        if i in ua or j in ub: continue
        ua.add(i); ub.add(j); d.append(b[j] - a[i])
    p = len(ub) / len(b) if b else 0.0; r = len(ua) / len(a) if a else 0.0
    return {'precision': round(p, 3), 'recall': round(r, 3), 'f1': round(2 * p * r / (p + r), 3) if p + r else 0.0, 'n_ans': len(a), 'n_rin': len(b),
            'median_off': round(sorted(d)[len(d) // 2], 3) if d else None}

def bigrams(s):
    s = N(s); return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())

VIS = [('告知・特典', r'告知|特典|プレゼント|終了画面|映画風'), ('写真・画面', r'写真|実写|映像|動画|画像|素材|スクショ|画面録画|スマホ|iMac|切り抜き'),
       ('絵・人物', r'人物|イラスト|アイコン|考える人|本人|ロゴ|絵'), ('図解', r'図解|チェック|カレンダー|矢印|リスト|表|グラフ')]
def vis_class(s):
    s = s or ''
    if '前の画面のまま' in s: return None
    for name, pat in VIS:
        if re.search(pat, s): return name
    return '文字'
def rin_vis(v):
    if not v: return '文字'
    if '告知' in v: return '告知・特典'
    if '人物' in v or '絵' in v or '行動の画面' in v: return '絵・人物'
    if '図' in v: return '図解'
    if '写真' in v or '画面' in v: return '写真・画面'
    return '文字'

def flow_cat(t):
    """区間の名前・役割の文 → 6つの役割（山場 > フック > 問題提起 > まとめ > 告知・行動 > 本編 の順で当てる）"""
    t = t or ''
    for name, pat in (('山場', r'山'), ('フック', r'フック|つかみ|冒頭'), ('問題提起', r'問題|悩み|提起|共感'), ('まとめ', r'まとめ|締め|振り返り|おわり|終わり'),
                      ('告知・行動', r'告知|CTA|LINE|登録|特典|概要欄|勉強会|案内')):
        if re.search(pat, t): return name
    return '本編'

def flow_score(P, ans, D):
    """作業AIが声だけから書いた1本の流れ（video_marketing.json）と、元の編集の流れ（per_full の video_marketing.flow）を比べる
    ① 区間の切れ目（±mikai.flow_tol 秒で1対1・F1）② 0.5秒ごとの区間の役割の一致 ③ 作業AIの山場が元の「山」の区間に入っているか → 3つの平均"""
    avm = ans.get('video_marketing') or {}; afl = [x for x in (avm.get('flow') or []) if isinstance(x, dict) and 't0' in x and 't1' in x]
    vp = os.path.join(P, 'video_marketing.json')
    if not afl: return {'score': None, 'why': '元の per_full に video_marketing.flow が無い（型を書く作業員が書き足したら測れる）'}
    if not os.path.exists(vp): return {'score': 0.0, 'why': '作業AIの video_marketing.json が無い'}
    rvm = json.load(open(vp)); rfl = [x for x in (rvm.get('flow') or []) if isinstance(x, dict) and 't0' in x]
    tol = max(MK.get('flow_tol', 3.0), 0.02 * D)
    bd = match_f1([float(x['t0']) for x in afl[1:]], [float(x['t0']) for x in rfl[1:]], tol)
    def cat_at(fl, t, key):
        for x in fl:
            if float(x['t0']) <= t < float(x.get('t1') or 1e9): return flow_cat(' '.join(str(x.get(k) or '') for k in key))
        return None
    same = tot = 0; conf = {}
    for k in range(int(D / 0.5)):
        t = k * 0.5; a = cat_at(afl, t, ('name', 'role')); r = cat_at(rfl, t, ('name', 'aim'))
        a, r = [('本編' if v == '山場' else v) for v in (a, r)]   # 元は本編の区間を全部「本編の山」と書く（山場を1つに絞らない）→ 役割の一致では山場と本編を同じに数える。山場は ③ で見る
        if a is None or r is None: continue
        tot += 1; same += a == r
        if a != r: conf['%s→%s' % (a, r)] = conf.get('%s→%s' % (a, r), 0) + 0.5
    lab = same / tot if tot else 0.0
    cl = rvm.get('climax') or {}; ct = cl.get('t') if isinstance(cl, dict) else None
    yama = [(float(x['t0']), float(x['t1'])) for x in afl if '山' in str(x.get('role') or x.get('name') or '')]
    hit = (1.0 if any(a - 2 <= ct <= b + 2 for a, b in yama) else 0.0) if ct is not None and yama else (None if not yama else 0.0)
    sc = [bd['f1'], lab] + ([hit] if hit is not None else [])
    return {'score': round(sum(sc) / len(sc), 3), 'boundary': bd, 'label_agree': round(lab, 3), 'climax_hit': hit, 'climax_t': ct, 'yama': yama, 'tol': round(tol, 1),
            'ans_flow': [(x['t0'], x['t1'], flow_cat(str(x.get('name') or '') + str(x.get('role') or ''))) for x in afl],
            'rin_flow': [(x['t0'], x.get('t1'), flow_cat(str(x.get('name') or '') + str(x.get('aim') or ''))) for x in rfl],
            'top_mismatch_s': sorted(((v, k) for k, v in conf.items()), reverse=True)[:5]}

def kanten_score(P, ans):
    """観点の全部（kanten-zenbu.md）で、作業AIの1本（声だけから決めた story）を新しい合格で見る（10/16 依頼主「60点は下位互換」→ 完コピか上位互換）。
    ①本質ルールの破り0 ②全観点で見本（講義型）の中央値以上 ③どの観点でも答え（元の動画）より下にならない。
    映像を書き出さない練習なので、場面の記録から出せる指標だけ（テンポ・音・見やすさの実測は check.py ⑮）"""
    import kanten as KT
    kj = json.load(open(os.path.join(BASE, 'kata', 'kanten_kijun.json')))
    r = KT.from_project(P); a = KT.from_per_full(ans)
    G = KT.gate(r, kj, K['kanten'].get('format', '講義型'), a, ans_id=ans.get('video_id') or os.path.basename(P.rstrip('/')))
    return {'pass': G['pass'], '①破り0': G['①破り0'], '破り': G['破り'], '破りの中身': G['破りの中身'], '破りの上限': G['破りの上限'], '②上位互換': G['②上位互換'], '②中央値以上': G['②中央値以上'], '②': G['②'], '中央値に届かない観点': G['中央値に届かない観点'],
            '③答えより下でない': G['③答えより下でない'], '答えより下の観点': G['答えより下の観点'], 'median': G['median'], 'vs_answer': G['vs_answer'],
            'kanten': [{'name': h['name'], 'score': h['score'], 'broken': h['broken']} for h in G['hon']]}

def ito_compare(P, ans, D):
    """意図の型（ito-zenbu.md）での比べ：0.5秒ごとに 元の場面の意図のまとまり と 作業AIの場面の意図のまとまり が同じ割合、まとまりごとの時間の割合（元・作業AI）"""
    import ito as IT
    meta = json.load(open(os.path.join(P, 'work', 'story_meta.json')))
    rin = sorted(meta.get('intent') or [], key=lambda x: x['t']); sc = [s for s in ans.get('scenes') or [] if isinstance(s, dict)]
    same = tot = 0; ta, tr = {}, {}
    for k in range(int(D / 0.5)):
        t = k * 0.5
        s_ = next((s for s in sc if float(s.get('t0', 0)) <= t < float(s.get('t1') or 1e9)), None)
        r_ = [x for x in rin if x['t'] <= t]
        ga = IT.group((s_ or {}).get('role')) if s_ else None; gr = IT.group(r_[-1]['role']) if r_ else None
        if ga: ta[ga] = ta.get(ga, 0) + 0.5
        if gr: tr[gr] = tr.get(gr, 0) + 0.5
        if ga and gr: tot += 1; same += ga == gr
    keys = sorted(set(ta) | set(tr), key=lambda g: -ta.get(g, 0))
    return {'agree': round(same / tot, 3) if tot else None, 'n': tot,
            'share': {g: {'元': round(ta.get(g, 0) / D, 3), '作業AI': round(tr.get(g, 0) / D, 3)} for g in keys}}

def score(vid, label='下書き（道具だけ）'):
    P = os.path.join(HOME_M, vid)
    meta = run_story(P)
    ans = json.load(open(os.path.join(PER, vid + '.json')))     # ← ここで初めて答えを開く
    D = float(ans.get('duration_s') or meta['end']); sc = [s for s in ans['scenes'] if isinstance(s, dict)]
    plan = sorted(meta.get('selection_plan', []), key=lambda x: x['t'])
    # ② 切り替えの秒
    cut = match_f1([float(s['t0']) for s in sc if float(s['t0']) > 0.3], [t for t in meta['scenes'] if t > 0.3], MK['cut_tol'])
    # ③ 効果音の位置
    sfx = match_f1([float(x['t']) for s in sc for x in (s.get('sfx') or []) if isinstance(x, dict) and 't' in x], [t for t, _ in meta['sfx']], MK['sfx_tol'])
    # ① テロップの言葉
    def ans_texts(s):
        sh = (s.get('telop') or {}).get('shown') or ''
        if N(sh) in ('', 'なし', '不明'): return []
        return [v for v in re.split(r'\s*/\s*', sh) if N(v)]
    rin_shown = [(p['t'], ' '.join(p['shown'])) for p in plan if p.get('shown')]
    rec, prec, agree = [], [], []
    for s in sc:
        a0, a1 = float(s['t0']) - 0.5, float(s.get('t1') or s['t0']) + 0.5
        R = set().union(*[bigrams(t) for tt, t in rin_shown if a0 <= tt <= a1]) if rin_shown else set()
        vs = ans_texts(s)
        agree.append(bool(vs) == bool(R))
        if vs: rec.append(max(len(bigrams(v) & R) / max(1, len(bigrams(v))) for v in vs))
    for tt, t in rin_shown:
        A = set()
        for s in sc:
            if float(s['t0']) - 0.5 <= tt <= float(s.get('t1') or s['t0']) + 0.5:
                for v in ans_texts(s): A |= bigrams(v)
        prec.append(len(bigrams(t) & A) / max(1, len(bigrams(t))))
    rr = sum(rec) / len(rec) if rec else 0.0; pp = sum(prec) / len(prec) if prec else 0.0
    telop = {'recall': round(rr, 3), 'precision': round(pp, 3), 'f1': round(2 * rr * pp / (rr + pp), 3) if rr + pp else 0.0,
             'show_agree': round(sum(agree) / len(agree), 3) if agree else 0.0, 'n_ans_scenes_with_text': len(rec), 'n_rin_shown': len(rin_shown)}
    # ④ 絵の意図（0.5秒ごと）
    same = tot = 0; conf = {}
    for k in range(int(D / 0.5)):
        t = k * 0.5
        s_ = next((s for s in sc if float(s['t0']) <= t < float(s.get('t1') or 1e9)), None)
        if not s_: continue
        a = vis_class((s_.get('visual') or {}).get('kind'))
        if a is None: continue
        p_ = [p for p in plan if p['t'] <= t]
        r = rin_vis(p_[-1]['visual'] if p_ else '')
        tot += 1; same += a == r; conf['%s→%s' % (a, r)] = conf.get('%s→%s' % (a, r), 0) + 1
    vis = {'agree': round(same / tot, 3) if tot else 0.0, 'n': tot, 'top_mismatch': sorted(((v, k) for k, v in conf.items() if k.split('→')[0] != k.split('→')[1]), reverse=True)[:5]}
    # 参考：テロップの選び方の割合（元 vs 作業AI）
    from collections import Counter
    def kk(k):
        for a, b in (('全文', '全文'), ('言い換え', '言い換え'), ('要約', '要約'), ('キーワード', 'キーワード'), ('絵', '出さない'), ('何も', '出さない'), ('出さない', '出さない'), ('足す', '足す')):
            if a in (k or ''): return b
        return 'その他'
    ca = Counter(kk((s.get('selection') or {}).get('kind')) for s in sc); cr = Counter(kk(p['kind']) for p in plan)
    sel = {'元': {k: round(v / max(1, len(sc)), 2) for k, v in ca.most_common()}, '作業AI': {k: round(v / max(1, len(plan)), 2) for k, v in cr.most_common()}}
    # ⑤ 1本全体の流れ（video_marketing の flow）：区間の切れ目・0.5秒ごとの区間の役割・山場の位置（依頼主 19:55「動画1本単位で」）
    flow = flow_score(P, ans, D)
    kan = kanten_score(P, ans)   # 観点の全部（依頼主 10/15「つかみ・離脱・CTAだけではない」）
    ito_c = ito_compare(P, ans, D)   # 意図の型での比べ（参考・合否には使わない）
    parts = {'telop': telop['f1'], 'cut': cut['f1'], 'sfx': sfx['f1'], 'visual': vis['agree']}
    if flow.get('score') is not None: parts['flow'] = flow['score']
    total = round(sum(parts[k] * MK['weights'].get(k, 1) for k in parts) / sum(MK['weights'].get(k, 1) for k in parts), 3)   # 一致率の平均（参考・合否に使わない）
    passed = kan['pass']   # 合格は観点の門だけ（①破り0 ②全観点で中央値以上 ③答えより下にならない）。60点の線は捨てた（10/16）
    res = {'id': vid, 'label': label, 'at': datetime.datetime.now().isoformat(timespec='seconds'), 'dur': D, 'total': total, 'pass': passed,
           'parts': parts, 'line': '①破り0 ②全観点で中央値以上 ③答えより下にならない', 'telop': telop, 'cut': cut, 'sfx': sfx, 'visual': vis, 'flow': flow, 'kanten': kan, 'ito': ito_c, 'selection_share': sel,
           'tol': {'cut': MK['cut_tol'], 'sfx': MK['sfx_tol']}}
    json.dump(res, open(os.path.join(P, 'score.json'), 'w'), ensure_ascii=False, indent=1)
    new = not os.path.exists(KIROKU)
    with open(KIROKU, 'a') as f:
        if new: f.write('日時\tid\t何で作ったか\t合計\tテロップ\t切り替え\t効果音\t絵\t流れ\t合否\t観点\n')
        f.write('%s\t%s\t%s\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%s\t%s\t%s\n' % (res['at'], vid, label, total, parts['telop'], parts['cut'], parts['sfx'], parts['visual'],
                '%.3f' % parts['flow'] if 'flow' in parts else '元に記録なし', '合格' if passed else '不合格',
                '破り%d・下4分の1に届かない%d・答えより下%d' % (kan['破り'], len(kan['中央値に届かない観点']), len(kan['答えより下の観点'] or []))))
    print(json.dumps({k: res[k] for k in ('id', 'label', 'total', 'pass', 'parts')}, ensure_ascii=False))
    print('テロップ', telop); print('切り替え', cut); print('効果音', sfx); print('絵', vis); print('流れ', flow); print('選び方の割合', sel)
    print('意図の型：0.5秒ごとの一致 %s（%s）' % (ito_c['agree'], '・'.join('%s 元%.0f%%/作業AI%.0f%%' % (g, 100 * v['元'], 100 * v['作業AI']) for g, v in list(ito_c['share'].items())[:6])))
    J = kan.get('②') or {}
    print('観点の点（手本の編集者さんの講義型の下から4分の1）：' + '・'.join('%s %s/%s' % (r['name'].split('（')[0], r['score'], r['p25']) for r in J.get('rows', [])) + '／合計 %s（中央値 %s）' % (J.get('sum'), J.get('sum_med')))
    for d in kan.get('破りの中身') or []: print('  破り：%s／%s（%s %s・線 %s〜%s）%s' % (d['観点'], d['ルール'], d['指標'], d['値'], d['線'][0], d['線'][1], '【本人の誰より悪い＝不合格】' if d['本人の誰より悪い'] else ''))
    print('合格の門：①破り0 %s ②上位互換 %s（届かない：%s） ③答えより下でない %s（下：%s）' % (kan['①破り0'], kan['②上位互換'], '・'.join(kan['中央値に届かない観点']) or 'なし',
          kan['③答えより下でない'], '・'.join(kan['答えより下の観点'] or []) or 'なし'))
    return res

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'list': print('\n'.join(avail())); sys.exit(0)
    (os.getpriority(os.PRIO_PROCESS, 0) < 19 and os.setpriority(os.PRIO_PROCESS, 0, 19))
    cmd, vid = a[0], a[1]
    lab = a[a.index('--label') + 1] if '--label' in a else '下書き（道具だけ）'
    if cmd == 'prep': prep(vid)
    elif cmd == 'score': score(vid, lab)
    elif cmd == 'run': prep(vid); score(vid, lab)
