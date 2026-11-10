# 観点の全部（作業AI・2026-10-16）
#   依頼主 10/15「合格の基準はつかみ・離脱・CTAだけではない。ほかにも色々ある。YouTube動画編集者になってほしい」
#   見本＝委託の編集者さんの per_full（全編を1コマずつ見た記録）から、この編集者が実際に気をつけていることを観点ごとに数にする。
#   同じ観点・同じ式を 見本（per_full） と 作業AIの1本（story_meta.json・video_marketing.json・check の測り） の両方に当てる。
#
#   from_per_full(d)        見本1本 → {指標: 値}
#   from_project(P, extra)  作業AIの1本 → {指標: 値}（extra＝check.py が mp4 から測った値）
#   build(per_dir)          全見本 → 指標ごとの分布（中央値・10〜90%・本数）
#   score(vals, kijun)      観点ごとの点（0〜100）・外れた指標
import os, re, json, glob, statistics, collections

# ---- 場面の役割（見本の言葉）を束ねる。作業AIの intent の role もこの言葉で書く（違う言葉は数に入らない）
R_PROOF = r'権威|実績|証拠'
R_ANSWER = r'結論'
R_NEG = r'煽り|損失|否定|問題|危機|不安|共感|警告|常識破り|逆転'
R_POS = r'結論|解決|希望|チャンス|まとめ|手順|実績|証拠'
R_TURN = r'否定|常識破り|逆転|煽り|損失|限定|希少'
R_PROMO = r'告知|宣伝|特典|CTA|限定|希少'
R_CTA = r'CTA'
R_JOINT = r'場面つなぎ|章'
VIS_DIAGRAM = r'図|チェック|矢印|流れ|表|グラフ|比較|アイコン|箇条|リスト|ピクト|括弧|式'
VIS_REAL = r'スクショ|画面録画|実物|チャンネル|管理画面|実写|写真|画面の|ページ'
CALL_Q = r'[？?]'
CALL_DO = r'ください|しよう|しましょう|してみて|やってみ|見て|登録|お願い|べき|こと[!！]'


def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _g(d, *path):
    for p in path:
        if not isinstance(d, dict): return None
        d = d.get(p)
    return d


def _bigr(s):
    s = re.sub(r'[^ぁ-んァ-ヶー一-龠々0-9A-Za-z０-９Ａ-Ｚａ-ｚ]', '', s or '')
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _hist_share(h, lo, hi):
    if not isinstance(h, dict) or not h: return None
    tot = sum(v for v in h.values()); ok = 0
    for k, v in h.items():
        try: x = float(k)
        except ValueError: continue
        if lo <= x <= hi: ok += v
    return ok / tot if tot else None


