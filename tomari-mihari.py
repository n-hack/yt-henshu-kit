#!/usr/bin/env python3
# YouTube の止まり見張り（作業AI・2026-10-16・依頼主 20:18「これサボらないように仕組み化して」）
#   10/16 19:3x に書き手8人が上限で消え、20:16 まで87分だれも気づかなかった。前処理も 16:55 から止まっていた
#   （古い ana-gen が札を握ったまま・evict.py が cron で sysctl を見つけられず落ちていた）。毎時の報告は「87分進んでいない」と書いたが手を打たなかった。
#   → 測る → 赤なら機械は自分で直す → 書き手は作業AIの本体へ「出し直して」の合図 → 60分直らなければ依頼主の部屋へ1行
#
#   python3 tomari-mihari.py           … 測って、赤なら直す・合図する（cron 5分おき）
#   python3 tomari-mihari.py --dry     … 測って判定を出すだけ（直さない・合図しない・state も変えない）
#   python3 tomari-mihari.py --kaisuu  … 今日の「見つけた／自動で直した」回数を1行（houkoku.py が読む）
#   試験用  --base <dir>（置き場を差し替え）／--now 'YYYY-MM-DD HH:MM:SS'（いまの時刻を差し替え）／--state <file>／--win <tmux窓>／--no-okuru
#
# 赤の決まり
#   書き手   … その shard の書き手（yt-full-<N>…）の会話記録が30分以上動いていない（＝上限などで消えた）で、その shard がまだ全部合格していない
#              1本に動画の長さ以上かけるので per_full の更新だけでは30分の空きが普通に出る → 生死は会話記録（subagents/agent-a<名前>-*.jsonl）の更新で見る
#   書き手が遅い … 会話記録は動いているのに、その shard の最後の進み（progress・per_full・門の判定）が4時間以上前（出し直さず本体に見てもらう）
#   前処理   … progress.tsv の最後の済みが30分以上前で、残りがあり、かつ yoru が動いていない か 解析も音も1本も動いていない
#   孤児の札 … ana-gen が生きているのに yoru が動いていない／ana-gen が札を持ったまま30分だれも進んでいない
#   死んだ札 … raw/<id>/.yoru_ana1 の持ち主の pid が死んでいる（10分以上たったもの）
#   evict    … hozon/log/cron.log に evict.py の落ちた跡（Traceback）が前回より増えた
# 直すこと（データは消さない。札＝中に pid が1つあるだけの空の印 は返してよい）
#   孤児の ana-gen … SIGTERM（ana-gen は受けると持っていた札を全部返して終わる）→ 5秒で消えなければ SIGKILL → その pid の札だけ返す
#   死んだ札 …… 中身が pid だけのものを返す
#   yoru が止まっている …… cron と同じ形で1回起こす（二重には起きない＝yoru.lock）
#   evict が落ちた …… 直さない（道具の直しは人の手）。記録して本体へ知らせる
#   書き手 …… cron からは作業員を出せないので、本体の窓（tmux rin:rin6）へ「[自動・YouTube止まり] 出し直す作業員: …」を届ける（30分に1回まで）
#   60分 赤が続いたら … 依頼主の部屋へ1行（その止まりで1回だけ）
import os, sys, json, time, glob, re, signal, subprocess, datetime, argparse

ap = argparse.ArgumentParser()
ap.add_argument('--dry', action='store_true')
ap.add_argument('--kaisuu', action='store_true')
ap.add_argument('--shiken-aizu', action='store_true')   # 試験：本体の窓へ「何もしなくて大丈夫」の合図を1回だけ届ける
ap.add_argument('--base', default='~/rin6/state/yt-anime-1014')
ap.add_argument('--now')
ap.add_argument('--state', default=os.path.expanduser('~/rin6/state/yt-henshu/tomari/state.json'))
ap.add_argument('--win', default='rin6')
ap.add_argument('--no-okuru', action='store_true')
ap.add_argument('--proj', default='~/.claude-rin6/projects/-Users-sam-rin6')
A = ap.parse_args()

