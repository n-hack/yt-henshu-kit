#!/usr/bin/env python3
# 質の門：書き出した動画を見本と同じ式で測り、kijun.json の幅に入っているか調べる。1つでも外れたら不合格（終了コード1）
#   python3 check.py <プロジェクト> [動画]   → out/check.json・out/hikaku.tsv（見本 vs 今回）
import os, sys, json, wave, numpy as np
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'); sys.path.insert(0, LIB)
import paths, metrics as HM
K = json.load(open(paths.KIJUN)); F = K['frame']
MEAS = json.load(open(os.path.join(paths.ENGINE, 'kata', 'kijun_measured.json')))['by_win']
def rd(p, sr=48000):
    """声のファイルを float で読む（16bit・24bit・32bit どれでも。粗い声の編集は 24bit で書き出すため ffmpeg で読む）"""
    import subprocess
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True, check=True).stdout, np.float32).copy()
    return y, sr
def nearest(ev, t): 
    if len(ev) == 0: return None
    k = np.argmin(abs(ev - t)); return float(ev[k] - t)
def main(proj, video=None):
    W = os.path.join(proj, 'work'); O = os.path.join(proj, 'out')
    meta = json.load(open(os.path.join(W, 'story_meta.json'))); TJ = json.load(open(os.path.join(W, 'timing.json')))
    placed = json.load(open(os.path.join(W, 'sfx_placed.json')))
    video = video or os.path.join(O, os.path.basename(proj.rstrip('/')) + '.mp4')
    y, sr = rd(os.path.join(W, 'vocals.wav')); D = meta['end']
    res = []; NG = []
    def judge(name, val, ok, rule, ref=''):
        res.append({'項目': name, '今回': val, '基準': rule, '見本': ref, '合否': '合格' if ok else '不合格'})
        if not ok: NG.append('%s：今回 %s ／ 基準 %s' % (name, val, rule))
    # ① 声の時刻の正確さ：行の頭（無音のあと）の時刻が、声の実際の立ち上がりから2コマ以内か
    on = HM.voice_onsets(y, sr)
    d1 = [nearest(on, TJ['starts'][int(i)]) for i in TJ['line0'].values()]
    d1 = [x for x in d1 if x is not None and abs(x) <= 0.4]
    worst = max(abs(x) for x in d1) if d1 else 9
    judge('① 行の頭の時刻（声の立ち上がりとの差の最大）', round(worst, 3), worst <= 2 * F, '≤ %.3f 秒（2コマ）' % (2 * F))
    # 全体の画面の変化（30fps）
    ev, d = HM.changes(video, 0, D)
    # 部品・効果音の当たり判定は「そのコマで差が跳ね上がったか」（直前5コマの中央値より 0.08 以上大きい）で見る＝背景が動いていても拾える
    base = np.array([np.median(d[max(0, i - 5):i]) if i else 0 for i in range(len(d))])
    ev_lo = np.array([(i + 1) / HM.FPS for i in range(1, len(d)) if d[i] - base[i] > 0.08 and not (d[i - 1] - base[i - 1] > 0.08)])
    # ① 部品が描かれるコマ：部品の四角の中だけの差で「描かれ始めたコマ」を測り、予定の秒との差が±2コマか
    import subprocess
    GW, GH = 480, 270
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', 'scale=%d:%d' % (GW, GH), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    FR = np.frombuffer(raw, np.uint8).reshape(-1, GH, GW)
    sx, sy = GW / 1920, GH / 1080
    def drawn_at(ts, box):
        x0, y0, x1, y1 = int(box[0] * sx), int(box[1] * sy), max(int(box[2] * sx), int(box[0] * sx) + 2), max(int(box[3] * sy), int(box[1] * sy) + 2)
        i0 = int(round(ts * HM.FPS))
        for i in range(max(1, i0 - 4), min(len(FR), i0 + 12)):
            dd = np.abs(FR[i, y0:y1, x0:x1].astype(np.int16) - FR[i - 1, y0:y1, x0:x1].astype(np.int16)).mean()
            if dd > 1.0: return i / HM.FPS - ts
        return None
    offs = []; miss = []; skip = 0
    scs = np.array(meta['scenes']); BX = meta.get('boxes', [])
    def busy(b_):
        # 場面の頭（場面ごと切り替わる＝画面全体の変化で別に確かめる）か、同じ所で直前に別の部品が消える／出るときは四角の差では測れない
        ts = b_[0]
        if len(scs) and np.min(np.abs(scs - ts)) <= 0.3: return True
        for o in BX:
            if o is b_: continue
            ov = not (o[3] <= b_[1] or o[1] >= b_[3] or o[4] <= b_[2] or o[2] >= b_[4])
            if ov and ((o[6] and -0.35 <= o[6] - ts <= 0.15) or (0 < abs(o[0] - ts) <= 0.3)): return True
        return False
    for b_ in BX:
        ts = b_[0]
        if not (0.3 < ts < D - 0.3) or b_[5] == 'none': continue
        if busy(b_): skip += 1; continue
        o = drawn_at(ts, b_[1:5])
        if o is None or abs(o) > 2 * F + 0.001: miss.append((ts, o))
        else: offs.append(o)
    n_all = len(offs) + len(miss); r = len(offs) / n_all if n_all else 0
    judge('① 部品が描かれ始めたコマ（予定の秒±2コマの割合・%d個／場面の頭や重なり %d個は次の項目）' % (n_all, skip), round(r, 3), r >= 0.95, '≥ 0.95（部品の四角の中の差で測る）')
    sh = [nearest(ev_lo, t) for t in meta['scenes'] if 0.3 < t < D - 0.3]; sh = [x for x in sh if x is not None]
    r_s = float(np.mean([abs(x) <= 2 * F + 0.001 for x in sh])) if sh else 0
    judge('① 場面の頭（予定の秒±2コマで画面が変わった割合）', round(r_s, 3), r_s >= 0.95, '≥ 0.95')
    json.dump({'外れた部品': [[round(a, 3), (round(b, 3) if b is not None else None)] for a, b in miss]}, open(os.path.join(O, 'check_buhin.json'), 'w'), ensure_ascii=False)
    DRAWN = {round(b_[0], 3): drawn_at(b_[0], b_[1:5]) for b_ in BX if b_[5] != 'none' and not busy(b_)}
    # ① テロップと声のずれ（見本と同じ測り方）
    tv = [nearest(ev, o) for o in on]; tv = np.array([x for x in tv if x is not None and abs(x) <= 0.5])
    mt = float(np.median(tv)) if len(tv) else 9
    judge('① 画面の変化−声の立ち上がり（中央値）', round(mt, 3), abs(mt - K['telop']['offset_target']) <= K['telop']['tol'],
          '%.3f ± %.3f 秒' % (K['telop']['offset_target'], K['telop']['tol']), 'p25〜p75 %s〜%s' % (MEAS['mid']['telop_offset']['p25'], MEAS['mid']['telop_offset']['p75']))
    # ② 効果音：置いた効果音の±2コマに画面の変化があるか・中央値
    st = [t for t, k in placed]
    # 効果音は同じ秒に置いた部品が描かれ始めたコマと比べる（部品の無い効果音は画面の変化と比べる）
    so = []; smiss = []
    for t, k in placed:
        o = DRAWN.get(round(t, 3))
        x = (t - (t + o)) if o is not None else nearest(ev_lo, t)
        if x is None: continue
        so.append(x)
        if abs(x) > 2 * F + 0.001: smiss.append([round(t, 3), k, round(x, 3), 'buhin' if o is not None else 'gamen'])
    so = np.array(so)
    bj = os.path.join(O, 'check_buhin.json'); J_ = json.load(open(bj)); J_['外れた効果音'] = smiss; json.dump(J_, open(bj, 'w'), ensure_ascii=False)
    r2 = float(np.mean(abs(so) <= 2 * F + 0.001)) if len(so) else 0
    judge('② 効果音の位置（部品が描かれ始めたコマから±2コマの割合）', round(r2, 3), r2 >= 0.95, '≥ 0.95')
    ms = float(np.median(so[abs(so) <= 0.3])) if len(so) else 9
    judge('② 効果音−画面の変化（中央値）', round(ms, 3), abs(ms - K['sfx']['offset_target']) <= K['sfx']['tol'], '%.3f ± %.3f 秒' % (K['sfx']['offset_target'], K['sfx']['tol']),
          'p25〜p75 %s〜%s' % (MEAS['mid']['sfx_offset']['p25'], MEAS['mid']['sfx_offset']['p75']))
    # 区間ごと（③⑤⑥⑦⑧）
    WINS = [('hook30', 0, min(30, D)), ('hook', 0, min(90, D)), ('mid', max(0, D / 2 - 30), min(D, D / 2 + 30)), ('end', max(0, D - 45), D - 0.3)]
    ma = sum(1 for x in TJ['lines'] if '【間】' in x['text'])
    for name, a, b in WINS:
        m = HM.window_metrics(video, a, b, y, sr, 0.0, st); M = MEAS[name]
        judge('⑦ 画面の切り替わり/分 [%s]' % name, m['changes_pm'], K['changes_pm']['min'][name] <= m['changes_pm'] <= K['changes_pm']['max'][name],
              '%s〜%s' % (K['changes_pm']['min'][name], K['changes_pm']['max'][name]), '中央 %s' % M['changes_pm']['p50'])
        judge('⑦ 止まった画面の最長 [%s]' % name, m['longest_static'], m['longest_static'] <= K['longest_static']['max'][name], '≤ %s 秒' % K['longest_static']['max'][name], '中央 %s' % M['longest_static']['p50'])
        judge('⑤ 動いているコマの割合 [%s]' % name, m['motion_share'], m['motion_share'] >= K['motion']['share_min'][name], '≥ %s' % K['motion']['share_min'][name], '中央 %s' % M['motion_share']['p50'])
        judge('② 効果音/分 [%s]' % name, m['sfx_pm'], K['sfx_pm']['min'][name] <= m['sfx_pm'] <= K['sfx_pm']['max'][name], '%s〜%s' % (K['sfx_pm']['min'][name], K['sfx_pm']['max'][name]), '中央 %s' % M['sfx_pm']['p50'])
        pz = np.array(m['pauses']); pm = len(pz) / m['dur'] * 60
        judge('⑥ 声の無音の数/分 [%s]' % name, round(pm, 1), pm <= K['pause']['pm_max'][name] + ma, '≤ %s（＋【間】%d）' % (K['pause']['pm_max'][name], ma), '中央 %s' % M['pauses_pm']['p50'])
        if len(pz):
            p50, p90 = float(np.percentile(pz, 50)), float(np.percentile(pz[pz < K['pause']['ma_keep'] - 0.05], 90)) if (pz < K['pause']['ma_keep'] - 0.05).any() else 0
            judge('⑥ 無音の長さ 中央 [%s]' % name, round(p50, 3), p50 <= K['pause']['p50_max'], '≤ %s' % K['pause']['p50_max'], '中央 %s' % M['pause_len']['p50'])
            judge('⑥ 無音の長さ 90%%（【間】を除く）[%s]' % name, round(p90, 3), p90 <= K['pause']['p90_max'], '≤ %s' % K['pause']['p90_max'], '90%% %s' % M['pause_len']['p90'])
        if name == 'hook30':
            judge('⑧ 冒頭30秒の切り替わり/分', m['changes_pm'], m['changes_pm'] >= K['hook30_density']['changes_pm_min'], '≥ %s（見本の中央値）' % K['hook30_density']['changes_pm_min'])
            judge('⑧ 冒頭30秒の効果音/分', m['sfx_pm'], m['sfx_pm'] >= K['hook30_density']['sfx_pm_min'], '≥ %s' % K['hook30_density']['sfx_pm_min'])
    # ③ 場面の長さ
    sc = np.diff(np.array(meta['scenes'] + [D])); 
    judge('③ 1場面の長さ 中央（秒）', round(float(np.median(sc)), 2), 1.6 <= float(np.median(sc)) <= 6.2, '1.6〜6.2（見本 25〜75%）', '冒頭3.3・本編4.8・締め2.5')
    # ⑧ 訴求の理由が全場面にあるか
    miss = [i['t'] for i in meta['intent'] if not i.get('intent')]
    judge('⑧ 場面の訴求の記入', len(meta['intent']) - len(miss), not miss and len(meta['intent']) > 0, '全場面')
    # ⑪ テロップの選び方：台本を全部テロップで出していないか（全文の割合・連続）
    sel = meta.get('selection', [])
    if sel:
        fs = sum(1 for x in sel if x['kind'] == '全文') / len(sel); run = mx = 0
        for x in sel:
            run = run + 1 if x['kind'] == '全文' else 0; mx = max(mx, run)
        TS = K['telop_selection']
        judge('⑪ 全文テロップの場面の割合', round(fs, 2), fs <= TS['full_share_max'], '≤ %s' % TS['full_share_max'])
        judge('⑪ 全文テロップの場面の連続', mx, mx <= TS['full_run_max'], '≤ %s 場面' % TS['full_run_max'])
    else:
        judge('⑪ テロップの選び方の記録', 'なし', False, '場面ごとの selection（story_meta.json）')
    # ⑪ 台本の行ごとの判断：どこを出す・出さない・言い換える・足すか と理由（draft.py の sel・依頼主 10/15 09:36 絶対ルール）
    sp_ = meta.get('selection_plan', [])
    nl = len(TJ['lines']); ok_sp = [x for x in sp_ if x.get('kind') and x.get('why') and 'TODO' not in x.get('why', '')]
    judge('⑪ 台本の行ごとのテロップの判断（選び方と理由）', '%d / %d 行' % (len(ok_sp), nl), len(ok_sp) >= nl, '全行（出す・出さない・言い換え・足す と理由）')
    # ⑪ 前後のつながりを理由にしたか：行ごとに 強調・切り替え・前後のどの行につながるか（link）・流れの区間（flow）が書かれているか（依頼主 20:3x「文脈理解をマーケター目線で」）
    ok_ctx = [x for x in sp_ if x.get('link') and x.get('cut') and 'emphasis' in x and x.get('flow') and 'TODO' not in x.get('link', '')]
    judge('⑪ 行ごとの判断が前後のつながりと流れを理由にしているか（強調・間・切り替え・link・flow）', '%d / %d 行' % (len(ok_ctx), nl), len(ok_ctx) >= nl, '全行')
    emp = [x for x in sp_ if x.get('emphasis') == '強']
    judge('⑪ 強調の数（全部を強くしない・山場が埋もれない）', '%d / %d 行' % (len(emp), nl), 1 <= len(emp) <= max(2, int(0.35 * nl)), '1行以上・35%以下')
    # ⑫ 1本の流れ（video_marketing.json）：依頼主 10/15 19:55「動画1本単位でちゃんとマーケター目線で分析」。見本の per_full と同じ門（lib/vm_check.py）
    import vm_check
    vp = os.path.join(proj, 'video_marketing.json')
    vf = vm_check.fails(json.load(open(vp)) if os.path.exists(vp) else None, D, make=True)
    judge('⑫ 1本の流れ（video_marketing：target・promise・hook・flow・retention・cta・why_it_works・reusable）', '外れ %d' % len(vf), not vf, '外れ 0（%s）' % '；'.join(vf[:3]) if vf else '外れ 0')
    # ⑨ 音は元の編集者さんのものだけ：使った効果音・BGM が素材集にあり、出どころ（index.tsv の動画id）が見本の動画であること
    su = json.load(open(os.path.join(W, 'sound_used.json')))
    idx_se = os.path.join(su['se_dir'], 'index.tsv'); idx_bgm = os.path.join(su['sozai'], 'bgm', 'index.tsv')
    known = set()
    for ip in (idx_se, idx_bgm):
        if os.path.exists(ip):
            for l in open(ip).read().splitlines()[1:]:
                c_ = l.split('\t')
                if len(c_) > 1: known.add(c_[1].strip())
    used_kinds = {k for _, k in placed}
    bad = [su['se'][k] for k in used_kinds if su['se'].get(k) not in known]
    bad += [b for b in su['bgm'] if os.path.basename(b) not in known]
    judge('⑨ 音はすべて元の編集者さんの素材（出どころの記録あり）', '外れ %d' % len(bad), not bad, '外れ 0（%s）' % ', '.join(bad[:5]) if bad else '外れ 0')
    # ⑩ 書き出した mp4 そのものの整合性
    import subprocess
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', video], capture_output=True, text=True).stdout)
    vs = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]; as_ = [s for s in pr['streams'] if s['codec_type'] == 'audio'][0]
    rate_ok = vs.get('r_frame_rate') == '30000/1001' and vs.get('avg_frame_rate') == '30000/1001'
    judge('⑩ フレームレート（固定 29.97・混在なし）', '%s / %s' % (vs.get('r_frame_rate'), vs.get('avg_frame_rate')), rate_ok, '30000/1001 と 30000/1001')
    vd, ad = float(vs['duration']), float(as_['duration'])
    judge('⑩ 映像と音声の長さの差', round(abs(vd - ad), 3), abs(vd - ad) <= F + 0.001, '≤ 1コマ（%.3f 秒）' % F)
    # mp4 の音声と編集後の声を、頭・真ん中・最後で突き合わせる（ずれ・後ろに行くほど溜まるずれ）
    def dec(p, sr=8000):
        return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
    A = dec(video); V = dec(os.path.join(W, 'vocals.wav')); sr = 8000
    lags = []
    for c0 in (8.0, D / 2, D - 20.0):
        a0, a1 = int(c0 * sr), int((c0 + 12) * sr)
        x = V[a0:a1]; best = (-1, 0)
        for lag in range(-int(0.5 * sr), int(0.5 * sr) + 1, 8):
            y_ = A[a0 + lag:a1 + lag]
            if len(y_) != len(x): continue
            cc = float(np.dot(x, y_) / (np.linalg.norm(x) * np.linalg.norm(y_) + 1e-9))
            if cc > best[0]: best = (cc, lag)
        lag = best[1]
        for l2 in range(lag - 8, lag + 9):   # 1サンプル単位で詰める
            y_ = A[a0 + l2:a1 + l2]
            if len(y_) == len(x):
                cc = float(np.dot(x, y_) / (np.linalg.norm(x) * np.linalg.norm(y_) + 1e-9))
                if cc > best[0]: best = (cc, l2)
        lags.append(best[1] / sr)
    judge('⑩ mp4 の声のずれ（頭・真ん中・最後）', ' / '.join('%+.3f' % l for l in lags), max(abs(l) for l in lags) <= F / 2, '各 ≤ 半コマ（%.3f 秒）' % (F / 2))
    judge('⑩ 後ろに行くほど溜まるずれ（最後−頭）', round(lags[-1] - lags[0], 3), abs(lags[-1] - lags[0]) <= F / 2, '0 コマ（≤ %.3f 秒）' % (F / 2))
    # 映像側：場面の頭（予定）と mp4 で画面が変わったコマの差を、頭・真ん中・最後の3つに分けて比べる
    sh_all = [(t, nearest(ev_lo, t)) for t in meta['scenes'] if 0.3 < t < D - 0.3]
    parts = [[o for t, o in sh_all if o is not None and lo_ <= t < hi_ and abs(o) <= 0.2] for lo_, hi_ in ((0, D / 3), (D / 3, 2 * D / 3), (2 * D / 3, D))]
    meds = [float(np.median(p)) if p else 9 for p in parts]
    judge('⑩ 映像のずれ（場面の頭・頭／真ん中／最後の中央値）', ' / '.join('%+.3f' % m for m in meds), max(abs(m) for m in meds) <= F + 0.001, '各 ≤ 1コマ')
    judge('⑩ 映像の溜まるずれ（最後−頭）', round(meds[-1] - meds[0], 3), abs(meds[-1] - meds[0]) <= F / 2 + 0.001, '0 コマ（≤ 半コマ）')
    os.makedirs(O, exist_ok=True)
    # ⑬ 音量（抜けE）：1本全体の LUFS・声と声以外（BGM＋効果音）の差・ピーク。見本の stems と同じ分け方（lib/loud.py）で測る
    import loud
    LK = K.get('loudness')
    if LK:
        lm = loud.measure_video(video, os.path.join(W, 'vocals.wav'))
        judge('⑬ 1本全体の大きさ（LUFS）', lm['I'], lm['I'] is not None and LK['I_min'] - 1 <= lm['I'] <= LK['I_max'] + 1, '%s〜%s（見本 10〜90%%・±1）' % (LK['I_min'], LK['I_max']), '中央 %s' % LK['I_median'])
        judge('⑬ 声と声以外の差（dB・声が上）', lm['diff'], lm['diff'] is not None and LK['diff_min'] <= lm['diff'] <= LK['diff_max'], '%s〜%s（見本 10〜90%%）' % (LK['diff_min'], LK['diff_max']), '中央 %s' % LK['diff_median'])
        judge('⑬ ピーク（割れない）', lm['peak'], lm['peak'] <= LK['peak_max'], '≤ %s dBFS' % LK['peak_max'])
    else:
        judge('⑬ 音量の合格線（kijun.json loudness）', 'なし', False, 'kijun_loud.py で見本から作る')
    # ⑭ テロップの数字・固有名詞（抜けK）：画面に出した文字が台本に無い数・語／台本と声の聞き直しで数が食い違う → 止める
    import moji_check
    shown = [x for sc_ in meta.get('selection', []) for x in sc_.get('shown', [])]
    dsrc = TJ.get('script')
    dtext = open(dsrc, encoding='utf-8').read() if dsrc and os.path.exists(dsrc) else '\n'.join(x['text'] for x in TJ['lines'])
    heard = []
    jp = os.path.join(TJ.get('narr') or os.path.join(W, 'narr'), 'jikoku.json')
    if os.path.exists(jp):
        for s_ in json.load(open(jp)).get('sentences', []):
            heard.append((s_.get('text', ''), ''.join(w.get('t', '') for w in (s_.get('words') or []))))
    stop, ref = moji_check.check(shown, dtext, heard)
    judge('⑭ テロップの数字・固有名詞（台本に無い・声と食い違う）', '外れ %d' % len(stop), not stop, '外れ 0（%s）' % '；'.join(stop[:3]) if stop else '外れ 0',
          '参考 %d（%s）' % (len(ref), '；'.join(ref[:2])) if ref else '')
    judge('⑭ 声の聞き直しがあるか（数の突き合わせに使う）', '%d 文' % len(heard), len(heard) > 0 or TJ.get('as_is') is None, '編集後の声を Whisper large-v3 で聞き直した文があること')
    # ⑮ 観点の全部（state/yt-anime-1014/kanten-zenbu.md・依頼主 10/15「つかみ・離脱・CTAだけではない。YouTube動画編集者に」）
    #    mp4 を見本の per_full と同じ道具（onepass→demucs→Whisper large-v3→ana1）で測り、場面の記録（story_meta・video_marketing）と合わせて観点ごとに点を出す
    import kanten as KT, kanten_sokutei as KS
    kj = json.load(open(os.path.join(paths.ENGINE, 'kata', 'kanten_kijun.json'))); KL = K['kanten']
    ana, ap = KS.measure(video, os.path.basename(proj.rstrip('/')))
    kv = KS.values(os.path.dirname(ap), ana, D); kv.update(KT.from_project(proj)); kv['a_moji_ng'] = float(len(stop))
    ks = KT.score_hon(kv, kj)   # 点は本質のルールを守れているかだけ（好みの指標は kanten.json に参考で残す）
    for r_ in ks:
        low = '・'.join('%s（%s %s・線 %s〜%s）' % (i['rule'], i['label'], i['value'], i['line'][0], i['line'][1]) for i in r_['items'] if i['kept'] is False)
        nm = '・'.join(i['rule'] for i in r_['items'] if i['pt'] is None)
        judge('⑮ 観点：%s（本質のルール %d/%d を測れた）' % (r_['name'], r_['measured'], r_['of']), r_['score'], r_['score'] is not None and r_['score'] >= KL['each_min'],
              '≥ %s点' % KL['each_min'], ('破り：' + low if low else '') + ('／未測定：' + nm if nm else ''))
    G = KT.gate(kv, kj, KL.get('format', '講義型'))   # 合格＝①破り0 ②観点ごとに手本の編集者さんの講義型の下から4分の1より上・13観点の合計が手本の編集者さんの中央値以上（10/16）
    judge('⑮① 本質のルールの破り（全%d観点）' % len(ks), '%d個' % G['破り'], G['①破り'], '%d個まで・手本の編集者さん本人の誰より悪い指標は0個・全観点に点' % G['破りの上限'],
          '；'.join('%s：%s（%s %s・線 %s〜%s）%s' % (d['観点'], d['ルール'], d['指標'], d['値'], d['線'][0], d['線'][1], '【本人の誰より悪い＝不合格】' if d['本人の誰より悪い'] else '') for d in G['破りの中身']))
    md_ = {r_['id']: r_ for r_ in G['median']}
    for r_ in (G['②'] or {}).get('rows', []):
        m_ = md_.get(r_['id']) or {'short': [], 'unmeasured': []}
        sh_ = '・'.join('%s %s（中央値 %s）' % (i['label'], i['value'], i['median']) for i in m_['short'])
        judge('⑮② 下から4分の1より上：%s' % r_['name'], '%s点' % r_['score'], r_['reached'] is True,
              '≥ %s点（手本の編集者さんの講義型の下から4分の1）' % r_['p25'], ('中央値に届かない指標：' + sh_ if sh_ else '') + ('／未測定：' + '・'.join(m_['unmeasured']) if m_['unmeasured'] else ''))
    if G['②']:
        judge('⑮② 13観点の合計', '%s点' % G['②']['sum'], G['②']['sum_ok'] is True, '≥ %s点（手本の編集者さんの講義型の中央値）' % G['②']['sum_med'], '')
    ks_ref = KT.score(kv, kj)
    json.dump({'指標': kv, '観点': ks, '合格': {k: v for k, v in G.items() if k not in ('hon', 'median', 'vs_answer')}, '中央値': G['median'], '好みも含めた見本の幅との比べ（参考）': ks_ref, '測りの材料': ap}, open(os.path.join(O, 'kanten.json'), 'w'), ensure_ascii=False, indent=1)
    ok = not NG
    json.dump({'合否': '合格' if ok else '不合格', '外れ': NG, '結果': res}, open(os.path.join(O, 'check.json'), 'w'), ensure_ascii=False, indent=1)
    open(os.path.join(O, 'hikaku.tsv'), 'w').write('項目\t今回\t基準\t見本\t合否\n' + ''.join('%s\t%s\t%s\t%s\t%s\n' % (r['項目'], r['今回'], r['基準'], r['見本'], r['合否']) for r in res))
    for r_ in res: print('%s  %-40s 今回 %-8s 基準 %s  見本 %s' % ('✅' if r_['合否'] == '合格' else '🔴', r_['項目'], r_['今回'], r_['基準'], r_['見本']))
    print('\n' + ('合格' if ok else '不合格：\n  ' + '\n  '.join(NG)))
    return ok
if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None) else 1)
