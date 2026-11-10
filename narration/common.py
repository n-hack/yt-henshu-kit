# ナレーションの下ごしらえ：共通の部品（音の読み書き・無音の検出・読み（かな）・話す速さ）
import json, os, re, subprocess, unicodedata
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000          # 書き出しの標本化周波数
HOP = 0.01          # 無音の検出の刻み（10ms）

# 告知（チャンネル登録・LINE・概要欄・特典など）の言葉。見本の区間分けと台本の区間分けで同じものを使う
PROMO = re.compile(r"(LINE|ライン登録|公式ライン|概要欄|チャンネル登録|高評価|コメント欄|特典|プレゼント|無料で|勉強会|セミナー|お申し込み|申し込み|"
                   r"登録して|登録者|受け取って|期間限定|限定で|今だけ|リンク|ボタン|コンサル|個別相談|オプチャ|オープンチャット|フォロー)")
# 強調の前の間（「結論」「実は」など、言い切りの前に間を置く言葉）
EMPH = re.compile(r"^(結論|つまり|実は|じつは|なぜなら|なんでかというと|ポイントは|大事なのは|重要なのは|答えは|正解は|ズバリ|ずばり|はっきり言って|"
                  r"一番|まず|最後に|2つ目|二つ目|3つ目|三つ目|1つ目|一つ目|では|それでは|じゃあ|さて)")
# つなぎ言葉（台本に無ければ消す）
FILLERS = ["えーっと", "えっと", "えーと", "ええと", "えー", "ええ", "え", "あのー", "あの", "あー", "あ", "うーん", "うん", "んー", "ん",
           "まあ", "まぁ", "まー", "なんか", "そのー", "その", "こう", "ちょっと", "おー", "はい", "で"]
FILLER_STRONG = {"えーっと", "えっと", "えーと", "ええと", "えー", "ええ", "え", "あのー", "あー", "うーん", "んー", "ん", "まー", "そのー", "おー", "あ", "あの"}


def load(path, sr=SR):
    """どんな音・動画でも 1ch float32 で読む"""
    r = subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def save(path, x, sr=SR):
    x = np.clip(x, -1, 1).astype(np.float32)
    subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s24le", str(path)], input=x.tobytes(), check=True)


def mlx_tight():
    """MLX（Whisper の GPU）が使い終わった置き場を手放さずに溜めるのを 2GB までにする（10/15 実測：10分の声で溜め 12GB→2GB・字は同じ・速さ同じ）
    溜めの上限が無いと、起こすたびに増えて henshu.py が 34GB まで太った"""
    import mlx.core as mx
    mx.set_cache_limit(int(float(os.environ.get("YT_MLX_CACHE_GB", "2")) * 2 ** 30))
    return mx


def frame_db(x, sr, hop=HOP, win=0.025):
    h, w = int(sr * hop), int(sr * win)
    n = max(1, (len(x) - w) // h + 1)
    if len(x) < w:
        x = np.pad(x, (0, w - len(x)))
    # 刻みの束（2万刻み＝200秒）ずつ測る（全編を一度に並べると30分の声で 3GB を超えた）
    e = []
    for a in range(0, n, 20000):
        idx = np.arange(w)[None, :] + h * np.arange(a, min(n, a + 20000))[:, None]
        e.append(np.sqrt(np.mean(x[idx] ** 2, axis=1) + 1e-12))
    e = np.concatenate(e)
    return 20 * np.log10(e + 1e-9)


def voice_mask(db, rel=30.0, floor_gap=8.0):
    """声のある刻み。いちばん大きい所（95%点）から rel dB 下、かつ底（10%点）より floor_gap dB 上を声とみなす"""
    top, bot = np.percentile(db, 95), np.percentile(db, 10)
    thr = max(top - rel, bot + floor_gap)
    m = db > thr
    # 1刻みだけの穴・飛び出しをならす
    m2 = m.copy()
    m2[1:-1] = (m[:-2].astype(int) + m[1:-1] + m[2:]) >= 2
    return m2, thr


def runs(mask, val=False):
    """mask==val の連続区間 [(始, 終)]（刻みの番号）"""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i] == val:
            j = i
            while j < n and mask[j] == val:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def silences(x, sr, min_len=0.06, rel=30.0):
    """無音の区間（秒）。声の最初と最後の外側は含めない"""
    db = frame_db(x, sr)
    m, thr = voice_mask(db, rel)
    if not m.any():
        return [], m, db, thr
    first, last = np.argmax(m), len(m) - np.argmax(m[::-1])
    out = [(a * HOP, b * HOP) for a, b in runs(m, False) if a >= first and b <= last and (b - a) * HOP >= min_len]
    return out, m, db, thr


