# 試しの生ナレーションを作る：作業AIの声（Gemini TTS・Kore）で台本を読ませ、わざと
#   同じ文を2回・言いかけ・言い間違い→言い直し・「えー」「あのー」・噛み・台本に無い独り言・速さ違い・長い無音・
#   リップノイズ・吹かれ・部屋のノイズ を混ぜる。どこが「消すべき」かの正解（truth.json）も書く
# 使い方: .venv/bin/python make_test.py 出力フォルダ
import base64, hashlib, json, os, random, subprocess, sys, time, urllib.request
from pathlib import Path
import numpy as np
from common import SR, load, save

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "test/tts1")
CL = OUT / "clips"
CL.mkdir(parents=True, exist_ok=True)
random.seed(7)

SCRIPT = """【冒頭】
今回はインスタグラムで、フォロワーを一気に増やす方法をお話しします。
実はこれ、僕が三か月でフォロワーを一万人増やしたときに使ったやり方なんですね。
最後まで見ていただければ、明日からすぐに使えるようになります。

【本編】
まず一つ目のポイントは、投稿の最初の一枚で手を止めてもらうことです。
ほとんどの人は、ここで何も考えずに写真を一枚載せてしまっています。
でもそれだと、流れていく投稿の中で一瞬で読み飛ばされてしまうんですね。
だからこそ、一枚目には大きな文字で、相手の悩みをそのまま書いてあげてください。

二つ目のポイントは、保存したくなる中身を入れることです。
インスタグラムは、保存の数が多い投稿を、もっと多くの人に見せる仕組みになっています。
つまり、あとで見返したくなる手順や、まとめを入れるのが一番の近道なんです。

【告知】
ここで一つお知らせです。
今回の内容をまとめた資料を、公式ラインで無料でプレゼントしています。
概要欄のリンクから登録して、ぜひ受け取ってください。

【締め】
今日お話しした二つのポイントを、まずは次の投稿で一つだけ試してみてください。
それでは、また次の動画でお会いしましょう。
"""

# 読む順（正解つき）。("say", 文番号) は台本どおり。("del", 理由, 文字) は消すべきもの。("var", 文番号, 文字) は言い方違い（意味は同じ＝残してよい）
# speed は速さの倍率（rubberband で後から変える）
PLAN = [
    ("del", "つなぎ言葉", "えー、"),
    ("say", 0, 1.0),
    ("say", 1, 0.82),                                   # ゆっくり
    ("del", "言いかけ", "最後まで見ていただ"),
    ("say", 2, 1.0),
    ("del", "言い直し（前の回・言い間違い）", "まず一つ目のポイントは、投稿の最後の一枚で手を止めてもらうことです。"),
    ("del", "独り言", "あれ、違うな。"),
    ("say", 3, 1.0),
    ("say", 4, 1.22),                                   # 速い
    ("del", "つなぎ言葉", "あのー、"),
    ("say", 5, 1.0),
    ("del", "噛み", "だから"),
    ("say", 6, 0.85),
    ("say", 7, 1.0),
    ("del", "言い直し（前の回）", "保存の数が多い投稿を、もっと多くの人に見せる仕組みになっています。"),  # 文8の途中から言い直す前の回は下で
    ("del", "言い直し（前の回）", "インスタグラムは、保存の数が多い投稿を、もっと多くの人に見せる仕組みになっています。"),
    ("say", 8, 1.0),
    ("del", "つなぎ言葉", "えっと、"),
    ("var", 9, "つまり、後で見返したくなるような手順とか、まとめを入れるのが一番の近道なんです。"),  # 言い方違い・これしか無い→残す
    ("del", "独り言", "ちょっと水飲みます。"),
    ("say", 10, 1.15),
    ("say", 11, 1.0),
    ("del", "言い直し（前の回）", "概要欄のリンクから登録して、ぜひ受け取ってください。"),
    ("say", 12, 0.9),                                   # 同じ文を2回・最後の回を残す
    ("say", 13, 1.0),
    ("del", "言い直し（言い方違い・台本どおりの前の回を残す）", "では、また次の動画で会いましょう。"),
    ("say", 14, 1.0),
]
# 最後の2つは「台本どおりの回（文14）」を後に置く。逆の並び（台本どおりが先・言い方違いが後）は別の試し
PLAN2 = PLAN[:-2] + [("say", 14, 1.0), ("del", "言い直し（言い方違い・台本どおりの前の回を残す）", "それじゃあ、また次の動画で会いましょうね。")]


def key(name):
    if os.environ.get(name):
        return os.environ[name]
    for f in ["~/rin/gateway/.env", "~/rin/gateway/.env.bak-20260820-025721"]:
        f = os.path.expanduser(f)
        if os.path.exists(f):
            for l in open(f):
                if l.startswith(name + "="):
                    return l.split("=", 1)[1].strip()
    raise SystemExit(f"{name} が見つかりません")


