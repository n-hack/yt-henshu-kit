#!/usr/bin/env python3
# YouTube 編集の進みを依頼主へ毎時（作業AI・2026-10-16・依頼主 00:25「動画編集の進捗は、このスレッドで随時こまめに報告して」）
#   python3 houkoku.py          … 測って、送る時間なら #報告の部屋「YouTubeマーケター・動画編集」へ1通。前回の数字を state に残す
#   python3 houkoku.py --dry    … 測って本文を出すだけ（送らない・state も変えない）
#   python3 houkoku.py --force  … 夜中でも送る
# 送る時間：毎時0分（cron）。夜中（1〜6時台）は節目（練習の点数が出た・型のデータが全部そろった・作業員が全員止まった）の時だけ
# 置き場：前回の数字 ~/rin6/state/yt-henshu/houkoku-state.json ／ 送った本文 ~/rin6/state/yt-henshu/houkoku/<日時>.txt
import os, sys, json, glob, re, time, datetime, subprocess

BASE = '~/rin6/state/yt-anime-1014'
FULL = os.path.join(BASE, 'kata/full')
PER = os.path.join(BASE, 'kata/per_full')
YORU = os.path.join(FULL, 'yoru')
MIKAI = os.path.join(BASE, 'mikai')
KANTEN = os.path.join(BASE, 'kanten-zenbu.md')
ME = os.path.expanduser('~/rin6/state/yt-henshu')
STATE = os.path.join(ME, 'houkoku-state.json')
OUT = os.path.join(ME, 'houkoku')
OKURU = os.path.expanduser('~/rin6/tools/okuru.sh')
CH = '000000000000000000'          # #報告の部屋「YouTubeマーケター・動画編集」
DAIHYO = '<@000000000000000000>'
ZENTAI = 202
YORU_JIKAN = range(1, 7)            # 1:00〜6:59 は節目だけ
TOMATTA_MIN = 30                    # これより長く誰も進んでいなければ頭に一言
ZENIN_TOMATTA_MIN = 60              # これより長く誰も進んでいなければ「全員止まった」（夜中も送る節目）
MOKUHYOU = datetime.date(2026, 10, 22)   # 依頼主に1本お見せする目標（dandori.json が読めないときだけ使う・10/18 作業AIの決定）
MOKUHYOU_JOUKEN = '依頼主の声と台本が10/20までに届いた場合'
KATA_SHIMEKIRI = datetime.datetime(2026, 10, 18, 23, 59)   # 目標に間に合うには型のデータがここまでにそろう（残り2日は練習と1本目）
YOUBI = '月火水木金土日'

now = datetime.datetime.now()


def ts(s):
    try:
        return datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def hi(d):
    return '%d/%d(%s)' % (d.month, d.day, YOUBI[d.weekday()])


def itsu(d):
    return '%s %d時ごろ' % (hi(d), d.hour)


