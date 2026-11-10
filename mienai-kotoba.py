#!/usr/bin/env python3
# 見た印（合言葉）の道具（作業AI・2026-10-17・mienai-kensa.py の後継の門）
#   10/15 15:45 以降、書き手の会話記録には「[media removed: request limit]」が残らない（記録上は全部 画像あり）。
#   記録を読む mienai-kensa.py は 12,254 回中「出なかった 0 回」と出し、取り下げた実例（4d の rkzk9VW92fw s0081〜）も拾えなかった。
#   そこで、画像の中にだけある使い捨ての合言葉を焼き込み、書き手がそれを写せたシートだけを「見た」と数える。
#   画像が出なかった回は合言葉が分からないので、印が付かない＝門で止まる。
#
#   python3 mienai-kotoba.py --dasu <id> s0081 s0082 s0083   … 合言葉入りの写しを作り、写しのパスだけを出す（合言葉は出さない）
#   python3 mienai-kotoba.py --mita <id> s0081=XXXXX ...      … 画像に見えた合言葉を打つ。合えば印、違えば終了コード 1
#   python3 mienai-kotoba.py --nokori <id>                    … 印の無いシートを出す（終了コード 1＝残りあり）
#   python3 mienai-kotoba.py --ichiran                        … 本ごとの 印／全シート
# 門 saboranai.py が呼ぶのは gate(vid)。スイッチ（ON の印ファイル）が無い間は数えるだけで止めない。
# 置き場 ~/rin6/state/yt-henshu/mienai/kotoba/
#   salt        … 合言葉を混ぜる種（600）
#   daicho.jsonl… 出した合言葉（混ぜた形）・合った／違った（1回ごと）
#   utsushi/<id>/sNNNN.jpg … 合言葉入りの写し（印が付いたら消す）
#   ON          … これがあると門で止める（書き手への案内を配ってから本体が置く）
import os, sys, json, glob, hashlib, secrets, datetime, fcntl

BASE = '~/rin6/state/yt-anime-1014/kata/full'
OUT = os.path.expanduser('~/rin6/state/yt-henshu/mienai/kotoba')
DAICHO = os.path.join(OUT, 'daicho.jsonl')
SALT = os.path.join(OUT, 'salt')
ON = os.path.join(OUT, 'ON')
ABC = 'ACEFHJKLMNPRTUWXY3479'   # 見間違えやすい字（0O1I5S8B2Z）を抜いた
NLEN = 5
FAIL_HEAD = '見た印（合言葉）の無いシートがある'
FONT = '/System/Library/Fonts/Menlo.ttc'


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def salt():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(SALT):
        fd = os.open(SALT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_hex(32).encode()); os.close(fd)
    return open(SALT).read().strip()


def mix(vid, sheet, code):
    return hashlib.sha256(('%s|%s|%s|%s' % (salt(), vid, sheet, code.upper())).encode()).hexdigest()


def sheet_name(s):
    s = os.path.basename(s).replace('.jpg', '')
    if not s.startswith('s'): s = 's' + s
    return 's%04d' % int(s[1:])


def sheets_of(vid):
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(BASE, 'raw', vid, 'sb', 's*.jpg')))


def append(rec):
    os.makedirs(OUT, exist_ok=True)
    with open(DAICHO, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def rows():
    out = []
    if os.path.exists(DAICHO):
        for l in open(DAICHO):
            try: out.append(json.loads(l))
            except Exception: pass
    return out


def stamp(src, dst, code):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(src).convert('RGB')
    w, h = im.size
    band = 90
    out = Image.new('RGB', (w, h + band), (0, 0, 0))
    out.paste(im, (0, 0))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT, 64)
    d.text((24, h + 10), 'MITA %s' % code, font=f, fill=(255, 230, 0))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out.save(dst, quality=88)


def dasu(vid, names):
    have = set(sheets_of(vid))
    if not have: sys.exit('%s のシートが raw/%s/sb に無い' % (vid, vid))
    for n in names:
        s = sheet_name(n)
        if s not in have: sys.exit('%s に %s は無い' % (vid, s))
        code = ''.join(secrets.choice(ABC) for _ in range(NLEN))
        dst = os.path.join(OUT, 'utsushi', vid, s + '.jpg')
        stamp(os.path.join(BASE, 'raw', vid, 'sb', s + '.jpg'), dst, code)
        append({'at': now(), 'vid': vid, 'sheet': s, 'kind': 'dasu', 'h': mix(vid, s, code), 'by': os.environ.get('MIENAI_BY', '')})
        print(dst)


