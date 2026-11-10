#!/usr/bin/env python3
# 字幕に出す字を決める（yt-henshu-pipe・10/19）：話した字（work/timing_fa.json の行）を台本（input/daihon.txt）と突き合わせ、
#   ① 同じ字は台本の書き方で出す（ai→AI・chatgpt→ChatGPT・漢字の違い）
#   ② 違う所（聞き違い／言い換え・言い足し）は、1件ずつ「聞き違いなら台本の字・言い換えなら話した字」を AI（claude -p）が決める
#      面談前VSL v10 では作業AIが声を聞き直して手で直した 60件余り（ki1.py の JIMAKU_FIX）。その判断をここで毎回する
#   ③ 台本の文の切れ目（。！？・改行）が行の中にあれば「｜」を入れ、字幕の1枚が文をまたがないようにする
#   出力 work/jimaku_disp.json＝{行の番号: {"disp": 出す字（｜入り）, "idx": 1字ずつの話した字の位置（行の中）}}・work/jimaku_ji.tsv（決めた中身の一覧）
#   python3 jimaku_ji.py <作業フォルダ> [--no-ai]（--no-ai は既定の決め方だけ＝試し用）
import os, sys, json, re, difflib, unicodedata, subprocess
P = sys.argv[1]; NOAI = '--no-ai' in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
J = json.load(open(os.path.join(P, 'work', 'timing_fa.json')))
S = J['ref']; LINES = J['lines']; L0 = {int(k): v for k, v in J['line0'].items()}
DAI = open(os.path.join(P, 'input', 'daihon.txt'), encoding='utf-8-sig').read()
PUNCT = r'[、。「」『』！？!?,.\s・…（）()【】%％]'
DROP = set('、。，．,.!！?？「」『』（）()【】…"“”\'')
# 台本の字：照合用（小文字・句読点なし）と表示用（元の字）を並べる。英字の間の空白は表示に残す
D = ''; DD = []; DB = set(); prev_len = 99; prev_owari = True
_DB_MACHI = None
for line in DAI.splitlines():
    if not re.sub(PUNCT, '', line).strip(): continue
    if re.match(r'^\s*[（(].*[)）]\s*$', line): continue
    t = unicodedata.normalize('NFKC', line).strip()
    t = re.sub(r'^[・\-\*●■◆]\s*', '', t)                       # 箇条書きの印
    t = re.sub(r'^\d+[:：]', '', t) if re.match(r'^\d+[:：]\D', t) else t
    sp = False; ten = False; last_kugiri = len(D); ten_len = 99
    if _DB_MACHI is not None:
        _t1 = re.sub(PUNCT, '', unicodedata.normalize('NFKC', line))
        if len(_t1) >= 9 and re.match(r'[A-Za-z0-9ァ-ヴー一-龥]', _t1[:1]): DB.add(_DB_MACHI)
        _DB_MACHI = None
    # 10/20 ⑤（作業AI）：台本で1行ずつ並べた短い語（才能／努力の量／運）が、字幕で「量運」とつながった → 前の行が短く（8字以下）文の終わり（。！？、）が無く、
    #   この行も短い語で始まるなら、行の頭に「・」を置く（台本の改行＝語の区切り）
    _KJ0 = r'[A-Za-z0-9ァ-ヴー一-龥]'; _t0 = re.sub(PUNCT, '', t)
    nami_gyou = bool(DD) and prev_len <= 8 and not prev_owari and bool(re.match(_KJ0, DD[-1][-1:])) and bool(re.match(_KJ0, _t0[:1] or ' ')) and len(re.split(r'[、,。！？!?]', t)[0]) <= 8
    for ti, ch in enumerate(t):
        if ch == ' ' or ch == '　': sp = True; continue
        if re.sub(PUNCT, '', ch):
            lat = DD and re.match(r'[A-Za-z0-9]', DD[-1][-1:]) and re.match(r'[A-Za-z0-9]', ch)
            # 名詞を「、」で並べた所は・（Claude・GPTs／資料作成・リサーチ）。前後とも2〜8字の短い並びだけ（「ただ、」「なので、」は前がひらがななので除く）
            KJ = r'[A-Za-z0-9ァ-ヴー一-龥]'
            nami = ten and DD and re.match(KJ, DD[-1][-1:]) and re.match(KJ, ch) and 2 <= ten_len <= 8 and len(re.split(r'[、,。！？!?]', t[ti:])[0]) <= 8
            pre = '・' if (ten and lat) or nami else ' ' if sp and lat else ''
            if nami_gyou: pre = '・'; nami_gyou = False
            D += ch.lower(); DD.append(pre + ch); sp = False; ten = False
        else:
            sp = False; ten = ch in '、,'
            if ch in '、,。！？!?': ten_len = len(D) - last_kugiri; last_kugiri = len(D)
            if ch in '。！？!?' and D: DB.add(len(D))
            if ch == '・' and DD: DD[-1] += '・'                  # 語と語の間の中黒（Claude・GPTs）は表示に残す
            if ch in '→×〜' and DD: DD[-1] += ch
    # 短い行（8字以下）が句点も文の終わりの形も無く終わるとき（「才能／努力の量／運」の並べ書き）は、行の終わりを文の切れ目にするかを次の行を見て決める（10/20 ⑤ koe-5c「多くの人が｜才能｜・努力の量」・作業AI）
    #   次の行が9字以上で漢字・カナ・英数字で始まる（別の項目「AI特許取得／元日テレ新規事業部」）ときだけ切る。次も短い語・ひらがなの続き（「運／などと」）なら切らない
    _ln = re.sub(PUNCT, '', t)
    if D and len(_ln) <= 8 and not re.search(r'[。！？!?]\s*$', t) and not re.search(r'(ます|です|ください|ません|ました|でした|ですか|ますか|しょう)$', _ln): _DB_MACHI = len(D)
    elif D: DB.add(len(D))
    prev_len = len(re.sub(PUNCT, '', t)); prev_owari = bool(re.search(r'[。！？!?、,]\s*$', t))
