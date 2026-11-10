# 1本の流れ（video_marketing）が書けているか・薄くないかを見る（作業AI・2026-10-15）
#   依頼主 10/15 19:55「1本の動画の中で流れっていうのがあるので、動画1本単位でちゃんとマーケター目線で分析する」
#   形は kata/full/AGENT_FULL.md の追記9。見本の記録（per_full）と、作業AIが作る1本（<プロジェクト>/video_marketing.json）の両方に同じ門を当てる
#   fails(vm, dur) → 外れの一覧（空なら合格）
import re

LINE = dict(
    TEXT_MIN=8,          # 文の欄は 8字以上（「不明」「TODO」「なし」は数えない）
    HOOK_MAX_S=15.0,     # hook は最初の15秒までの中で、秒つき
    FLOW_MIN=4,          # flow は 4区間以上（フック→つかみ→問題提起→本編の山→まとめ→CTA）
    FLOW_COVER_MIN=0.80, # flow の区間で 動画の長さの 80% 以上を覆う
    RETENTION_MIN=3,     # 離脱を防ぐ仕掛け 3つ以上・それぞれ秒つき
    WHY_MIN=3,           # 効いた理由の仮説 3つ以上・それぞれ根拠の秒つき
    REUSABLE_MIN=3, REUSABLE_MAX=5,
)
BAD = re.compile(r'(不明|TODO|未記入|あとで|後で書く|仮置き|\?\?\?)')
SEC = re.compile(r'(\d+(?:\.\d+)?)\s*秒')
TKEYS = ('t', 't0', 't1', 's', 'e', 'sec', 'at', 'start', 'end', 'evidence_t', 'times', 'where')


def _text(o):
    if isinstance(o, str): return o
    if isinstance(o, dict): return ' '.join(_text(v) for v in o.values())
    if isinstance(o, (list, tuple)): return ' '.join(_text(v) for v in o)
    return '' if o is None else str(o)


def _ok_text(o, n=None):
    t = _text(o).strip()
    return len(re.sub(r'\s', '', t)) >= (n or LINE['TEXT_MIN']) and not BAD.search(t)


def secs(o):
    """欄の中の秒（数の欄・「12.3秒」の書き方）を全部拾う"""
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in TKEYS:
                for u in (v if isinstance(v, (list, tuple)) else [v]):
                    if isinstance(u, (int, float)) and not isinstance(u, bool): out.append(float(u))
                    elif isinstance(u, str): out += [float(m) for m in re.findall(r'\d+(?:\.\d+)?', u)]
            else: out += secs(v)
    elif isinstance(o, (list, tuple)):
        for v in o: out += secs(v)
    elif isinstance(o, str):
        out += [float(m) for m in SEC.findall(o)]
    return out


def _span(seg):
    a = next((seg[k] for k in ('t0', 's', 'start') if isinstance(seg, dict) and isinstance(seg.get(k), (int, float))), None)
    b = next((seg[k] for k in ('t1', 'e', 'end') if isinstance(seg, dict) and isinstance(seg.get(k), (int, float))), None)
    if a is None or b is None:
        ss = secs(seg)
        if len(ss) >= 2: a, b = ss[0], ss[1]
    return (float(a), float(b)) if a is not None and b is not None and b > a else None