BASE = A.base
FULL = os.path.join(BASE, 'kata/full')
PER = os.path.join(BASE, 'kata/per_full')
RAW = os.path.join(FULL, 'raw')
YORU = os.path.join(FULL, 'yoru')
VERD = os.path.join(FULL, 'saboranai/verdict')
EVICT_LOG = os.path.join(BASE, 'hozon/log/cron.log')
PROMPTS = os.path.expanduser('~/rin6/state/workers/prompts')
ME = os.path.dirname(A.state)
EVENTS = os.path.join(ME, 'events.tsv')
WAKE = '~/rin/scripts/wake-rin.sh'
OKURU = os.path.expanduser('~/rin6/tools/okuru.sh')
CH = '000000000000000000'           # #報告の部屋「YouTubeマーケター・動画編集」
DAIHYO = '<@000000000000000000>'
TAG = '[自動・YouTube止まり]'
ZENTAI = 202
TOMARI_MIN = 30                     # これより長く進まなければ赤
AIZU_MIN = 30                       # 本体への合図は30分に1回まで
DAIHYO_MIN = 60                     # 赤がこれより長く続いたら依頼主の部屋へ1行
SHINDA_FUDA_MIN = 10                # 死んだ札は10分たってから返す
OSOI_MIN = 240                      # 書き手が生きていても、これより長く1本も進まなければ本体に見てもらう
PY = '/opt/homebrew/bin/python3'
YORU_ENV = {'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'ja_JP.UTF-8',
            'YORU_GA': '4', 'YORU_OTO': '2', 'YORU_WHISPER': '2', 'YORU_ANA': '4', 'HOME': '~'}   # cron の行と同じ
OTO = ('words3.py', 'stems.py', 'resample.py', 'demucs', 'whisper')

NOW = datetime.datetime.strptime(A.now, '%Y-%m-%d %H:%M:%S') if A.now else datetime.datetime.now()
NOWT = NOW.timestamp()


def ts(s):
    try:
        return datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').timestamp()
    except Exception:
        return None


def hm(t):
    return datetime.datetime.fromtimestamp(t).strftime('%H:%M') if t else 'なし'


def mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return None


