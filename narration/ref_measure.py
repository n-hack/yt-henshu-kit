# 見本の202本（声を分けた区間：冒頭90秒・真ん中60秒・最後）から、話す速さ・無音の長さ・声の大きさを測る
# 使い方: .venv/bin/python ref_measure.py   → ref_stats.json（henshu.py が読む）
import json, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from common import HERE, PROMO, EMPH, load, silences, kana, mora, norm

ROOT = Path("~/rin6/state/yt-anime-1014")
RAW = ROOT / "kata/raw"
SR = 16000


def lufs(path, ss=None, t=None):
    cmd = ["ffmpeg", "-nostats", "-hide_banner"]
    if ss is not None:
        cmd += ["-ss", str(ss), "-t", str(t)]
    cmd += ["-i", str(path), "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def one(job):
    vid, w, mp4 = job
    wav = RAW / vid / ("w" + w["name"]) / "vocals.wav"
    if not wav.exists():
        return None
    x = load(wav, SR)
    sil, mask, db, thr = silences(x, SR, min_len=0.06)
    t0 = w["t0"]
    segs = [s for s in w["transcript"] if norm(s["text"])]
    out = {"id": vid, "win": w["name"], "sent": [], "pause": [], "lufs_voice": lufs(wav),
           "lufs_mix": lufs(mp4, t0, w["t1"] - t0) if mp4 else None}
    scenes = [c["t"] - t0 for c in w.get("changes", []) if c.get("kind") == "scene"]

    def sec_of(text):
        if PROMO.search(text):
            return "告知"
        return {"hook": "冒頭", "mid": "本編", "end": "締め"}[w["name"]]

    # 文ごとの速さ（文の中の 0.15秒以上の無音は話していない時間として除く＝発話の速さ）
    for s in segs:
        a, b = s["s"] - t0, s["e"] - t0
        fa, fb = int(a / 0.01), int(b / 0.01)
        seg_mask = mask[max(fa, 0):max(fb, 0)]
        if len(seg_mask) < 50:
            continue
        on = np.flatnonzero(seg_mask)
        if len(on) < 30:
            continue
        span = (on[-1] - on[0] + 1) * 0.01
        inner = sum(min(e, b) - max(st, a) for st, e in sil if e - st >= 0.15 and st > a + on[0] * 0.01 and e < a + on[-1] * 0.01)
        art = span - max(inner, 0)
        k = kana(s["text"])
        if art < 1.0 or mora(k) < 8:
            continue
        out["sent"].append({"sec": sec_of(s["text"]), "mora_s": mora(k) / art, "char_s": len(norm(s["text"])) / art,
                            "mora": mora(k), "art": round(art, 3)})
    # 間：文の切れ目にある無音＝文間、文の中＝文中。画面の場面転換と重なる＝場面、次の文が強調の言葉で始まる＝強調前
    bounds = [(segs[i]["e"] - t0, segs[i + 1]["s"] - t0, segs[i + 1]["text"]) for i in range(len(segs) - 1)]
    for st, e in sil:
        kind, nxt = "文中", None
        for be, bs, txt in bounds:
            if st - 0.25 <= be <= e + 0.25 or st - 0.25 <= bs <= e + 0.25:
                kind, nxt = "文間", txt
                break
        if kind == "文間":
            if any(st - 0.3 <= sc <= e + 0.6 for sc in scenes):
                kind = "場面"
            elif EMPH.search(nxt or ""):
                kind = "強調前"
        mid = (st + e) / 2 + t0
        seg_here = next((s for s in segs if s["s"] <= mid <= s["e"] + 0.5), None)
        sec = sec_of(seg_here["text"]) if seg_here else {"hook": "冒頭", "mid": "本編", "end": "締め"}[w["name"]]
        out["pause"].append({"kind": kind, "sec": sec, "len": round(e - st, 3)})
    return out


def q(v, ps=(5, 10, 25, 50, 75, 90, 95)):
    v = np.asarray(v, float)
    return {f"p{p}": round(float(np.percentile(v, p)), 3) for p in ps} if len(v) else {}


def main():
    jobs = []
    mp4s = {p.stem: p for p in (ROOT / "channels/dl").glob("*/*.mp4")}
    for d in sorted(RAW.iterdir()):
        f = d / "data.json"
        if not f.exists():
            continue
        data = json.load(open(f))
        for w in data["windows"]:
            jobs.append((data["id"], w, mp4s.get(data["id"])))
    print(f"区間 {len(jobs)} 個を測ります", file=sys.stderr)
    res = []
    with ProcessPoolExecutor(2) as ex:
        for i, r in enumerate(ex.map(one, jobs, chunksize=4)):
            if r:
                res.append(r)
            if i % 50 == 0:
                print(i, file=sys.stderr)
    json.dump(res, open(HERE / "ref_raw.json", "w"), ensure_ascii=False)
    stats = {"n_videos": len({r["id"] for r in res}), "n_windows": len(res), "speed": {}, "pause": {}, "loud": {}}
    # 速さ：区間ごとの全文の分布＋1本の中のばらつき（1本ごとの 標準偏差/中央値）
    for sec in ["冒頭", "本編", "告知", "締め", "全体"]:
        ss = [s for r in res for s in r["sent"] if sec == "全体" or s["sec"] == sec]
        if not ss:
            continue
        cv = []
        for r in res:
            v = [s["mora_s"] for s in r["sent"] if sec == "全体" or s["sec"] == sec]
            if len(v) >= 5:
                cv.append(np.std(v) / np.median(v))
        stats["speed"][sec] = {"n": len(ss), "mora_s": q([s["mora_s"] for s in ss]), "char_s": q([s["char_s"] for s in ss]),
                               "cv_in_video": q(cv, (25, 50, 75))}
    for kind in ["文中", "文間", "強調前", "場面", "全体"]:
        for sec in ["冒頭", "本編", "告知", "締め", "全体"]:
            ps = [p["len"] for r in res for p in r["pause"] if (kind == "全体" or p["kind"] == kind) and (sec == "全体" or p["sec"] == sec)]
            if len(ps) < 20:
                continue
            stats["pause"].setdefault(kind, {})[sec] = {"n": len(ps), **q(ps), "mean": round(float(np.mean(ps)), 3),
                                                       "share_ge_0_5": round(float(np.mean(np.array(ps) >= 0.5)), 3)}
    # 1分あたりの間の数
    tot = sum(sum(s["art"] for s in r["sent"]) for r in res)
    stats["pause_per_min_speech"] = round(sum(len(r["pause"]) for r in res) / (tot / 60), 1)
    stats["loud"] = {"voice_lufs": q([r["lufs_voice"] for r in res if r["lufs_voice"] is not None], (10, 25, 50, 75, 90)),
                     "mix_lufs": q([r["lufs_mix"] for r in res if r["lufs_mix"] is not None], (10, 25, 50, 75, 90))}
    stats["pause_grid"] = pause_grid(res)
    json.dump(stats, open(HERE / "ref_stats.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k != "pause_grid"}, ensure_ascii=False, indent=1))


def pause_grid(res):
    """間の長さの 0〜100% 点（1%刻み）。henshu.py が 順位→長さ の置き換えに使う"""
    g = {}
    for kind in ["文中", "文間", "強調前", "場面", "全体"]:
        for sec in ["冒頭", "本編", "告知", "締め", "全体"]:
            ps = [p["len"] for r in res for p in r["pause"] if (kind == "全体" or p["kind"] == kind) and (sec == "全体" or p["sec"] == sec)]
            if len(ps) >= 20:
                g.setdefault(kind, {})[sec] = {"n": len(ps), "grid": [round(float(v), 3) for v in np.percentile(ps, np.arange(101))]}
    return g


def grid_only():
    """測り直さず ref_raw.json から pause_grid だけ足す"""
    res = json.load(open(HERE / "ref_raw.json"))
    stats = json.load(open(HERE / "ref_stats.json"))
    stats["pause_grid"] = pause_grid(res)
    json.dump(stats, open(HERE / "ref_stats.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    grid_only() if "--grid-only" in sys.argv else main()