def fails(vm, dur, make=False):
    """make=True … 作業AIが作る1本（check.py ⑫）。見本の記録の形に加えて、山場（climax・秒つき）と、flow に山場の区間があることを求める
    （依頼主 20:3x「毎回、その台本の意図が見る人に伝わる演出」＝1本の中でどこを一番強く見せるかを先に決めてから一文ずつ決める）"""
    F = []
    if not isinstance(vm, dict) or not vm:
        return ['video_marketing が無い（追記9：1本の流れ。target・promise・hook・flow・retention・cta・why_it_works・reusable）']
    dur = float(dur or 0)
    for k, name in (('target', '誰に向けた動画か'), ('promise', '冒頭で約束していること')):
        if not _ok_text(vm.get(k)): F.append('video_marketing.%s（%s）が無いか薄い（%d字以上・「不明」なし）' % (k, name, LINE['TEXT_MIN']))
    h = vm.get('hook')
    hs = [t for t in secs(h) if 0 <= t <= LINE['HOOK_MAX_S']]
    if not _ok_text(h) or not hs:
        F.append('video_marketing.hook（最初の3〜10秒で何をして止めているか）が無いか、%d秒以内の秒が書かれていない' % LINE['HOOK_MAX_S'])
    fl = vm.get('flow') if isinstance(vm.get('flow'), list) else []
    spans = [_span(x) for x in fl]
    good = [x for x, sp in zip(fl, spans) if sp and _ok_text(x, 16)]
    if len(good) < LINE['FLOW_MIN']:
        F.append('video_marketing.flow の区間が %d（線 %d 以上・各区間に 開始〜終了秒・思わせたいこと・使った演出）' % (len(good), LINE['FLOW_MIN']))
    else:
        sp = sorted(s for s in spans if s)
        cov = 0.0; cur = 0.0
        for a, b in sp:
            a = max(a, cur)
            if b > a: cov += b - a; cur = b
        if dur > 0 and cov / dur < LINE['FLOW_COVER_MIN']:
            F.append('video_marketing.flow が動画の %.0f%% しか覆っていない（線 %.0f%%）' % (100 * cov / dur, 100 * LINE['FLOW_COVER_MIN']))
        if dur > 0 and any(b > dur + 2 for _, b in sp):
            F.append('video_marketing.flow に動画の長さ（%.1f秒）を超える秒がある' % dur)
        miss = [i for i, x in enumerate(fl) if isinstance(x, dict) and not any(_ok_text(x.get(k), 4) for k in ('devices', 'edit', 'how', '演出', 'tools'))]
        if len(miss) > len(fl) / 2:
            F.append('video_marketing.flow の %d区間に「そのために使っている演出／効果音／テロップ／絵」（devices）が無い' % len(miss))
    rt = vm.get('retention') if isinstance(vm.get('retention'), list) else []
    rg = [x for x in rt if secs(x) and _ok_text(x)]
    if len(rg) < LINE['RETENTION_MIN']:
        F.append('video_marketing.retention（離脱を防ぐ仕掛け）が秒つきで %d（線 %d 以上）' % (len(rg), LINE['RETENTION_MIN']))
    c = vm.get('cta')
    if not _ok_text(c) or not secs(c):
        F.append('video_marketing.cta（何をさせたいか・どこで何回・言い方と画面）が無いか秒が無い')
    wy = vm.get('why_it_works') if isinstance(vm.get('why_it_works'), list) else []
    wg = [x for x in wy if secs(x) and _ok_text(x, 12)]
    if len(wg) < LINE['WHY_MIN']:
        F.append('video_marketing.why_it_works（効いた理由の仮説）が根拠の秒つきで %d（線 %d 以上）' % (len(wg), LINE['WHY_MIN']))
    ru = vm.get('reusable') if isinstance(vm.get('reusable'), list) else []
    rug = [x for x in ru if _ok_text(x)]
    if not (LINE['REUSABLE_MIN'] <= len(rug) <= LINE['REUSABLE_MAX']):
        F.append('video_marketing.reusable（ほかの動画に使える型）が %d（線 %d〜%d）' % (len(rug), LINE['REUSABLE_MIN'], LINE['REUSABLE_MAX']))
    if make:
        cl = vm.get('climax')
        cs = [t for t in secs(cl) if 0 <= t <= (dur or 1e9)]
        if not _ok_text(cl) or not cs:
            F.append('video_marketing.climax（山場：どの秒の何を一番強く見せるか・なぜそこか）が無いか、動画の中の秒が無い')
        elif fl and not any(isinstance(x, dict) and '山' in str(x.get('name', '')) and (_span(x) or (0, 0))[0] - 1 <= cs[0] <= (_span(x) or (0, 0))[1] + 1 for x in fl):
            F.append('video_marketing.flow に、山場（%.1f秒）を含む「山」の区間が無い' % cs[0])
    return F
