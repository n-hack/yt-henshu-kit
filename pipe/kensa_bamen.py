#!/usr/bin/env python3
# 場面表の検査（yt-henshu-pipe・10/19）：書き出す前に、章ごとに直すべき所を機械で数える
#   ① 重なり：同じ画面に並ぶ部品どうしが重なる（小さい方の面積の5%超）。暗い幕（over）の下に沈んだ部品は除く
#   ② 字幕帯へのはみ出し：部品の下の端が y 960 を超える（字幕は y 970〜1066 に自動で出る）
#   ③ 間の空き：新しく動く部品が5秒以上無い所／4秒以上ある行に、その行の言葉で出る部品が1つも無い
#   ④ 帯と字幕の食い違い：画面の字が字幕の言葉とほぼ同じ（8割以上一致）なのに1字でも違う（v12 の 599秒「最後まで／ここまで」）
#   ⑤ 動画全体の種類：挿絵・イラスト・図解・全画面挿絵・実際の画面が各1回以上（門のルール7）
#   出力 work/bamen/kensa.json＝{"ch": {章: [直す所の文]}, "zentai": [...], "kazu": {...}}
#   python3 kensa_bamen.py <作業フォルダ>
import os, sys, json, re, difflib
P = os.path.abspath(sys.argv[1]); os.environ['PROJ'] = P
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
import render
S = render.load_story(P)
import henshu as H
W_, H_ = 1920, 1080
N = lambda s: re.sub(r'<[^>]+>|[、。「」『』！？!?,.\s・…（）()【】\n]', '', s or '').lower()
iss = {}
def put(ch, msg): iss.setdefault(ch or '?', []).append(msg)
def box(e):
    w, h = e._src.width, e._src.height
    x, y = (e.x - w / 2, e.y - h / 2) if e.anchor == 'cc' else (e.x, e.y)
    return x, y, x + w, y + h