# 英字の書き方（台本にある形）：ai → AI など
CASE = {}
for m in re.finditer(r'[A-Za-z][A-Za-z0-9]*', unicodedata.normalize('NFKC', DAI)): CASE.setdefault(m.group().lower(), m.group())
def fix_case(s):
    return re.sub(r'[a-z][a-z0-9]*', lambda m: CASE.get(m.group(), m.group().upper() if len(m.group()) <= 4 else m.group()), s)
ops = difflib.SequenceMatcher(None, S, D, autojunk=False).get_opcodes()
# 台本の1文まるごとを話していない所で、離れた台本の1字だけが偶然そろった「1字の一致」を、前後の違う所とまとめる
#   r14：話した「ステップ3」と台本「STEP2 高単価アフィリエイトコン［テ］ンツ…STEP3」の「テ」がそろい、字幕が「STEPテ3」になった（10/20）
_m = []
for o in ops:
    _m.append(list(o))
    while len(_m) >= 3 and _m[-2][0] == 'equal' and _m[-2][2] - _m[-2][1] <= 1 and _m[-3][0] != 'equal' and _m[-1][0] != 'equal':
        a3, e2, c1 = _m[-3], _m[-2], _m[-1]
        sp_n = (a3[2] - a3[1]) + (c1[2] - c1[1]) + 1; dp_n = (a3[4] - a3[3]) + (c1[4] - c1[3]) + 1
        if dp_n <= 3 * sp_n + 5: break
        _m[-3:] = [['replace', a3[1], c1[2], a3[3], c1[4]]]
ops = [tuple(o) for o in _m]
# 違う所を1件ずつ
items = []
for k, (op, i1, i2, j1, j2) in enumerate(ops):
    if op in ('replace', 'delete'):   # SequenceMatcher(話した字, 台本)：delete＝話した字だけ（言い足し）・insert＝台本だけ（話していない）
        sp_, dp_ = S[i1:i2], ''.join(DD[j1:j2]).strip()
        n = max([n for n, v in L0.items() if v <= i1] or [1])
        ctx_s = S[max(0, i1 - 12):i1] + '［' + sp_ + '］' + S[i2:i2 + 12]
        ctx_d = ''.join(DD[max(0, j1 - 12):j1]) + '［' + dp_ + '］' + ''.join(DD[j2:j2 + 12])
        default = 'daihon' if op == 'replace' and len(sp_) <= 12 and len(dp_) <= 16 else 'spoken'
        items.append({'id': len(items), 'op': k, 'n': n, 'spoken': sp_, 'daihon': dp_, 'ctx_spoken': ctx_s, 'ctx_daihon': ctx_d, 'choice': default, 'text': ''})
