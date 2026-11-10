#!/usr/bin/env python3
# 台本と声 → 1本の流れ（video_marketing.json）を先に書き、そのあと場面表（story.py）の下書きを作る。python3 draft.py <プロジェクト>
#   依頼主 10/15 19:55「1本の動画の中で流れっていうのがあるので、動画1本単位でちゃんとマーケター目線で分析する」
#   依頼主 10/15 20:3x「文脈理解をマーケター目線で活用」「同じ台本は二度と来ない。毎回、その台本の意図が見る人に伝わる演出に」
#   読むもの：work/timing.json（① 声で作った 行ごとの区間・訴求・役割・話し始め。区間・訴求・【間】は作業AIが台本と声から決めたもの＝work/kousei.json）
#
#   段1 ナレーション全体を先に読む（一文ずつ決めない）
#       ・何度も出る語（この1本のテーマ）・数字・問いと答えの組・行動の呼びかけ・告知・【間】
#       ・山場（約束への答え・結論・間のあと・テーマの語がそろう所）を1つ決める
#       ・video_marketing を書く：誰に（target）・約束（promise）・つかみ（hook）・流れ（flow）・山場（climax）・締めの行動（cta）
#         ＋離脱を防ぐ仕掛け（retention）・効いた理由（why_it_works）・ほかの動画に使える型（reusable）＝ AGENT_FULL.md 追記9 と同じ形
#   段2 一文ごとに、前後のつながりと流れの中の区間を理由にして決める（sel 欄）
#       ・テロップに 全文／要約／キーワード／言い換え／足す／出さない
#       ・強調（強／中／なし）・間（後ろに間を残すか）・切り替え（場面転換／切り替え／続ける）
#       ・理由（why）と、前後のどの行につながるか（link）を必ず書く → story_meta.json の selection_plan → 質の門⑪
#     全文は場面の 30% まで・3場面続けない（kijun.json の telop_selection）
#   下書きは「動く・質の門の数字に入る」ところまで。作業AIが訴求と流れを見て仕上げる（story.py の TODO・video_marketing.json の by）。
import os, sys, re, json
from collections import Counter
TOOL = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(TOOL, 'lib'))
import paths
P = os.path.abspath(sys.argv[1])
TJ = json.load(open(os.path.join(P, 'work', 'timing.json')))
L = TJ['lines']; D = float(TJ['duration'])
K = json.load(open(paths.KIJUN)); TS = K['telop_selection']
title = os.path.basename(P.rstrip('/'))
N = lambda s: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】“”"]', '', s.replace('【間】', ''))
TX = lambda x: x['text'].replace('【間】', '')


def sec_of(s):
    for k, v in (('フック', 'hook'), ('冒頭', 'hook'), ('告知', 'kokuchi'), ('締め', 'shime'), ('CTA', 'shime')):
        if k in s: return v
    return 'honpen'


JOSHI_CUT = re.compile(r'(?<=[てでがはをにとも])(?=[^てでがはをにともっー])|(?<=けど)|(?<=ので)|(?<=から)')


def chunks(t, n=16):
    """意味の切れ目（、。）で区切り、1行 n 字までにまとめる。句読点の無い長い文（声から起こした台本）は助詞の後ろで切る"""
    parts = [p for p in re.split(r'(?<=[、。！？])', t.replace('【間】', '')) if p.strip()]
    if any(len(p) > n * 1.6 for p in parts):
        parts = [q for p in parts for q in (JOSHI_CUT.split(p) if len(p) > n * 1.6 else [p]) if q]
    out = []; cur = ''
    for p in parts:
        if len(cur) + len(p) > n and cur: out.append(cur); cur = p
        else: cur += p
    if cur: out.append(cur)
    return [o.rstrip('、。') for o in out]


TSUNAGI = re.compile(r'^(それでは|では|さて|まず|次に|ということで|というわけで|さっきの|じゃあ|ここから|続いて|それと|そして|で、|でね|なので|だから|つまり)')
ZUKAI = re.compile(r'(ステップ|手順|[一二三四五1-9１-９](つ目|つの|個の)|計算式|公式|式|掛け算|足し算|比べ|比較|違い|リスト|一覧|流れ|仕組み|構成|型|フォーマット|×)')
GAMEN = re.compile(r'(画面|スクショ|ツール|アプリ|実際に|実績|見てください|こちら|このように|ご覧|LINE|概要欄|YouTube|インスタ|TikTok|X|再生数|フォロワー)')
CONT = re.compile(r'^(で、|でね|なので|だから|そして|それで|しかも|さらに|あと|それと|ただ|でも|けど)')
STOP = {'という', 'ところ', 'こちら', 'みなさん', '皆さん', 'ください', 'します', 'ちゃんと', '本当に', 'ですね'}


def keywords(t):
    """覚えてほしい語：「」の中・カタカナ3字以上・英数字の語・漢字3字以上の熟語（長い順に2つまで）"""
    ks = re.findall(r'[「『]([^」』]{2,14})[」』]', t)
    ks += [w for w in re.findall(r'[ァ-ヴー]{3,}|[A-Za-z][A-Za-z0-9\.\-]{1,}|[一-龠々]{3,6}', t) if w not in ks and w not in STOP]
    seen = []
    for k in ks:
        if not any(k in s for s in seen): seen.append(k)
    return sorted(seen[:4], key=len, reverse=True)[:2]


def number_of(t):
    m = re.search(r'[0-9０-９][0-9０-９,，.]*\s*[^\s、。0-9]{0,3}|[一二三四五六七八九十百千万億]+(人|社|件|円|倍|分|時間|日|か月|ヶ月|年|%|割|本|回|つ)', t)
    return m.group(0).strip() if m else None