def hakaru():
    m = {'at': now.strftime('%Y-%m-%d %H:%M:%S')}
    # 前処理（機械）… raw/<id>/yoru.done（やり直しの控え _yarinaoshi_* の中は数えない）
    m['mae'] = len(glob.glob(os.path.join(FULL, 'raw/*/yoru.done')))
    rows = []
    for l in open(os.path.join(YORU, 'progress.tsv'), encoding='utf-8'):
        t = ts(l.split('\t')[0])
        if t: rows.append(t)
    m['mae_1h'] = sum(1 for t in rows if t >= now - datetime.timedelta(hours=1))
    m['mae_3h'] = sum(1 for t in rows if t >= now - datetime.timedelta(hours=3))
    # 型のデータ（per_full）と検査（サボらない門）の最新の報告
    m['kata'] = len(glob.glob(os.path.join(PER, '*.json')))
    m['kata_ids'] = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(PER, '*.json')))
    rep = sorted(glob.glob(os.path.join(FULL, 'saboranai-2*.md')))
    m['kensa'] = None
    if rep:
        for l in open(rep[-1], encoding='utf-8'):
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            if len(c) == 6 and c[0] == '計':
                m['kensa'] = {'at': os.path.basename(rep[-1])[10:-3], 'tsuita': int(c[2]), 'gokaku': int(c[3]), 'fugokaku': int(c[4]), 'machi': int(c[5])}
    # 観点の一覧
    m['kanten'] = None
    if os.path.exists(KANTEN):
        s = open(KANTEN, encoding='utf-8').read()
        n = len(re.findall(r'^## \d+\. ', s, re.M))
        b = re.search(r'\*\*(\d+)本\*\*', s)
        m['kanten'] = {'n': n, 'bosuu': int(b.group(1)) if b else None,
                       'at': datetime.datetime.fromtimestamp(os.path.getmtime(KANTEN)).strftime('%m/%d %H:%M')}
    # 答えを見ない練習（mikai/<id>/score.json）
    m['renshu'] = []
    for p in sorted(glob.glob(os.path.join(MIKAI, '*/score.json'))):
        try:
            d = json.load(open(p))
            m['renshu'].append({'id': d.get('id'), 'at': d.get('at'), 'ten': round(d.get('total', 0) * 100),
                                'sen': round(d.get('line', {}).get('total_min', 0) * 100), 'pass': bool(d.get('pass')), 'label': d.get('label', '')})
        except Exception:
            pass
    # 作業員（progress-<shard>.txt の最終行の時刻）と型のデータの最後の更新
    saigo = []
    for p in sorted(glob.glob(os.path.join(FULL, 'progress-*.txt'))):
        ls = [l for l in open(p, encoding='utf-8') if ts(l)]
        if ls: saigo.append(ts(ls[-1]))
    m['sagyouin'] = len(glob.glob(os.path.join(FULL, 'progress-*.txt')))
    m['ugoku'] = sum(1 for t in saigo if t >= now - datetime.timedelta(minutes=TOMATTA_MIN))
    pf = [datetime.datetime.fromtimestamp(os.path.getmtime(p)) for p in glob.glob(os.path.join(PER, '*.json'))]
    last = max(saigo + pf) if (saigo or pf) else None
    m['saigo_susumi'] = last.strftime('%Y-%m-%d %H:%M:%S') if last else None
    m['tomatta_min'] = int((now - last).total_seconds() // 60) if last else None
    # 10/18 作業AI：書き手を決めた進め方で止めている（指示が prompts-paused-* にあり、prompts/ に動いている yt-full-*.json が無い）ときは「止まり」と数えない
    W = os.path.expanduser('~/rin6/state/workers')
    m['tometeiru'] = bool(glob.glob(os.path.join(W, 'prompts-paused-*', 'yt-full-*.json'))) and not glob.glob(os.path.join(W, 'prompts', 'yt-full-*.json'))
    # 10/18 作業AI：答えを見ない練習の結果は yt-renshu の kekka-new.tsv（1行1回・id／作り／見た目の点）
    m['renshu_kekka'] = []
    KK = os.path.expanduser('~/rin6/state/yt-renshu/1018/kekka-new.tsv')
    if os.path.exists(KK):
        for l in open(KK, encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            g = re.search(r'見た目([0-9.]+)', c[2]) if len(c) >= 3 else None
            if g: m['renshu_kekka'].append({'id': c[0], 'tsukuri': c[1], 'ten': round(float(g.group(1)) * 100)})
    return m


def tomari_kaisuu():
    """止まり見張り（tomari-mihari.py・5分おき）の今日の回数を1行。読めなければ出さない"""
    try:
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tomari-mihari.py'), '--kaisuu'],
                           capture_output=True, text=True, timeout=60)
        return '今日の止まりの見張り：' + r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def kata_pace(m, st):
    """型のデータの1時間あたり。前回までの記録から直近3時間ぶん（無ければ per_full の更新時刻）で見る"""
    hist = [h for h in st.get('hist', []) if ts(h['at']) and ts(h['at']) >= now - datetime.timedelta(hours=3, minutes=10)]
    if hist and (now - ts(hist[0]['at'])).total_seconds() >= 3600:
        hrs = (now - ts(hist[0]['at'])).total_seconds() / 3600
        return max(m['kata'] - hist[0]['kata'], 0) / hrs
    n = sum(1 for p in glob.glob(os.path.join(PER, '*.json')) if os.path.getmtime(p) >= time.time() - 3 * 3600)
    return n / 3


def kata_1h(m, st):
    hist = [h for h in st.get('hist', []) if ts(h['at'])]
    base = [h for h in hist if ts(h['at']) <= now - datetime.timedelta(minutes=50)]
    if base:
        return m['kata'] - base[-1]['kata']
    return sum(1 for p in glob.glob(os.path.join(PER, '*.json')) if os.path.getmtime(p) >= time.time() - 3600)


def mae_jikan_pace():
    """前処理の1時間あたり済んだ動画の長さ（秒/時）。progress.tsv の3列目（動画の秒）を直近3時間で"""
    t = 0.0
    for l in open(os.path.join(YORU, 'progress.tsv'), encoding='utf-8'):
        c = l.rstrip('\n').split('\t'); d = ts(c[0])
        if d and d >= now - datetime.timedelta(hours=3) and len(c) > 2:
            try: t += float(c[2])
            except ValueError: pass
    return t / 3


def mae_nokori_jikan():
    """まだ yoru.done の無い本の動画の長さの合計（秒）。長さは yoru/durs.tsv"""
    durs = {}
    for l in open(os.path.join(YORU, 'durs.tsv'), encoding='utf-8'):
        c = l.rstrip('\n').split('\t')
        if len(c) > 1: durs[c[0]] = float(c[1])
    t = 0.0
    for l in open(os.path.join(FULL, 'all.txt'), encoding='utf-8'):
        v = os.path.basename(l.strip())[:-4]
        if v and not os.path.exists(os.path.join(FULL, 'raw', v, 'yoru.done')): t += durs.get(v, 0)
    return t


def sa(n):
    return ('+%d' % n) if n >= 0 else ('%d' % n)


def honbun(m, st):
    mae = st.get('mae') or {}
    L = []
    tomatta = m['tomatta_min'] is not None and m['tomatta_min'] >= TOMATTA_MIN and not m.get('tometeiru')
    if tomatta:
        L.append('作業員が%d分、1本も進んでいません（いま立て直しています）' % m['tomatta_min'])
        L.append('')
    L.append('%s 動画編集の進み（%s）' % (DAIHYO, now.strftime('%m/%d %H:%M').lstrip('0')))
    L.append('')
    # 前処理
    nokori = ZENTAI - m['mae']
    L.append('■ 202本の前処理（機械）')
    zen = '（前回%d本から%s・この1時間 +%d）' % (mae['mae'], sa(m['mae'] - mae['mae']), m['mae_1h']) if 'mae' in mae else '（この1時間 +%d）' % m['mae_1h']
    L.append('%d本済み%s' % (m['mae'], zen))
    # 10/17 yt-hozon：本数ではなく動画の時間で見込む（残りは長い本ほど多い＝本数の割合だと早く出すぎる）。直近3時間に済んだ動画時間の1時間あたりで割る
    rate = mae_jikan_pace()
    if nokori <= 0:
        L.append('全部済みました')
    elif rate > 0:
        L.append('このペースだと全部済むのは %s' % itsu(now + datetime.timedelta(hours=mae_nokori_jikan() / rate)))
    else:
        L.append('この3時間 0本のため、済む日はまだ出せません')
    L.append('')
    # 型のデータ
    k1 = kata_1h(m, st)
    L.append('■ 型のデータ（1本ずつ全編を見て書く）')
    zen = '（前回%d本から%s・この1時間 %s）' % (mae['kata'], sa(m['kata'] - mae['kata']), sa(k1)) if 'kata' in mae else '（この1時間 %s）' % sa(k1)
    L.append('%d本%s' % (m['kata'], zen))
    if m['kensa']:
        L.append('検査に合格 %d本・やり直し %d本' % (m['kensa']['gokaku'], m['kensa']['fugokaku']))
    kp = kata_pace(m, st)
    kata_owari = None
    if m['kata'] >= ZENTAI:
        L.append('全部そろいました')
    elif m.get('tometeiru'):
        L.append('%d本で止めて練習を先に回しています（予定どおり）' % m['kata'])
    elif kp > 0:
        kata_owari = now + datetime.timedelta(hours=(ZENTAI - m['kata']) / kp)
        L.append('直近3時間のペース（1時間 %.1f本）だと全部そろうのは %s' % (kp, itsu(kata_owari)))
    else:
        L.append('直近3時間 0本のため、そろう日はまだ出せません')
    if not m.get('tometeiru'):
        L.append('作業員 %d人のうち、この30分に進んだのは %d人' % (m['sagyouin'], m['ugoku']))
    tm = tomari_kaisuu()
    if tm:
        L.append(tm)
    L.append('')
    # 観点
    if m['kanten']:
        L.append('■ 編集者さんが気をつけていることの一覧')
        L.append('%d観点・見本%d本から基準の数字つき（%s 更新）' % (m['kanten']['n'], m['kanten']['bosuu'] or 0, m['kanten']['at']))
        L.append('')
    # 練習
    L.append('■ 答えを見ない練習（元の動画を見ずに作業AIが作り、元と比べる）')
    if m.get('renshu_kekka'):
        saishin = {}
        for r in m['renshu_kekka']: saishin[r['id']] = r   # 本ごとに最新の版
        L.append('%d回・%d本で練習しました。本ごとの最新の点（100点満点）' % (len(m['renshu_kekka']), len(saishin)))
        for r in sorted(saishin.values(), key=lambda r: -r['ten']):
            L.append('・%s %d点（%s）' % (r['id'], r['ten'], r['tsukuri']))
        L.append('まだ完コピの線には届いていません（直しを続けています）')
    elif m['renshu']:
        for r in m['renshu'][-3:]:
            L.append('%d点（合格の線 %d点）%s' % (r['ten'], r['sen'], '合格' if r['pass'] else ''))
    else:
        L.append('まだ点数はありません')
    L.append('')
    # 目標（10/18 作業AI：日付は道具に固定せず ~/rin6/state/yt-keikaku/dandori.json から読む・読めなければ MOKUHYOU）
    mok, jouken = MOKUHYOU, MOKUHYOU_JOUKEN
    try:
        dj = json.load(open(os.path.expanduser('~/rin6/state/yt-keikaku/dandori.json'), encoding='utf-8'))
        mok = datetime.date.fromisoformat(dj['mokuhyou']); jouken = dj.get('jouken', '')
    except Exception:
        pass
    kijun = mok
    if kata_owari and kata_owari > KATA_SHIMEKIRI:
        mok = kijun + datetime.timedelta(days=(kata_owari - KATA_SHIMEKIRI).days + 1)
    if mok == kijun:
        L.append('依頼主に1本お見せする目標は%s%s' % (hi(mok), '（%s）' % jouken if jouken else ''))
    else:
        L.append('依頼主に1本お見せする目標は%s（型のデータのいまのペースから、%sより%d日ずれる見込みです）' % (hi(mok), hi(kijun), (mok - kijun).days))
    return '\n'.join(L)


def fushime(m, st):
    """夜中でも送る節目。理由の文字列か None"""
    mae = st.get('mae') or {}
    mae_r = {(r['id'], r['at']) for r in mae.get('renshu', [])}
    if any((r['id'], r['at']) not in mae_r for r in m['renshu']):
        return '練習の点数が出た'
    if m['kata'] >= ZENTAI and mae.get('kata', 0) < ZENTAI:
        return '型のデータが全部そろった'
    tm = m['tomatta_min'] or 0
    if tm >= ZENIN_TOMATTA_MIN and (mae.get('tomatta_min') or 0) < ZENIN_TOMATTA_MIN and not m.get('tometeiru'):
        return '作業員が全員止まった'
    return None


def main():
    dry = '--dry' in sys.argv
    force = '--force' in sys.argv
    os.makedirs(OUT, exist_ok=True)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    m = hakaru()
    yoru = now.hour in YORU_JIKAN
    fs = fushime(m, st)
    body = honbun(m, st)
    print(body)
    print('--- 夜中=%s 節目=%s' % (yoru, fs))
    if dry:
        print('--- 試し（送っていません・state はそのまま）')
        return 0
    soru = force or not yoru or fs
    if soru:
        f = os.path.join(OUT, now.strftime('%Y%m%d-%H%M%S') + '.txt')
        open(f, 'w', encoding='utf-8').write(body + '\n')
        env = dict(os.environ, RIN6_JIHATSU_OK='1')
        r = subprocess.run([OKURU, CH, f], env=env)
        if r.returncode != 0:
            print('🔴 送れませんでした（okuru.sh %d）。前回の数字は変えません' % r.returncode, file=sys.stderr)
            return 1
        st['mae'] = {k: m[k] for k in ('at', 'mae', 'kata', 'renshu', 'tomatta_min')}
    else:
        print('--- 夜中で節目なし：送りません')
        # 夜中に送らなかった回も「止まった」の始まりは覚えておく（同じ節目で2回送らない）
        st.setdefault('mae', {})['tomatta_min'] = m['tomatta_min']
        st['mae']['renshu'] = m['renshu']
    h = st.get('hist', []) + [{'at': m['at'], 'mae': m['mae'], 'kata': m['kata']}]
    st['hist'] = [x for x in h if ts(x['at']) and ts(x['at']) >= now - datetime.timedelta(hours=26)]
    tmp = STATE + '.tmp'
    json.dump(st, open(tmp, 'w'), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