GUIDE = '''あなたは動画の字幕係です。話し手の声を書き起こした字（Whisper）と、その動画の台本を突き合わせた「違う所」の一覧を渡します。
字幕は「声で実際に言った言葉」を正しい字で出すのが決まりです。1件ずつ、字幕に出す字を決めてください。
- 書き起こしの聞き違い（意味の通らない字・同じ音の別の字・固有名詞やサービス名の書き方・数字の書き方）→ 台本の字（choice "daihon"）
- 話し手が台本と違う言い方をした・言い足した（意味の通る別の言い方）→ 話した字のまま（choice "spoken"）。字幕は声と一致させる
- 聞き違いだが、台本の言葉とも違うことを言っている → 実際に言ったと思われる言葉を正しい字で（choice "custom"・text に字）
- 台本にしか無い言葉（話していない）は出さない（この一覧には来ない）
- 「AI」だけでなく「AIエージェント」と言っている所は「AIエージェント」のまま。サービス名は Claude Code・Codex・ChatGPT・GPTs・Claude・SNS・note・LINE のように台本の書き方にそろえる
- 句読点は付けない
返事は JSON の配列だけ：[{"id": 番号, "choice": "daihon"|"spoken"|"custom", "text": "customのときの字"}]（全件・説明なし）'''
def ask(chunk):
    body = GUIDE + '\n\n一覧（ctx_spoken は書き起こしの前後・［］が違う所、ctx_daihon は台本の前後）：\n' + json.dumps(
        [{k: it[k] for k in ('id', 'spoken', 'daihon', 'ctx_spoken', 'ctx_daihon')} for it in chunk], ensure_ascii=False, indent=0)
    r = subprocess.run(['claude', '-p', '--model', 'opus', '--output-format', 'text'], input=body, capture_output=True, text=True, cwd='/tmp', timeout=900)
    m = re.search(r'\[.*\]', r.stdout, re.S)
    if not m: raise SystemExit('字幕の字の判断が返ってこない：' + r.stdout[-500:] + r.stderr[-500:])
    return json.loads(m.group())
CACHE = os.path.join(P, 'work', 'jimaku_ji_ai.json')   # 同じ「違う所」への判断は使い回す（AI を呼び直さない）
key = lambda it: it['ctx_spoken'] + '‖' + it['ctx_daihon'].replace('・', '')   # 行の区切りの「・」（10/20）で前の判断の控えが外れないよう、・は鍵に入れない
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
for it in items:
    c = cache.get(key(it))
    if c: it['choice'], it['text'], it['ai'] = c['choice'], c.get('text', ''), True
todo = [it for it in items if not it.get('ai')]
if todo and not NOAI:
    from concurrent.futures import ThreadPoolExecutor
    chunks = [todo[i:i + 60] for i in range(0, len(todo), 60)]
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(ask, chunks):
            for r in res:
                it = items[int(r['id'])]
                if r.get('choice') in ('daihon', 'spoken', 'custom'):
                    it['choice'] = r['choice']; it['text'] = r.get('text', '') or ''; it['ai'] = True
                    cache[key(it)] = {'choice': it['choice'], 'text': it['text']}
    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False, indent=0)
# 字ごとの表示を組む：話した字の位置 i ごとに「そこから出す字」OUT[i] をつける（置き換えた字は区間の中へ均等に割り振る＝行をまたいでも割れる）
OUT = [''] * len(S)
byop = {it['op']: it for it in items}
for k, (op, i1, i2, j1, j2) in enumerate(ops):
    if op == 'equal':
        for d in range(i2 - i1): OUT[i1 + d] = DD[j1 + d]
    elif op in ('replace', 'delete'):
        it = byop[k]
        if it['choice'] == 'spoken':
            fx = fix_case(S[i1:i2])                 # 大文字にするだけ（字の数は変わらない）
            for d in range(i2 - i1): OUT[i1 + d] = fx[d] if fx[d] not in DROP else ''
            continue
        # 台本の字を選んだ所は、表示用の台本の字（DD：語の間の「・」入り）で出す（10/20 ⑤：「運」が聞き違いの区間に入り「量運」と・が落ちた）
        txt = ''.join(c for c in (''.join(DD[j1:j2]) if it['choice'] == 'daihon' else it['text']) if c not in DROP)
        if ''.join(DD[j1:j2]).startswith('・') and not txt.startswith('・') and txt: txt = '・' + txt   # AI が直した字（custom）でも、行の区切りの「・」は残す
        # 直した字の1字ずつを話した字の位置に当てる（同じ字は同じ所・入れ替えた字はその区間に均等・足した字は次の字の所）。
        #   均等に割るだけだと、長い直しで字が前後の行へずれた（10/19 試し：「ま｜だ世に出回って」）
        sp_ = S[i1:i2]; lo = txt.lower()
        for o2, a1, a2, b1, b2 in difflib.SequenceMatcher(None, sp_, lo, autojunk=False).get_opcodes():
            for q in range(b1, b2):
                if o2 == 'equal': pos = a1 + (q - b1)
                elif o2 == 'replace': pos = a1 + (q - b1) * (a2 - a1) // (b2 - b1)
                else: pos = min(a1, len(sp_) - 1)
                OUT[i1 + pos] += txt[q]
