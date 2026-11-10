#!/usr/bin/env python3
# 0:00〜3:00 の場面表（話す言葉の時刻＝tr/words.json に合わせて置く）
# 1行＝1つの部品。時刻は「その言葉を話し始める秒」。
from anim import *

ORANGE = (250, 150, 60); BLUE = (90, 170, 220); PURPLE = (110, 30, 200); GREEN = (40, 190, 80); DGREEN = (30, 150, 90)

def title_tiles(text, size=96):
    """白抜き文字を赤い四角に1字ずつ（「完全版」）"""
    f = font(size, 900)
    n = len(text); s = int(size * 1.12); gap = 6
    im = Image.new('RGBA', (n * (s + gap), s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, ch in enumerate(text):
        x = i * (s + gap); d.rectangle([x, 0, x + s, s], fill=(230, 20, 30))
        d.text((x + s / 2, s / 2), ch, font=f, fill=WHITE, anchor='mm')
    return im

def redbox(text, size=78):
    t, _ = text_img(text, size=size, wght=900, color=WHITE, pad_x=0)
    im = Image.new('RGBA', (t.width + 40, int(size * 1.35)), (235, 20, 30, 255))
    im.alpha_composite(t, (20, -int(size * 0.16)))
    return im

def stamp(text, size=50, angle=8):
    t, _ = text_img(text, size=size, wght=900, color=WHITE, align='center', pad_x=0, line_gap=0.1)
    w, h = t.width + 50, t.height + 10
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    g = lin_grad(w, h, [(0, (230, 40, 40)), (1, (140, 0, 0))])
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 10, fill=255)
    im.paste(g, (0, 0), m)
    ImageDraw.Draw(im).rounded_rectangle([5, 5, w - 6, h - 6], 8, outline=WHITE, width=4)
    im.alpha_composite(t, (25, -4))
    im, _ = shadowed(im, off=(4, 8), blur=8, alpha=0.35, pad=20)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)

