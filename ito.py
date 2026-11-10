#!/usr/bin/env python3
# 手本の編集者さんの意図の型（作業AI・2026-10-16）
#   依頼主「手本の編集者さんの意図を読み取ってね」。見本 per_full の場面ごとの role・intent・why・visual・telop・sfx・transition から、
#   「何を見せたいか（意図）」「視聴者のどんな気持ちに向けたか」「そのためにどう編集したか」を意図のまとまりごとに束ねる。
#   python3 ito.py build          見本から意図の型を作る → kata/ito_kata.json と ito-zenbu.md（手で md を直さない。正本はこのファイルの ITO）
#   python3 ito.py check <プロジェクト>  作業AIの1本の場面ごとに意図の型を当て、「形だけ合って意図が違う」場面を出す（答えは開かない）
import os, sys, re, json, glob, collections, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import paths
PER = os.path.join(paths.ENGINE, 'kata', 'per_full')
KJ = os.path.join(paths.ENGINE, 'kata', 'ito_kata.json')
MD = os.path.join(paths.ENGINE, 'ito-zenbu.md')
HO = os.path.join(paths.ENGINE, 'kata', 'holdout.txt')

# 意図のまとまり：(名前, 見本の role に当てる語, 何を見せたいか, 視聴者のどんな気持ちに向けるか, 中身に要るもの（台本の言葉）)
#   気持ちは見本の why・intent に出た語を数えて決めた（build の「気持ちの語」に実数を出す）
ITO = [
 ('告知・宣伝', r'告知|宣伝|特典', '本編と切り離した「売り込みの時間」に入ったことと、受け取れる物', '得をしたい・取り残されたくない', r'告知|勉強会|特典|プレゼント|無料|募集|開催|講座|コンサル|セミナー|参加|暴露|開発|ツール|作れる|レベル'),
 ('CTA', r'CTA|登録|高評価|コメント', '次に何をすればよいか（場所と操作）', '今すぐ動く気持ち（迷わせない）', r'ください|概要欄|LINE|ライン|登録|面談|申し込|応募|クリック|コメント|チャンネル|フォーム|見て|しよう|ましょう|べき|てほしい|任せ|依頼|もらえたら|おう|こう[!！]?$|意識|逃げない|ないで'),
 ('限定・希少', r'限定|希少', '数・期限・人数の枠', '今しかない・逃すと損', r'限定|先着|名|人|日|まで|だけ|締め切|満席|残り|今回|のみ|一度きり'),
 ('実績・権威・証拠', r'実績|権威|証拠|信頼|実例', '言っていることが本当だという裏付け（数字・実物）', 'この人の言うことなら信じられる', r'[0-9０-９一二三四五六七八九十百千万億]|実績|受講生|売上|稼|達成|事例|立ち上げ|指導|結果|伸び|山ほど|大手|ジャンル|たくさん'),
 ('否定・常識破り', r'否定|常識破り|逆転|反論', '思い込みを崩す一言', '「え、違うの？」という驚きで止まる', r'ない|ダメ|だめ|NG|違う|間違|逆|実は|むしろ|しない|やめ|嘘|いらない|不要|どうでもいい|誰でも|十分|ほとんどの|みんな.*けど|って言うんですけど|なし|多いんですよ|めんどくさい|しか'),
 ('煽り・損失回避', r'煽り|損失|危機|警告', 'このままだと失うもの', '損をしたくない・危機感', r'損|失|終わ|負け|勝てない|売れない|伸びない|危|ヤバ|やば|手遅れ|一生|消え|落ち|ならない|刺さ|響か|伝わら|成長しない|きつい|難しい|もったいない|無駄|微妙|しまう|ちゃう|なくなる|言えない|ないと'),
 ('問題提起・問い', r'問題提起|問い|疑問', '見る人自身の悩み・問い', '「自分のことだ」と思う', r'[？?]|悩|なぜ|なんで|どう|困|できない|わからない|分からない'),
 ('共感', r'共感|自己開示', '見る人と同じ立場・気持ち', '「わかってくれている」安心', None),
 ('結論・主張', r'結論|主張|原則|定義|気づき', '動画の答えそのもの', '納得・期待（これを知れば変わる）', None),
 ('比較', r'比較|対比', '2つ以上の違い（どちらが良いか）', '違いが一目で分かる納得', r'より|vs|VS|と|違い|＜|＞|比べ|一方|逆に|どっち|ではなく|じゃなく|方が|でも'),
 ('手順・打ち手', r'手順|打ち手|ステップ', 'やることの順番', '自分にもできそう（行動したい）', r'ステップ|手順|まず|次に|最後|①|②|③|④|段目|1つ目|2つ目|一つ目|二つ目|ポイント|やり方|方法|その後|逆算|動線|作ります'),
 ('理由', r'理由', '答えの根拠', '「なるほど」の納得', None),
 ('具体例', r'具体例|自分の例', '抽象を具体で見せる例', '自分の場合を思い浮かべる', None),
 ('まとめ', r'まとめ|締め', '持ち帰ってほしい要点', '覚えて帰れる安心・行動したい', None),
 ('フック・つかみ', r'フック|つかみ|予告|約束', '見続ける理由（題の言い切り・山の先出し）', '続きが気になる期待', None),
 ('場面つなぎ', r'場面つなぎ|章|転換', '話の区切り・今どこにいるか', '迷わず次へ進める', None),
]
NAMES = [x[0] for x in ITO]


