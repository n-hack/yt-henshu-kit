#!/usr/bin/env python3
# 画像が出なかった回の検査（作業AI・2026-10-16 夜・shard5 eiQaTiAwLVg／NzjnSa2FrxU・shard6 T5pL46B7N6c の取り下げのあと）
#   書き手（agent-ayt-full-*）の会話記録を読み、画像の Read の結果が「[media removed: request limit]」など
#   画像の無い結果だった回を拾う。言葉の決まり（記憶 never-describe-an-image-that-did-not-display）では防げなかったので機械で見る。
#   python3 mienai-kensa.py               … 記録を読み足して（前回の続きから）一覧を出す
#   python3 mienai-kensa.py --id <id>     … 1本だけ、読み直しの済んでいない画像を出す（終了コード 1＝残りあり）
#   python3 mienai-kensa.py --gokaku      … 門に合格している本だけ通し、引っかかった本の一覧を出す（合格は消さない）
#   python3 mienai-kensa.py --rescan      … 控えを捨てて全部読み直す
# 判定（門 saboranai.py が呼ぶ mikaiketsu()）
#   同じファイル（sb/sNNNN.jpg・札など）を、出なかった最後の回より後に、画像ありで読んだ記録があれば済み。無ければ残り。
# 置き場  ~/rin6/state/yt-henshu/mienai/
#   cache.json   … 記録ごとの読んだ位置・答え待ちの Read
#   events.jsonl … 画像の Read 1回ごと（時刻・作業員・パス・本・出たか）
#   ichiran.tsv  … 出なかった回の一覧（本・ファイル・時刻・作業員・読み直し）
#   gokaku-<日時>.tsv … --gokaku の結果
import os, sys, json, re, glob, fcntl, datetime

ROOTS = [os.path.expanduser('~/.claude-rin6/projects/-Users-sam-rin6')]
PAT = 'agent-ayt-full-*.jsonl'
BASE = '~/rin6/state/yt-anime-1014'
FULL = os.path.join(BASE, 'kata/full')
VERD = os.path.join(FULL, 'saboranai/verdict')
OUT = os.path.expanduser('~/rin6/state/yt-henshu/mienai')
CACHE = os.path.join(OUT, 'cache.json')
EVENTS = os.path.join(OUT, 'events.jsonl')
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
# 記録の中の実物の字（10/16 に 119本を数えた：画像の Read の結果 11097回が image、424回が下の text だけ）
MARKS = ('[media removed', 'request limit', 'could not be displayed', 'image could not', 'image was removed')
FAIL_HEAD = '画像が出なかったまま読み直していない'   # 門の fails の頭（saboranai がこの頭で入れ替える）
TS_RE = re.compile(r'"timestamp":"([^"]+)"')
ID_RE = re.compile(r'"tool_use_id":"(toolu_[A-Za-z0-9_-]+)"')