def person(name, label=None, color=None, h=330):
    im = fit(asset(name), h=h)
    if not label: return im
    lb = label_img(label, color, size=78, pad=(34, 6))
    out = Image.new('RGBA', (max(im.width, lb.width), im.height + lb.height - 10), (0, 0, 0, 0))
    out.alpha_composite(im, ((out.width - im.width) // 2, 0))
    out.alpha_composite(lb, ((out.width - lb.width) // 2, im.height - 10))
    return out

def checked(ts, x, y, text, size=46, gap=28, icon_color=(60, 130, 110)):
    ic = check_icon(int(size * 1.2), icon_color)
    return [Icon(ts, ic, x=x, y=y + int(size * 0.3), anim='pop'),
            Text(ts + 0.08, text, size=size, wght=700, x=x + ic.width + gap - 10, y=y)]

def starred(ts, x, y, text, size=40):
    st = star_img(int(size * 1.35))
    return [Icon(ts, st, x=x, y=y + int(size * 0.2), anim='bounce', dur=0.3),
            Text(ts + 0.08, text, size=size, wght=800, x=x + st.width + 6, y=y)]

def glyph_item(ts, x, y, text, size=42):
    g = insta_glyph(int(size * 1.2))
    return [Icon(ts, g, x=x, y=y + int(size * 0.3), anim='pop'),
            Text(ts + 0.08, text, size=size, wght=700, x=x + g.width + 10, y=y)]

S = []
# --- 0:00 ロゴ ---
S.append(Scene(0.0, 0.7, [Raw(0.0, ring_logo(460), x=W // 2, y=H // 2, anchor='cc', anim='pop', dur=0.35)], ring=False, trans=0))
# --- 0:00.7 タイトル ---
S.append(Scene(0.7, 9.8, [
    Raw(0.7, phone_img(690), x=70, y=160, anim='up', dur=0.35),
    Text(1.35, 'Instagram', size=150, name='script', color=INK, x=500, y=60, anim='wipe', dur=0.5),
    Raw(2.0, title_tiles('完全版', 150), x=1290, y=150, anim='pop'),
    Text(4.2, 'Instagramを始めて2ヶ月で', size=72, wght=800, marker=YEL, x=500, y=400),
    Raw(5.7, redbox('1万フォロワー', 120), x=520, y=520, anim='pop'),
    Text(6.35, 'を達成するために使った', size=72, wght=800, marker=YEL, x=560, y=700),
    Text(7.2, '<big>戦略</big>を大公開!', size=72, wght=900, marker=YEL, x=700, y=810, color=INK),
]))
# --- 0:09.8 なぜ ---
S.append(Scene(9.8, 13.1, [
    Text(10.9, 'なぜ\nこの動画を\n撮ろうと思ったか', size=136, wght=900, marker=YEL, x=100, y=170, line_gap=0.32),
]))
# --- 0:13.1 吹き出し ---
S.append(Scene(13.1, 21.2, [
    Img(13.4, 'p_woman_phone', h=380, x=60, y=90, anim='up'),
    Bubble(14.1, 'Instagramで副業やろう!', ORANGE, 'left', size=104, x=290, y=100),
    Img(15.9, 'p_man_suit', h=400, x=60, y=540, anim='up'),
    Bubble(16.1, 'Instagramで\n　　集客しよう!', BLUE, 'left', size=104, x=380, y=490),
]))
# --- 0:21.2 写真 ---
S.append(Scene(21.2, 23.9, [], bg='ph_tired', kb=(1.0, 1.06), ring=False))
S.append(Scene(23.9, 27.4, [], bg='ph_phone', kb=(1.04, 1.0), ring=False, trans=0.15))
S.append(Scene(27.4, 31.5, [], bg='ph_stress', kb=(1.0, 1.07), ring=True, trans=0.15))
# --- 0:31.5 伸びない ---
S.append(Scene(31.5, 35.3, [
    CirclePhoto(31.5, 'ph_tired', d=380, x=40, y=30, tg=31.85),
    CirclePhoto(31.62, 'ph_phone', d=380, x=470, y=30, tg=31.85),
    CirclePhoto(31.74, 'ph_stress', d=380, x=900, y=30, tg=31.85),
    Raw(31.65, impact_img('このまま運用しても', 160, top=(255, 60, 60), bottom=(120, 0, 10), angle=4), x=60, y=330, anim='zoom', dur=0.22),
    Raw(32.9, impact_img('伸びない…', 250, top=(255, 60, 60), bottom=(120, 0, 10), angle=4), x=140, y=560, anim='zoom', dur=0.22),
]))
# --- 0:35.3 砂時計 ---
S.append(Scene(35.3, 40.4, [], bg='ph_hourglass', kb=(1.0, 1.08), dim=0.1, ring=False))
# --- 0:40.4 見るべき人 ---
S.append(Scene(40.4, 56.9, [
    Text(40.5, 'この動画を見るべき人', size=84, wght=900, marker=YEL, x=30, y=10),
    *checked(41.8, 40, 200, '正しい知識がなく、<r>運用方法が間違っている</r>人', size=74),
    *checked(45.2, 40, 345, 'Instagramアツいって知ってて始めたいけど、\n<r>どうやって伸ばせばいい</r>のか分からない人', size=74),
    *checked(49.1, 40, 600, '<r>どうやって運用</r>していけばいいの?', size=74),
    *checked(51.8, 40, 745, '<r>どういう流れ</r>でフォロワー増える?', size=74),
]))
# --- 0:56.9 戦略を立てれば ---
S.append(Scene(56.9, 68.4, [
    Img(57.4, 'chara_flat', h=330, x=40, y=20, anim='up'),
    Text(58.6, 'この動画の内容を\n理解して戦略を立てれば', size=100, wght=900, marker=YEL, x=330, y=40, line_gap=0.22),
    Text(63.6, '基本的には', size=92, wght=900, x=40, y=410),
    Text(64.2, '半年で<hugr>1万</hugr><r>フォロワー</r>', size=120, wght=900, x=30, y=470, anim='pop', dur=0.3, stroke=6, stroke_color=WHITE),
    Raw(67.3, stamp('狙えなければ\nおかしい', 70, 7), x=1060, y=760, anim='bounce', dur=0.3),
]))
# --- 1:08.4 狙えなさそう ---
S.append(Scene(68.4, 75.0, [
    Img(68.6, 'p_man_think', h=430, x=80, y=70, anim='up'),
    Bubble(68.7, '半年で1万フォロワー\n狙えなさそうだな…', PURPLE, 'left', size=100, thought=True, x=440, y=100, tcolor=WHITE),
    Raw(72.9, impact_img('その運用方法は\n間違っている', 170, top=(255, 235, 235), bottom=(205, 25, 35), out_color=(90, 0, 0), angle=-4), x=200, y=480, anim='zoom', dur=0.22),
]))
# --- 1:15 今回の動画を見て ---
S.append(Scene(75.0, 83.0, [
    Text(75.7, '今回の動画を見て', size=104, wght=900, marker=YEL, x=20, y=10),
    Chart(76.6, w=900, h=640, x=430, y=230, dur=1.8),
    Badge(77.1, d=420, x=40, y=290),
]))
# --- 1:23 実績 ---
S.append(Scene(83.0, 112.4, [
    Card(83.2, 1360, 900, x=60, y=80),
    *starred(84.6, 110, 115, '2ヶ月で<r>1万フォロワー</r>', 74),
    *starred(86.1, 110, 255, '1年で<r>10万フォロワー</r>', 74),
    *starred(89.5, 110, 395, '3ヶ月で<r>1万フォロワー</r>', 74),
    *starred(90.4, 110, 535, '3ヶ月半で<r>2万フォロワー</r>', 74),
    *starred(92.7, 110, 675, '企業の運用代行を<r>20社</r>', 74),
    *starred(96.9, 110, 815, '3〜4ヶ月で<r>1万フォロワー</r>続出', 74),
    Raw(101.4, impact_img('嘘やん!!', 200, top=(255, 255, 255), bottom=(255, 215, 215), out_color=(120, 0, 0), angle=-10, name='pop'), x=1080, y=60, anim='bounce', dur=0.3, z=2),
    Dim(102.8, alpha=0.62, z=3),
    Bubble(103.7, 'そんな早く<yt>1万フォロワー達成</yt>するわけないやん!!', PURPLE, 'none', size=58, x=30, y=70, anim='left', dur=0.2, z=4),
    Bubble(105.8, 'どうせ<yt>イケメン</yt>の<yt>モデル</yt>がやってるんでしょ?', PURPLE, 'none', size=58, x=30, y=270, anim='left', dur=0.2, z=4),
    Bubble(107.8, 'どうせ<yt>美女</yt>がやってるんでしょ?', PURPLE, 'none', size=58, x=30, y=470, anim='left', dur=0.2, z=4),
    Bubble(109.2, 'どうせ<yt>フォロワー買った</yt>んでしょ?', PURPLE, 'none', size=58, x=30, y=670, anim='left', dur=0.2, z=4),
]))
# --- 1:52 有名人じゃない ---
S.append(Scene(112.4, 120.8, [
    Card(112.6, 1800, 530, x=60, y=40),
    Icon(114.6, face_ng_icon(150), x=100, y=80),
    Text(114.65, '<bigr>顔出し</bigr>していない', size=92, wght=800, x=270, y=55),
    Icon(116.1, share_icon(140), x=105, y=345),
    Text(116.15, '誰からも<bigr>拡散</bigr>してもらってない', size=92, wght=800, x=270, y=300),
    Text(118.0, 'つまり、<big>有名人</big>じゃない', size=104, wght=900, marker=YEL, x=60, y=640, anim='pop', dur=0.28),
]))
# --- 2:00.8 ネオン ---
S.append(Scene(120.8, 126.8, [], bg='ph_neon', kb=(1.0, 1.08), ring=False, photo_focus=(0.75, 0.5)))
# --- 2:06.8 ゼロから ---
S.append(Scene(126.8, 139.3, [
    *glyph_item(127.5, 60, 50, 'Instagram内でゼロからアカウントを構築', size=80),
    *glyph_item(130.4, 60, 210, '他のSNSからフォロワーを流さない', size=80),
    *glyph_item(132.4, 60, 370, 'フォロワーは買わない', size=80),
    *glyph_item(133.7, 60, 530, '広告費もかけない', size=80),
    Raw(135.3, impact_img('初期費用0円', 230, top=(255, 70, 70), bottom=(170, 0, 20), angle=0, name='dela'), x=20, y=650, anim='zoom', dur=0.22),
]))
# --- 2:19.3 誰でも ---
S.append(Scene(139.3, 147.5, [
    Raw(140.8, person('p_office', '会社員', (20, 40, 210), 400), x=250, y=90, anim='up'),
    Raw(141.9, person('p_housewife', '主婦', (230, 50, 80), 400), x=760, y=90, anim='up'),
    Raw(142.8, person('p_student', '学生', (245, 130, 20), 400), x=1260, y=90, anim='up'),
    Raw(144.4, impact_img('誰でもやれる!!', 200, top=(255, 70, 70), bottom=(170, 0, 20), name='pop'), x=780, y=640, anchor='ct', anim='zoom', dur=0.22),
    Dim(147.5, alpha=0.55, z=3),
    Raw(147.9, impact_img('なんでこんなに\n上手くいくねん!', 180, top=(255, 255, 255), bottom=(235, 235, 235), out_color=(30, 30, 30), angle=8, name='pop'), x=140, y=100, anim='bounce', dur=0.3, z=4),
], trans=0.2))
S[-1].t1 = 150.6
S.append(Scene(150.6, 153.7, [
    Raw(151.9, impact_img('戦略を立てて\n運用しているから', 210, top=(255, 250, 225), bottom=(235, 195, 80), out_color=(40, 30, 0), name='pop', align='center'), x=W // 2, y=300, anchor='ct', anim='zoom', dur=0.22),
], bg='ph_chess', kb=(1.0, 1.06), dim=0.2, ring=False))
# --- 2:33.7 分かった状態 ---
L = ['どういう投稿をしたら<r>伸びる</r>のか?', 'どういう投稿が<r>Instagramに評価される</r>のか?',
     'どういう<r>運用方法</r>をしたらいいのか?', '何をしたら<r>伸びなくなる</r>のか?']
T = [155.2, 156.9, 159.5, 160.7]
els = [Card(153.9, 1820, 820, x=40, y=40)]
for i, (s_, t) in enumerate(zip(L, T)):
    y = 80 + i * 185
    els += checked(t, 80, y, s_, size=80)
    ic = int(80 * 1.2)
    els.append(Text(165.1 + i * 0.25, s_, size=80, wght=700, marker=PALE_Y, x=80 + ic + 28 - 10, y=y, z=1))
S.append(Scene(153.7, 170.6, els))
# --- 2:50.6 99% ---
S.append(Scene(170.6, 175.7, [
    Text(171.2, '<d>上手くいかない人</d>の', size=116, wght=900, x=30, y=60),
    Text(172.4, '<xr>99%</xr>が', size=116, wght=900, x=30 + text_img('<d>上手くいかない人</d>の', size=116, wght=900)[0].width - 20, y=-28, anim='pop', dur=0.28),
    Raw(173.8, impact_img('戦略なしに\n戦っている', 250, top=(130, 40, 255), bottom=(40, 0, 110), out_color=(20, 0, 40), name='noto'), x=10, y=330, anim='zoom', dur=0.22),
]))
# --- 2:55.7 とりあえず ---
S.append(Scene(175.7, 180.5, [
    Bubble(176.0, '全然分かってないけど\nとりあえず伸ばそう!', GREEN, 'right', size=74, x=500, y=130),
    Img(176.0, 'p_woman_phone', h=360, x=1430, y=90, anim='up'),
    Img(178.0, 'p_man_cheer', h=360, x=60, y=520, anim='up'),
    Bubble(178.1, 'とりあえず投稿しよう!', GREEN, 'left', size=74, x=500, y=590),
]))

SUBS = Subs([
    (13.2, 14.0, 'ぶっちゃけですけど'),
    (17.7, 19.9, 'インスタ使ってる人とか いろんな人がいると思うんですけど'),
    (20.0, 21.3, 'やっぱりいろんな人を見てて'),
    (21.4, 23.9, 'すごくやっぱり<y>適当に</y>している人が多いなとか'),
    (23.9, 25.8, '知識がすごく<y>足りてない</y>から'),
    (25.8, 27.5, 'やっぱり<y>運用方法が間違ってる</y>なとか'),
    (27.5, 28.7, 'めちゃめちゃ<y>もったいない</y>なと思う人が'),
    (28.7, 30.2, '本当にたくさんいるわけですね'),
    (30.3, 31.6, 'そういう人たちに向けて'),
    (33.7, 35.3, 'ということが起きてくると思うので'),
    (35.3, 37.5, 'その人たちの<y>時間が無駄にならないように</y>'),
    (37.5, 39.9, '今回しっかりと動画を作ろうかなと思いました'),
    (53.9, 55.1, 'そういう方がたくさんいると思うので'),
    (55.1, 56.1, 'そういう人たちに向けて'),
    (56.1, 57.6, '動画を作っていければなと思います!'),
    (78.0, 79.6, 'どういう流れでやっていけばいいのか'),
    (79.6, 80.7, 'っていうところが<y>全部分かる</y>と思うので'),
    (80.7, 82.9, 'その辺りを見てってもらえればなと思います'),
    (100.0, 101.4, 'こんなこと言うと'),
    (102.0, 103.7, 'という風に思われると思うんですよ'),
    (110.4, 111.7, 'って言われるんですけど'),
    (111.7, 113.3, 'そんなことは<y>一切</y>していなくて'),
    (119.7, 121.6, '本当に<y>ゼロからやってる人</y>が非常に多い'),
    (122.0, 123.8, '僕自身もInstagramを始めたときは'),
    (123.8, 125.6, 'TwitterもYouTubeも何もやってないわけですから'),
    (125.6, 127.5, '<y>どこからも流すことができない</y>わけですよ'),
    (135.8, 137.8, 'っていうところから始めているので'),
    (137.8, 139.3, '<y>本当に誰でも行けます!</y>'),
    (139.3, 140.6, 'みんな普通の人なので'),
    (145.5, 147.5, '分かってほしいなと思いますね'),
    (150.6, 151.9, 'これは結論としては'),
    (154.1, 155.2, '僕らっていうのは'),
    (162.1, 163.8, '基本的に<y>全部分かった状態</y>で'),
    (163.8, 165.1, '運用を始めているんですね'),
    (165.1, 167.3, 'その辺を全部理解して運用しているからこそ'),
    (167.3, 168.2, 'やっぱり結果は出るし'),
    (168.2, 169.3, '<y>伸びないわけがない</y>んですよね'),
    (169.3, 170.8, 'ここら辺をちゃんと分かっていれば'),
    (179.0, 180.5, 'という形でやってる人ばっかりなので'),
])
SCENES = build_timeline(S)