def tts(text, path):
    if path.exists():
        return
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}}}}
    r = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent?key={key('GEMINI_API_KEY')}",
                               data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    for i in range(5):
        try:
            d = json.load(urllib.request.urlopen(r, timeout=300))
            raw = base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            break
        except Exception as e:
            if i == 4:
                raise
            time.sleep(5)
    tmp = path.with_suffix(".raw")
    tmp.write_bytes(raw)
    src = ["-i", str(tmp)] if raw[:4] == b"RIFF" else ["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(tmp)]
    af = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *src, "-af", af, "-ar", str(SR), "-ac", "1", str(path)], check=True)
    tmp.unlink()


def stretch(path, speed):
    out = path.with_name(path.stem + f"_x{speed}.wav")
    if not out.exists():
        subprocess.run(["rubberband", "-q", "-3", "-T", str(speed), str(path), str(out)], check=True)
    return out


def build(plan, name):
    from common import split_sentences
    sents = [s["text"] for s in split_sentences(SCRIPT)]
    jobs = []
    for i, p in enumerate(plan):
        txt = sents[p[1]] if p[0] == "say" else p[2]
        jobs.append((p, txt, CL / f"{hashlib.md5(txt.encode()).hexdigest()[:12]}.wav"))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        uniq = {path: txt for _, txt, path in jobs}       # 同じ文は1回だけ作る（同じファイルを2つの手で書くと壊れる）
        list(ex.map(lambda pt: tts(pt[1], pt[0]), uniq.items()))
    parts, truth, t = [], [], 0.0
    noise_rng = np.random.default_rng(3)

    def gap(sec):
        nonlocal t
        n = int(sec * SR)
        parts.append(np.zeros(n, np.float32))
        t += sec

    gap(0.8)
    for p, txt, path in jobs:
        if p[0] == "say" and p[2] != 1.0:
            path = stretch(path, p[2])
        x = load(path)
        x = x / (np.max(np.abs(x)) + 1e-9) * (0.5 if p[0] != "del" or "つなぎ" not in p[1] else 0.35)
        if p[0] == "say" and p[1] in (3, 10):
            x = x * 0.45                                # 声の大きさのばらつき（小さい文）
        kind = {"say": "keep", "var": "keep", "del": "del"}[p[0]]
        truth.append({"kind": kind, "s": round(t, 3), "e": round(t + len(x) / SR, 3), "text": txt,
                      "sent": p[1] if p[0] in ("say", "var") else None, "reason": p[1] if p[0] == "del" else None,
                      "speed": p[2] if p[0] == "say" else 1.0})
        parts.append(x.astype(np.float32))
        t += len(x) / SR
        # 間：短すぎ・長すぎを混ぜる
        gap(random.choice([0.15, 0.35, 0.6, 0.9, 1.4, 2.2, 3.0]) if p[0] != "del" else random.choice([0.2, 0.5, 0.9]))
    y = np.concatenate(parts)
    # 部屋のノイズ（-58dB 前後のピンクっぽい音）
    w = noise_rng.standard_normal(len(y)).astype(np.float32)
    w = np.convolve(w, np.ones(8) / 8, mode="same") * 10 ** (-52 / 20)
    y = y + w
    # リップノイズ（短いクリック）と 吹かれ（低い「ボフッ」）を声の頭に入れる
    events = []
    for k, tr in enumerate(truth):
        if tr["kind"] == "keep" and k % 3 == 0:
            i0 = int((tr["s"] + 0.02) * SR)
            click = np.zeros(int(0.003 * SR), np.float32)
            click[0], click[1], click[2] = 0.35, -0.3, 0.15
            y[i0:i0 + len(click)] += click
            events.append({"kind": "リップノイズ", "t": round(tr["s"] + 0.02, 3)})
        if tr["kind"] == "keep" and k % 4 == 1:
            i0 = int((tr["s"] + 0.01) * SR)
            n = int(0.08 * SR)
            tt = np.arange(n) / SR
            boom = 0.5 * np.sin(2 * np.pi * 45 * tt) * np.exp(-tt * 40)
            y[i0:i0 + n] += boom.astype(np.float32)
            events.append({"kind": "吹かれ", "t": round(tr["s"] + 0.01, 3)})
    save(OUT / f"{name}.wav", y)
    json.dump({"script_sentences": sents, "truth": truth, "events": events}, open(OUT / f"{name}.truth.json", "w"), ensure_ascii=False, indent=1)
    print(name, round(len(y) / SR, 1), "秒")


(OUT / "daihon.txt").write_text(SCRIPT)
build(PLAN, "raw_a")
build(PLAN2, "raw_b")
