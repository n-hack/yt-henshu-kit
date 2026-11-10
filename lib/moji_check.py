# テロップの数字・固有名詞の誤りを止める（作業AI・2026-10-15・抜けK）
#   別の作業AI 10/15 19:58「Whisper の起こし違いは固有名詞と数字に出やすい」。テロップに数字・金額・人名が出る
#   ① 画面に出した文字（story_meta.json の selection の shown＝実際に描いた文字）の数字・固有名詞が、台本に無い → 止める
#   ② 台本の行の数字と、編集後の声を Whisper large-v3 で聞き直した数字が食い違う → 止める（声と画面が食い違う）
#   ③ 台本の固有名詞（カタカナ3字以上・英字）が声の聞き直しに見つからない → 参考（読みの表記ゆれがあるので止めない）
import re

ZEN = str.maketrans('０１２３４５６７８９，．％', '0123456789,.%')
KD = {'〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
KU = {'十': 10, '百': 100, '千': 1000}
KB = {'万': 10 ** 4, '億': 10 ** 8, '兆': 10 ** 12}


def kan2int(s):
    """漢数字（三百二十万 など）→ 数。読めなければ None"""
    total = sec = cur = 0; seen = False
    for ch in s:
        if ch in KD: cur = cur * 10 + KD[ch] if cur else KD[ch]; seen = True
        elif ch in KU: sec += (cur or 1) * KU[ch]; cur = 0; seen = True
        elif ch in KB: total += (sec + cur or 1) * KB[ch]; sec = cur = 0; seen = True
        else: return None
    return total + sec + cur if seen else None


def numbers(t):
    """文の中の数を全部（算用数字・漢数字・万／億の混ざり 例 3万・1.5倍・二十）→ 数の集合"""
    t = (t or '').translate(ZEN)
    out = set()
    for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)\s*([万億兆]?)', t):
        v = float(m.group(1).replace(',', '')); v *= KB.get(m.group(2), 1); out.add(round(v, 3))
    for m in re.finditer(r'[〇零一二三四五六七八九十百千万億兆]{1,12}', t):
        w = m.group(0)
        if w in ('一', '千', '万', '億') and len(t) > 1: continue          # 「一番」「一つの」「千差万別」など数でない字を外す（単独の字は数えない）
        v = kan2int(w)
        if v is not None and v > 0: out.add(float(v))
    return out


# 固有名詞ではない一般の語（見出しの「ポイント①」など。見本も台本に無い見出しを足す）は数えない（10/16）
FUTSU = {'ポイント', 'ノウハウ', 'ステップ', 'テーマ'}
_VU = str.maketrans({'ヴ': 'ブ'})


def _kana(w):
    """表記ゆれをそろえる：ヴァ→バ・ヴ→ブ（エヴァー と エバー を同じ語に）"""
    return w.replace('ヴァ', 'バ').replace('ヴィ', 'ビ').replace('ヴェ', 'ベ').replace('ヴォ', 'ボ').translate(_VU)


def proper(t):
    """固有名詞らしい語：カタカナ3字以上・英字2字以上（大文字小文字は区別しない）。一般の語（FUTSU）は除く"""
    return {_kana(w.lower()) for w in re.findall(r'[ァ-ヴー]{3,}|[A-Za-z][A-Za-z0-9\.\+\-]{1,}', t or '') if w not in FUTSU}


def check(shown_list, daihon_text, lines_heard):
    """shown_list … 画面に出した文字の並び／daihon_text … 台本全文／lines_heard … [(台本の行, 声の聞き直し)]
    → (止める外れ, 参考)"""
    stop, ref = [], []
    dn, dp = numbers(daihon_text), proper(daihon_text)
    dflat = _kana(re.sub(r'\s', '', daihon_text or '').lower())
    for sh in shown_list:
        for v in numbers(sh) - dn:
            stop.append('テロップ「%s」の数 %s が台本に無い' % (sh[:20], ('%g' % v)))
        for w in proper(sh):
            if w not in dp and w not in dflat: stop.append('テロップ「%s」の語「%s」が台本に無い' % (sh[:20], w))
    for line, heard in lines_heard:
        a, b = numbers(line), numbers(heard)
        if a != b and (a or b):
            stop.append('台本「%s」の数 %s と 声の聞き直し %s が食い違う' % (line[:24], sorted('%g' % v for v in a), sorted('%g' % v for v in b)))
        miss = [w for w in proper(line) if w not in proper(heard) and w not in (heard or '').lower()]
        if miss: ref.append('台本「%s」の %s が声の聞き直しに見つからない（読みの表記ゆれなら問題なし）' % (line[:20], '・'.join(miss)))
    return stop, ref
