#!/usr/bin/env python3
# 編集者の指示書（yt-edl の edl-v14.json：1文ずつ「絵・動き・大字・切り替え・理由」を言葉で書いたもの）を、
#   組み立ての形（EDL-SCHEMA.md の shots）へ写す（v14・10/19）。写すのは AI（claude -p・opus）が章ごとに。
#   決まり：編集者が書いた絵・動き・大字・切り替えを変えない（選び直さない）。手元に無い部品は一番近い部品で置き、tarinai に残す。
#   python3 edl_henkan.py <edl-v14.json> <出力 edl-kumi.json> [--shou 1,2,3] [--heiretsu 4]
import os, sys, json, re, subprocess, argparse, glob
from concurrent.futures import ThreadPoolExecutor
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--shou', default=''); ap.add_argument('--heiretsu', type=int, default=4)
ap.add_argument('--naoshi', default='', help='組み立てで出た直す所（edl_kumi.json）を渡して、その章だけ写し直す')
A = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = json.load(open(os.path.expanduser(A.src)))
SCHEMA = open(os.path.expanduser('~/rin6/state/yt-henshu/pipe-1019/v14/edl/EDL-SCHEMA.md')).read()
JIN = os.path.expanduser('~/rin6/state/yt-henshu/jinbutsu')
def katalog():
    names = sorted({os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(JIN, '**', '*.mov'), recursive=True) + glob.glob(os.path.join(JIN, '**', '*.webm'), recursive=True)} - {'ichiran'})
    imi = {}
    try:
        for m in re.finditer(r"@clip\('([a-z0-9_]+)', '([^']*)', '([^']*)'", open(os.path.join(JIN, 'jinbutsu.py')).read()): imi[m.group(1)] = m.group(2) + '／動き：' + m.group(3)
    except Exception: pass
    rd = os.path.join(JIN, 'README.md'); readme = open(rd).read()[:6000] if os.path.exists(rd) else ''
    gm = json.load(open(os.path.join(HERE, 'gamen.json')))
    return ('動く人物（kind=jinbutsu・name）：\n' + '\n'.join('- %s：%s' % (n, imi.get(n, imi.get(re.sub(r'_(otoko|onna)$', '', n), ''))) for n in names) +
            '\n（同じ動きの男女は _otoko／_onna。A＝みる人の男→_otoko、B＝みる人の女→_onna、R＝エージェント相方→ai_*、M＝自社キャラ→無ければ moji3d の名札＋自社キャラのアイコン mono "chara_icon1024"、C＝チャットAI→mono "chat"（ic）か icon3d "chat"）\n'
            + ('README（部品係）：\n' + readme + '\n' if readme else '') +
            '実際の画面（kind=gamen・name）：' + '・'.join('%s=%s' % kv for kv in gm.items()) + '\n'
            '図解（kind=zukai・fn・args）：kazu_up(label, "数字の文字", size=200)／bars_up(vals, labels)／sen_graph(pts)／en_graph(ratio, label)／maru(w,h)／shitasen(w)／chk(text)／'
            'atsumaru(n, red)／hyou_umeru(rows, head)／kaidan(labels)／tsunagu(length, direction)／sumaho(gamen の name)／card3(icon, head, body, col)／yaji(direction, length, width)／hito_mure(n, red)\n'
            '字：moji3d（大きな立体文字・iro 青赤金白）／fuki（吹き出し）／oaka（赤い明朝の大字）／ao／midashi／obi_aka（赤い帯）／tag／check\n'
            '色の立体アイコン：icon3d（Material Symbols の名前・iro）。黒い単色アイコン（mono の ic）は見づらいので使わない\n'
            '効果：kouka（kamifubuki・spot・kira・hatena・bikkuri・ase・shuchusen）\n')
KIRIKAE = ('切り替えの写し方：全消し→cut／残し足し・続き・帯差替→keep／白飛び→flash／暗転・暗転明け→anten／横流れ→yokobure／ズーム→zoom／放射→hosha／フェード→fade／ワイプ→slide。'
           '「続き（カメラが引く・右へ・上へ…）」は keep＋camera（hiku／pan dx／tilt dy）')