def short_q(t):
    q = re.sub(r'^(では|じゃあ|まず|さて|それでは)[、,]?', '', t.replace('【間】', '')).strip()
    q = re.split(r'(?<=[、])', q)
    last = q[-1].rstrip('。')
    if len(N(''.join(q))) <= 16: return ''.join(q).rstrip('。').rstrip('、') + ('' if ''.join(q).rstrip('。').endswith(('？', '?')) else '？')
    return (last if last.endswith(('？', '?')) else last + '？')


# 言い換え（観点4：見本は出した文字の約半分が言い換え。口語→見出し語・推量→断定・お願い→言い切り・つなぎ言葉を外す）
FILLER = re.compile(r'(めちゃめちゃ|めっちゃ|本当に|ほんとに|やっぱり|やっぱ|ちょっと|結構|なんか|まあ|ですね|ね[、。]?$|っていう|みたいな|とか|ぶっちゃけ|正直)')
IIKAE = [(r'した方がいい(です|んです)?(よ|ね)?$', 'すべき！'), (r'してほしい(です|んです)?$', 'してください！'), (r'(と思います|と思うんです|かなと思います|かなと)$', ''),
         (r'(なんですよ|なんです|んですよ|んです|ですよ|ですね|じゃないですか)$', ''), (r'(できるんじゃないかな|できるのでは)$', 'できる'),
         (r'(やばい|ヤバい)$', '危険'), (r'(でかい|デカい)', '大きい'), (r'(ムズい|むずい)', '難しい'), (r'^僕(は|が|の)?', '')]
def iikae(c):
    o = FILLER.sub('', c).strip('、。 ')
    for a_, b_ in IIKAE: o = re.sub(a_, b_, o)
    return o.strip('、。 ') or c
def as_question(c):
    c = iikae(c).rstrip('？?！!')
    return c if c.endswith(('か', 'の')) and len(c) > 3 else c + '？'


def short(t, n=24):
    t = t.replace('【間】', ''); return t if len(t) <= n else t[:n] + '…'


# ======================================================================
# 段1 ナレーション全体を先に読む
# ======================================================================
n_lines = len(L)
roles = [x.get('role', '説明') for x in L]
secs0 = [sec_of(x['sec']) for x in L]


def smooth_secs(sc):
    """区間を1本の流れとしてならす（声から推した区間は 告知の言葉が出るたびに行ったり来たりする＝流れが細切れになる）：
    告知 … 前から30%までの中で一番長い告知のかたまり1つだけ（間の2行以内の本編はまとめる）／フック … 告知より前（告知が無ければ前の8%）／
    締め … 後ろ15%の中で、最後から続く締め・行動の行／ほかは本編"""
    n = len(sc); st = [x['start'] for x in L]
    out = ['honpen'] * n
    lim = 0.3 * D
    runs, cur = [], None
    for i, v in enumerate(sc):
        if v == 'kokuchi' and st[i] <= lim:
            if cur and i - cur[1] <= 3: cur[1] = i
            else: cur = [i, i]; runs.append(cur)
    kb = max(runs, key=lambda r: st[min(r[1] + 1, n - 1)] - st[r[0]]) if runs else None
    if kb:
        for i in range(kb[0], kb[1] + 1): out[i] = 'kokuchi'
        for i in range(kb[0]): out[i] = 'hook'
    else:
        for i in range(n):
            if st[i] <= max(0.08 * D, st[min(1, n - 1)]): out[i] = 'hook'
    for i in range(n - 1, -1, -1):
        if st[i] < 0.85 * D or not (sc[i] == 'shime' or roles[i] == '行動' or i == n - 1): break
        out[i] = 'shime'
    return out


secs = smooth_secs(secs0)
# 作業AIの仕上げ（work/shiage.json）：台本全体を読んで作業AIが決めた 区間・山場・流れ・行ごとの判断。下書きの推定より優先する（SHIAGE.md）
SHP = os.path.join(P, 'work', 'shiage.json'); SH = json.load(open(SHP)) if os.path.exists(SHP) else {}
_sec = SH.get('sec') or {}
for sec_, a_, b_ in (list(_sec) if isinstance(_sec, list) else [(k, v[0], v[1]) for k, v in _sec.items()]):   # {区間: [から, まで]} か [[区間, から, まで], …]（告知が2回ある本）
    for i in range(n_lines):
        if a_ <= L[i]['n'] <= b_: secs[i] = sec_
kw_of = [keywords(TX(x)) for x in L]
kwc = Counter(k for ks in kw_of for k in ks)
theme = [k for k, c in kwc.most_common(6) if c >= 2][:3] or [k for k, _ in kwc.most_common(2)]
first_seen = {}
for i, ks in enumerate(kw_of):
    for k in ks: first_seen.setdefault(k, i)
answers = {i for i in range(1, n_lines) if roles[i - 1] == '問い' and roles[i] != '問い'}
ma_after = {i for i, x in enumerate(L) if '【間】' in x['text']}            # この行の後ろに間（kousei の【間】）
acts = [i for i, r in enumerate(roles) if r == '行動']
kok = [i for i, s in enumerate(secs) if s == 'kokuchi']
hook_idx = [i for i, s in enumerate(secs) if s == 'hook'] or list(range(min(3, n_lines)))
prom_i = next((i for i in hook_idx if re.search(r'(今日は|今回は|この動画|最後まで|お話しします|話して|分かります|お伝えします|紹介します|方法|やり方)', TX(L[i]))), hook_idx[-1])
promise_kw = set(kw_of[prom_i]) | set(theme)
honpen = [i for i, s in enumerate(secs) if s == 'honpen'] or list(range(n_lines))