def _scene_common(scenes, D, role_of, shown_of, visual_of, t0_of, t1_of):
    """見本と作業AIで同じ式：場面の役割・出した文字・絵の種類から、信頼・感情・告知・呼びかけ・図解・章を数える"""
    v = {}
    if not scenes or not D: return v
    mins = D / 60.0
    rs = [(t0_of(s), t1_of(s), role_of(s) or '', shown_of(s) or '', visual_of(s) or '') for s in scenes]
    dur = lambda a, b: max(0.0, (b or a) - a)
    proof = [x for x in rs if re.search(R_PROOF, x[2])]
    v['tr_first_proof_s'] = proof[0][0] if proof else D
    v['tr_proof_share'] = sum(dur(x[0], x[1]) for x in proof) / D
    v['tr_proof_per10'] = len(proof) / mins * 10
    v['tr_real_share'] = sum(dur(x[0], x[1]) for x in rs if re.search(VIS_REAL, x[4])) / D
    ans = [x for x in rs if re.search(R_ANSWER, x[2])]
    v['p_answer_first_s'] = ans[0][0] if ans else D
    turns = [x for x in rs if re.search(R_TURN, x[2])]
    v['e_turn_per10'] = len(turns) / mins * 10
    pol = []
    for x in rs:
        n_, p_ = bool(re.search(R_NEG, x[2])), bool(re.search(R_POS, x[2]))
        if n_ != p_: pol.append(1 if p_ else -1)
    v['e_updown_per10'] = sum(1 for a, b in zip(pol, pol[1:]) if a != b) / mins * 10
    promo = [x for x in rs if re.search(R_PROMO, x[2])]
    v['c_promo_share'] = sum(dur(x[0], x[1]) for x in promo) / D
    v['c_promo_before_body'] = 1.0 if any(x[0] < 0.3 * D and re.search(r'告知|宣伝', x[2]) for x in rs) else 0.0
    cta = [x for x in rs if re.search(R_CTA, x[2])]
    v['k_cta_scenes'] = float(len(cta))
    v['k_cta_first_ratio'] = cta[0][0] / D if cta else 1.0
    v['k_question_per10'] = sum(1 for x in rs if re.search(CALL_Q, x[3])) / mins * 10
    v['k_do_per10'] = sum(1 for x in rs if re.search(CALL_DO, x[3])) / mins * 10
    v['c_joint_per10'] = sum(1 for x in rs if re.search(R_JOINT, x[2])) / mins * 10
    v['u_diagram_share'] = sum(dur(x[0], x[1]) for x in rs if re.search(VIS_DIAGRAM, x[4])) / D
    lens = [dur(x[0], x[1]) for x in rs if x[1]]
    if lens: v['t_scene_len_med_s'] = statistics.median(lens)
    v['t_scenes_pm'] = len(rs) / mins
    # 約束の回収：冒頭30秒に出した文字と、終わり（告知・CTA を除く最後の25%）に出した文字の重なり（2字の切れ端）
    head = set().union(*[_bigr(x[3]) for x in rs if x[0] < 30] or [set()])
    tail = [x for x in rs if x[0] >= 0.6 * D and not re.search(R_PROMO, x[2])]
    tail = tail[-max(1, len(tail) // 2):] if tail else []
    best = 0.0
    for x in tail:
        b = _bigr(x[3])
        if b and head: best = max(best, len(b & head) / len(b))
    v['p_recall_end'] = best
    return v


def has_band(d):
    """常に出ている字幕帯があるか（base_look.always_on に「字幕」）"""
    return any('字幕' in str(x) for x in ((d.get('base_look') or {}).get('always_on') or []))


def fmt_of(d):
    """見本の形式の札：対談型（受講生・ゲストとの対談）／字幕帯型（ほぼ全編に字幕帯を出し声と同時に入れ替える）／講義型（それ以外・作業AIの1本はこれ）"""
    fam = str(d.get('family') or '')
    if '対談' in fam: return '対談型'
    ao = ' '.join(str(x) for x in ((d.get('base_look') or {}).get('always_on') or []))
    if '字幕帯' in ao and '全編' in ao: return '字幕帯型'
    return '講義型'


# 耳で確かめるまで基準に入れない値（10/16 作業AIの指示）
UNSURE = {('yBd_8rzhlFQ', 's_voice_minus_bg_db'): '未確定：声と背景の分け方の漏れの可能性があり、耳で確かめるまで基準に入れない（元の音では声の切れ目でも背景が他の本より約8dB大きい＝本当にBGMが大きい可能性が高い）'}


# 動き続けを変化の山で切り直した数字を使う（lib/yama.py・10/16 作業AIの指示）。False にすると前処理の数字のまま（比べる用）
YAMA = True
RAW_DIR = os.path.join(os.path.expanduser('~'), 'rin6/state/yt-anime-1014/kata/full/raw')


def from_per_full(d):
    """見本1本（per_full）→ 指標。古い形（numbers.total）と新しい形（numbers.full）の両方を読む"""
    n = d.get('numbers') or {}; D = float(d.get('duration_s') or 0); v = {}
    vid = d.get('id') or d.get('video_id')
    if YAMA and vid and isinstance(n.get('full'), dict):
        import yama
        n = yama.overlay(n, os.path.join(RAW_DIR, vid))
    F = n.get('full'); T = n.get('total'); H = n.get('first30'); H0 = n.get('hook30')
    if F:
        v['t_changes_pm'] = _num(F.get('changes_per_min'))
        v['t_change_med_s'] = _num(_g(F, 'change_interval_s', 'median'))
        v['t_change_max_s'] = _num(_g(F, 'change_interval_s', 'max'))
        v['t_anim_pm'] = _num(F.get('anim_per_min'))
        v['t_telop_pm'] = _num(F.get('telop_in_per_min'))
        if F.get('frames'): v['t_motion_share'] = (F.get('moving_frames') or 0) / F['frames']
        v['s_sfx_pm'] = _num(F.get('sfx_per_min'))
        v['s_sfx_sync_med_f'] = _num(_g(F, 'sfx_minus_change_f', 'median'))
        v['s_sfx_sync_in2f'] = _hist_share(_g(F, 'sfx_minus_change_f', 'hist'), -2, 2)
        v['s_silence_med_s'] = _num(_g(F, 'silence_s', 'median'))
        v['s_silence_p90_s'] = _num(_g(F, 'silence_s', 'p90'))
        v['a_telop_sync_med_f'] = _num(_g(F, 'telop_in_minus_word_f', 'median'))
        v['a_telop_sync_in3f'] = _hist_share(_g(F, 'telop_in_minus_word_f', 'hist'), -3, 3)
        v['a_telop_out_med_f'] = _num(_g(F, 'telop_out_minus_wordend_f', 'median'))
        vm = F.get('telop_visibility_median') or {}
        for k, kk in (('height_px', 'v_height_px'), ('contrast', 'v_contrast'), ('outline_px', 'v_outline_px'), ('chars', 'v_chars'),
                      ('shown_s', 'v_shown_s'), ('chars_per_s', 'v_chars_per_s'), ('phone390_height_px', 'v_phone390_px')):
            v[kk] = _num(vm.get(k))
        kinds = F.get('sfx_kinds') or {}
        if kinds and sum(kinds.values()): v['s_sfx_top_kind_share'] = max(kinds.values()) / sum(kinds.values())
    elif T:
        v['t_changes_pm'] = _num(T.get('changes_per_min')); v['t_anim_pm'] = _num(T.get('anim_per_min'))
        v['s_sfx_pm'] = _num(T.get('sfx_per_min'))
        st = _g(T, 'sfx_frames_from_change', 'stats'); v['s_sfx_sync_med_f'] = _num(_g(st, 'median')) if st else None
        v['s_sfx_sync_in2f'] = _hist_share(_g(T, 'sfx_frames_from_change', 'hist'), -2, 2)
        v['a_telop_sync_med_f'] = _num(_g(T, 'telop_frames_from_word', 'stats', 'median'))
        v['a_telop_sync_in3f'] = _hist_share(_g(T, 'telop_frames_from_word', 'hist'), -3, 3)
        vm = n.get('visibility_median') or {}
        v['v_height_px'] = _num(vm.get('glyph_h_px')); v['v_phone390_px'] = _num(vm.get('phone_390_glyph_h_px'))
        v['v_outline_px'] = _num(vm.get('edge_px')); v['v_chars_per_s'] = _num(vm.get('chars_per_s'))
    if H:
        v['h_changes_pm'] = _num(H.get('changes_per_min')); v['h_sfx_pm'] = _num(H.get('sfx_per_min'))
        v['h_anim_pm'] = _num(H.get('anim_per_min')); v['h_telop_pm'] = _num(H.get('telop_in_per_min'))
    elif H0:
        v['h_changes_pm'] = _num(H0.get('changes_per_min')); v['h_sfx_pm'] = _num(H0.get('sfx_per_min')); v['h_anim_pm'] = _num(H0.get('anim_per_min'))
    if v.get('h_changes_pm') and v.get('t_changes_pm'): v['h_changes_ratio'] = v['h_changes_pm'] / v['t_changes_pm']
    vb = n.get('voice_minus_bg_db')
    v['s_voice_minus_bg_db'] = _num(vb.get('full') if isinstance(vb, dict) else vb)
    sw = n.get('bgm_switch_candidates')
    if isinstance(sw, list) and D: v['s_bgm_switch_per10'] = len(sw) / (D / 600)
    sp = n.get('speed') or {}
    v['n_cps'] = _num(sp.get('chars_per_s_speaking') if 'chars_per_s_speaking' in sp else sp.get('chars_per_voiced_s'))
    su = sp.get('whole_speedup_guess')
    if su is None:
        m = re.search(r'約\s*([0-9.]+)\s*倍', str(sp.get('speedup_estimate') or '')); su = float(m.group(1)) if m else None
    v['n_speedup'] = _num(su)
    if v.get('s_silence_med_s') is None: v['s_silence_med_s'] = _num(sp.get('pause_median_s'))
    p03 = _g(n, '4_silence', 'pauses_0.3s_plus')
    if isinstance(p03, list) and D: v['n_pause03_pm'] = len(p03) / (D / 60)
    elif sp.get('pause_count_ge_0.3s') is not None and D: v['n_pause03_pm'] = sp['pause_count_ge_0.3s'] / (D / 60)
    sel = (n.get('selection') or {}).get('ratio') or {}
    def sr(pat):
        x = [val for k, val in sel.items() if re.search(pat, k)]
        return sum(x) if x else None
    if sel:
        v['u_sel_full'] = sr(r'全文'); v['u_sel_rephrase'] = sr(r'言い換え'); v['u_sel_summary'] = sr(r'要約')
        v['u_sel_keyword'] = sr(r'キーワード'); v['u_sel_visual_only'] = sr(r'絵'); v['u_sel_nothing'] = sr(r'何も')
    sc = [s for s in d.get('scenes') or [] if isinstance(s, dict)]
    rp = sum(len((s.get('selection') or {}).get('rephrase') or []) for s in sc)
    if D: v['u_rephrase_pm'] = rp / (D / 60)
    # テロップ1行ずつの見やすさ（スマホで小さすぎる・背景に埋もれる行の割合）
    rows = [r for s in sc for r in ((s.get('telop') or {}).get('visibility') or []) if isinstance(r, dict)]
    if has_band(d):
        # 常に出ている字幕帯（下の帯）は「読ませる字幕」でテロップではない。下4分の1の行を外して、見やすさの中央値を測り直す（10/16 作業AIの指示）
        rows = [r for r in rows if not r.get('lower_quarter')]
        for k, kk in (('height_px', 'v_height_px'), ('phone390_height_px', 'v_phone390_px'), ('chars', 'v_chars'), ('shown_s', 'v_shown_s'), ('chars_per_s', 'v_chars_per_s'),
                      ('contrast_fill_vs_surround', 'v_contrast'), ('outline_px', 'v_outline_px')):
            xs = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
            if xs: v[kk] = statistics.median(xs)
    ph = [r.get('phone390_height_px') for r in rows if isinstance(r.get('phone390_height_px'), (int, float))]
    if ph: v['v_small_share'] = sum(1 for x in ph if x < 15) / len(ph)
    ct = [r.get('contrast_fill_vs_surround') for r in rows if isinstance(r.get('contrast_fill_vs_surround'), (int, float))]
    if ct: v['v_lowcontrast_share'] = sum(1 for x in ct if x < 3) / len(ct)
    v.update(_scene_common(sc, D, lambda s: s.get('role'), lambda s: (s.get('telop') or {}).get('shown') or (s.get('selection') or {}).get('shown'),
                           lambda s: ' '.join(str((s.get('visual') or {}).get(k) or '') for k in ('kind', 'what')),
                           lambda s: float(s.get('t0') or 0), lambda s: float(s.get('t1') or s.get('t0') or 0)))
    # 世界観の統一：見た目の型の数・本編の見た目が占める割合・差し色の数・常に出ているもの
    modes = d.get('modes') or []
    v['w_modes'] = float(len(modes))
    best = 0.0
    for m in modes:
        tot = 0.0
        for a, b in re.findall(r'(\d+(?:\.\d+)?)\s*〜\s*(\d+(?:\.\d+)?)', str(m.get('times') or '')):
            tot += max(0.0, float(b) - float(a))
        best = max(best, tot)
    if D and best: v['w_main_share'] = min(1.0, best / D)
    bl = d.get('base_look') or {}
    if isinstance(bl.get('accent'), list): v['w_accent_n'] = float(len(bl['accent']))
    if isinstance(bl.get('always_on'), list): v['w_always_on'] = float(len(bl['always_on']))
    vm_ = d.get('video_marketing') or {}
    fl = [x for x in vm_.get('flow') or [] if isinstance(x, dict) and _num(x.get('t0')) is not None and _num(x.get('t1')) is not None]
    if fl:
        v['c_flow_n'] = float(len(fl)); v['c_flow_len_med_s'] = statistics.median(float(x['t1']) - float(x['t0']) for x in fl)
        v['e_yama_n'] = float(sum(1 for x in fl if '山' in ' '.join(str(x.get(k) or '') for k in ('role', 'name', 'part'))))
    v['k_retention_n'] = float(len(vm_.get('retention') or []))
    v['c_duration_s'] = D
    import kanten_tsuika   # 観点の足し分（yt-hozon 10/16）：場面転換・強調・色・効果音の役割・図の形・動き・最初の問い・話の順番・図解の続き・間の場所
    v.update(kanten_tsuika.from_per_full(d))
    return _derive({k: x for k, x in v.items() if x is not None})


def _rin_as_per_full(meta, P, D):
    """作業AIの1本の場面の記録（story_meta）を per_full の場面の形に直す（kanten_tsuika を見本と同じ式で当てるため・10/16）。
    役割＝intent の role／場面の替え方＝selection_plan の cut（続ける＝足し算）／強調＝emphasis（なし以外）／出した文字＝selection の shown／
    効果音＝sfx の名前を見本の語に（don→ドン・pon→ポン・kira→キラーン・whoosh→シュッ・telop→カチッ）／図＝visual／動き＝boxes の入り方／画面の変化＝elems の数。
    色は作業AIの記録に役割ごとの色が無いので出さない（x_color_* は未測定になる）"""
    TOL = 0.006
    scs = sorted(meta.get('scenes') or []); ends = scs[1:] + [D]
    def at(lst, t, key='t'):
        c = [x for x in lst if x[key] <= t + TOL]; return c[-1] if c else None
    intent = sorted(meta.get('intent') or [], key=lambda x: x['t']); plan = sorted(meta.get('selection_plan') or [], key=lambda x: x['t'])
    onscr = {round(float(x['t0']), 2): x.get('shown') or [] for x in meta.get('selection') or [] if x.get('t0') is not None}
    SE = {'don': 'ドン', 'don_long': 'ドン', 'pon': 'ポン', 'pon_hi': 'ポン', 'kira': 'キラーン', 'kira_hi': 'キラーン', 'whoosh': 'シュッ', 'telop': 'カチッ'}
    AN = {'pop': 'ポップ', 'slam': '揺れ', 'blur': 'ぼかし', 'wipeblur': 'ぼかし', 'wipe': 'ワイプ', 'up': ''}
    sfx = [(float(x[0]), x[1]) for x in meta.get('sfx') or [] if isinstance(x, (list, tuple)) and len(x) >= 2]
    box = [(float(x[0]), x[5]) for x in meta.get('boxes') or [] if isinstance(x, (list, tuple)) and len(x) >= 6]
    el = [float(x) for x in meta.get('elems') or [] if isinstance(x, (int, float))]
    out = []
    for a, b in zip(scs, ends):
        it = at(intent, a) or {}; pl = [p for p in plan if a - TOL <= p['t'] < b - TOL]; p0 = pl[0] if pl else {}
        got = [v_ for k_, v_ in onscr.items() if abs(k_ - a) <= TOL]
        cut = str(p0.get('cut') or '')
        emp = str(p0.get('emphasis') or '')
        out.append({'t0': a, 't1': b, 'role': it.get('role', ''),
                    'transition': '足す' if cut == '続ける' else cut,
                    'telop': {'emphasis': '' if emp in ('', 'なし') else emp, 'shown': ' '.join(got[0]) if got else ' '.join(' '.join(p.get('shown') or []) for p in pl)},
                    'sfx': [{'kind': SE[k]} for t, k in sfx if a - TOL <= t < b - TOL and k in SE],
                    'visual': {'kind': ' '.join(str(p.get('visual') or '') for p in pl), 'what': str(it.get('edit') or '')},
                    'anim': ' '.join(AN.get(k, '') for t, k in box if a - TOL <= t < b - TOL),
                    'frames': {'changes': sum(1 for t in el if a - TOL <= t < b - TOL)}})
    bg = [{'t': float(x[0])} for x in meta.get('bgm') or [] if isinstance(x, (list, tuple)) and x]
    return {'scenes': out, 'duration_s': D, 'numbers': {'bgm_switch_candidates': bg}}


def _derive(v):
    """見本と作業AIで同じ式の合わせ指標：台本を手で整えた割合（言い換え＋要約＋キーワード）"""
    xs = [v.get(k) for k in ('u_sel_rephrase', 'u_sel_summary', 'u_sel_keyword')]
    if any(isinstance(x, (int, float)) for x in xs): v['u_sel_digest'] = sum(x for x in xs if isinstance(x, (int, float)))
    return v


def from_project(P, extra=None):
    """作業AIの1本 → 指標（同じ式）。extra は check.py が mp4 と声から測った値（テンポ・音・冒頭）"""
    W = os.path.join(P, 'work'); meta = json.load(open(os.path.join(W, 'story_meta.json')))
    D = float(meta['end']); v = dict(extra or {})
    plan = sorted(meta.get('selection_plan') or [], key=lambda x: x['t'])
    intent = sorted(meta.get('intent') or [], key=lambda x: x['t'])
    scs = sorted(meta.get('scenes') or [])
    ends = scs[1:] + [D]
    # 意図・選び方の秒は小数2桁に丸めて残り、場面の頭は3桁（0.456 と 0.46）。丸めの幅（0.005）より少し広く見ないと、
    # 意図が1つ前の場面のものに当たる（10/16 見つけた：171場面中152場面で役割が1つずれていた）
    TOL = 0.006
    def at(lst, t):
        c = [x for x in lst if x['t'] <= t + TOL]; return c[-1] if c else None
    # 出した文字は画面に実際に描いた文字（selection＝部品が覚えた文字）で数える。予定（selection_plan）の文字が画面に無い場面がある（10/16 見つけた：Depy 164場面中48）
    onscr = {round(float(x['t0']), 2): x.get('shown') or [] for x in meta.get('selection') or [] if x.get('t0') is not None}
    rows = []
    for a, b in zip(scs, ends):
        it = at(intent, a) or {}; pl = [p for p in plan if a - TOL <= p['t'] < b - TOL]
        got = [v_ for k_, v_ in onscr.items() if abs(k_ - a) <= TOL]
        rows.append({'t0': a, 't1': b, 'role': it.get('role', ''), 'shown': ' '.join(got[0]) if got else ' '.join(' '.join(p.get('shown') or []) for p in pl),
                     'visual': ' '.join(str(p.get('visual') or '') for p in pl) + ' ' + str(it.get('edit') or '')})
    v.update(_scene_common(rows, D, lambda s: s['role'], lambda s: s['shown'], lambda s: s['visual'], lambda s: s['t0'], lambda s: s['t1']))
    if plan:
        k = [p.get('kind') or '' for p in plan]; n = len(k)
        v['u_sel_full'] = sum('全文' in x for x in k) / n; v['u_sel_rephrase'] = sum('言い換え' in x for x in k) / n
        v['u_sel_summary'] = sum('要約' in x for x in k) / n; v['u_sel_keyword'] = sum('キーワード' in x for x in k) / n
        v['u_sel_visual_only'] = sum(('出さない' in x and '絵' in str(p.get('visual'))) for x, p in zip(k, plan)) / n
        v['u_sel_nothing'] = sum(('出さない' in x and '絵' not in str(p.get('visual'))) for x, p in zip(k, plan)) / n
        v['u_rephrase_pm'] = sum(1 for p in plan if '言い換え' in (p.get('kind') or '')) / (D / 60)
    vp = os.path.join(P, 'video_marketing.json')
    if os.path.exists(vp):
        vm_ = json.load(open(vp))
        fl = [x for x in vm_.get('flow') or [] if isinstance(x, dict) and _num(x.get('t0')) is not None and _num(x.get('t1')) is not None]
        if fl:
            v['c_flow_n'] = float(len(fl)); v['c_flow_len_med_s'] = statistics.median(float(x['t1']) - float(x['t0']) for x in fl)
            v['e_yama_n'] = float(sum(1 for x in fl if '山' in ' '.join(str(x.get(k) or '') for k in ('role', 'name', 'aim'))))
        v['k_retention_n'] = float(len(vm_.get('retention') or []))
    th = os.path.join(P, 'theme_used.json')
    if os.path.exists(th):
        t = json.load(open(th))
        for k in ('w_modes', 'w_main_share', 'w_accent_n', 'w_always_on'):
            if k in t: v[k] = float(t[k])
    v['c_duration_s'] = D
    import kanten_tsuika
    for k, x in kanten_tsuika.from_per_full(_rin_as_per_full(meta, P, D)).items():
        v.setdefault(k, x)   # check.py が mp4 から測った値があればそちらを使う
    return _derive({k: x for k, x in v.items() if x is not None})


# ---- 観点の定義（名前・編集者が気をつけていること・測り方・指標）
#   指標：(キー, ラベル, 単位, 作業AIの1本で測る所)
KANTEN = [
 dict(id='tempo', name='テンポとリズム',
      what='画面は平均1〜1.5秒ごとに何かが変わる（文字が1つ出る・箱が足される・全消し）。同じ話題の中は「足し算」で積み、話題が変わる所だけ1コマで全消しする。'
           '長い説明の途中には30〜100秒おきに大きな動き（ぼかし重ね・揺れる大文字・背景動画の別世界）を置き、図解が90秒続いたら実写や画面録画を3〜10秒挟む。後半ほど章の切り替えを軽くしてテンポを上げる',
      how='画面の変化の数/分・変化の間の中央値と最長・アニメーション/分・テロップの出入り/分・動いているコマの割合（場面の長さは作業員ごとに場面の切り方が違うので測らない。作業AIの1本は check.py ③で見る）',
      m=[('t_changes_pm', '画面の変化/分', '回'), ('t_change_med_s', '変化の間（中央）', '秒'), ('t_change_max_s', '止まった画面の最長', '秒'),
         ('t_anim_pm', 'アニメーション/分', '回'), ('t_telop_pm', 'テロップの出入り/分', '回'), ('t_motion_share', '動いているコマの割合', ''),
         ('x_tr_clear_at_topic', '話題が変わる所で全消しした割合', ''), ('x_tr_add_in_topic', '同じ話題の中で足し算した割合', ''), ('x_tr_kinds', '場面の替え方の種類', '種'),
         ('x_diagram_run_max_s', '実写を挟まず図解が続いた最長', '秒'), ('x_late_speedup', '後半の変化÷前半の変化', '倍'),
         ('x_motion_shake_per10', '揺れ/10分', '回'), ('x_motion_zoom_per10', 'ズーム/10分', '回'), ('x_motion_blur_per10', 'ぼかし/10分', '回'),
         ('x_motion_fade_per10', 'フェード/10分', '回'), ('x_motion_pan_per10', 'パン/10分', '回'), ('x_motion_pop_per10', '飛び出し/10分', '回'), ('x_motion_yama_ratio', '山の場面の動き÷説明の場面の動き', '倍')]),
 dict(id='hook', name='冒頭30秒の密度（つかみ）',
      what='最初の3秒で題の言い切り（数字・対象語）を見せ、15秒以内に「問い→答えの一部」か「本編の山の先出し」を置く。冒頭30秒は本編より画面の変化・効果音を密にする',
      how='冒頭30秒の画面の変化/分・効果音/分・アニメ/分・テロップ/分、本編との比',
      m=[('h_changes_pm', '冒頭30秒の画面の変化/分', '回'), ('h_sfx_pm', '冒頭30秒の効果音/分', '回'), ('h_anim_pm', '冒頭30秒のアニメ/分', '回'),
         ('h_telop_pm', '冒頭30秒のテロップ/分', '回'), ('h_changes_ratio', '冒頭÷全編（画面の変化）', '倍'),
         ('x_hook_first_q_s', '最初の問い', '秒'), ('x_hook_first_claim_s', '最初の言い切り', '秒')]),
 dict(id='visibility', name='見やすさ（テロップの大きさ・量・色・出す時間）',
      what='テロップの字は中央で約90px（スマホ幅390pxで約18px）、主張の大字は100px以上。1行は7〜11字に絞り、表示は1〜2秒で差し替える（1秒に読む字は2〜5字）。色は役割で固定（赤＝言い切り・危機／青＝冷静な結論・比較の弱い側／黄＝要点・限定／金＝希望・山場／灰＝相手の考え）。'
           '縁取りはほとんど使わず（縁の中央0px）、座布団（箱）と地の色の差で浮かせる。左上の常駐ラベルや図の中の補足だけはスマホでぎりぎりの大きさを許す（絵で意味が伝わる作り）',
      how='テロップの字の高さ・コントラスト比・縁の太さ・1行の字数・表示秒・1秒に読む字・390px幅での高さ・小さすぎる行と背景に埋もれる行の割合',
      m=[('v_height_px', '字の高さ（中央）', 'px'), ('v_phone390_px', 'スマホ幅390pxでの高さ', 'px'), ('v_contrast', 'コントラスト比（中央）', ''),
         ('v_outline_px', '縁の太さ（中央）', 'px'), ('v_chars', '1行の字数（中央）', '字'), ('v_shown_s', '表示秒（中央）', '秒'),
         ('v_chars_per_s', '1秒に読む字（中央）', '字'), ('v_small_share', 'スマホで15px未満の行の割合', ''), ('v_lowcontrast_share', 'コントラスト3未満の行の割合', '')]),
 dict(id='wakariyasusa', name='分かりやすさ（図解・言い換え・情報の整理）',
      what='台本を全部は出さない。全文は2割前後で、半分以上は言い換え（口語→見出し語・推量→断定・「僕」→名前・幅のある数→大きい方で言い切り）。'
           '「〜とか」でつないだ例は箇条書きに、比べる話は同じ形の箱を左右に色違いで、手順は「アイコン→矢印→次」の流れ図に、抽象的な位置取りは十字の軸に。同じものは同じ絵で通す',
      how='テロップの選び方の割合（全文・言い換え・要約・キーワード・絵だけ・何も足さない）・言い換え/分・図解の場面が占める時間',
      m=[('u_sel_full', '全文の割合', ''), ('u_sel_rephrase', '言い換えの割合', ''), ('u_sel_summary', '要約の割合', ''), ('u_sel_keyword', 'キーワードだけの割合', ''),
         ('u_sel_visual_only', '絵・図だけの割合', ''), ('u_rephrase_pm', '言い換え/分', '回'), ('u_diagram_share', '図解の場面の時間の割合', ''),
         ('x_shape_match', '図の形が話の形に合う割合', ''), ('x_shape_named_share', '図の形を書いた割合', '')]),
 dict(id='shinrai', name='信頼の見せ方',
      what='実績は「実物のスクショ（チャンネル画面・管理画面）＋黄マーカーの名前＋赤や金の数字」を1組にして、声で言わずに画面で見せる。冒頭から1〜2分以内に1回、理屈を言った章の後半に受講生の前→後の数字を置く。'
           '弱点も字幕で正直に言ってから利点を返す（売り込みに見せない）',
      how='権威・実績・証拠の場面の最初の秒・時間の割合・10分あたりの数・実物（スクショ・画面録画・実写）の場面の割合',
      m=[('tr_first_proof_s', '最初の実績・証拠', '秒'), ('tr_proof_share', '実績・証拠の時間の割合', ''), ('tr_proof_per10', '実績・証拠/10分', '回'),
         ('tr_real_share', '実物（スクショ・画面録画・実写）の時間の割合', '')]),
 dict(id='kanjou', name='感情の起伏',
      what='不安を最大にしてから救う「上げ下げ」を章ごとに置く。否定・逆転の一文は前の画面をぼかしてから重ねる／赤い×で絵で消す。損の結末は縁取り文字を揺らし続けて次の話まで引っぱる。'
           '1本の山場は2〜3か所だけ見た目を大きく変える（背景動画の別世界・金の明朝・3Dの星）＝強弱をはっきりさせる',
      how='否定・常識破り・煽り・限定の場面/10分・負→正の切り替わり/10分・流れの中の山の数',
      m=[('e_turn_per10', '否定・常識破り・煽り・限定/10分', '回'), ('e_updown_per10', '上げ下げ（負⇄正の切り替わり）/10分', '回'), ('e_yama_n', '山の区間の数', '個'), ('x_emph_share', '強調した場面の割合', ''), ('x_emph_yama_ratio', '山・言い切りの強調率÷説明の強調率', '倍')]),
 dict(id='oto', name='音（BGM の抑揚・効果音・無音）',
      what='効果音は画面の変化と同じコマ（中央0〜6コマ以内）に1分約15〜25回。種類は「シュッ（入り）・ポン（足し算）・ドン（言い切り）・キラーン（数字・山）」で役割を固定。'
           '本編のBGMは声より10〜30dB下（講義型はほぼ無し）、告知に入る所で曲と音量を一度に変えて「売り込みの時間」を音で分ける。声の間は0.1秒前後まで詰め、【間】を残すのは結論の直後だけ',
      how='効果音/分・効果音と画面の変化のずれ（中央・±2コマの割合）・いちばん多い種類の割合・声とBGMの差 dB・BGMの切り替わり/10分・無音の長さ（中央・90%）',
      m=[('s_sfx_pm', '効果音/分', '回'), ('s_sfx_sync_med_f', '効果音−画面の変化（中央）', 'コマ'), ('s_sfx_sync_in2f', '効果音が±2コマに入る割合', ''),
         ('s_sfx_top_kind_share', 'いちばん多い効果音の割合', ''), ('s_voice_minus_bg_db', '声とBGMの差', 'dB'), ('s_bgm_switch_per10', 'BGMの切り替わり/10分', '回'),
         ('s_silence_med_s', '声の無音（中央）', '秒'), ('s_silence_p90_s', '声の無音（90%）', '秒'),
         ('x_sfx_role_consist', '役割ごとに同じ効果音を使う割合', ''), ('x_bgm_switch_at_cta', '告知の頭±10秒でBGMが変わる', '')]),
 dict(id='sekaikan', name='世界観の統一',
      what='1本の本編は1つの見た目（灰の板書＋人物の線画の透かし＋左上の題のラベル）を崩さず、別の見た目は冒頭・告知・山場・実写の数か所だけ。差し色は役割ごとに6〜8色に固定し、同じ型（章の入り・答えの出し方）を毎回同じ形でくり返す',
      how='見た目の型の数・本編の見た目が占める割合・差し色の数・常に出ているものの数（作業AIは theme_used.json に記録）',
      m=[('w_modes', '見た目の型の数', '個'), ('w_main_share', '本編の見た目が占める割合', ''), ('w_accent_n', '差し色の数', '色'), ('w_always_on', '常に出ているもの', '個'),
         ('x_color_role_consist', '役割ごとに同じ色で通す割合', ''), ('x_color_redgold_on_key', '言い切り・山に赤か金を使う割合', '')]),
 dict(id='yakusoku', name='サムネとタイトルの約束の回収',
      what='題（サムネと同じ言葉）を最初の0〜8秒に大きく出し、左上のラベルに残して全編で見せ続ける。答えは40秒以内に先に渡し、本編の後半で冒頭と同じ文言・同じ画面で回収する（先出しした山場は同じ要素・同じ順で出す）。最後に題と同じ言葉のキメ文字で締める',
      how='最初の答え（結論）の秒・終わりの文字と冒頭30秒の文字の重なり（2字の切れ端）',
      m=[('p_answer_first_s', '最初の答え（結論）', '秒'), ('p_recall_end', '冒頭の言葉を終わりで回収した重なり', '')]),
 dict(id='shousetsu', name='尺と章立て',
      what='10〜13分が中心。区間（フック→つかみ→本編の章→まとめ→告知・CTA）は6〜8に分け、章の頭は毎回同じ合図（全消し→同じ色の見出し・ラベル）で何章目かを見せる。告知は本編の前（「本編に入る前に1つだけ」→「本編の方どうぞ」）か後ろに、見た目と音を変えて丸ごと置く',
      how='長さ・区間の数・区間の長さ（中央）・章のつなぎ/10分・告知とCTAの時間の割合・本編の前に告知を置いたか',
      m=[('c_duration_s', '長さ', '秒'), ('c_flow_n', '区間の数', '個'), ('c_flow_len_med_s', '区間の長さ（中央）', '秒'), ('c_joint_per10', '章のつなぎ/10分', '回'),
         ('c_promo_share', '告知・CTAの時間の割合', ''), ('c_promo_before_body', '本編の前に告知を置いた', ''),
         ('x_order_score', '話の順番（つかみ・まとめ・告知・言い切りの位置）を満たす割合', '')]),
 dict(id='jimaku', name='字幕の正確さ',
      what='聞き違い・言い間違い（ガイラ→概要欄・15台→15大・トワロー→とある男が授業をしてみた 等）は画面では必ず正しい字に直す（全本で実施）。テロップは声の単語の頭と同じコマ前後で出し、声が終わってから少し残して消す',
      how='テロップの出−声の単語の頭（中央・±3コマの割合）・テロップの消え−単語の終わり（中央）。作業AIの1本は moji_check（台本と声の聞き直しで数・固有名詞の食い違い0）も合わせて見る',
      m=[('a_telop_sync_med_f', 'テロップの出−単語の頭（中央）', 'コマ'), ('a_telop_sync_in3f', '±3コマに入る割合', ''), ('a_telop_out_med_f', 'テロップの消え−単語の終わり（中央）', 'コマ'),
         ('a_moji_ng', '数字・固有名詞の食い違い', '件')]),
 dict(id='yobikake', name='視聴者への呼びかけ',
      what='問いを吹き出しや「？」の見出しで投げ、見る人に自分の数字や立場を思い浮かべさせる。行動のお願いは「〜してください!!」の言い切りにし、場所（概要欄・LINE）を黄色で強調、実際のスマホの操作を画面録画で見せる。CTAは軽い順（面談→無料→登録）か重い順に段をつけて3〜6か所',
      how='「？」の場面/10分・お願い（ください・しよう 等）の場面/10分・CTAの場面の数・最初のCTAの位置（長さに対する割合）・離脱を防ぐ仕掛けの数',
      m=[('k_question_per10', '問いかけ/10分', '回'), ('k_do_per10', 'お願いの言い切り/10分', '回'), ('k_cta_scenes', 'CTAの場面の数', '個'),
         ('k_cta_first_ratio', '最初のCTAの位置（長さの割合）', ''), ('k_retention_n', '離脱を防ぐ仕掛け（video_marketing）', '個')]),
 dict(id='koe', name='声の編集（ジャンプカット・話速）',
      what='言いかけ・言い直し・つなぎ言葉は切り、声の間は中央0.1秒前後まで詰める。0.3秒以上の間は結論の先出し・手順・まとめの直後にだけ残す。速さは場面ごとではなく動画全体で1つの倍率（話している間 約10字/秒＝普通の約1.3〜1.4倍）',
      how='話している間の字/秒・全体の倍率の見立て・0.3秒以上の間/分',
      m=[('n_cps', '話している間の字/秒', '字'), ('n_speedup', '全体の倍率（見立て）', '倍'), ('n_pause03_pm', '0.3秒以上の間/分', '回'), ('x_pause_at_key', '長い間が言い切り・まとめの直後にある割合', '')]),
]

KEYS = {k for kd in KANTEN for k, _, _ in kd['m']} | {'u_sel_digest'}


def build(per_dir, skip=()):
    """skip＝答えを見ない練習に取っておく本（kata/holdout.txt）。基準に混ぜない"""
    rows = {}
    for f in sorted(glob.glob(os.path.join(per_dir, '*.json'))):
        if os.path.basename(f)[:-5] in skip: continue
        try: d = json.load(open(f))
        except Exception: continue
        vid = os.path.basename(f)[:-5]; v = from_per_full(d)
        for (u, k) in UNSURE:
            if u == vid: v.pop(k, None)
        rows[vid] = (d.get('channel'), v, fmt_of(d))
    def dist_of(vals):
        dist = {}
        for k in KEYS:
            xs = sorted(v[k] for v in vals if isinstance(v.get(k), (int, float)))
            if not xs: continue
            q = lambda p: xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
            dist[k] = {'n': len(xs), 'p10': round(q(0.1), 3), 'p25': round(q(0.25), 3), 'p50': round(statistics.median(xs), 3), 'p75': round(q(0.75), 3), 'p90': round(q(0.9), 3),
                       'min': round(xs[0], 3), 'max': round(xs[-1], 3)}
        return dist
    fmts = collections.Counter(f_ for _, _, f_ in rows.values())
    return {'n_videos': len(rows), 'channels': sorted({c for c, _, _ in rows.values() if c}), 'dist': dist_of([v for _, v, _ in rows.values()]),
            'formats': {f_: sorted(i for i, r in rows.items() if r[2] == f_) for f_ in fmts},
            'by_format': {f_: {'n': n_, 'dist': dist_of([v for _, v, ff in rows.values() if ff == f_])} for f_, n_ in fmts.items()},
            'unsure': [{'id': u, 'key': k, 'why': w} for (u, k), w in UNSURE.items() if u in rows],
            'per_video': {i: {'channel': c, 'format': f_, **{k: round(x, 3) for k, x in v.items() if k in KEYS}} for i, (c, v, f_) in rows.items()}}


# 作業AIの1本では別の式で測る指標（見本の分布でなく固定の線で見る）
FIXED = {'a_moji_ng': (0, 0)}
# 片側だけ見る指標：'hi'＝大きいほど良い（10%より上なら満点）・'lo'＝小さいほど良い（90%より下なら満点）・'abs_lo'＝0に近いほど良い（絶対値が90%以下なら満点）
DIR = {'s_sfx_sync_in2f': 'hi', 'a_telop_sync_in3f': 'hi', 'p_recall_end': 'hi', 'k_retention_n': 'hi', 'v_height_px': 'hi', 'v_phone390_px': 'hi', 'v_contrast': 'hi',
       'v_small_share': 'lo', 'v_lowcontrast_share': 'lo', 'tr_first_proof_s': 'lo', 'p_answer_first_s': 'lo', 't_change_max_s': 'lo', 's_silence_p90_s': 'lo',
       'n_pause03_pm': 'lo', 's_sfx_sync_med_f': 'abs_lo'}


def score(vals, kj, tol=0.5):
    """指標の点：見本の10〜90%に入れば100、外れたら幅（p90−p10）の tol 倍で0まで下がる。観点の点＝測れた指標の平均。測れた指標が1つも無い観点は点なし"""
    out = []
    for kd in KANTEN:
        items = []
        for k, lab, unit in kd['m']:
            x = vals.get(k)
            if k in FIXED:
                lo, hi = FIXED[k]
            else:
                ds = kj['dist'].get(k)
                if not ds: items.append({'key': k, 'label': lab, 'value': x, 'band': None, 'pt': None, 'note': '見本の値なし'}); continue
                lo, hi = ds['p10'], ds['p90']
            dr = DIR.get(k)
            if dr == 'hi': hi = float('inf')
            elif dr == 'lo': lo = float('-inf')
            elif dr == 'abs_lo': lo, hi = -abs(hi), abs(hi)
            if x is None: items.append({'key': k, 'label': lab, 'value': None, 'band': [lo, hi], 'pt': None, 'note': '未測定'}); continue
            ds = kj['dist'].get(k) or {'p10': lo, 'p90': hi}
            span = max(ds['p90'] - ds['p10'], 1e-6, abs(ds['p90']) * 0.1)
            dd = 0 if lo <= x <= hi else (lo - x if x < lo else x - hi)
            pt = max(0.0, 100.0 * (1 - dd / (tol * span))) if dd else 100.0
            items.append({'key': k, 'label': lab, 'value': round(x, 3), 'band': [None if lo == float('-inf') else lo, None if hi == float('inf') else hi], 'pt': round(pt, 1)})
        got = [i['pt'] for i in items if i['pt'] is not None]
        out.append({'id': kd['id'], 'name': kd['name'], 'score': round(sum(got) / len(got), 1) if got else None, 'measured': len(got), 'of': len(items), 'items': items})
    return out


# ---- 本質のルール（外してはいけない）と 好みで変えてよい所（作業AIの指示 10/16・依頼主 00:35「答えはないが本質的なルールはある。その塩梅を」）
#   ルール：(キー, 向き, 言葉)。向き 'ge'＝線より下にしない／'le'＝線より上にしない／'in'＝両側の線の内に／'abs_le'＝0からのずれを線より大きくしない／'zero'＝0件
#   線は見本の本物から作る（build）。各ルールで、いちばん外れた1本だけを外して、残りが全部通る所（2番目に外れた本の値）に置く＝本物がほぼ全部通る線
#   点は「本質を守れているか」：守れていれば100、線を越えたら見本の幅（p90−p10）の半分で0まで下がる。観点の点＝その観点の本質ルールの平均
#   好みの指標は点に入れない（見本の幅と並べて参考に出すだけ）
HON = {
 'tempo': ([('t_changes_pm', 'ge', '画面を止めない（1分に一定以上は何かが変わる）'), ('t_change_med_s', 'le', '変化と変化の間を空けすぎない'),
            ('t_change_max_s', 'le', '同じ画面のまま長く置かない'),
            ('x_tr_clear_at_topic', 'ge', '話題が変わる所は全消しで区切る'), ('x_diagram_run_max_s', 'le', '図解ばかりを長く続けない')],
           'アニメーションの数・テロップの出入りの多さ・動いているコマの割合・同じ話題の中で足し算する割合・後半ほど速くするか・動きの種類（揺れ・ズーム・ぼかし…）と山の場面での増やし方（何で変化を作るかは台本しだい）'),
 'hook': ([('h_changes_pm', 'ge', '冒頭30秒を薄くしない'), ('h_sfx_pm', 'ge', '冒頭30秒に音の合図を入れる'),
          ('x_hook_first_q_s', 'le', '最初の問いを早く投げる')],
          '冒頭のアニメ・テロップの数・本編との比・最初の言い切りの秒（つかみを絵で作るか言葉で作るかは台本しだい）'),
 'visibility': ([('v_phone390_px', 'ge', 'スマホで読める大きさにする'), ('v_contrast', 'ge', '字を地に埋もれさせない'), ('v_chars', 'le', '1行を長くしない'),
                 ('v_chars_per_s', 'le', '読む速さを超えて字を出さない'), ('v_small_share', 'le', '小さすぎる行を増やさない'),
                 ('v_lowcontrast_share', 'le', '埋もれる行を増やさない')],
                '縁取りの太さ・表示秒・字の高さそのもの（座布団で浮かせるか縁で浮かせるか・何秒出すかは場面しだい）'),
 'wakariyasusa': ([('u_sel_full', 'le', '台本をそのまま貼りすぎない'), ('u_sel_digest', 'ge', '言い換え・要約・キーワードに整えて出す'),
                   ('u_diagram_share', 'ge', '図で見せる時間を作る'),
                   ('x_shape_match', 'ge', '図の形を話の形に合わせる（比較は左右・表、手順は流れ図、列挙は箇条）')],
                  '言い換え・要約・キーワードの配分・言い換えの回数・絵だけの場面の割合・図の形を書いた割合'),
 'shinrai': ([('tr_first_proof_s', 'le', '実績・証拠を早めに見せる'), ('tr_proof_per10', 'ge', '実績・証拠をくり返し見せる')],
             '実績の時間の長さ・実物（スクショ・実写）の割合（台本にある実績しだい）'),
 'kanjou': ([('e_updown_per10', 'ge', '上げ下げ（不安→救い）を作る'), ('x_emph_yama_ratio', 'ge', '強調は山・言い切りに集める')],
            '強調した場面の割合そのもの・否定・逆転の場面の数（0回の本物もある）・山の区間の数・山の見せ方（別世界の背景・金の明朝など）'),
 'oto': ([('s_sfx_pm', 'ge', '効果音で区切る'), ('s_sfx_sync_med_f', 'abs_le', '効果音を画面の変化に合わせる'),
          ('s_voice_minus_bg_db', 'ge', 'BGMで声を邪魔しない'), ('s_silence_med_s', 'le', '声の間を詰める'),
          ('x_sfx_role_consist', 'ge', '同じ役割には同じ効果音を使う')],
         '告知の頭でBGMを変えるか・効果音の種類の偏り・±2コマに入る割合・BGMの切り替えの回数・長い無音の残し方'),
 'sekaikan': ([('w_main_share', 'ge', '本編は1つの見た目で通す'), ('w_modes', 'le', '見た目の型を増やしすぎない'), ('w_accent_n', 'le', '差し色を増やしすぎない')],
              '役割ごとに同じ色で通す割合（本質の候補。作業AIの場面の記録に役割ごとの色が無く測れないので、色を記録してから本質に上げる）・言い切りに赤か金を使う割合・常に出しておくものの数・どの見た目にするか'),
 'yakusoku': ([('p_recall_end', 'ge', '冒頭の言葉を終わりで回収する')], '最初の答えの位置（本物でも最後まで答えを置かない本がある＝台本しだい）'),
 'shousetsu': ([('c_flow_n', 'ge', '区間に分けて見せる'), ('c_promo_share', 'le', '告知・CTAで本編を食わない'),
               ('x_order_score', 'ge', '話の順番を崩さない（つかみは頭・まとめは後ろ・告知で本編の真ん中を食わない・言い切りは前半）')],
               '長さ・区間の長さ・章のつなぎの数・告知を本編の前に置くか後ろに置くか'),
 'jimaku': ([('a_moji_ng', 'zero', '数字・固有名詞を間違えない'), ('a_telop_sync_med_f', 'in', 'テロップを声に合わせて出す（早すぎ・遅すぎにしない）'),
             ('a_telop_out_med_f', 'ge', '声が終わる前に消さない')],
            '±3コマに入る割合（測る道具の差が大きい）'),
 'yobikake': ([('k_do_per10', 'ge', '行動のお願いを言い切る'), ('k_cta_scenes', 'ge', 'CTAを置く'), ('k_retention_n', 'ge', '離脱を防ぐ仕掛けを置く')],
              '問いかけの数・最初のCTAの位置（前に置くか後ろに置くか）'),
 'koe': ([('n_cps', 'ge', '話を間延びさせない'), ('n_pause03_pm', 'le', '長い間を残しすぎない')], '全体の倍率（声の元の速さしだい）・長い間を置く場所（測れた見本が22本だけ）'),
}
HON_KEYS = {k for rs, _ in HON.values() for k, _, _ in rs}
LABEL = {k: (lab, unit) for kd in KANTEN for k, lab, unit in kd['m']}
LABEL['u_sel_digest'] = ('言い換え・要約・キーワードの割合', '')


def hon_lines(per_video, drop=1):
    """本質ルールの線：各ルールで外れた側から drop 本だけ外し、残りが全部通る値"""
    out = {}
    for rs, _ in HON.values():
        for k, dr, _w in rs:
            if dr == 'zero': out[k] = {'lo': None, 'hi': 0.0, 'n': None}; continue
            xs = sorted(v[k] for v in per_video.values() if isinstance(v.get(k), (int, float)))
            if len(xs) < 5: continue
            d = min(drop, len(xs) - 1)
            if dr == 'ge': out[k] = {'lo': xs[d], 'hi': None, 'n': len(xs)}
            elif dr == 'le': out[k] = {'lo': None, 'hi': xs[-1 - d], 'n': len(xs)}
            elif dr == 'in': out[k] = {'lo': xs[d], 'hi': xs[-1 - d], 'n': len(xs)}
            elif dr == 'abs_le':
                ab = sorted(abs(x) for x in xs); out[k] = {'lo': -ab[-1 - d], 'hi': ab[-1 - d], 'n': len(xs)}
    return out


def score_hon(vals, kj, tol=0.5):
    """本質ルールを守れているかで観点の点を出す。好みの指標は参考（点に入れない）"""
    L = kj.get('hon_lines') or {}; out = []
    for kd in KANTEN:
        rs, konomi = HON.get(kd['id'], ([], ''))
        items = []
        for k, dr, w in rs:
            x = vals.get(k); ln = L.get(k); lab = LABEL.get(k, (k, ''))[0]
            if not ln: items.append({'key': k, 'rule': w, 'label': lab, 'value': x, 'line': None, 'pt': None, 'kept': None, 'note': '見本の値なし'}); continue
            if x is None: items.append({'key': k, 'rule': w, 'label': lab, 'value': None, 'line': [ln['lo'], ln['hi']], 'pt': None, 'kept': None, 'note': '未測定'}); continue
            lo = -float('inf') if ln['lo'] is None else ln['lo']; hi = float('inf') if ln['hi'] is None else ln['hi']
            dd = 0 if lo <= x <= hi else (lo - x if x < lo else x - hi)
            ds = kj['dist'].get(k) or {'p10': 0, 'p90': 1}
            span = max(ds['p90'] - ds['p10'], 1e-6, abs(ds['p90']) * 0.1) if dr != 'zero' else 2.0
            pt = 100.0 if not dd else max(0.0, 100.0 * (1 - dd / (tol * span)))
            items.append({'key': k, 'rule': w, 'label': lab, 'value': round(x, 3), 'line': [ln['lo'], ln['hi']], 'pt': round(pt, 1), 'kept': not dd})
        got = [i['pt'] for i in items if i['pt'] is not None]
        out.append({'id': kd['id'], 'name': kd['name'], 'score': round(sum(got) / len(got), 1) if got else None, 'measured': len(got), 'of': len(items),
                    'broken': [i['rule'] for i in items if i['kept'] is False], 'items': items, 'konomi': konomi})
    return out


def hon_pass(res, line):
    """門：全観点に点があり、破った本質ルールが line['max_broken'] 以下、どの観点も line['each_min'] 以上"""
    sc = [r['score'] for r in res]; br = sum(len(r['broken']) for r in res)
    ok = None not in sc and br <= line['max_broken'] and min(sc) >= line['each_min']
    return ok, br, (round(sum(sc) / len(sc), 1) if None not in sc else None), (min(sc) if None not in sc else None)



def _better_or_equal(dr, x, ref):
    """本質ルールの向きで、x が ref と同じか良い側にあるか"""
    if dr == 'ge': return x >= ref - 1e-9
    if dr == 'le' or dr == 'zero': return x <= ref + 1e-9
    if dr == 'abs_le': return abs(x) <= abs(ref) + 1e-9
    return None


def reach_median(vals, kj, fmt='講義型'):
    """新しい合格②：13観点の全部で、手本の編集者さんの見本（同じ形式）の中央値以上。本質ルールの指標ごとに、ルールの向きで中央値と同じか良い側か。
    'in'（テロップの出のずれ）は中央値からの離れが見本の半分の幅（p25〜p75の半分）以内"""
    dist = ((kj.get('by_format') or {}).get(fmt) or {}).get('dist') or kj['dist']; out = []
    for kd in KANTEN:
        rs, _ = HON.get(kd['id'], ([], '')); items = []
        for k, dr, w in rs:
            x = vals.get(k); ds = dist.get(k)
            if dr == 'zero': ok = (x == 0) if x is not None else None; med = 0
            elif x is None or not ds: ok, med = None, (ds or {}).get('p50')
            elif dr == 'in':
                med = ds['p50']; ok = abs(x - med) <= max(1e-6, (ds['p75'] - ds['p25']) / 2)
            else:
                med = ds['p50']; ok = _better_or_equal(dr, x, med)
            items.append({'key': k, 'rule': w, 'label': LABEL.get(k, (k, ''))[0], 'value': None if x is None else round(x, 3), 'median': med, 'reached': ok})
        got = [i for i in items if i['reached'] is not None]
        out.append({'id': kd['id'], 'name': kd['name'], 'reached': all(i['reached'] for i in got) if got and len(got) == len(items) else (False if any(i['reached'] is False for i in got) else None),
                    'short': [i for i in items if i['reached'] is False], 'unmeasured': [i['rule'] for i in items if i['reached'] is None], 'items': items})
    return out


def vs_answer(vals, ans):
    """新しい合格③：答え（元の動画）と並べて、どの観点でも答えより下にならない。本質ルールの指標ごとに向きで比べる"""
    out = []
    for kd in KANTEN:
        rs, _ = HON.get(kd['id'], ([], '')); items = []
        for k, dr, w in rs:
            x, a = vals.get(k), ans.get(k)
            if x is None or a is None or dr == 'in': ok = None
            else: ok = _better_or_equal(dr, x, a)
            items.append({'key': k, 'rule': w, '作業AI': None if x is None else round(x, 3), '答え': None if a is None else round(a, 3), 'not_below': ok})
        got = [i for i in items if i['not_below'] is not None]
        out.append({'id': kd['id'], 'name': kd['name'], 'not_below': (all(i['not_below'] for i in got) if got else None), 'below': [i for i in items if i['not_below'] is False], 'items': items})
    return out


def _good_share(k, dr, x, xs, med=None):
    """x が手本の編集者さんの本（xs）の何割より良い側か（0〜100）。向きは本質ルールのもの。同じ値は半分に数える"""
    if dr == 'ge': worse = sum(1 for y in xs if y < x); tie = sum(1 for y in xs if y == x)
    elif dr == 'le': worse = sum(1 for y in xs if y > x); tie = sum(1 for y in xs if y == x)
    elif dr == 'abs_le': worse = sum(1 for y in xs if abs(y) > abs(x)); tie = sum(1 for y in xs if abs(y) == abs(x))
    elif dr == 'in':
        d = abs(x - med); worse = sum(1 for y in xs if abs(y - med) > d); tie = sum(1 for y in xs if abs(y - med) == d)
    else: return None
    return 100.0 * (worse + 0.5 * tie) / len(xs)


def kanten_pct(vals, ref, skip_self=None):
    """観点の点（手本の編集者さんの講義型の本と比べた位置・0〜100）：本質ルールの指標ごとに、手本の編集者さんの本の何割より良い側かを出し、観点で平均。
    数字・固有名詞の食い違い（0件の線）は①で見るので点に入れない。skip_self＝手本の編集者さん自身の本を測るときは自分を外して比べる"""
    out = {}
    for kd in KANTEN:
        rs, _ = HON.get(kd['id'], ([], '')); got = []
        for k, dr, _w in rs:
            if dr == 'zero': continue
            x = vals.get(k); src = ref['vals'].get(k)
            if x is None or not src: continue
            xs = [y for i, y in src if i != skip_self]
            if len(xs) < 5: continue
            got.append(_good_share(k, dr, x, xs, ref['med'].get(k)))
        out[kd['id']] = round(sum(got) / len(got), 1) if got else None
    return out


def joui_ref(pv):
    """新しい合格②の物差し（10/16 作業AIの指示）：手本の編集者さん本人の講義型の本（pv）から
    観点ごとの点の下から4分の1（p25）と、13観点を合わせた点の中央値を出す。手本の編集者さんの本の点は自分を外して比べる"""
    ref = {'vals': {}, 'med': {}}
    for rs, _ in HON.values():
        for k, dr, _w in rs:
            xs = [(i, v[k]) for i, v in pv.items() if isinstance(v.get(k), (int, float))]
            if xs: ref['vals'][k] = xs; ref['med'][k] = statistics.median(x for _, x in xs)
    rows = {i: kanten_pct(v, ref, skip_self=i) for i, v in pv.items()}
    p25 = {}
    for kd in KANTEN:
        xs = sorted(r[kd['id']] for r in rows.values() if r.get(kd['id']) is not None)
        if xs: p25[kd['id']] = round(_q(xs, 0.25), 1)
    sums = sorted(sum(r.values()) for r in rows.values() if None not in r.values())
    # 下から4分の1を割ってよい観点の数 k：手本の編集者さん本人の本の8割以上がこの条件を満たす最小の数（10/16 作業AIの指示）
    nb = sorted(sum(1 for kd in KANTEN if r.get(kd['id']) is not None and kd['id'] in p25 and r[kd['id']] < p25[kd['id']] - 1e-9) for r in rows.values())
    k_ok = next((k for k in range(len(KANTEN) + 1) if sum(1 for x in nb if x <= k) >= 0.8 * len(nb)), len(KANTEN)) if nb else 0
    # 13観点の合計の線（10/16 作業AIの指示「手本の編集者さん本人の講義型の8割が②を満たす値まで下げる」）：k 個までの条件を満たす本の中で、
    # 合計を高い順に並べ、本人の本の8割（切り上げ）が通る いちばん高い値。中央値（sum_med）は参考に残す
    need = -(-len(rows) * 8 // 10)
    okk = sorted((sum(r.values()) for r in rows.values() if None not in r.values() and
                  sum(1 for kd in KANTEN if kd['id'] in p25 and r[kd['id']] < p25[kd['id']] - 1e-9) <= k_ok), reverse=True)
    sum_line = round(okk[need - 1], 1) if len(okk) >= need else (round(okk[-1], 1) if okk else None)
    ref.update({'p25': p25, 'k': k_ok, 'sum_med': round(_q(sums, 0.5), 1) if sums else None, 'sum_line': sum_line, 'sum_line_n': min(len(okk), need), 'n': len(pv), 'n_sum': len(sums),
                'rows': {i: {'kanten': r, 'sum': (round(sum(r.values()), 1) if None not in r.values() else None)} for i, r in rows.items()}})
    return ref


def _q(xs, q):
    """分位点（線形補間）"""
    if len(xs) == 1: return xs[0]
    pos = q * (len(xs) - 1); lo = int(pos); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def reach_joui(vals, kj, skip_self=None):
    """新しい合格②（10/16 作業AIの指示）：手本の編集者さん本人の講義型の本の下から4分の1（p25）を割る観点が k 個まで
    （k＝本人の本の8割がこれを満たす最小の数）、かつ 13観点を合わせた点が 手本の編集者さん本人の中央値以上"""
    ref = kj.get('joui')
    if not ref: return None
    pc = kanten_pct(vals, ref, skip_self)
    rows = [{'id': kd['id'], 'name': kd['name'], 'score': pc.get(kd['id']), 'p25': ref['p25'].get(kd['id']),
             'reached': (None if pc.get(kd['id']) is None or ref['p25'].get(kd['id']) is None else pc[kd['id']] >= ref['p25'][kd['id']] - 1e-9)} for kd in KANTEN]
    tot = None if any(r['score'] is None for r in rows) else round(sum(r['score'] for r in rows), 1)
    line = ref.get('sum_line', ref.get('sum_med'))   # 合計の線は 本人の本の8割が②を満たす値（sum_line）。古い物差しは中央値
    ok_sum = None if tot is None or line is None else tot >= line - 1e-9
    k = ref.get('k', 0); nshort = sum(1 for r in rows if r['reached'] is not True)
    return {'pass': nshort <= k and all(r['reached'] is not None for r in rows) and ok_sum is True, 'k': k, 'n_short': nshort, 'rows': rows, 'sum': tot, 'sum_med': ref.get('sum_med'), 'sum_line': line, 'sum_ok': ok_sum,
            'short': [r['name'] for r in rows if r['reached'] is not True]}


def gate(vals, kj, fmt='講義型', ans=None, skip_self=None, ans_id=None):
    """新しい合格（10/16 依頼主「60点は下位互換」→ 完コピか上位互換）：①本質ルールの破り0
    ②観点ごとに手本の編集者さん本人の講義型の本の下から4分の1より上、かつ13観点を合わせた点が手本の編集者さん本人の中央値以上（reach_joui・10/16 作業AIの指示）
    ③答えがあれば、どの観点でも答えより下にならない。'median'（指標ごとに中央値に届いたか）は直す所を探す手がかりとして残す"""
    hon = score_hon(vals, kj); med = reach_median(vals, kj, fmt); va = vs_answer(vals, ans) if ans else None
    if va is not None and kj.get('joui'):
        # ③ は観点の点で比べる（10/16 作業AIの指示「同じ台本の手本の編集者さんの答えより、どの観点でも下にならない」）。指標ごとの比べは直す所の手がかりに残す
        mine, theirs = kanten_pct(vals, kj['joui']), kanten_pct(ans, kj['joui'], ans_id)
        for r in va:
            r['作業AIの点'], r['答えの点'] = mine.get(r['id']), theirs.get(r['id'])
            r['not_below'] = None if r['作業AIの点'] is None or r['答えの点'] is None else r['作業AIの点'] >= r['答えの点'] - 1e-9
    broken = sum(len(r['broken']) for r in hon)
    # ①（10/16 作業AIの判断）：破りは max_broken 個まで（手本の編集者さん本人34本の88%が通る線）。ただし本人が1本も破っていない観点を破ったら1個でも不合格。
    # 破ったものは観点・指標・値・線を必ず出す（黙って通さない）
    # 外の線（hon_lines_outer＝本人のいちばん外れた1本の値）より外れたら、本人の誰よりも悪い＝破りの数に関係なく不合格
    mx = kj.get('hon_max_broken', 0); OUT = kj.get('hon_lines_outer') or {}
    def beyond(k, x):
        ln = OUT.get(k)
        if not ln or x is None: return False
        return (ln['lo'] is not None and x < ln['lo'] - 1e-9) or (ln['hi'] is not None and x > ln['hi'] + 1e-9)
    detail = [{'観点': r['name'], 'ルール': i['rule'], '指標': i['label'], '値': i['value'], '線': i['line'],
               '外の線': [(OUT.get(i['key']) or {}).get('lo'), (OUT.get(i['key']) or {}).get('hi')], '本人の誰より悪い': beyond(i['key'], vals.get(i['key']))}
              for r in hon for i in r['items'] if i['kept'] is False]
    g1 = broken <= mx and not any(d['本人の誰より悪い'] for d in detail) and all(r['score'] is not None for r in hon)
    jo = reach_joui(vals, kj, skip_self)
    g2 = jo['pass'] if jo else all(r['reached'] is True for r in med)   # 物差しが無い古い基準のときだけ前の形（全観点で中央値以上）
    g3 = None if va is None else all(r['not_below'] is not False for r in va)
    short = jo['short'] if jo else [r['name'] for r in med if r['reached'] is not True]
    return {'pass': g1 and g2 and (g3 is not False), '①破り0': g1, '①破り': g1, '破り': broken, '破りの中身': detail, '破りの上限': mx, '②上位互換': g2, '②中央値以上': g2, '②': jo,
            '届かない観点': short, '中央値に届かない観点': short, '③答えより下でない': g3,
            '答えより下の観点': [r['name'] for r in va if r['not_below'] is False] if va else None, 'hon': hon, 'median': med, 'vs_answer': va}