def jload(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def known_ids():
    s = set()
    for n in range(8):
        p = os.path.join(FULL, 'shard%d.txt' % n)
        if os.path.exists(p):
            s |= {os.path.splitext(os.path.basename(l.strip()))[0] for l in open(p) if l.strip()}
    return s


def vid_of(path, ids):
    for m in re.finditer(r'(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{11})(?![A-Za-z0-9-])', path):
        if m.group(1) in ids: return m.group(1)
    return None


def key_of(path):
    """同じ画像を指す名前：kata/full より後ろ（無ければパスそのまま）"""
    p = os.path.normpath(os.path.expanduser(path))
    i = p.find('/kata/full/')
    return p[i + len('/kata/full/'):] if i >= 0 else p


def result_kind(blocks):
    """tool_result の中身 → 'shown'（画像あり）／'removed'（出なかった印）／'error'（読めなかった）"""
    if isinstance(blocks, str):
        low = blocks.lower()
        return 'removed' if any(m in low for m in MARKS) else 'error'
    if any(isinstance(b, dict) and b.get('type') == 'image' for b in blocks or []): return 'shown'
    txt = ' '.join(str(b.get('text', '')) for b in blocks or [] if isinstance(b, dict)).lower()
    return 'removed' if any(m in txt for m in MARKS) else 'error'


def scan(rescan=False, quiet=True):
    """記録を前回の続きから読み、画像の Read を events.jsonl に足す。足した数を返す"""
    os.makedirs(OUT, exist_ok=True)
    lk = open(os.path.join(OUT, '.lock'), 'w'); fcntl.flock(lk, fcntl.LOCK_EX)
    st = {} if rescan else jload(CACHE, {})
    if rescan and os.path.exists(EVENTS): os.remove(EVENTS)
    ids = known_ids(); added = 0
    files = sorted(f for r in ROOTS for f in glob.glob(os.path.join(r, '*', 'subagents', PAT)))
    ev = open(EVENTS, 'a')
    for f in files:
        fs = st.get(f) or {'off': 0, 'pend': {}}
        size = os.path.getsize(f)
        if size < fs['off']: fs = {'off': 0, 'pend': {}}   # 縮んだ＝作り直された
        if size == fs['off']: st[f] = fs; continue
        agent = re.sub(r'^agent-a|-[0-9a-f]{16}\.jsonl$', '', os.path.basename(f))
        pend = fs['pend']
        with open(f, 'rb') as fh:
            fh.seek(fs['off'])
            off = fs['off']
            for raw in fh:
                if not raw.endswith(b'\n'): break   # 書きかけの行は次の回
                off += len(raw)
                if b'"tool_use"' in raw and b'"Read"' in raw and len(raw) < 2_000_000:
                    try: d = json.loads(raw)
                    except Exception: continue
                    for b in (d.get('message') or {}).get('content') or []:
                        if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('name') == 'Read':
                            fp = str((b.get('input') or {}).get('file_path', ''))
                            if fp.lower().endswith(IMG_EXT): pend[b['id']] = fp
                    continue
                if not pend or b'"tool_result"' not in raw: continue
                line = raw.decode('utf-8', 'replace')
                tids = [t for t in ID_RE.findall(line) if t in pend]
                if not tids: continue
                tm = TS_RE.search(line); ts = tm.group(1) if tm else ''
                if len(tids) == 1 and len(set(ID_RE.findall(line))) == 1:
                    # 画像の行は大きいので、1つだけの結果なら字で見分ける（全部 json にすると 15GB で遅い）
                    kind = 'shown' if '"type":"image"' in line else ('removed' if any(m in line.lower() for m in MARKS) else 'error')
                    kinds = {tids[0]: kind}
                else:
                    d = json.loads(line); kinds = {}
                    for b in (d.get('message') or {}).get('content') or []:
                        if isinstance(b, dict) and b.get('type') == 'tool_result' and b.get('tool_use_id') in pend:
                            kinds[b['tool_use_id']] = result_kind(b.get('content'))
                for tid, kind in kinds.items():
                    fp = pend.pop(tid)
                    ev.write(json.dumps({'ts': ts, 'agent': agent, 'file': os.path.basename(f), 'path': fp, 'key': key_of(fp),
                                         'vid': vid_of(fp, ids), 'kind': kind}, ensure_ascii=False) + '\n')
                    added += 1
        st[f] = {'off': off, 'pend': pend}
        if not quiet: print('読んだ', os.path.basename(f), '%.0fMB' % (size / 1e6), file=sys.stderr)
    ev.close()
    tmp = CACHE + '.tmp'; json.dump(st, open(tmp, 'w')); os.replace(tmp, CACHE)
    return added


def events():
    out = []
    if os.path.exists(EVENTS):
        for l in open(EVENTS):
            try: out.append(json.loads(l))
            except Exception: pass
    return out


def per_key(evs, vid=None):
    """本→ファイル→回の列（時刻順）"""
    m = {}
    for e in sorted(evs, key=lambda e: e['ts']):
        if not e.get('vid') or (vid and e['vid'] != vid): continue
        m.setdefault(e['vid'], {}).setdefault(e['key'], []).append(e)
    return m


def mikaiketsu(vid, do_scan=True):
    """その本で、出なかった最後の回より後に画像ありで読み直していないファイル → [(key, 出なかった時刻, 作業員)]"""
    if do_scan: scan()
    rows = []
    for key, lst in per_key(events(), vid).get(vid, {}).items():
        miss = [e for e in lst if e['kind'] == 'removed']
        if not miss: continue
        last = miss[-1]
        if not any(e['kind'] == 'shown' and e['ts'] > last['ts'] for e in lst):
            rows.append((key, last['ts'], last['agent']))
    return sorted(rows)


def gate_fail(vid, do_scan=True):
    """門に入れる1行（無ければ None）"""
    r = mikaiketsu(vid, do_scan)
    if not r: return None
    names = [os.path.basename(k) for k, _, _ in r]
    return ('%s：%d 枚（%s%s）。Read の結果が [media removed: request limit] で画像が表示されていないのに、その後に同じファイルを画像ありで開き直した記録が無い。'
            '1回3枚までで開き直し、画像が出たものだけでメモと per_full を確かめ直してから門に通す（記録 %s）'
            % (FAIL_HEAD, len(r), '・'.join(names[:12]), ' ほか' if len(names) > 12 else '', ' '.join(sorted({a for _, _, a in r}))))


def jst(ts):
    try:
        return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone().strftime('%m/%d %H:%M:%S')
    except Exception:
        return ts


def write_ichiran():
    m = per_key(events())
    L = ['vid\tファイル\t出なかった回\t最後に出なかった時刻\t作業員\t読み直し（画像あり）']
    for vid in sorted(m):
        for key, lst in sorted(m[vid].items()):
            miss = [e for e in lst if e['kind'] == 'removed']
            if not miss: continue
            re_ = [e for e in lst if e['kind'] == 'shown' and e['ts'] > miss[-1]['ts']]
            L.append('%s\t%s\t%d\t%s\t%s\t%s' % (vid, key, len(miss), jst(miss[-1]['ts']), miss[-1]['agent'],
                                                 ('済み %s %s' % (jst(re_[0]['ts']), re_[0]['agent'])) if re_ else 'なし'))
    p = os.path.join(OUT, 'ichiran.tsv'); open(p, 'w').write('\n'.join(L) + '\n')
    return p, len(L) - 1


def main():
    a = sys.argv[1:]
    n = scan(rescan='--rescan' in a, quiet=False)
    if '--id' in a:
        vid = a[a.index('--id') + 1]
        r = mikaiketsu(vid, do_scan=False)
        for k, ts, ag in r: print('%s\t%s\t%s' % (k, jst(ts), ag))
        print('%s：読み直していない出なかった画像 %d 枚' % (vid, len(r)))
        sys.exit(1 if r else 0)
    p, rows = write_ichiran()
    evs = events()
    print('足した画像の Read %d 回／全 %d 回（出なかった %d 回）／一覧 %s（%d 行）'
          % (n, len(evs), sum(1 for e in evs if e['kind'] == 'removed'), p, rows))
    if '--gokaku' in a:
        L = ['vid\tshard\t読み直していない枚数\tファイル（先頭）\t作業員']
        ok = [os.path.basename(v)[:-5] for v in glob.glob(os.path.join(VERD, '*.json'))
              if not [f for f in (jload(v, {}) or {}).get('fails', []) if not f.startswith(FAIL_HEAD)]]
        sh = {}
        for k in range(8):
            pth = os.path.join(FULL, 'shard%d.txt' % k)
            if os.path.exists(pth):
                for l in open(pth):
                    if l.strip(): sh[os.path.splitext(os.path.basename(l.strip()))[0]] = k
        hit = 0
        for vid in sorted(ok):
            r = mikaiketsu(vid, do_scan=False)
            if r:
                hit += 1
                L.append('%s\t%s\t%d\t%s\t%s' % (vid, sh.get(vid, '?'), len(r), ' '.join(os.path.basename(k) for k, _, _ in r[:8]),
                                                 ' '.join(sorted({x for _, _, x in r}))))
        out = os.path.join(OUT, 'gokaku-%s.tsv' % datetime.datetime.now().strftime('%Y%m%d-%H%M'))
        open(out, 'w').write('\n'.join(L) + '\n')
        print('合格 %d 本のうち 引っかかった %d 本 → %s' % (len(ok), hit, out))


if __name__ == '__main__':
    main()