def group(role):
    for name, pat, *_ in ITO:
        if re.search(pat, role or ''): return name
    return None


def vclass(kind):
    k = str(kind or '')
    if re.search('スクショ|画面録画|実写|写真|管理画面|チャンネル画面|ページ|実物|行動の画面|画面', k): return '実物'
    if re.search('図|チェック|矢印|比較|表|グラフ|箇条|リスト|アイコン|ピクト|括弧|式|流れ', k): return '図解'
    if re.search('告知|暗い', k): return '告知の地'
    if re.search('人物|イラスト|いらすと|線画', k): return '人物'
    if re.search('キメ|大文字|光|背景動画|明朝|極太|金の数字|赤', k): return 'キメ文字'
    return '文字'


def hue(text):
    s = str(text or '')
    if re.search('赤', s): return '赤'
    if re.search('金|黄', s): return '黄・金'
    if re.search('青|紺', s): return '青'
    m = re.search(r'#([0-9A-Fa-f]{6})', s)
    if not m: return '黒・白・その他'
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)); mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 40: return '黒・白・その他'
    if r >= mx - 10 and g < 120 and b < 120: return '赤'
    if r > 180 and g > 100 and b < 120: return '黄・金'
    if b >= mx - 10 and r < 120: return '青'
    return '黒・白・その他'


FEEL = r'不安|焦り|驚き|安心|期待|共感|納得|信頼|興味|疑問|危機感|希望|笑い|自分ごと|損|得|行動'


def build():
    skip = {l.split()[0] for l in open(HO) if l.strip() and not l.startswith('#')} if os.path.exists(HO) else set()
    G = collections.defaultdict(list); nv = 0
    for f in sorted(glob.glob(os.path.join(PER, '*.json'))):
        vid = os.path.basename(f)[:-5]
        if vid in skip: continue
        nv += 1
        for s in json.load(open(f)).get('scenes') or []:
            if not isinstance(s, dict): continue
            g = group(s.get('role'))
            if g: G[g].append((vid, s))
    out = {'n_videos': nv, 'at': datetime.datetime.now().isoformat(timespec='minutes'), 'groups': {}}
    for name, pat, show, feel, need in ITO:
        ss = G.get(name) or []
        if not ss: continue
        n = len(ss)
        vc = collections.Counter(vclass((s.get('visual') or {}).get('kind')) for _, s in ss)
        cc = collections.Counter(hue((s.get('telop') or {}).get('color')) for _, s in ss)
        sfx = sum(1 for _, s in ss if s.get('sfx')) / n
        tr = collections.Counter('全消し' if re.search('全消し|切り替|カット|場面', str(s.get('transition'))) else '足し算' if '足し' in str(s.get('transition')) else 'そのほか' for _, s in ss)
        fw = collections.Counter(w for _, s in ss for w in re.findall(FEEL, (s.get('why') or '') + (s.get('intent') or '')))
        # 例：別々の本から、why が具体的なもの（長さ 40〜140 字）を3つ
        ex, seen = [], set()
        for vid, s in sorted(ss, key=lambda x: abs(len(x[1].get('why') or '') - 90)):
            if vid in seen or not (40 <= len(s.get('why') or '') <= 140): continue
            seen.add(vid); ex.append({'id': vid, 't0': s.get('t0'), 'say': (s.get('say') or '')[:40], 'intent': s.get('intent'), 'why': s.get('why'),
                                      'visual': (s.get('visual') or {}).get('kind')})
            if len(ex) == 3: break
        share = {k: round(v / n, 3) for k, v in vc.most_common()}
        out['groups'][name] = {'n': n, 'videos': len({v for v, _ in ss}), 'show': show, 'feel': feel, 'need': need,
                               'visual': share, 'color': {k: round(v / n, 3) for k, v in cc.most_common()}, 'sfx': round(sfx, 3),
                               'transition': {k: round(v / n, 3) for k, v in tr.most_common()}, 'feel_words': fw.most_common(5), 'examples': ex,
                               'main_means': [k for k, v in share.items() if v >= 0.15], 'rare_means': [k for k in ('文字', '図解', '実物', '人物', 'キメ文字', '告知の地') if share.get(k, 0) < 0.05]}
    json.dump(out, open(KJ, 'w'), ensure_ascii=False, indent=1)
    open(MD, 'w').write(md(out)); print('見本 %d本・意図のまとまり %d → %s・%s' % (nv, len(out['groups']), KJ, MD))


