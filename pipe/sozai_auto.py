#!/usr/bin/env python3
# 素材一覧（<作業フォルダ>/sozai-ichiran.json・門のルール1・3・7・8）を、場面表が置いた部品の記録（work/sozai_used.json）から作る（yt-henshu-pipe・10/19）
#   出どころ・ライセンスの書き方は面談前VSL v12 の素材一覧（作業AIが確かめたもの）と同じ。種類ごとの「使った秒」は記録から入れる
#   python3 sozai_auto.py <作業フォルダ>
import os, sys, json, glob
P = os.path.abspath(sys.argv[1]); E = os.path.expanduser('~/rin6/state/yt-evervsl-1019/e')
KS = os.path.expanduser('~/rin6/state/yt-anime-1014/sozai/koushiki/anthropic_press_kit/Anthropic media resources/Anthropic logos/Claude logos')
U = json.load(open(os.path.join(P, 'work', 'sozai_used.json')))
def basho(f): return sorted({u['t'] for u in U if f(u)})
items = []
LOGO = {'openai': {'name': 'OpenAI のマーク（ChatGPT・GPTs・Codex）', 'file': E + '/logo/openai_blossom.png', 'service': 'ChatGPT',
                   'moto': 'openai.com/brand の openai_blossom_light.svg から格子を除いてマークだけ（形・色は変えていない）', 'url': 'https://openai.com/brand/'},
        'claude': {'name': 'Claude のロゴ', 'file': KS + '/1 Claude logo/PNG/Claude logo - Slate.png', 'service': 'Claude', 'moto': 'Anthropic press kit', 'url': 'https://www.anthropic.com/press-kit'},
        'youtube': {'name': 'YouTube のロゴ', 'file': E + '/logo/youtube_logo.png', 'service': 'YouTube', 'moto': 'YouTube 公式ロゴ https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg（koushiki/youtube_logo.svg と md5 edad0130…一致・10/22 取り直して確認）を形・色を変えずに PNG にした', 'url': 'https://www.youtube.com/howyoutubeworks/resources/brand-resources/', 'license': 'YouTube ブランド リソースの手引き（サービスを指すときに公式ロゴを形・色を変えずに使う）'},
        'instagram': {'name': 'Instagram のマーク', 'file': E + '/logo/instagram_glyph.png', 'service': 'Instagram', 'moto': 'Meta 公式 Instagram ブランドリソースの Instagram_Glyph_Gradient.png（koushiki/instagram/01 Static Glyph）を形・色を変えずに 600px に縮めた', 'url': 'https://about.meta.com/brand/resources/instagram/instagram-brand/', 'license': 'Instagram ブランドガイドライン（サービスを指すときに公式マークを形・色を変えずに使う）'},
        'claude_code': {'name': 'Claude Code のロゴ', 'file': KS + '/2 Claude Code logo/PNG/Claude Code logo - Slate.png', 'service': 'Claude Code', 'moto': 'Anthropic press kit', 'url': 'https://www.anthropic.com/press-kit'}}
for k, v in LOGO.items():
    b = basho(lambda u: u['shurui'] == 'ロゴ' and u['arg'] == k)
    if b: items.append(dict(v, shurui='ロゴ', deguchi='公式', basho=b))
KATA = {'挿絵': {'name': '人型・物のピクトグラム', 'file': None, 'deguchi': '素材サイト', 'moto': 'Google Material Symbols', 'license': 'Apache License 2.0・商用可・表示不要',
                'url': 'https://github.com/google/material-design-icons/blob/master/LICENSE'},
        'イラスト': {'name': '人物のイラスト（jinbutsu）', 'file': None, 'deguchi': '手本の作者さん', 'moto': 'sozai/jinbutsu（許可済み）'},
        '図解': {'name': '流れ図・比べ・表', 'file': None, 'deguchi': '自作', 'moto': '場面表で描いた'},
        '全画面挿絵': {'name': '全画面の写真（地）', 'file': None, 'deguchi': '手本の作者さん', 'moto': 'sozai/shashin photo_kaku／photo_tablet（許可済み）'},
        '実際の画面': {'name': 'うちの画面録画の1コマ', 'file': None, 'deguchi': '自作', 'moto': 'seminar-canva-douga の差し込み動画（自社のエージェント・データはダミー）'}}
if os.environ.get('PIPE_EDL'):   # v14：人物は yt-jinbutsu の自作（state/yt-henshu/jinbutsu/README.md の出どころ）
    KATA['イラスト'] = {'name': '動く人物（jinbutsu・自作）', 'file': None, 'deguchi': '自作', 'moto': 'yt-jinbutsu が jinbutsu.py で描いた（素材サイトの絵・AI生成画像なし）'}
# 実際のサービスの画面録画（chat-rokuga／jitsu-gamen-2 が作業AIのブラウザで本物のページを録った・ルール1の公式の画面）。表情の差し替え（kao の clip）で出る物は親の部品の秒で数える（yt-edl・10/20）
REAL = {'real-chatgpt': ('ChatGPT', 'ChatGPT の実際の画面', 'https://chatgpt.com'), 'real-claude': ('Claude', 'Claude の実際の画面', 'https://claude.ai'),
        'real-claude-code': ('Claude', 'Claude Code の実際の画面', 'https://claude.com/claude-code'), 'real-threads-note': ('Threads', 'Threads の実際の画面', 'https://www.threads.com')}
EDL = os.path.join(P, 'work', 'edl.json'); KAO = {}
if os.environ.get('PIPE_EDL') and os.path.exists(EDL):
    for s in json.load(open(EDL))['shots']:
        for q in s.get('parts', []):
            if q.get('kind') == 'kao' and q.get('clip') in REAL: KAO.setdefault(q['clip'], set()).update(x['name'] for x in s['parts'] if x.get('na') == q.get('name'))