def jload(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def last_ts_line(p):
    t = None
    try:
        for l in open(p, encoding='utf-8', errors='replace'):
            x = ts(l)
            if x and x <= NOWT + 60: t = x
    except OSError:
        pass
    return t


def ps():
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    rows = []
    for l in out.splitlines():
        l = l.strip()
        if not l: continue
        pid, _, cmd = l.partition(' ')
        if 'tomari-mihari' in cmd or cmd.startswith('/bin/sh -c') or cmd.startswith('/bin/zsh') or cmd.startswith('bash -c'):
            continue   # cron の殻・自分・試しのシェルは数えない（中の本体だけ数える）
        rows.append((int(pid), cmd))
    return rows


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def event(kind, detail):
    if A.dry: return
    os.makedirs(ME, exist_ok=True)
    open(EVENTS, 'a', encoding='utf-8').write('%s\t%s\t%s\n' % (NOW.strftime('%Y-%m-%d %H:%M:%S'), kind, detail.replace('\n', ' ')[:500]))


# ---------------- 測る ----------------
def hakaru():
    m = {}
    P = ps()
    # 書き手（shard ごと）
    shards = {}
    for p in sorted(glob.glob(os.path.join(FULL, 'shard*.txt'))):
        n = re.sub(r'\D', '', os.path.basename(p))
        ids = [os.path.splitext(os.path.basename(l.strip()))[0] for l in open(p) if l.strip()]
        ok = [v for v in ids if os.path.exists(os.path.join(PER, v + '.json')) and os.path.exists(os.path.join(VERD, v + '.json'))
              and not (jload(os.path.join(VERD, v + '.json'), {}) or {}).get('fails')]
        last = [last_ts_line(os.path.join(FULL, 'progress-%s.txt' % n))]
        for v in ids:
            last += [mtime(os.path.join(PER, v + '.json')), mtime(os.path.join(VERD, v + '.json'))]
        last = max([x for x in last if x and x <= NOWT + 60] or [0]) or None
        iki, name = None, None
        for f in glob.glob(os.path.join(A.proj, '*', 'subagents', 'agent-ayt-full-%s*.jsonl' % n)):
            mm = re.fullmatch(r'agent-a(yt-full-%s[a-z]?)-[0-9a-f]+\.jsonl' % n, os.path.basename(f))
            t = mtime(f) if mm else None
            if t and t <= NOWT + 60 and (iki is None or t > iki): iki, name = t, mm.group(1)   # --now の再現では未来の更新を見ない
        shards[n] = {'hon': len(ids), 'goukaku': len(ok), 'last': last, 'owari': len(ok) >= len(ids) > 0, 'iki': iki, 'name': name}
    m['shards'] = shards
    m['kata'] = len(glob.glob(os.path.join(PER, '*.json')))
    m['goukaku'] = sum(s['goukaku'] for s in shards.values())
    lasts = [s['last'] for s in shards.values() if s['last']]
    m['kata_last'] = max(lasts) if lasts else None
    # 前処理
    m['mae'] = len(glob.glob(os.path.join(RAW, '*/yoru.done')))
    m['mae_last'] = last_ts_line(os.path.join(YORU, 'progress.tsv'))
    m['mae_nokori'] = max(0, ZENTAI - m['mae'])
    yoru_py = os.path.join(YORU, 'yoru.py')
    m['yoru'] = [pid for pid, c in P if yoru_py in c]
    m['ana1'] = [pid for pid, c in P if os.path.join(YORU, 'ana1.py') in c]
    m['oto'] = [pid for pid, c in P if any(k in c for k in OTO) and BASE in c]
    m['anagen'] = [pid for pid, c in P if os.path.join(YORU, 'ana-gen.py') in c]
    m['paused'] = os.path.exists(os.path.join(YORU, 'DISK_PAUSE'))
    # 札
    fuda = []
    for lk in glob.glob(os.path.join(RAW, '*/.yoru_ana1')):
        try: holder = int(open(os.path.join(lk, 'pid')).read().strip() or 0)
        except Exception: holder = 0
        try: naka = os.listdir(lk)
        except OSError: continue
        fuda.append({'lk': lk, 'vid': lk.split('/')[-2], 'pid': holder, 'alive': bool(holder) and alive(holder),
                     'age_min': (NOWT - (mtime(lk) or NOWT)) / 60, 'naka': naka})
    m['fuda'] = fuda
    # evict の落ちた跡
    try:
        s = open(EVICT_LOG, encoding='utf-8', errors='replace').read()
        m['evict_tb'] = len(re.findall(r'Traceback \(most recent call last\):\n  File "[^"]*evict\.py"', s))
        m['evict_err'] = next((l for l in reversed(s.splitlines()) if re.match(r'^\w+Error', l)), '')[:160]
    except OSError:
        m['evict_tb'], m['evict_err'] = 0, ''
    return m


# ---------------- 判定 ----------------
def hantei(m, st):
    aka = []
    kakite = []
    for n, s in sorted(m['shards'].items(), key=lambda x: int(x[0])):
        if s['owari']: continue
        if not s['iki'] or NOWT - s['iki'] >= TOMARI_MIN * 60:
            kakite.append(n)
    if kakite:
        aka.append(('kakite', '書き手 %d人が%d分以上動いていない（%s）' % (len(kakite), TOMARI_MIN,
                    '・'.join('shard%s 最後に動いた %s・最後の進み %s' % (n, hm(m['shards'][n]['iki']), hm(m['shards'][n]['last'])) for n in kakite))))
    osoi = [n for n, s in m['shards'].items() if not s['owari'] and n not in kakite and (not s['last'] or NOWT - s['last'] >= OSOI_MIN * 60)]
    if osoi:
        aka.append(('osoi', '書き手は動いているが%d時間以上1本も進んでいない（%s）' % (OSOI_MIN // 60,
                    '・'.join('shard%s 最後の進み %s' % (n, hm(m['shards'][n]['last'])) for n in sorted(osoi, key=int)))))
    ugoku = m['ana1'] or m['oto']
    mae_tomari = m['mae_nokori'] > 0 and (not m['mae_last'] or NOWT - m['mae_last'] >= TOMARI_MIN * 60)
    if mae_tomari and (not m['yoru'] or not ugoku):
        why = 'yoru が動いていない' if not m['yoru'] else '解析も音も1本も動いていない'
        if m['paused']: why += '・DISK_PAUSE あり（空きを待つ片付け運転）'
        aka.append(('mae', '前処理が%d分以上済んでいない（最後 %s・残り %d本・%s）' % (TOMARI_MIN, hm(m['mae_last']), m['mae_nokori'], why)))
    # 孤児の ana-gen
    koji = []
    for pid in m['anagen']:
        motsu = [f for f in m['fuda'] if f['pid'] == pid]
        if not m['yoru']:
            koji.append((pid, len(motsu), 'yoru が動いていないのに札を %d 持っている' % len(motsu)))
        elif motsu and mae_tomari:
            koji.append((pid, len(motsu), '札を %d 持ったまま前処理が%d分進んでいない' % (len(motsu), TOMARI_MIN)))
    if koji:
        aka.append(('koji', '孤児の ana-gen：' + '／'.join('pid %d %s' % (p, w) for p, _, w in koji)))
    shinda = [f for f in m['fuda'] if not f['alive'] and f['age_min'] >= SHINDA_FUDA_MIN and set(f['naka']) <= {'pid'}]
    if shinda:
        aka.append(('shinda', '持ち主の死んだ札 %d（%s）' % (len(shinda), '・'.join(f['vid'] for f in shinda[:5]))))
    prev_tb = st.get('evict_tb')
    if prev_tb is not None and m['evict_tb'] > prev_tb:
        aka.append(('evict', 'evict.py が落ちた跡が %d 件増えた（%s）' % (m['evict_tb'] - prev_tb, m['evict_err'] or '中身は hozon/log/cron.log')))
    return aka, kakite, koji, shinda


def sagyouin(n, m=None):
    """shard N の書き手の名前（最後に動いていた会話記録の名前。無ければ台帳 prompts/ の yt-full-<N>… のうち一番新しいもの）"""
    if m and m['shards'].get(n, {}).get('name'):
        return m['shards'][n]['name']
    best = None
    for p in glob.glob(os.path.join(PROMPTS, 'yt-full-%s*.json' % n)):
        nm = os.path.basename(p)[:-5]
        if not re.fullmatch(r'yt-full-%s[a-z]?' % n, nm): continue
        e = jload(p, {}) or {}
        if best is None or e.get('saved_at', '') > best[1]:
            best = (nm, e.get('saved_at', ''))
    return best[0] if best else 'yt-full-%sd' % n


# ---------------- 直す ----------------
def naosu(m, aka, kakite, koji, shinda, st):
    done = []
    kinds = {k for k, _ in aka}
    for pid, n_fuda, why in koji:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(10):
            if not alive(pid): break
            time.sleep(0.5)
        if alive(pid):
            try: os.kill(pid, signal.SIGKILL)
            except OSError: pass
            time.sleep(0.5)
        left = 0
        for f in glob.glob(os.path.join(RAW, '*/.yoru_ana1')):   # 返し損ねた札（その pid のものだけ）
            try:
                if int(open(os.path.join(f, 'pid')).read().strip() or 0) == pid and set(os.listdir(f)) <= {'pid'}:
                    os.remove(os.path.join(f, 'pid')); os.rmdir(f); left += 1
            except Exception:
                pass
        ok = not alive(pid)
        done.append(('koji', ok, '孤児の ana-gen pid %d を止めた（%s・札 %d・残っていた札 %d を返した）%s' % (pid, why, n_fuda, left, '' if ok else ' 🔴 止まらない')))
    n = 0
    for f in shinda:
        try:
            if not alive(f['pid']) and set(os.listdir(f['lk'])) <= {'pid'}:
                for x in os.listdir(f['lk']): os.remove(os.path.join(f['lk'], x))
                os.rmdir(f['lk']); n += 1
        except Exception:
            pass
    if shinda:
        done.append(('shinda', n == len(shinda), '持ち主の死んだ札 %d/%d を返した' % (n, len(shinda))))
    if ('mae' in kinds or 'koji' in kinds) and m['mae_nokori'] > 0 and not hakaru_yoru():
        cmd = ['/usr/bin/nice', '-n', '19', PY, os.path.join(YORU, 'yoru.py')]
        logf = open(os.path.join(YORU, 'log', 'cron.log') if os.path.isdir(os.path.join(YORU, 'log')) else os.devnull, 'a')
        subprocess.Popen(cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL, env=YORU_ENV, start_new_session=True, cwd=BASE)
        time.sleep(8)
        ok = bool(hakaru_yoru())
        done.append(('yoru', ok, 'yoru を起こした%s' % ('（動いている）' if ok else '（8秒後にはもう終わっていた＝やれる本が無い形。理由は上の行・yoru の記録）')))
    if 'evict' in kinds:
        done.append(('evict', False, 'evict.py が落ちている。道具の直しは手で（hozon/tools/evict.py・hozon/log/cron.log）'))
    return done


def hakaru_yoru():
    yp = os.path.join(YORU, 'yoru.py')
    return [pid for pid, c in ps() if len(c.split()) > 1 and os.path.basename(c.split()[0]).lower().startswith('python') and c.split()[1] == yp]   # 10/18 22:5x 先頭が python で2つ目が yoru.py の本物だけ


# ---------------- 合図・依頼主へ ----------------
def aizu_bun(m, aka, kakite, done, test=False):
    names = [sagyouin(n, m) for n in kakite]
    L = [TAG + ('[試験・何もしなくて大丈夫です]' if test else '')]
    if names:
        L.append('出し直す作業員: %s%s。' % (names[0], (' ほか（%s）' % '・'.join(names[1:])) if len(names) > 1 else ''))
        L.append('ListAgents で生きている名前は除き、いない名前は同じ名前で ~/rin6/state/workers/prompts/<名前>.json の prompt をそのまま渡して出し直す（続きは progress と notes から）。')
    for k, s in aka:
        if k != 'kakite': L.append('赤: ' + s + '。')
    for k, ok, s in done:
        L.append(('直した: ' if ok else '直せていない: ') + s + '。')
    L.append('いま 型 %d本（合格 %d）・前処理 %d/%d。終わったら worker-ledger.py で印を付け、YouTube スレッドに「再開しました」1行（tomari-mihari）' % (m['kata'], m['goukaku'], m['mae'], ZENTAI))
    return ' '.join(L)


def todokeru(text):
    env = dict(os.environ, WAKE_RIN_NO_INTERRUPT='yes', PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin')
    r = subprocess.run(['bash', WAKE, text, A.win], capture_output=True, text=True, env=env, timeout=60)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]


def daihyo_e(fun):
    os.makedirs(os.path.join(ME, 'okuru'), exist_ok=True)
    f = os.path.join(ME, 'okuru', NOW.strftime('%Y%m%d-%H%M%S') + '.txt')
    open(f, 'w', encoding='utf-8').write('%s YouTubeの作業が%d分止まっています・いま直しています\n' % (DAIHYO, fun))
    if A.no_okuru:
        return True, '送っていません（--no-okuru）: ' + f
    env = dict(os.environ, RIN6_JIHATSU_OK='1', RIN6_RENSOU_OK='1')   # 止まりの知らせは連投の門で遅らせない（1回だけの決まりは daihyo_sent で守る）
    r = subprocess.run([OKURU, CH, f], capture_output=True, text=True, env=env, timeout=180)
    return r.returncode == 0, (r.stdout + r.stderr).strip()[-300:]


# ---------------- 回数 ----------------
def kaisuu(day=None):
    day = day or NOW.strftime('%Y-%m-%d')
    mitsu = naoshi = aizu = 0
    try:
        for l in open(EVENTS, encoding='utf-8'):
            c = l.rstrip('\n').split('\t')
            if len(c) < 3 or not c[0].startswith(day): continue
            if c[1] == 'aka_hajime': mitsu += 1
            elif c[1].startswith('naoshita'): naoshi += 1
            elif c[1] == 'aizu_ok': aizu += 1
    except OSError:
        pass
    return mitsu, naoshi, aizu


def main():
    if A.kaisuu:
        mi, na, ai = kaisuu()
        print('止まりを見つけた %d回・自動で直した %d回（うち作業の出し直し %d回）' % (mi, na + ai, ai))
        return 0
    st = jload(A.state, {}) or {}
    m = hakaru()
    if A.shiken_aizu:
        ok, err = todokeru(aizu_bun(m, [], [], [], test=True))
        print('試験の合図 %s %s' % ('✅' if ok else '🔴', err))
        return 0 if ok else 1
    aka, kakite, koji, shinda = hantei(m, st)
    print('%s 型 %d本（合格 %d・最後 %s）・前処理 %d/%d（最後 %s）・yoru %s・解析 %d・音 %d・ana-gen %s・札 %d（死 %d）・evict の跡 %d' % (
        NOW.strftime('%m/%d %H:%M'), m['kata'], m['goukaku'], hm(m['kata_last']), m['mae'], ZENTAI, hm(m['mae_last']),
        m['yoru'] or 'なし', len(m['ana1']), len(m['oto']), m['anagen'] or 'なし', len(m['fuda']), sum(1 for f in m['fuda'] if not f['alive']), m['evict_tb']))
    for k, s in aka:
        print('  赤 [%s] %s' % (k, s))
    if not aka:
        print('  緑')
    if A.dry:
        if aka:
            print('--- 合図の文（試し・届けていません）\n' + aizu_bun(m, aka, kakite, []))
        return 0
    kinds = sorted({k for k, _ in aka})
    if aka and not st.get('aka_since'):
        st['aka_since'] = NOWT; st['daihyo_sent'] = False
        event('aka_hajime', ' / '.join(s for _, s in aka))
    done = naosu(m, aka, kakite, koji, shinda, st) if aka else []
    for k, ok, s in done:
        print('  %s %s' % ('直した' if ok else '直せていない', s))
        if k != 'evict': event('naoshita_' + k if ok else 'naosenai_' + k, s)
        else: event('evict_ochita', s)
    # 本体への合図（書き手が止まった・機械で直せないものがあるとき。30分に1回まで）
    need = bool(kakite) or 'osoi' in kinds or 'evict' in kinds or any(not ok for _, ok, _ in done) or ('mae' in kinds and not any(k == 'yoru' and ok for k, ok, _ in done))
    if need and NOWT - st.get('last_aizu', 0) >= AIZU_MIN * 60:
        text = aizu_bun(m, aka, kakite, done)
        ok, err = todokeru(text)
        print('  合図 %s %s' % ('✅' if ok else '🔴', err[:200]))
        event('aizu_ok' if ok else 'aizu_ng', text if ok else err)
        if ok: st['last_aizu'] = NOWT
    elif need:
        print('  合図は %d分前に出したので今回は出さない' % ((NOWT - st.get('last_aizu', 0)) // 60))
    # 60分直らなければ依頼主の部屋へ1行（その止まりで1回）
    if aka and st.get('aka_since') and NOWT - st['aka_since'] >= DAIHYO_MIN * 60 and not st.get('daihyo_sent'):
        fun = int((NOWT - st['aka_since']) // 60) + TOMARI_MIN
        ok, err = daihyo_e(fun)
        print('  依頼主の部屋へ %s %s' % ('✅' if ok else '🔴', err[-200:]))
        event('daihyo_ok' if ok else 'daihyo_ng', err)
        if ok: st['daihyo_sent'] = True
    if not aka and st.get('aka_since'):
        event('midori', '%d分で緑に戻った' % ((NOWT - st['aka_since']) // 60))
        st['aka_since'] = None; st['daihyo_sent'] = False
    st['evict_tb'] = m['evict_tb']; st['at'] = NOW.strftime('%Y-%m-%d %H:%M:%S'); st['aka'] = kinds
    os.makedirs(ME, exist_ok=True)
    tmp = A.state + '.tmp'
    json.dump(st, open(tmp, 'w'), ensure_ascii=False, indent=1)
    os.replace(tmp, A.state)
    return 0


if __name__ == '__main__':
    sys.exit(main())