def pct(d): return '・'.join('%s %d%%' % (k, round(v * 100)) for k, v in d.items() if v >= 0.05)


def md(o):
    L = ['# 手本の編集者さんの意図の型（作業AI・%s 作成）' % o['at'].replace('T', ' '), '',
         '見本 per_full **%d本** の場面ごとの記録（役割・意図・理由・絵・文字の色・効果音・切り替え）から、この編集者が場面ごとに「何を見せたいか」「視聴者のどんな気持ちに向けたか」「そのためにどう編集したか」を、意図のまとまりごとに束ねた。'
         '`python3 ~/rin6/tools/yt-henshu/ito.py build` で per_full が増えるたびに作り直す（この md は自動で書く。正本は `tools/yt-henshu/ito.py` の ITO）。' % o['n_videos'], '',
         '## 使い方', '',
         '- 作業AIの1本は `ito.py check <プロジェクト>` で、場面ごとに意図のまとまりを当てて点検する。見るのは2つ',
         '  - 中身が意図に合っているか：役割を「実績」と書いたのに数字も実物もない、「比較」と書いたのに比べる2つがない、など（形だけ合って意図が違う）',
         '  - 手段が意図に合っているか：その意図で見本がほとんど使わない絵（5%未満）を選んでいないか',
         '- 下書きの決まり文句（「〜の流れの中で言った順に積む」「口語・推量を外して見出し語に直し…」）のままの場面は、意図を言葉にしていないので直す対象', '']
    for name, *_ in ITO:
        g = o['groups'].get(name)
        if not g: continue
        L += ['## %s（%d場面・%d本）' % (name, g['n'], g['videos']), '',
              '- **見せたいもの**：' + g['show'], '- **視聴者の気持ち**：' + g['feel'] + '（見本の理由に出た語：' + '・'.join('%s %d' % w for w in g['feel_words']) + '）',
              '- **編集の手段**：絵は ' + pct(g['visual']) + '／文字の色は ' + pct(g['color']) + '／効果音あり %d%%' % round(g['sfx'] * 100) + '／切り替えは ' + pct(g['transition']),
              '- **ほぼ使わない絵**：' + ('・'.join(g['rare_means']) or 'なし'), '- **中身に要るもの**：' + ('台本にこの語のどれか（' + g['need'].replace('|', '・')[:80] + '）' if g['need'] else '決めていない（形で縛らない）'), '',
              '例（別々の本から）', '']
        for e in g['examples']:
            L.append('- %s %s秒「%s」→ 意図：%s ／ 編集：%s（%s）' % (e['id'], e['t0'], e['say'], e['intent'], e['why'], e['visual']))
        L.append('')
    return '\n'.join(L) + '\n'


BOILER = r'の流れの中で言った順に積む|口語・推量を外して見出し語に直し'


def check(P):
    o = json.load(open(KJ)); meta = json.load(open(os.path.join(P, 'work', 'story_meta.json')))
    plan = sorted(meta.get('selection_plan') or [], key=lambda x: x['t']); intent = sorted(meta.get('intent') or [], key=lambda x: x['t'])
    rows = []
    for it in intent:
        pl = [p for p in plan if abs(p['t'] - it['t']) < 0.05]
        p = pl[0] if pl else {}
        said = ' '.join(p.get('dropped') or []) + ' ' + ' '.join(p.get('shown') or [])
        g = group(it.get('role')); vc = vclass(p.get('visual') or it.get('edit'))
        why = []
        if re.search(BOILER, (it.get('intent') or '') + (it.get('why') or '')): why.append('意図が決まり文句のまま')
        if g and g in o['groups']:
            gg = o['groups'][g]
            if gg['need'] and not re.search(gg['need'], said): why.append('中身が「%s」になっていない' % g)
            if vc in gg['rare_means'] and not re.search('告知', str(p.get('flow') or '')): why.append('「%s」で見本がほぼ使わない絵（%s）' % (g, vc))
        rows.append({'t': it['t'], 'role': it.get('role'), 'group': g, 'visual': p.get('visual'), 'said': said.strip()[:60], 'why': why})
    bad = [r for r in rows if r['why']]
    for r in bad: print('%7.1f %-10s %-14s %s ｜ %s' % (r['t'], r['role'], r['visual'], '／'.join(r['why']), r['said']))
    print('場面 %d ／ 点検に掛かった %d（決まり文句 %d・中身が違う %d・手段が違う %d）' % (len(rows), len(bad), sum('決まり文句' in ' '.join(r['why']) for r in bad),
          sum('中身が' in ' '.join(r['why']) for r in bad), sum('ほぼ使わない' in ' '.join(r['why']) for r in bad)))
    json.dump(rows, open(os.path.join(P, 'work', 'ito_check.json'), 'w'), ensure_ascii=False, indent=1)
    return bad


if __name__ == '__main__':
    a = sys.argv[1:] or ['build']
    if a[0] == 'build': build()
    elif a[0] == 'check': check(os.path.abspath(a[1]))