def ask(shou, rows, naoshi=''):
    prompt = ('あなたは動画の組み立て係です。編集者が1文ずつ言葉で書いた指示（下の rows）を、組み立ての道具が読む JSON（下の形）に写してください。\n'
              '決まり：①編集者が書いた絵（e）・動き（ugoki）・大字（ooji）・切り替え（kirikae）をそのまま写す。中身を足したり選び直したりしない。②1行の中で絵や動きが段階的に変わるなら、'
              '場面（shot）を複数に分け、2つ目以降の kotoba はその行の kotoba の中の言葉（声に出てくる字そのまま・4〜8字）にする。最初の shot の kotoba は行の kotoba の頭の8字。'
              '③部品の出（at）は、その場面の中の言葉か秒（数）。④手元に無い部品は一番近い部品で置き、"tarinai" に「行番号：欲しい部品」を書く。⑤ooji があれば moji3d か oaka で必ず出す（「大字なし」は出さない）。'
              '⑥人物は動く人物（jinbutsu）を必ず使う。止まった絵だけの場面は作らない（人物の動き・move・idle・camera・kouka のどれかで動かす）。⑦字幕帯（y≧960）に部品を置かない。'
              '⑧各 shot に imi（言葉の意味）・riyuu（編集者の理由を短く）・wakaru（編集者の isshun）を入れる。id は "s<行番号>_<連番>"、ch は章番号。\n'
              + KIRIKAE + '\n\n組み立ての形：\n' + SCHEMA + '\n\n手元の部品：\n' + katalog() + '\n'
              + (('前回の組み立てで出た直す所（これを直す）：\n' + naoshi + '\n') if naoshi else '') +
              '\n章 %s の訴求：%s\n\nrows：\n%s\n\n返事は JSON だけ：{"shots": [...], "tarinai": ["..."]}') % (shou['shou'], shou.get('sokyu', ''), json.dumps(rows, ensure_ascii=False, indent=0))
    for k in range(2):
        r = subprocess.run(['claude', '-p', '--model', 'opus', '--output-format', 'text'], input=prompt, capture_output=True, text=True, cwd='/tmp', timeout=1800)
        m = re.search(r'\{.*\}', r.stdout, re.S)
        try:
            J = json.loads(m.group()); assert J['shots']; return J
        except Exception: prompt += '\n\n（前の返事が JSON として読めなかった。JSON だけを返す）'
    raise SystemExit('🔴 章 %s の写しが読めない：%s' % (shou['shou'], r.stdout[-400:]))
shous = [s for s in SRC['shou'] if not A.shou or str(s['shou']) in A.shou.split(',')]
rows_of = lambda n: [r for r in SRC['rows'] if r['shou'] == n and not r.get('koe_machi')]
naoshi = json.load(open(A.naoshi)) if A.naoshi else {}
with ThreadPoolExecutor(A.heiretsu) as ex:
    res = list(ex.map(lambda s: ask(s, rows_of(s['shou']), json.dumps([x for x in (naoshi.get('buhin_nashi', []) + naoshi.get('mitsukaranai', [])) if str(x.get('id', '')).startswith('s')], ensure_ascii=False) if naoshi else ''), shous))
old = json.load(open(A.out)) if os.path.exists(A.out) and A.shou else {'shou': [], 'shots': [], 'tarinai': []}
done = {str(s['shou']) for s in shous}
keep = [x for x in old['shots'] if str(x.get('ch')) not in done]
shots = keep + [x for J in res for x in J['shots']]
def key(x):
    m = re.match(r's(\d+)_(\d+)', str(x.get('id', ''))); return (int(m.group(1)), int(m.group(2))) if m else (9999, 0)
shots.sort(key=key)
RT = {r['no']: [r['start'], r['end']] for r in SRC['rows']}
for x in shots:   # 指示書の行の秒（声に合わせ済み）を付ける：言葉の字が声の字と違っても、その秒の範囲で探せる
    if key(x)[0] in RT: x['jikan'] = RT[key(x)[0]]
OUT = {'koe': SRC['meta'].get('koe'), 'moto': A.src,
       'shou': [{'ch': str(s['shou']), 'fuda': s.get('dai', '') if s['shou'] != 1 else '', 'uttae': s.get('sokyu', ''), 'kokuchi': ('面談' in s.get('dai', '') and s['shou'] >= 13)} for s in SRC['shou']],
       'shots': shots, 'tarinai': sorted(set([t for t in old.get('tarinai', []) if not any(t.startswith(str(r['no']) + '：') for s in shous for r in rows_of(s['shou']))] + [t for J in res for t in J.get('tarinai', [])]))}
json.dump(OUT, open(A.out, 'w'), ensure_ascii=False, indent=1)
print('写した：章 %s・場面 %d（全体 %d）・足りない部品 %d' % (','.join(str(s['shou']) for s in shous), sum(len(J['shots']) for J in res), len(shots), len(OUT['tarinai'])))