# ---------------------------------------------------------------- 読み
_kks = None


_KD = "〇一二三四五六七八九"


def _kansuji(n):
    """整数 → 漢数字（読みを pykakasi に任せるため。1万→一万、25→二十五）"""
    if n == 0:
        return "零"
    out = ""
    for unit, name in ((10 ** 12, "兆"), (10 ** 8, "億"), (10 ** 4, "万"), (1, "")):
        q, n = divmod(n, unit)
        if q:
            part = ""
            for u, nm in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
                d, q = divmod(q, u)
                if d:
                    part += ("" if d == 1 and nm else _KD[d]) + nm
            out += part + name
    return out


def kana(text):
    """ひらがなの読み（記号・空白は落とす）。文字起こしは数字で書くので（2つ目・3ヶ月）、漢数字に直してから読む"""
    global _kks
    if _kks is None:
        import pykakasi
        _kks = pykakasi.kakasi()
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"(?<=[0-9０-９〇一二三四五六七八九十百千万])[ヶヵケ](?=[月所国年])", "か", t)
    t = re.sub(r"[0-9]+(?:,[0-9]{3})*", lambda m: _kansuji(int(m.group().replace(",", ""))), t)
    out = "".join(it["hira"] for it in _kks.convert(t))
    out = re.sub(r"[^ぁ-ゖー0-9a-zA-Z]", "", out)
    return out


SMALL = set("ぁぃぅぇぉゃゅょゎ")


def mora(k):
    """拍の数（小さい ゃゅょ などは前と合わせて1拍）"""
    return sum(1 for c in k if c not in SMALL)


def norm(text):
    """比べるための字（記号・空白を落とす）"""
    t = unicodedata.normalize("NFKC", text)
    return re.sub(r"[\s、。，．,.!！?？…・「」『』（）()\[\]【】〜~ー―\-:：;；\"'“”]", "", t)


def split_sentences(script):
    """台本 → 文の並び。【冒頭】【本編】【告知】【締め】の見出しと、空行（場面の区切り）を拾う"""
    sec, para, out = None, 0, []
    for line in script.splitlines():
        s = line.strip()
        if not s:
            para += 1
            continue
        m = re.match(r"^[【\[]\s*(冒頭|本編|告知|締め)\s*[】\]]\s*(.*)$", s)
        if m:
            sec, s = m.group(1), m.group(2).strip()
            para += 1
            if not s:
                continue
        for p in re.findall(r"[^。！？!?]+[。！？!?]*", s):
            p = p.strip()
            if norm(p):
                out.append({"text": p, "sec": sec, "para": para})
    return out


def short_sentences(timing, frac=0.35):
    """落とした文の数え直し（10/16）：「見つかった」でも、残った声が字数に比べて短すぎる文は話した言葉が消えている。
    文の長さ（s_edit〜e_edit・無ければ s〜e）が、字数÷全体の中央の速さ の frac 倍より短い文を返す。0件で「落とした文0」"""
    xs = []
    for t in timing["sentences"]:
        if not t.get("found"):
            xs.append((t, 0.0, len(norm(t["text"])))); continue
        a = t["s_edit"] if t.get("s_edit") is not None else t["s"]
        b = t["e_edit"] if t.get("e_edit") is not None else t["e"]
        xs.append((t, max(0.0, b - a), len(norm(t["text"]))))
    rates = [n / d for _, d, n in xs if d > 0.3 and n >= 5]
    if not rates:
        return []
    med = float(np.median(rates))
    return [{"i": t["i"], "text": t["text"], "dur": round(d, 2), "expect": round(n / med, 2)} for t, d, n in xs if n >= 4 and d < frac * n / med]