for k, (svc, nm, url) in REAL.items():
    b = basho(lambda u: u['name'] == k or u['name'] in KAO.get(k, ()))
    if b: items.append({'name': nm, 'file': os.path.expanduser('~/rin6/state/yt-henshu/jinbutsu/clips/%s.mp4' % k), 'service': svc, 'shurui': '実際の画面', 'deguchi': '公式',
                        'moto': '%s を作業AIのブラウザで開いて録った本物の画面（ページの中身だけ・名前や個人向けの表示は消して撮影・houkoku/chat-rokuga.log）' % url, 'url': url, 'basho': b})
for k, v in KATA.items():
    b = basho(lambda u: u['shurui'] == k and u['name'] not in REAL)
    if b: items.append(dict(v, shurui=k, basho=b))
items.append({'name': '自社キャラのアイコン', 'file': os.path.expanduser('~/rin6/state/xtep-vtuber-buzz-1017/vtuber/chara/icon1024.png'), 'shurui': '話し手アイコン', 'deguchi': '自作', 'moto': '自社キャラの X のアイコン（自社のキャラ）'})
# 背景の線画（自社キャラ）は 10/21 に外した（依頼主 10/20 23:45 棒人間は一生使わない）
nar = sorted(glob.glob(os.path.join(P, 'input', 'narration.*')))
TEHON = ['zRXbZG4AZ1k', '82LvNeazll0', 'crlzmL2m4sE', 'NzjnSa2FrxU', 'iwoLSZoX7h8', 'FTC5gFfZSso', 'kUPDyQA1pNs', 'WLV8YtdQSeI', '2PoVYWZBlv4', 'F0Qh6l4OQHA',
         'NgA9DzmvZL0', '7dRZqvNGKPM', 'bA4JqhYKM58', 'zJCrYi2kRKo', 'mu6YEEFlteI']   # 手本の固定15本（記憶 youtube-tehon-fixed-15・作業AIから変えない）
# 1枚ずつの出どころ（作業AI 10/20「出どころを1枚ずつ記録」）：置いた部品の名前ごとに、種類の出どころと使った秒を1行にする
DEG = {it['shurui']: it for it in items}
ichimai = []
for (sh, nm), ts in sorted({(u['shurui'], u['name']): None for u in U}.items()):
    g = DEG.get(sh, {})
    ichimai.append({'name': nm, 'shurui': sh, 'deguchi': g.get('deguchi', '不明'), 'moto': g.get('moto', '不明'), 'basho': basho(lambda u, sh=sh, nm=nm: u['shurui'] == sh and u['name'] == nm)})
_dg = os.path.join(P, 'sozai-deguchi.json')   # 素材サイトから取った部品の1枚ずつの出どころ（名前→deguchi・moto・license・url・kakin・kounyuu）。種類の決め打ちより先に使う（10/20 ソコスト・Pixabay）
if os.path.exists(_dg):
    _DG = json.load(open(_dg))
    _EDLTXT = open(os.path.join(P, 'work', 'edl.json')).read() if os.path.exists(os.path.join(P, 'work', 'edl.json')) else ''   # 写真の地（ji の「写真:名前」）は部品の一覧に出ないので指示書の字で見る
    for x in ichimai:
        if x['name'] in _DG: x.update(_DG[x['name']])
    for _n, _v in _DG.items():
        if _v.get('file') and (_n in {x['name'] for x in ichimai} or _n in _EDLTXT): items.append(dict(_v, name=_n))   # 使った部品だけ（試しで足した物が一覧に残って課金の門を止めた 10/20）   # ファイルの置き場がある物は素材一覧にも1行（門が開いたファイルと突き合わせる）
# 実際の画面の置き場（e/gamen）にある素材サイトの写真の切り抜き（px＝Pexels・pb＝Pixabay の番号）は自作の画面録画ではない。名前の番号から出どころを1枚ずつ書く（dEw0 px5081405_ichiran・MJrC px3227986_yoko が「うちの画面録画（自作）」と記録されていた 10/22）
if os.path.exists(EDL):
    import re as _re
    _seen = {it.get('name') for it in items}
    for _s in json.load(open(EDL))['shots']:
        for _q in _s.get('parts', []):
            _nm = _q.get('name') or ''
            _m = _re.match(r'(px|pb)(\d+)', _nm)
            if _q.get('kind') == 'gamen' and _m and _nm not in _seen:
                _seen.add(_nm); _px = _m.group(1) == 'px'
                items.append({'name': _nm, 'file': E + '/gamen/%s.png' % _nm, 'shurui': '実際の画面', 'deguchi': '素材サイト', 'kakin': False,
                              'moto': ('Pexels %s https://www.pexels.com/photo/%s/' if _px else 'Pixabay %s https://pixabay.com/ja/photos/%s/') % (_m.group(2), _m.group(2)) + ' を切り抜いた1枚',
                              'license': 'Pexelsライセンス・商用可・表示不要' if _px else 'Pixabay コンテンツライセンス・商用可・表示不要'})
fumei = [x['name'] for x in ichimai if x['deguchi'] == '不明']
if fumei: print('🔴 出どころが分からない部品：', fumei)
json.dump({'narration_moto': nar[0] if nar else '', 'tehon': TEHON, 'sozai': items, 'ichimai': ichimai, 'tsukutta': 'pipe/sozai_auto.py'}, open(os.path.join(P, 'sozai-ichiran.json'), 'w'), ensure_ascii=False, indent=1)
from collections import Counter
print('素材一覧：', dict(Counter(u['shurui'] for u in U)))