def climax_score(i):
    """山場らしさ：約束への答え・結論・前に間・テーマの語・数字・本編の後ろ寄り（見本も山場は本編の 4〜9 割の所）"""
    t = TX(L[i]); sc = 0.0
    if roles[i] in ('結論', '言い切り'): sc += 3
    if i in answers: sc += 2
    if (i - 1) in ma_after: sc += 2
    if re.search(r'^(結論|つまり|実は|じつは|ポイントは|大事なのは|重要なのは|答えは|正解は|一番)', t): sc += 2
    sc += sum(1 for k in kw_of[i] if k in promise_kw)
    if number_of(t): sc += 1
    pos = (honpen.index(i) + 0.5) / max(1, len(honpen)) if i in honpen else 0
    sc += 1.5 if 0.35 <= pos <= 0.9 else -2
    return sc


climax = max(honpen, key=lambda i: (climax_score(i), -abs(((honpen.index(i) + 0.5) / len(honpen)) - 0.65)))
if SH.get('climax'): climax = next(i for i in range(n_lines) if L[i]['n'] == SH['climax'])

# 流れ：区間の変わり目で切る。本編は 問題提起 → 本編の展開 → 山場 → まとめ に山場の位置で分ける
segs = []
for i, s in enumerate(secs):
    if not segs or s != segs[-1]['s']: segs.append({'s': s, 'ids': [i]})
    else: segs[-1]['ids'].append(i)
flow_parts = []
NAME = {'hook': 'フック・つかみ', 'kokuchi': '告知', 'shime': 'まとめ・CTA'}
AIM = {'hook': '「自分のことだ」と止まらせ、最後まで見る理由（約束）を渡す', 'kokuchi': '空気を変え、最後まで見る理由（特典）を作る',
       'shime': '要点を1つ持ち帰らせ、行動を1つに絞る'}
ENUM = re.compile(r'^(まず|次に|続いて|最後に|そして最後|[一二三四五1-9１-９](つ目|個目|番目)|ポイント[一二三1-9１-９]|ステップ[一二三1-9１-９])')


def topic_split(ids, min_s):
    """本編を話の切れ目（まず／次に／2つ目…）で分ける。短すぎる区切りは作らない"""
    parts, cur = [], []
    for i in ids:
        if cur and ENUM.search(TX(L[i])) and (L[i]['start'] - L[cur[0]]['start']) >= min_s:
            parts.append(cur); cur = []
        cur.append(i)
    if cur: parts.append(cur)
    return parts