seen_ov = set(); seen_band = set()
for sc in H.SCENES:
    els = [e for e in sc.elems if hasattr(e, '_src')]
    # 暗い幕（画面と同じ大きさ）より前の部品は沈んでいるので数えない。章札（左上）も除く
    k0 = 0
    for i, e in enumerate(els):
        if e._src.width >= W_ and e._src.height >= H_: k0 = i + 1
    live = [e for e in els[k0:] if not (e.anchor == 'lt' and e.x == 0 and e.y == 0) and not (e._src.width >= W_ and e._src.height >= H_)]
    for i, a in enumerate(live):
        ba = box(a)
        if a.anim != 'none' and ba[3] > 960 and id(a._src) not in seen_band:
            seen_band.add(id(a._src)); put(getattr(a, 'pipe_ch', ''), '%.1f秒「%s」の下の端が y %d（字幕帯 y 970〜にかかる。y 950 より上へ）' % (a.t_plan if hasattr(a, 't_plan') else sc.t0, (a._src.info.get('pipe_text') or a._src.info.get('pipe_name') or '部品')[:16], ba[3]))
        for b in live[i + 1:]:
            if a.anim == 'none' and b.anim == 'none': continue   # 前の画面で数え済み
            if (a._src.info or {}).get('pipe_kasane') or (b._src.info or {}).get('pipe_kasane'): continue   # v14：丸で囲む・下線は重ねる部品
            bb = box(b)
            ix = max(0, min(ba[2], bb[2]) - max(ba[0], bb[0])); iy = max(0, min(ba[3], bb[3]) - max(ba[1], bb[1]))
            sm = min((ba[2] - ba[0]) * (ba[3] - ba[1]), (bb[2] - bb[0]) * (bb[3] - bb[1]))
            if sm > 0 and ix * iy / sm > 0.05:   # 15% では別の目が「重なって読めない」と言った3件を拾えなかった（10/19 試し1回目）→ 5%
                key = (id(a._src), id(b._src))
                if key in seen_ov: continue
                seen_ov.add(key)
                nm = lambda e: (e._src.info.get('pipe_text') or e._src.info.get('pipe_name') or '部品')[:14]
                put(getattr(b, 'pipe_ch', '') or getattr(a, 'pipe_ch', ''), '%.1f秒「%s」(中心 %d,%d) と「%s」(中心 %d,%d) が %d%% 重なる（位置をずらすか新しい Stack に）' % (
                    getattr(b, 't_plan', sc.t0), nm(a), (ba[0] + ba[2]) / 2, (ba[1] + ba[3]) / 2, nm(b), (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, 100 * ix * iy / sm))
mov = sorted([(getattr(e, 't_plan', 0), getattr(e, 'pipe_ch', '')) for e in H.ELEMS if e.anim != 'none'])
for (t0, c0), (t1, c1) in zip(mov, mov[1:]):
    if t1 - t0 > 5.0: put(c1 or c0, '%.1f〜%.1f秒 の %.1f 秒、新しい部品が出ない（その間の言葉で1〜2個足す）' % (t0, t1, t1 - t0))
J = json.load(open(os.path.join(P, 'work', 'timing_fa.json')))
ts = [t for t, c in mov]
import bisect
for ln in J['lines']:
    a, b = ln['start'], ln['end']
    if b - a >= 4.0:
        i = bisect.bisect_left(ts, a - 0.05); j = bisect.bisect_right(ts, b)
        if j - i == 0:
            ch = next((c for t, c in mov if t >= a), '')
            put(ch, '%d行目（%.1f〜%.1f秒「%s」）に、その行の言葉で出る部品が無い' % (ln['n'], a, b, ln['text'][:20]))
# ④ 帯と字幕の食い違い
import ki1
JM = ki1.JIMAKU
for e in H.ELEMS:
    if e.anim == 'none': continue
    tx = N(e._src.info.get('pipe_text', ''))
    if len(tx) < 6: continue
    t = getattr(e, 't_plan', 0)
    win = N(''.join(s for a, b, s in JM if t - 6 <= a <= t + 6))
    if not win: continue
    m = difflib.SequenceMatcher(None, tx, win, autojunk=False)
    blocks = m.get_matching_blocks(); same = sum(b.size for b in blocks)
    if same / len(tx) >= 0.8 and same < len(tx):
        # 字幕の中の対応する所を取り出す
        a0 = min(b.b for b in blocks if b.size); a1 = max(b.b + b.size for b in blocks if b.size)
        put(getattr(e, 'pipe_ch', ''), '%.1f秒 画面の字「%s」が字幕「%s」と1〜2字だけ違う（字幕と同じ言葉にそろえる）' % (t, e._src.info.get('pipe_text', '')[:30], win[a0:a1][:30]))
# ⑤ 種類
U = json.load(open(os.path.join(P, 'work', 'sozai_used.json')))
from collections import Counter
cnt = Counter(u['shurui'] for u in U)
zentai = ['%s が動画全体で0回（どこかの章で1回以上使う）' % k for k in ('挿絵', 'イラスト', '図解', '全画面挿絵', '実際の画面') if not cnt.get(k)]
dur = S.END
# ⑥ v13 の決まり（手本の作者さん15本対v12 10/19）：動く部品 1分18〜22（章ごとに 15〜25 を外れたら直させる）・切り替え6種類・動く切り替え 場面の6〜11%・字だけ差し替え 5〜10%・出方の配分
MOVE_PM = 34
PL = json.load(open(os.path.join(P, 'work', 'bamen', 'plan.json')))['chapters'] if os.path.exists(os.path.join(P, 'work', 'bamen', 'plan.json')) else []
stt = {ln['n']: ln['start'] for ln in J['lines']}; ent = {ln['n']: ln['end'] for ln in J['lines']}
KV = json.load(open(os.path.join(P, 'work', 'kata_v13.json'))) if os.path.exists(os.path.join(P, 'work', 'kata_v13.json')) else {'kirikae': [], 'dekata_ato': {}}
TRL = KV['kirikae']; trc = Counter(x['kind'] for x in TRL); ntr = max(1, len(TRL))
for c in PL:
    a0, b0 = stt[int(c['a'])], ent[int(c['b'])]; span = max(1.0, b0 - a0)
    n = sum(1 for t, cc in mov if cc == c['id']); pm = n / span * 60
    # v14（依頼主 10/19 19:12「数は多ければ多いほどいい」）：上限は外し、下限 1分 34 個（手本で一番多い本 31.2 より上）
    if pm < MOVE_PM and span > 15: put(c['id'], 'この章（%.0f秒）の動く部品は %d 個＝1分 %.1f 個。1分 %d 個以上（この章なら %d 個以上）に足す：行の言葉が替わるたびに部品を1つ・動く図解（kazu_up・bars_up・sen_graph・en_graph・chk・atsumaru・hyou_umeru・kaidan・maru）・矢印の伸び・下線・字の差し替えを足す' % (span, n, pm, MOVE_PM, int(span * MOVE_PM / 60 + 0.999)))
def _need(kind, lo, label, how):
    share = trc.get(kind, 0) / ntr
    if share >= lo: return
    have = {x['ch'] for x in TRL if x['kind'] == kind}
    cand = sorted([c for c in PL if c['id'] not in have], key=lambda c: -(stt[int(c['b'])] - stt[int(c['a'])]))
    k = max(1, int((lo * ntr - trc.get(kind, 0)) / max(1, len(cand)) + 0.999))
    for c in cand: put(c['id'], '%s が動画全体で場面の %.0f%%（目標 %.0f%% 以上）。この章で %d 回使う：%s' % (label, share * 100, lo * 100, k, how))
_need('動く切り替え', 0.12, '動く切り替え', "新しい Stack を Stack(bg, tr='zoom'|'slide'|'fade'|'flash'|'blur') にする（話題が大きく替わる所・言い切りの後）")
_need('字・帯だけ差し替え', 0.05, '字・帯だけ差し替え', "st.swap(t, 新しい部品, 'type', se='pon') で、いちばん新しい帯・見出し・札を同じ場所で別の字に替える")
_need('実写・画面・写真へ', 0.015, '実写・画面・写真へ', '新しい Stack(photo(...)) か、新しい Stack の最初の部品を gamen(...) にする')
def _over(kind, hi, label, how):
    share = trc.get(kind, 0) / ntr
    if share <= hi: return
    for c in PL:
        nc = [x for x in TRL if x['ch'] == c['id'] and x['kind'] == kind]
        span = max(1.0, ent[int(c['b'])] - stt[int(c['a'])]); lim = max(1, int(span / 60 * hi * 22 + 0.5))
        if len(nc) > lim: put(c['id'], '%s が動画全体で場面の %.0f%%（手本の作者さんは中央値 8%%・上は %.0f%% まで）。この章は %d 回→%d 回以内に減らす：%s（%s）' % (label, share * 100, hi * 100, len(nc), lim, how, '・'.join('%.1f秒' % x['t'] for x in nc)))
# v14：動く切り替え・差し替えの上限は外した（依頼主「画面をコロコロ変えて」）。同じ tr が続く所だけ直させる
_prev = None
for x in TRL:
    if x.get('tr'):
        if x['tr'] == _prev: put(x['ch'], '%.1f秒 動く切り替え tr=%r が前の動く切り替えと同じ（9種類 zoom・slide・yokobure・hosha・flash・fade・blur・glitch・anten を順に混ぜる）' % (x['t'], x['tr']))
        _prev = x['tr']
# ⑦ 大きな切り替え（全消し・動く切り替え・実写へ・重ねる）：v13 で部品を減らしたら門の「大きな切り替わり/分」が 12.5（線 12.51）に落ちた（10/19 15:40）。予定 107 回→測り 125 回（約1.17倍）
#    v12（測り 15.3）を減らさないため、章ごとに 1分 12.5 回以上（測りで 14.5 前後）を求める
BIG_PM = float(os.environ.get('BIG_PM', '22'))   # v14（依頼主 10/19 19:12「切り替えは多いほど良い」）：手本で上から2番目の本 19.7 より上（予定で 22）   # 作業AI 10/19 16:3x：v12 の門の測り 15.3 を下回らない（質を下げない）。v13c は予定 13.3→測り 13.9（約1.05倍）なので予定で 15.0
BIG = ('全消し（1コマ）', '動く切り替え', '実写・画面・写真へ', '重ねる（後ろをぼかす・暗くする）')
for c in PL:
    span = max(1.0, ent[int(c['b'])] - stt[int(c['a'])])
    if span < 20: continue
    nb = sum(1 for x in TRL if x['ch'] == c['id'] and x['kind'] in BIG); need = int(span * BIG_PM / 60 + 0.999)
    if nb < need: put(c['id'], 'この章（%.0f秒）の大きな切り替え（新しい Stack・動く切り替え・実写へ・over）は %d 回＝1分 %.1f 回。1分 %.1f 回以上（この章なら %d 回以上）にする：前を残して足している所のうち、話題・言い切りの替わり目を新しい Stack() にする（部品の数は増やさない・動く部品 1分18〜22 は保つ）' % (span, nb, nb / span * 60, BIG_PM, need))
if trc.get('前を残して足す', 0) / ntr > 0.45:
    for c in PL:
        nc = [x for x in TRL if x['ch'] == c['id']]
        if nc and sum(1 for x in nc if x['kind'] == '前を残して足す') / len(nc) > 0.5: put(c['id'], 'この章は場面の %d%% が「前を残して足す」。新しい Stack・動く切り替え・差し替え・over を混ぜる（全体で4割まで）' % (100 * sum(1 for x in nc if x['kind'] == '前を残して足す') / len(nc)))
# v14 表現の型（手本13本の48型・pipe/kata_v14.py と同じ当て方）：章ごとに 10 種類以上・動く図解 2 つ以上・動画全体で全部
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zukai.py')).read(); _ns = {}; exec(_src[_src.index('ANIM_KATA = {'):], _ns)
_AK, _PK, _TK = _ns['ANIM_KATA'], _ns['PART_KATA'], _ns['TR_KATA']
_BOX = [r['kata'] for r in json.load(open(os.path.expanduser('~/rin6/state/yt-henshu/pipe-1019/v14/kata-tehon.json')))['rows']]
_K2 = {'全消し（1コマ）': '全消し（1コマ）', '字・帯だけ差し替え': '字幕・帯だけ差し替え', '前を残して足す': '前を残して足す', '重ねる（後ろをぼかす・暗くする）': '暗い地に大字（重ね）', '実写・画面・写真へ': '実写・写真'}
def _kata_ch(cid):
    k = set(); nz = 0
    for x in KV.get('katalog', []):
        if cid is not None and x['ch'] != cid: continue
        a = x.get('anim_ato', x['anim'])
        if _AK.get(a): k.add(_AK[a])
        if _PK.get(x['fn']): k.add(_PK[x['fn']])
        if x.get('zukai') in _BOX: k.add(x['zukai'])
        if a in ('grow', 'nobi', 'egaku'): nz += 1
    for x in TRL:
        if cid is not None and x['ch'] != cid: continue
        if _K2.get(x['kind']): k.add(_K2[x['kind']])
        if x.get('tr'): k.add(_TK.get(x['tr'], x['tr']))
        if x.get('ji') in _BOX: k.add(x['ji'])
        if x.get('ji') == '写真の地': k.add('実写・写真'); k.add('カメラがゆっくり寄る')
    return k & set(_BOX), nz
for c in PL:
    ks, nz = _kata_ch(c['id']); span = max(1.0, ent[int(c['b'])] - stt[int(c['a'])])
    if len(ks) < 10: put(c['id'], 'この章の表現の型は %d 種類（10 種類以上にする）。使っていない型から足す：%s' % (len(ks), '・'.join([b for b in _BOX if b not in ks][:14])))
    if nz < 2 and span > 15: put(c['id'], 'この章の動く図解（出方 grow・nobi・egaku）は %d 個（2 個以上にする：kazu_up・bars_up・sen_graph・en_graph・chk・atsumaru・hyou_umeru・kaidan・maru＋grow ／ yaji・tsunagu・shitasen＋nobi ／ ic・icl＋egaku）' % nz)
_all, _ = _kata_ch(None)
_miss = [b for b in _BOX if b not in _all and b != 'ワイプで替わる']   # ワイプ（左から拭く切り替え）は右の部品が言葉より遅れて見えるので使わない（門のルール5）
for _m in _miss: zentai.append('表現の型「%s」が動画全体で一度も出ていない（この章で1回使う）' % _m)
# 同じ型が3回以上続く所（story_tail が字・絵の出方は直す。残るのは動く図解が3つ続く所）
_F = KV.get('firsts', []); _r = 0; _pk = None
for x in _F:
    _r = _r + 1 if x['kata'] == _pk else 1; _pk = x['kata']
    if _r == 3: put(x['ch'], '%.1f秒 同じ表現の型「%s」が3回続く（間に別の型を入れる）' % (x['t'], x['kata']))
DA = KV.get('dekata_ato', {}); nd = max(1, sum(DA.values()))
dek = {k: round(v / nd, 3) for k, v in DA.items()}
if dek.get('pop', 0) > 0.20: zentai.append('出方のポップが %.0f%%（20%%以下）' % (dek['pop'] * 100))
for k_, lab in (('type', '1字ずつ'), ('blur', 'ぼけから')):
    if dek.get(k_, 0) < 0.12: zentai.append('出方の%sが %.0f%%（12%%以上）' % (lab, dek.get(k_, 0) * 100))
kazu = {'動く部品': len(mov), '1分あたり': round(len(mov) / dur * 60, 1), '切り替え': dict(trc), '切り替えの種類': len(trc), '大きな切り替え/分': round(sum(trc.get(k, 0) for k in BIG) / dur * 60, 1), '出方': dek, '出方を直した数': len(KV.get('naoshita', [])), '場面': len(H.SCENES), '効果音': len(S.SFX), '種類': dict(cnt),
        '直す所': sum(len(v) for v in iss.values()), '字幕の札': len(JM), '表現の型の種類': len(_all), '同じ型の最長連続': KV.get('kata_saichou_renzoku')}
os.makedirs(os.path.join(P, 'work', 'bamen'), exist_ok=True)
json.dump({'ch': iss, 'zentai': zentai, 'kazu': kazu}, open(os.path.join(P, 'work', 'bamen', 'kensa.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(kazu, ensure_ascii=False)); print('全体:', zentai)
for c, v in sorted(iss.items()): print('章', c, len(v), '件 例:', v[0])