def latest_dasu(vid, s):
    r = [x for x in rows() if x.get('vid') == vid and x.get('sheet') == s and x.get('kind') == 'dasu']
    return r[-1] if r else None


def mita(vid, pairs):
    bad = 0
    for p in pairs:
        if '=' not in p: sys.exit('「s0081=合言葉」の形で打つ（%s）' % p)
        n, code = p.split('=', 1)
        s = sheet_name(n)
        d = latest_dasu(vid, s)
        if not d:
            print('%s %s：合言葉を出していない（先に --dasu）' % (vid, s)); bad += 1; continue
        if any(x.get('dasu_at') == d['at'] for x in rows() if x.get('vid') == vid and x.get('sheet') == s):
            print('%s %s：この合言葉はもう使った（当て直しはできない）。--dasu で出し直して開き直す' % (vid, s)); bad += 1; continue
        ok = mix(vid, s, code.strip()) == d['h']
        append({'at': now(), 'vid': vid, 'sheet': s, 'kind': 'mita' if ok else 'chigau', 'dasu_at': d['at'], 'by': os.environ.get('MIENAI_BY', '')})
        if ok:
            print('%s %s：見た印 OK' % (vid, s))
            try: os.remove(os.path.join(OUT, 'utsushi', vid, s + '.jpg'))
            except OSError: pass
        else:
            bad += 1
            print('%s %s：合言葉が違う。画像が出ていなかった可能性。このシートについて書いたことは使わず、--dasu で出し直して開き直す' % (vid, s))
    sys.exit(1 if bad else 0)


def mita_set(vid, rs=None):
    rs = rows() if rs is None else rs
    return {x['sheet'] for x in rs if x.get('vid') == vid and x.get('kind') == 'mita'}


def nokori(vid, rs=None):
    m = mita_set(vid, rs)
    return [s for s in sheets_of(vid) if s not in m]


def on_time():
    """ON を置いた時刻（中身の ISO 日時、読めなければ mtime）。ON が無ければ None"""
    if not os.path.exists(ON): return None
    try:
        return datetime.datetime.fromisoformat(open(ON).read().strip()).timestamp()
    except Exception:
        return os.path.getmtime(ON)


def gate(vid, rs=None, per_mtime=None):
    """(門の1行 or None, メモの1行)。ON が無いとき・ON より前に per_full が更新された本は止めない（数えるだけ）"""
    all_ = sheets_of(vid)
    if not all_: return None, '見た印：シート無し'
    left = nokori(vid, rs)
    note = '見た印（合言葉）：%d／%d 枚' % (len(all_) - len(left), len(all_))
    if not left: return None, note
    t_on = on_time()
    if t_on is None: return None, note + '（スイッチ OFF のため数えるだけ）'
    if per_mtime is not None and per_mtime <= t_on: return None, note + '（ON より前の per_full のため数えるだけ）'
    return ('%s：%d／%d 枚（%s%s）。tools/yt-henshu/mienai-kotoba.py --dasu で合言葉入りの写しを出し、画像に見えた合言葉を --mita で打つ。'
            '合言葉が見えなかったシートは画像が出ていない＝そのシートについて書いたことを使わず開き直す'
            % (FAIL_HEAD, len(left), len(all_), '・'.join(left[:12]), ' ほか' if len(left) > 12 else '')), note


def ichiran():
    rs = rows()
    vids = sorted({x['vid'] for x in rs} | {os.path.basename(os.path.dirname(os.path.dirname(p))) for p in glob.glob(os.path.join(BASE, 'raw', '*', 'sb'))})
    for v in vids:
        n = len(sheets_of(v))
        if not n: continue
        m = len(mita_set(v, rs) & set(sheets_of(v)))
        ch = sum(1 for x in rs if x.get('vid') == v and x.get('kind') == 'chigau')
        if m or ch: print('%s\t%d/%d\t違った %d' % (v, m, n, ch))
    print('スイッチ：%s' % ('ON（門で止める）' if os.path.exists(ON) else 'OFF（数えるだけ）'))


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == '--dasu': dasu(a[1], a[2:])
    elif len(a) >= 3 and a[0] == '--mita': mita(a[1], a[2:])
    elif len(a) == 2 and a[0] == '--nokori':
        r = nokori(a[1]); print('\n'.join(r)); print('%s：印の無いシート %d 枚' % (a[1], len(r))); sys.exit(1 if r else 0)
    elif a == ['--ichiran']: ichiran()
    else: sys.exit(__doc__ or open(__file__).read().split('import os')[0])


if __name__ == '__main__':
    main()