for sg in segs:
    ids = sg['ids']
    if sg['s'] != 'honpen':
        flow_parts.append((NAME[sg['s']], AIM[sg['s']], ids)); continue
    if climax in ids:
        c = ids.index(climax); pre = ids[:max(0, c - 1)]; peak = ids[max(0, c - 1):c + 2]; post = ids[c + 2:]
        k1 = max(1, len(pre) // 4) if pre else 0
        parts = [('問題提起', '問題を自分のことにさせ、答えを待たせる', pre[:k1])]
        for k, part in enumerate(topic_split(pre[k1:], 0.08 * D)):
            parts.append(('本編の展開%d' % (k + 1), '答えと理由を言った順に足して腹落ちさせ、山場へ上げていく', part))
        parts.append(('山場', '約束「%s」への答えを一番強く刻む' % short(TX(L[prom_i]), 20), peak))
        for k, part in enumerate(topic_split(post, 0.08 * D)):
            parts.append(('本編のまとめ%d' % (k + 1) if k else '本編のまとめ', '山場の答えを分解して持ち帰らせる', part))
        for name, aim, part in parts:
            if part: flow_parts.append((name, aim, part))
    else:
        for k, part in enumerate(topic_split(ids, 0.08 * D)):
            flow_parts.append(('本編%d' % (k + 1), '言った順に足して理解させる', part))
# 区間を見本の粒にそろえる（観点10：見本は1本7〜11区間・1区間 中央約80秒）。短すぎる本編の区切りは前の区切りへまとめる（山場・告知・フック・まとめは残す）
KEEP = ('フック', '告知', 'まとめ・CTA', '山場')
def _len(ids): return (st_all[ids[-1] + 1] if ids[-1] + 1 < n_lines else D) - st_all[ids[0]]
st_all = [x['start'] for x in L]
merged = []
for name, aim, ids in flow_parts:
    if merged and name.split('・')[0] not in KEEP and merged[-1][0].split('・')[0] not in KEEP and (_len(ids) < 0.06 * D or _len(merged[-1][2]) < 0.06 * D):
        merged[-1] = (merged[-1][0], merged[-1][1], merged[-1][2] + ids)
    else: merged.append((name, aim, ids))
while len(merged) > max(7, round(D / 70)):
    cand = [k for k in range(1, len(merged)) if merged[k][0].split('・')[0] not in KEEP and merged[k - 1][0].split('・')[0] not in KEEP]
    if not cand: break
    k = min(cand, key=lambda k: _len(merged[k][2]) + _len(merged[k - 1][2]))
    merged[k - 1] = (merged[k - 1][0], merged[k - 1][1], merged[k - 1][2] + merged[k][2]); del merged[k]
flow_parts = merged
if SH.get('flow'):   # 作業AIが決めた流れ（行の番号で区切る）
    flow_parts = [(f['name'], f['aim'], [i for i in range(n_lines) if f['from'] <= L[i]['n'] <= f['to']]) for f in SH['flow']]
flow_of = {}
for fi, (name, aim, ids) in enumerate(flow_parts):
    for i in ids: flow_of[i] = (fi, name)

# 場面の役割を見本（per_full）の言葉で決める（観点：信頼・感情・呼びかけ・章立ては この言葉で数える）
MR = [('CTA', r'概要欄|LINE|ライン登録|チャンネル登録|高評価|コメント(して|ください|で)|申し込|お申込|参加して|受け取って|登録して|ぜひ.*(見て|やって|して)'),
      ('限定・希少', r'限定|先着|今だけ|締め切り|残り\d|期間|一度きり|終了'),
      ('権威・実績', r'(受講生|実績|月商|年商|万再生|登録者|達成|稼い|稼げ|売れた|売り上げた|立ち上げ(た|てき)|指導して|コンサルして)'),
      ('煽り・損失回避', r'損|危な|やば|ヤバ|消え|終わ|失敗|もったいない|手遅れ|置いていかれ|取り残'),
      ('否定・常識破り', r'実は|じつは|逆に|ではなく|じゃなくて|勘違い|間違|常識|嘘|意外'),
      ('手順', r'まず|次に|ステップ|手順|やり方|方法は|[一二三四五1-9１-９](つ目|番目)'),
      ('比較', r'比べ|違い|よりも|に対して|一方で|vs|VS'),
      ('共感', r'ありますよね|悩み|困って|分かります|わかります|不安|迷って'),
      ('理由', r'なぜなら|なんでかって|理由は|だからこそ'),
      ('まとめ', r'まとめ|つまり|結局|要するに|ということで'),
      ('具体例', r'例えば|たとえば|実際に|事例')]
def mrole(i):
    o = (SH.get('lines') or {}).get(str(L[i]['n'])) or {}
    if o.get('role'): return o['role']
    t = TX(L[i]); r = roles[i]; s_ = secs[i]
    if s_ == 'kokuchi': return '告知・宣伝'
    if r == '行動': return 'CTA'
    if r == 'つかみ' or (s_ == 'hook' and i == hook_idx[0]): return 'フック'
    if s_ == 'hook' and (r in ('結論', '言い切り', '数字') or re.search(r'(です|ます|んです|だ)。?$', t)): return '結論の先出し'
    if i == climax: return '結論'
    if r == '問い': return '問題提起'
    for name, pat in MR:
        if re.search(pat, t): return name
    if r == '数字': return '権威・実績' if re.search(r'人|件|円|再生|万|億', t) else '具体例'
    if r in ('結論', '言い切り') or i in answers: return '結論の先出し'
    if r == '具体例': return '具体例'
    if r == '理由': return '理由'
    if len(N(t)) <= 12 or TSUNAGI.match(t): return '場面つなぎ'
    return '結論の先出し' if re.search(r'(です|ます|んです|だ)。?$', t) else '具体例'

# ======================================================================
# 段2 一文ごとに、前後のつながりと流れの中の区間を理由にして決める
# ======================================================================
shown_recent = []          # 直前2場面で画面に出した語（同じ語を重ねて出さない）


def decide(i):
    """→ dict(kind, shown, dropped, added, why, visual, emphasis, ma, cut, link)"""
    x = L[i]; t = TX(x); s = secs[i]; role = roles[i]; cs = chunks(t); n = len(N(t))
    prv = TX(L[i - 1]) if i > 0 else ''; nxt = TX(L[i + 1]) if i + 1 < n_lines else ''
    fi, fname = flow_of.get(i, (0, ''))
    first_of_flow = i == 0 or flow_of.get(i - 1, (None,))[0] != fi
    def dropped(shown):
        rest = t
        for sh in shown: rest = rest.replace(sh.rstrip('？?'), '｜')
        return [w.strip('、。') for w in rest.split('｜') if len(N(w)) >= 2][:6]
    # 切り替え：流れの区間が変わる所は場面転換、前の文の続き（で、/だから…）は続ける
    if first_of_flow and i > 0:
        cut = '場面転換'; cut_why = '流れが「%s」→「%s」に変わる。地と見た目を変えて区切りを見せる' % (flow_of[i - 1][1], fname)
    elif CONT.match(t) and i > 0:
        cut = '続ける'; cut_why = '前の文「%s」の続き。地を変えず文字だけ入れ替え、話の勢いを切らない' % short(prv, 14)
    else:
        cut = '切り替え'; cut_why = '新しい文。同じ地のまま場面を替える'
    ma = '後ろに間（次の「%s」を待たせる）' % short(nxt, 14) if i in ma_after else ''
    D_ = dict(cut=cut, ma=ma, flow=fname)
    def out(kind, shown, why, visual, emphasis='なし', added=(), link=''):
        shown = [x for x in shown if N(x)]   # 空の文字は出さない（句点だけの文など）
        if not shown and kind not in ('出さない', '足す'): kind, visual = '出さない', '絵だけ（人物）'
        return dict(D_, kind=kind, shown=list(shown), dropped=dropped(shown) if kind not in ('出さない', '足す') else [t], added=list(added),
                    why=why, visual=visual, emphasis=emphasis, link=(link + '／' if link else '') + cut_why)
    if s == 'kokuchi' and i == kok[0]:
        return out('足す', ['重大告知'], '本編と空気を変え、大事な知らせとして独立させる（台本に無い見出しを足す）', '告知', '強', ['重大告知'],
                   '前の「%s」で本編へ入る直前に割り込む' % short(prv, 12))
    if role == '行動':
        sh = cs[:3]
        return out('全文' if n <= 40 else '要約', sh, '行動は一字落とすと迷う。何をするかをそのまま出す', '行動の画面', '強',
                   link='流れの締めの行動（%s）' % fname)
    if i == climax:
        core = cs[-1] if len(cs) > 1 else cs[0]
        return out('全文' if N(core) == N(t) else '要約', [core], '1本の山場。約束「%s」への答えなので、芯の1行だけを一番強く出す' % short(TX(L[prom_i]), 16),
                   '文字（赤の極太）', '強', link=('前の間で待たせた答え' if (i - 1) in ma_after else '前の「%s」から上げてきた答え' % short(prv, 12)))
    if role == '問い' and (i + 1) in answers:
        q = short_q(t)
        return out('全文' if N(q) == N(t) else '言い換え', [q], '次の行「%s」で答えるので、ここは問いだけ短く出して答えを待たせる' % short(nxt, 14),
                   '人物（考える人）', '中', link='次の答えへ渡す問い')
    if i in answers:
        big = number_of(t) or (kw_of[i][0] if kw_of[i] else (cs[-1] if cs else t))
        return out('キーワード' if N(big) != N(t) else '全文', [big], '前の問い「%s」への答え。答えの芯だけを強く出す' % short(prv, 14),
                   '文字（金の数字）' if number_of(t) else '文字（赤の極太）', '強', link='前の問いの答え')
    if role == '数字':
        big = number_of(t) or cs[-1]; ctx = next((c for c in cs if big not in c), '')[:14]
        core = iikae(next((c for c in cs if big in c), big))
        sh = ([iikae(ctx)] if ctx and len(N(core)) <= 6 else []) + [core if len(N(core)) <= 16 else big]
        kind = 'キーワード' if sh == [big] else ('言い換え' if any(N(x) not in N(t) for x in sh) else '要約')
        return out(kind, sh, '数字を含む芯を見出し語に直して大きく見せ、残りは声に任せる（目は数字に止まる）', '文字（金の数字）', '強',
                   link='%sの根拠' % ('前の「%s」' % short(prv, 12) if prv else '冒頭の約束'))
    if role == '問い':
        q = short_q(t)
        return out('全文' if N(q) == N(t) else '言い換え', [q], '問いは短く言い換えて座布団に乗せ、見る人に答えを考えさせる', '人物（考える人）', '中',
                   link='答えは後ろ（%s）で出る' % fname)
    rep = kw_of[i] and all(k in shown_recent for k in kw_of[i]) and not number_of(t)
    if role != 'つかみ' and rep:
        return out('出さない', [], '前の場面で出した「%s」の繰り返し。文字を重ねず絵で受ける' % '・'.join(kw_of[i]), '絵だけ（人物）',
                   link='前の「%s」の言い直し' % short(prv, 12))
    if role != 'つかみ' and (n <= 12 or (TSUNAGI.match(t) and not kw_of[i] and n <= 22)):
        return out('出さない', [], 'つなぎの文。文字を足すと声の勢いが落ちるので、絵だけで受ける', '絵だけ（人物）',
                   link='次の「%s」へ渡すつなぎ' % short(nxt, 12))
    if role in ('言い切り', '結論'):
        sh = cs[-1:] if len(cs) > 1 else cs
        return out('全文' if len(cs) == 1 and n <= 18 else '要約', sh, '言い切りの芯だけを赤の極太で出し、前置きは声に任せる', '文字（赤の極太）', '中',
                   link='%sの中の言い切り' % fname)
    new_theme = [k for k in kw_of[i] if k in theme and first_seen.get(k) == i]
    if new_theme:
        return out('キーワード', new_theme[:1] + [k for k in kw_of[i] if k not in new_theme][:1], 'この1本のテーマの語「%s」が初めて出る所。語だけを大きく出して覚えさせる' % new_theme[0],
                   '文字（キーワード）', '強', link='後ろで何度も出る語の初出')
    if ZUKAI.search(t):
        sh = cs[:3] if n > 20 else cs
        return out('要約', [c[:16] for c in sh], '並び・手順・式・比べる話は、言葉を図に置いて目で追わせる（図解）', '図解', link='%sで並べて見せる所' % fname)
    if GAMEN.search(t):
        sh = (kw_of[i][:1] or [cs[0][:14]])
        return out('キーワード', sh, '実物（画面・ツール・実績）の話は、文字より実物を見せて信じさせる（写真・画面）', '写真・画面', link='%sの実物' % fname)
    if role == '具体例':
        sh = [iikae(c) for c in (cs[-1:] if cs else [t[:14]])]
        return out('言い換え' if N(sh[0]) not in N(t) else '要約', sh, '具体例は人物の絵で場面を浮かばせ、芯の1行だけ口語を見出し語に直して出す', '絵・人物', link='前の「%s」の具体例' % short(prv, 12))
    if re.search(r'(ありますよね|悩み|困って|迷って|不安)', t) and n <= 40:
        q = as_question(cs[-1] if cs else t)
        return out('言い換え', [q], '見る人の悩みを問いの形にして、自分のことだと思わせる（共感）', '人物（考える人）', '中', link='%sの共感' % fname)
    kw = kw_of[i]
    core = [c for c in cs if any(k in c for k in kw)][:1] or cs[-1:]
    if n > 28 and core and len(N(core[0])) <= 18:
        r_ = [iikae(core[0])]
        return out('言い換え' if N(r_[0]) != N(core[0]) else '要約', r_, '長い説明は耳に任せ、覚えてほしい芯の1行だけを言い切りに直して出す', '文字', link='%sの説明' % fname)
    if n > 28 and kw:
        return out('キーワード', kw, '長い説明は覚えてほしい語だけ出し、声に集中させる', '文字（キーワード）', link='%sの説明' % fname)
    sh = [iikae(c) for c in (cs[:2] if n > 20 else cs)]
    kind = '全文' if N(''.join(sh)) == N(t) else ('要約' if all(N(c) in N(t) for c in sh) else '言い換え')
    return out(kind, sh, '短い文なのでそのまま出す' if kind == '全文' else '耳で分かる所を落とし、意味の芯だけを2行で出す', '文字',
               link='%sの説明' % fname)


plans = []; run = 0
OV = SH.get('lines') or {}
for i, x in enumerate(L):
    d = decide(i)
    if d['kind'] == '全文':
        n_full = sum(1 for p in plans if p['kind'] == '全文')
        if (run >= TS['full_run_max'] or (n_full + 1) / max(1, n_lines) > TS['full_share_max']) and d['emphasis'] != '強' or run >= TS['full_run_max']:
            sh = d['shown']
            if len(sh) > 1: d['shown'] = sh[-1:]; d['kind'] = '要約'
            elif kw_of[i]: d['shown'] = kw_of[i]; d['kind'] = 'キーワード'
            else: d['shown'] = [chunks(TX(x), 10)[0]]; d['kind'] = '要約'
            d['why'] += '（全文が続いた・多いので短くした）'
            d['dropped'] = [w for w in re.split(r'[、。]', TX(x)) if w and not any(w in q for q in d['shown'])][:6]
    o = OV.get(str(x['n'])) or {}
    for k_ in ('kind', 'shown', 'visual', 'emphasis', 'cut', 'why', 'added', 'ma'):
        if k_ in o: d[k_] = o[k_]
    if 'shown' in o and d['kind'] not in ('出さない', '足す'):
        d['dropped'] = [w for w in re.split(r'[、。]', TX(x)) if N(w) and not any(N(w) in N(q) for q in d['shown'])][:6]
    if o: d['link'] = (o.get('link') or d['link'])
    run = run + 1 if d['kind'] == '全文' else 0
    plans.append(d)
    shown_recent = (shown_recent + [k for k in kw_of[i] if any(k in sh for sh in d['shown'])])[-6:]

# ---- 1本の流れ（video_marketing.json）：段1で読んだものから書く（作業AIが仕上げる・質の門⑫）
vp = os.path.join(P, 'video_marketing.json')
st = [x['start'] for x in L] + [D]
flow = []
for name, aim, ids in flow_parts:
    used = Counter(plans[j]['visual'] for j in ids)
    flow.append({'t0': round(st[ids[0]], 2), 't1': round(st[ids[-1] + 1], 2), 'name': name, 'aim': aim,
                 'devices': '・'.join('%s %d場面' % (k_, v) for k_, v in used.most_common()) + '／強調 %d・間 %d' % (
                     sum(1 for j in ids if plans[j]['emphasis'] == '強'), sum(1 for j in ids if plans[j]['ma'])),
                 'lines': [L[j]['n'] for j in ids]})
ret = []
for i, x in enumerate(L):
    if roles[i] == '問い' and (i + 1) in answers: ret.append({'t': round(x['start'], 2), 'what': '問い「%s」→ 次の行で答え。答えを待たせて離脱を止める' % short(TX(x), 18)})
    elif i in ma_after: ret.append({'t': round(x['start'], 2), 'what': '%d行目の後ろに間を残し、次の「%s」を待たせる' % (x['n'], short(TX(L[i + 1]) if i + 1 < n_lines else '', 14))})
    elif re.search(r'(最後に|あとで|後ほど|このあと|動画の最後)', TX(x)): ret.append({'t': round(x['start'], 2), 'what': '予告「%s」で最後まで見る理由を作る' % short(TX(x), 18)})
for a, b in zip(flow, flow[1:]):
    ret.append({'t': b['t0'], 'what': '流れの変わり目（%s→%s）で地と見た目を変え、テンポを切り替える' % (a['name'], b['name'])})
ret = sorted(ret, key=lambda z: z['t'])[:10]
cta = {'what': short(TX(L[acts[-1]]), 40) if acts else '（台本に行動の呼びかけが無い→作業AIが締めで何をさせるかを決める）', 'where': [round(L[i]['start'], 2) for i in acts],
       'count': len(acts), 'how': '行動の画面（LINEのロゴ＋白の光る文字・ピコン）で、することを1つだけ全文で出す'}
if not acts and n_lines: cta['where'] = [round(L[-1]['start'], 2)]
nums = [i for i in range(n_lines) if roles[i] == '数字' and L[i]['start'] < 30]
h0 = nums[0] if nums else 0
why = [{'h': '冒頭%sで「%s」を見せ、最初の数秒で見る理由を渡している' % ('の数字' if nums else 'のつかみ', short(TX(L[h0]), 20)), 'evidence_t': round(L[h0]['start'], 2)},
       {'h': '山場「%s」の前に%sを置き、答えを一番強く刻んでいる' % (short(TX(L[climax]), 18), '間' if (climax - 1) in ma_after else '問いと理由'), 'evidence_t': round(L[climax]['start'], 2)}]
qs = [i for i in range(n_lines) if roles[i] == '問い']
if qs: why.append({'h': '問い「%s」で見る人を自分ごとにし、答えまで離脱させない' % short(TX(L[qs[0]]), 18), 'evidence_t': round(L[qs[0]]['start'], 2)})
if kok: why.append({'h': '告知を本編の前に独立させ、最後まで見る理由（特典）を先に渡している', 'evidence_t': round(L[kok[0]]['start'], 2)})
if acts: why.append({'h': '締めで行動を1つ（%s）に絞り、迷わせない' % short(TX(L[acts[-1]]), 16), 'evidence_t': round(L[acts[-1]]['start'], 2)})
reu = ['冒頭は数字か問いで見る理由を先に渡す（金の極太・紺の座布団）', '山場の前に間か問いを置き、答えの芯だけを赤の極太で出す',
       'つなぎ・言い直しの文は文字を出さず絵だけで受け、声の勢いを落とさない', 'テーマの語は初めて出た所でだけ大きく出し、繰り返しでは重ねない']
if kok: reu.append('告知は暗い地に切り替えて「重大告知」を足し、本編と独立させる')
elif acts: reu.append('行動の呼びかけだけは全文で出し、することを1つに絞る')
VM = {'by': '作業AIの推定（台本と声の全体を先に読んで書いた・draft.py の下書き）。作業AIが流れを見て仕上げる',
      'target': '%sに関心があり、%s人' % ('・'.join('「%s」' % k_ for k_ in theme) or 'この話題', short(TX(L[hook_idx[0]]), 30).rstrip('。') + 'と感じている'),
      'promise': short(TX(L[prom_i]), 60),
      'hook': {'t0': 0.0, 't1': round(min(10.0, st[min(2, n_lines)]), 2), 'what': '冒頭「%s」（%s）で止める' % (short(TX(L[hook_idx[0]]), 24), roles[hook_idx[0]])},
      'flow': flow,
      'climax': {'t': round(L[climax]['start'], 2), 'line': L[climax]['n'], 'what': short(TX(L[climax]), 40),
                 'why': '約束「%s」への答え（山場らしさ %.1f：結論・前の間・テーマの語・本編の後ろ寄り）' % (short(TX(L[prom_i]), 16), climax_score(climax))},
      'retention': ret, 'cta': cta, 'why_it_works': why[:4], 'reusable': reu[:5], 'theme_words': theme}
if not os.path.exists(vp):
    json.dump(VM, open(vp, 'w'), ensure_ascii=False, indent=1)
else:
    VM = json.load(open(vp))     # 作業AIが仕上げた流れがあればそちらに合わせる（上書きしない）

# ---- 場面表（story.py）の下書き
JIN = ['hito_hatena_kiiro', 'hito_kangaeru', 'hito_pc_komaru', 'hito_suit_yubi', 'hito_pc_otoko', 'hito_banzai']
TRANS = {'場面転換': 0.32, '切り替え': 0.22, '続ける': 0.1}


def anchor(piece, x):
    """出す文字の秒：台本にその言葉があればその言葉の話し始め。言い換え・要約の字は、その中身が声で言われる所（CK.kw）。重ならなければ行の頭"""
    p = N(piece)[:4]
    if p and p in N(x['text']): return "at(%r, %d)" % (p, x['n'])
    return "CK.kw(%r, %d, t)" % (piece, x['n'])


lines = []; ji = 0
for i, (x, d) in enumerate(zip(L, plans)):
    n = x['n']; t = TX(x); s = secs[i]; role = roles[i]; k = d['kind']; sh = d['shown']; emp = d['emphasis']
    bg = {'hook': 'NET', 'kokuchi': 'DARK', 'honpen': 'None', 'shime': 'WINE'}[s]
    ring = 'False' if s != 'honpen' else 'True'
    dark = s != 'honpen'; tx = 'white_glow' if dark else 't_plain'
    L2 = ["# ---- %d行目［%s・%s・%s・強調%s・%s%s］%s" % (n, d['flow'], role, k, emp, d['cut'], '・間' if d['ma'] else '', t), "t = line(%d)" % n,
          ("intent(t, %r, %r, %r, %r)" % (mrole(i), OV[str(n)].get('intent') or x.get('intent') or 'TODO 訴求', OV[str(n)].get('edit') or '%s・%s' % (k, d['visual']), d['why'])
           if str(n) in OV else "intent(t, %r, %r, 'TODO 作業AIが仕上げる（下書き：%s・%s）', %r)" % (mrole(i), x.get('intent') or 'TODO 訴求', k, d['visual'], d['link'])),
          "sel(t, %r, %r, %r, %r, %r, %r, emphasis=%r, ma=%r, cut=%r, link=%r, flow=%r)" % (k, sh, d['dropped'], d['added'], d['why'], d['visual'], emp, d['ma'], d['cut'], d['link'], d['flow']),
          "E = []" + (" + [lbl(t)]" if s == 'honpen' else '')]
    if k == '足す':
        L2.append("E.append(R(t, kit.neon('重大告知', 400), W // 2, H // 2, 'cc', 'slam', dur=0.3, s='kokuchi'))")
    elif k == '出さない':
        L2.append("E.append(R(t, jin(%r, h=620), W // 2, 600, 'cc', 'up', s='pon'))" % JIN[ji % len(JIN)]); ji += 1
    elif role == '行動':
        L2.append("E.append(R(t, kit.logo_line(150), 170, 260, 'cc', 'pop'))")
        L2.append("E.append(R(t, kit.white_glow(%r, 110), 620, 560, 'cc', 'blur', dur=0.3, s='cta'))" % '\n'.join(sh))
    elif k in ('言い換え',) or (role == '問い' and k != 'キーワード'):
        # 人物は横幅760までに収め、文字は人物より上に重ねる（横に広い絵で文字が隠れていた・10/16）
        L2.append("E.append(R(%s, kit.navy(%r, 104), 760, 520, 'cc', 'pop', z=2, s='telop'))" % (anchor(sh[0], x), '\n'.join(chunks(sh[0], 12))))
        L2.append("E.append(R(t + 0.15, jin(%r, h=560, w=760), 1500, 620, 'cc', 'up', s='pon'))" % JIN[ji % len(JIN)]); ji += 1
    elif d['visual'].startswith('文字（金'):
        if len(sh) > 1: L2.append("E.append(R(%s, kit.%s(%r, 100), W // 2, 300, 'cc', 'wipe', dur=0.35, s='telop'))" % (anchor(sh[0], x), tx, sh[0]))
        L2.append("E.append(R(%s, kit.t_gold(%r, 200), W // 2, 640, 'cc', 'wipeblur', dur=0.45, s='kira'))" % (anchor(sh[-1], x), sh[-1]))
    elif d['visual'].startswith('文字（赤'):
        L2.append("E.append(R(%s, kit.t_red_italic(%r, %d), W // 2, 560, 'cc', 'slam', dur=0.28, s='don'))" % (anchor(sh[-1], x), sh[-1], 170 if i == climax else 150))
    elif k == 'キーワード':
        # 3つまでは縦に1列（420・650・880）。4つ以上は2列に並べて画面の縦（1080）に収める（縦1列のままだと4つ目から画面の外に出ていた）
        rows = (len(sh) + 1) // 2 if len(sh) > 3 else len(sh)
        for j, c in enumerate(sh):
            if len(sh) > 3: px, py, fs = ('W // 2 - 430', 'W // 2 + 430')[j % 2], 300 + (j // 2) * min(230, 600 // max(1, rows - 1)), 110
            else: px, py, fs = 'W // 2', 420 + j * 230, 150 if j == 0 else 120
            L2.append("E.append(R(%s, kit.%s(%r, %d), %s, %d, 'cc', 'wipeblur', dur=0.4%s))" % (anchor(c, x), 't_blue_big' if not dark else tx, c, fs, px, py, ", s='kira_hi'" if j == 0 and emp == '強' else (", s='telop'" if j == 0 else '')))
    else:
        for j, c in enumerate(sh[:3]):
            L2.append("E.append(R(%s, kit.%s(%r, 100), W // 2, %d, 'cc', 'wipe', dur=0.35%s))" % (anchor(c, x), tx, c, 330 + j * 170, ", s='telop'" if j == 0 else ''))
    L2.append("add(Sc(t, 0, E, bg=%s, ring=%s, trans=%s))" % (bg, ring, TRANS[d['cut']]))
    lines.append('\n'.join(L2))
head = '''#!/usr/bin/env python3
# 場面表の下書き（draft.py が台本と声の全体を先に読み、1本の流れ video_marketing.json を書いてから作った）。
# TODO の所を作業AIが訴求と流れに合わせて仕上げる。行ごとの sel(...) は「テロップに出す／出さない／言い換える／足す」と強調・間・切り替え、
# その理由（why）と前後のつながり（link）。変えたら理由も直す
import os, sys
PROJ = os.environ.get('PROJ') or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
from henshu import *
CK = Clock(PROJ); line, at, end_of = CK.line, CK.at, CK.end_of
END = CK.END + 0.3
NET = network_bg(); WINE = wine_bg()
def lbl(t0): return label(%r, t0)
''' % title
kokn = [L[i]['n'] for i in kok]; shin = [L[i]['n'] for i, s in enumerate(secs) if s == 'shime']
after = [L[i]['n'] for i in range(n_lines) if kok and i > kok[-1]]
tail = '''
finish(END)
BGM = %s
SFX_SPARSE = []
if __name__ == '__main__':
    dump_meta(PROJ, END, BGM, SFX_SPARSE); print(len(SCENES), 'scenes', len(SFX), 'sfx', 'END %%.2f' %% END)
''' % ('[' + ', '.join(filter(None, [
    # 告知のかたまりごとに曲を入れる（本編の前と最後に告知がある本は2回。かたまりの次の行の頭で切る・最後のかたまりは END まで）
    *[("(line(%d, -0.15), %s, 'bgm/kokuchi.wav', 0.0, -19.0)" % (L[a_]['n'], ("line(%d, -0.2)" % L[b_ + 1]['n']) if b_ + 1 < n_lines else 'END'))
      for a_, b_ in [(r[0], r[-1]) for r in [[j for j in kok if j >= k0 and all(m in kok for m in range(k0, j + 1))] for k0 in kok if k0 - 1 not in kok]]],
    ("(line(%d, -0.2), END, 'bgm/kokuchi.wav', 6.0, -20.0)" % shin[0]) if shin and not (kok and kok[-1] == n_lines - 1) else ''])) + ']')
sp = os.path.join(P, 'story.py')
open(sp, 'w').write(head + '\n\n'.join(lines) + tail)
json.dump({'theme': theme, 'climax_line': L[climax]['n'], 'flow': [(a, [L[j]['n'] for j in c]) for a, _, c in flow_parts], 'plans': plans},
          open(os.path.join(P, 'work', 'draft_plan.json'), 'w'), ensure_ascii=False, indent=1)
print(sp, n_lines, '行', '山場', L[climax]['n'], '行目', 'テーマ', theme, '選び方', dict(Counter(p['kind'] for p in plans)), '強調', dict(Counter(p['emphasis'] for p in plans)))
