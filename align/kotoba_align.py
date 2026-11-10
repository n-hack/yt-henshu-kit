#!/usr/bin/env python3
# 台本の字と人の声の強制アライメント（vsl-yt-1・10/18 依頼主の絶対ルール「テロップと動きは言葉の頭に1コマで合わせる」）
#   使い方: ~/rin6/tools/yt-henshu/align/.venv/bin/python kotoba_align.py <作業の場>
#   入力  work/timing.json（narr_bridge.prep が作る：台本の字 ref・行の頭 line0・Whisper の字ごとの時刻）と work/vocals.wav
#   出力  work/timing_fa.json（同じ形。starts を「声に合わせ直した字ごとの頭」に置き換え・whisper の時刻も残す）
#   やり方 ① 実際に話した字（work/whisper_words.json・whisper_words.py が作る）を、間で区切ったかたまりごとに
#            wav2vec2 の MMS_FA で声に貼る（読みのローマ字1字ごと・20ms）。台本と言い回しが違っても声の字で貼るのでずれない
#          ② 台本の字を、話した字へ字の並びで引き当てる（difflib）。台本にしか無い字は前後の字の間に置く
#          ③ 間のあとの言葉の頭は、10ms ごとの声の大きさで「静かな所から声へ上がった所」に寄せる
import os, sys, json, re, unicodedata
import numpy as np, torch, torchaudio, soundfile as sf
import pykakasi
P = sys.argv[1]
J = json.load(open(os.path.join(P, 'work', 'timing.json')))
REF = J['ref']; L0 = {int(k): v for k, v in J['line0'].items()}; WS = J['starts']
KKS = pykakasi.kakasi()
YOMI = {'chatgpt': 'チャットジーピーティー', 'claudecode': 'クロードコード', 'claude': 'クロード', 'gpts': 'ジーピーティーズ', 'codex': 'コーデックス',
        'code': 'コード', 'ai': 'エーアイ', 'gpt': 'ジーピーティー', 'vsl': 'ブイエスエル', 'line': 'ライン', 'x': 'エックス'}
KD = '〇一二三四五六七八九'
def kansuji(n):
    out = ''
    for unit, name in ((10 ** 8, '億'), (10 ** 4, '万'), (1, '')):
        q, n = divmod(n, unit)
        if q:
            for u, nm in ((1000, '千'), (100, '百'), (10, '十'), (1, '')):
                d, q = divmod(q, u)
                if d: out += ('' if d == 1 and nm else KD[d]) + nm
            out += name
    return out or '零'
def romaji(s):
    return re.sub(r'[^a-z]', '', ''.join(it['hepburn'] for it in KKS.convert(s)).lower())
def tokens(text):
    """台本の字 → [(字の始まり, 字の終わり, ローマ字)]。英字は読みの表、数字は漢数字にしてから読む"""
    out = []; i = 0
    for m in re.finditer(r'[A-Za-z]+|[0-9]+', text):
        out += [(a + i, b + i, r) for a, b, r in _kana_tok(text[i:m.start()])]
        w = m.group()
        if w[0].isdigit(): r = romaji(kansuji(int(w)))
        else:
            r = ''; lw = w.lower(); k = 0
            while k < len(lw):   # 長い順に読みの表を当てる（ClaudeGPTs → claude + gpts）
                for n in range(len(lw) - k, 0, -1):
                    if lw[k:k + n] in YOMI: r += romaji(YOMI[lw[k:k + n]]); k += n; break
                else: r += lw[k]; k += 1
        out.append((m.start(), m.end(), r)); i = m.end()
    out += [(a + i, b + i, r) for a, b, r in _kana_tok(text[i:])]
    return out
def _kana_tok(s):
    out = []; k = 0
    for it in KKS.convert(s):
        o = it['orig']; r = re.sub(r'[^a-z]', '', it['hepburn'].lower())
        if r: out.append((k, k + len(o), r))
        elif out: out[-1] = (out[-1][0], k + len(o), out[-1][2])
        k += len(o)
    return out

B = torchaudio.pipelines.MMS_FA
DEV = 'mps' if torch.backends.mps.is_available() else 'cpu'   # 混んでいるときは CPU が回らないので GPU で
MODEL = B.get_model(with_star=False).eval().to(DEV); TOK = B.get_tokenizer(); ALN = B.get_aligner()
x, sr = sf.read(os.path.join(P, 'work', 'vocals.wav'), dtype='float32')
if x.ndim > 1: x = x.mean(1)
if sr != 16000: x = torchaudio.functional.resample(torch.from_numpy(x), sr, 16000).numpy(); sr = 16000
n10 = len(x) // 160; DB = 20 * np.log10(np.sqrt((x[:n10 * 160].reshape(n10, 160) ** 2).mean(1)) + 1e-9)