# 字幕の字の直し（字の並びで当てる・字の数が変わっても話した字の位置にそろえる）
#   いつも：話し手の名前は「自社キャラ」（作業AI 10/19 22:4x「丸尾」→「自社キャラ」全編）
#   作業ごと：input/jimaku_naoshi.json [{"from": "…", "to": "…", "why": "…"}]（声を聞き直して決めた所だけ）
NAOSHI = [{'from': '丸尾', 'to': '自社キャラ', 'why': '話し手の名前の表記'}]
_nf = os.path.join(P, 'input', 'jimaku_naoshi.json')
if os.path.exists(_nf): NAOSHI += json.load(open(_nf, encoding='utf-8'))
NAOSHI_LOG = []; NAOSHI_KIRU = set()
for r_ in NAOSHI:
    while True:
        pos_ = []; cat_ = ''
        for i, o in enumerate(OUT):
            for ch in o: pos_.append(i); cat_ += ch
        f_ = cat_.find(r_['from'])
        if f_ < 0: break
        ps_ = pos_[f_:f_ + len(r_['from'])]
        if r_.get('kesu'):   # 字の位置はそのまま、from の中の [始め, 終わり) の字だけ消す（言い直しの前の方だけ消す・作業AI 10/20）。kiru があれば消した後ろで札を分ける
            k0, k1 = r_['kesu']; chs = [(i, ch) for i, o in enumerate(OUT) for ch in o]
            drop = set(range(f_ + k0, f_ + k1))
            for i in range(len(OUT)): OUT[i] = ''
            for n_, (i, ch) in enumerate(chs):
                if n_ not in drop: OUT[i] += ch
            if r_.get('kiru'): NAOSHI_KIRU.add(ps_[k1])
            NAOSHI_LOG.append('%s の %d〜%d字目を消す（%s）' % (r_['from'], k0 + 1, k1, r_.get('why', ''))); continue
        for i in sorted(set(ps_)): OUT[i] = ''
        to_ = r_['to']
        for q, ch in enumerate(to_): OUT[ps_[min(len(ps_) - 1, q * len(ps_) // max(1, len(to_)))]] += ch   # 前から順に同じ位置か後ろの位置へ
        NAOSHI_LOG.append('%s→%s（%s）' % (r_['from'], to_, r_.get('why', '')))
print('字幕の字の直し %d件：%s' % (len(NAOSHI_LOG), ' ／ '.join(NAOSHI_LOG)))
# 直しの to に書いた「｜」は、その位置で字幕の札を分ける印（作業AI 10/20：「かと思います｜これが」）。字としては出さない
NAOSHI_SB = set(NAOSHI_KIRU)
for i, o in enumerate(OUT):
    if '｜' in o:
        NAOSHI_SB.add(i if o.startswith('｜') else i + 1); OUT[i] = o.replace('｜', '')
# 台本の文の切れ目 → 話した字の位置（同じ字の所だけ）
SB = set()
for k, (op, i1, i2, j1, j2) in enumerate(ops):
    if op == 'equal':
        nxt = ops[k + 1][0] if k + 1 < len(ops) else 'equal'
        for b in DB:
            # 同じ字の区間の終わりちょうどの切れ目は、次が話した字だけの言い足し（「保存する｜など」）なら使わない＝台本の文の終わりが声の文の終わりとは限らない
            if b - j1 >= 3 and (j2 - b >= 3 or (b == j2 and nxt == 'insert' and j2 - j1 >= 6)) and i1 + (b - j1) < len(S): SB.add(i1 + (b - j1))   # 短い一致（言い足しの中の偶然の一致）の切れ目は使わない
SB |= set(J.get('sent_breaks', [])) | NAOSHI_SB   # 話した字の文の終わり＋間（gyou_auto.py --fa）
# 台本の文の終わりのすぐ後に、話した字だけの言い足しや台本だけの字（「笑」など）がある所：切れ目をその後ろ（次の文の頭）へ置く
#   r14：「思います（笑）｜優秀な」「保存する（など）｜つまり」が1枚の字幕にまたがっていた（作業AI 10/20）
for k, (op, i1, i2, j1, j2) in enumerate(ops):
    if op != 'equal' or j2 - j1 < 3: continue
    k2 = k + 1; ii = i2
    while k2 < len(ops) and ops[k2][0] != 'equal' and ops[k2][4] - ops[k2][3] <= 3 and ops[k2][2] - ops[k2][1] <= 4: ii = ops[k2][2]; k2 += 1
    if k2 == k + 1 or k2 >= len(ops) or ops[k2][0] != 'equal': continue
    if any(j2 <= b <= ops[k2][3] for b in DB) and ii < len(S): SB.add(ii)
# 台本に無い言い足しの中の文の終わり：「〜です／ます／ました／でした／ません」のすぐ後に続きの字（よ・ね・か・が・けど・ので…）が来ない所
from bunmatsu_re import OWARI as _OWARI
for m in _OWARI.finditer(S):
    if m.end() < len(S): SB.add(m.end())
# 10/20 ⑤：台本の小数（1.6億円）の「.」が句読点として落ち「16億円」と出た（数字が変わる＝絶対に出してはいけない）→ 台本にある「数字.数字＋次の字」の並びの所だけ「.」を戻す
for _m in re.finditer(r'(\d+)\.(\d+)(\D?)', unicodedata.normalize('NFKC', DAI)):
    _a, _b, _nx = _m.group(1), _m.group(2), _m.group(3)
    _pos = []; _cat = ''
    for _i, _o in enumerate(OUT):
        for _ch in _o: _pos.append(_i); _cat += _ch
    _st = 0
    while True:
        _f = _cat.find(_a + _b + _nx, _st)
        if _f < 0: break
        if _f > 0 and _cat[_f - 1].isdigit(): _st = _f + 1; continue   # 前にも数字が続く所（116億など）は別の数
        _i = _pos[_f + len(_a) - 1]; OUT[_i] = OUT[_i] + '.'
        _pos = []; _cat = ''
        for _i2, _o in enumerate(OUT):
            for _ch in _o: _pos.append(_i2); _cat += _ch
        _st = _f + len(_a) + 1 + len(_b)
res = {}; rows = []
nums = sorted(L0)
for k, n in enumerate(nums):
    a = L0[n]; b = L0[nums[k + 1]] if k + 1 < len(nums) else len(S)
    disp = ''; idx = []
    for i in range(a, b):
        if i in SB and i > a and disp and not disp.endswith('｜'): disp += '｜'; idx.append(i - a)
        for ch in OUT[i]: disp += ch; idx.append(i - a)
    disp = disp.strip('｜')
    idx = idx[:len(disp)]
    res[str(n)] = {'disp': disp, 'idx': idx, 'spoken': S[a:b]}
for it in items: rows.append('%d\t%d\t%s\t%s\t%s\t%s\t%s' % (it['id'], it['n'], it['choice'], it['spoken'], it['daihon'], it['text'], 'AI' if it.get('ai') else '既定'))
# 10/20 ⑤：台本の「3,500」の桁の区切りが、名詞の並びの「・」になって「3・500万円」と出た → 台本に「数字,3桁」がある所だけ「,」に戻す（字の数は同じ＝idx は変わらない）
_KETA = set(m.group(0).replace(',', '・') for m in re.finditer(r'\d,\d{3}', unicodedata.normalize('NFKC', DAI)))
for _v in res.values():
    if isinstance(_v, dict) and isinstance(_v.get('disp'), str):
        _v['disp'] = re.sub(r'\d・\d{3}', lambda m: m.group(0).replace('・', ',') if m.group(0) in _KETA else m.group(0), _v['disp'])
json.dump(res, open(os.path.join(P, 'work', 'jimaku_disp.json'), 'w'), ensure_ascii=False, indent=0)
open(os.path.join(P, 'work', 'jimaku_ji.tsv'), 'w').write('番号\t行\t決め\t話した字\t台本の字\t直した字\t決めた者\n' + '\n'.join(rows) + '\n')
from collections import Counter
c = Counter(it['choice'] for it in items)
print('違う所 %d（台本の字 %d・話した字 %d・直した字 %d／AIが決めた %d）・文の切れ目 %d' % (len(items), c['daihon'], c['spoken'], c['custom'], sum(1 for it in items if it.get('ai')), len(SB)))