def N(t): return re.sub(r'[、。「」『』！？!?,.\s・…（）()【】%％]', '', unicodedata.normalize('NFKC', t))
W = json.load(open(os.path.join(P, 'work', 'whisper_words.json')))
# かたまり：0.25秒より長い間か、12秒を超えたら区切る
groups = []; g = []
for w in W:
    if g and (w['s'] - g[-1]['e'] > 0.25 or w['e'] - g[0]['s'] > 12): groups.append(g); g = []
    g.append(w)
if g: groups.append(g)
TX = ''; TT = []; TW = []; TOKS = []; PREV = 0.0; DUR = len(x) / sr
for g in groups:
    text = N(''.join(w['w'] for w in g)); 
    if not text: continue
    ws = []
    for w in g: ws += [w['s']] * len(N(w['w']))
    tk = tokens(text)
    t0 = max(0.0, g[0]['s'] - 0.3, PREV); t1 = min(DUR, g[-1]['e'] + 0.3)
    seg = torch.from_numpy(x[int(t0 * sr):int(t1 * sr)])[None]
    with torch.inference_mode():
        em, _ = MODEL(seg.to(DEV)); em = torch.log_softmax(em, -1).cpu()
    ratio = seg.size(1) / em.size(1) / sr
    tt = [None] * len(text)
    if tk:
        spans = ALN(em[0], TOK([r for _, _, r in tk]))
        for (ca, cb, r), sp in zip(tk, spans):
            for c in range(ca, cb):   # 言葉の途中の字は、その字の手前までの読みの長さ番目の音の頭
                j = min(len(sp) - 1, len(romaji(text[ca:c]))) if c > ca else 0
                tt[c] = round(t0 + sp[j].start * ratio, 3)
            TOKS.append({'text': text[ca:cb], 'romaji': r, 'start': round(t0 + sp[0].start * ratio, 3), 'end': round(t0 + sp[-1].end * ratio, 3), 'whisper': ws[ca] if ca < len(ws) else None})
        PREV = TOKS[-1]['end']
    for c in range(len(text)):
        if tt[c] is None: tt[c] = tt[c - 1] if c else t0
    TX += text; TT += tt; TW += (ws + [ws[-1]] * len(text))[:len(text)]
# 間のあとの言葉：前の 100ms が静か（-35dB 未満）なら、頭の前後 80ms で -30dB を最初に越えた 10ms へ
KT = ['fa'] * len(TX); p = 0
for t in TOKS:
    q = TX.find(t['text'], p); p = q + len(t['text']) if q >= 0 else p
    i = int(t['start'] * 100)
    if q < 0 or i < 10 or DB[i - 10:i - 2].max() >= -35: continue
    for k in range(i - 8, min(len(DB), i + 8)):
        if DB[k] >= -30: t['onset'] = k / 100.0; TT[q] = t['onset']; KT[q] = 'fa+onset'; break
# 台本の字 → 話した字
import difflib
NEW = list(WS); KIND = ['whisper'] * len(REF)
for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, REF, TX, autojunk=False).get_opcodes():
    for i in range(i1, i2):
        if op == 'equal': j = j1 + (i - i1); NEW[i] = TT[j]; KIND[i] = KT[j]
        elif op == 'replace': j = min(j2 - 1, j1 + (i - i1) * (j2 - j1) // (i2 - i1)); NEW[i] = TT[j]; KIND[i] = 'fa(言い回し違い)'
        elif op == 'delete': j = min(len(TT) - 1, j1); NEW[i] = TT[j]; KIND[i] = 'fa(台本だけの字)'
for i in range(1, len(NEW)):   # 時刻は字の順に戻らない
    if NEW[i] < NEW[i - 1]: NEW[i] = NEW[i - 1]
out = dict(J); out['starts'] = NEW; out['starts_whisper'] = WS; out['kind'] = KIND; out['tokens'] = TOKS; out['spoken'] = TX
out['aligner'] = 'Whisper large-v3 の字を MMS_FA で声に貼り・台本へ引き当て・声の大きさで寄せる'
json.dump(out, open(os.path.join(P, 'work', 'timing_fa.json'), 'w'), ensure_ascii=False)
d = [abs(t['start'] - t['whisper']) for t in TOKS if t['whisper'] is not None]
sm = difflib.SequenceMatcher(None, REF, TX, autojunk=False)
print('かたまり %d ／ 言葉 %d ／ Whisper との差 中央値 %.3f秒 最大 %.3f秒 0.2秒超 %d ／ 間のあとで寄せた %d ／ 台本と話した字の一致 %.1f%%' % (
    len(groups), len(TOKS), np.median(d), max(d), sum(1 for v in d if v > 0.2), sum(1 for t in TOKS if 'onset' in t), sm.ratio() * 100))
