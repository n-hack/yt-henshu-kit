#!/usr/bin/env python3
"""手本の YouTube の全場面を「1場面＝1型」で残す（スライドの kata_zenbu.py と同じ考え・まとめない）。

読む  : state/yt-anime-1014/kata/per_full/*.json（手本1本ごとの場面の記録）
出す  : state/yt-anime-1014/kata/kata-zenbu-yt.json  … 型 Y00001〜（1場面1つ）
        state/yt-anime-1014/kata/kata-zenbu-yt.md    … 人が読む数え（伝えたいこと別・置き方別・積み上げの組）

1つの型が持つもの
  tsutae   伝えたいこと（役割と意図から決まりで付ける）
  mise     見せ方の種類（図解・キメ文字・アイコン・画面録画・実写・字幕だけ …）
  haichi   置き方（中央・上から積む・左右・横に並ぶ・格子・全面 …）
  tsugi    前の場面とのつなぎ（足す＝前の部品を残す／消す／字幕だけ差し替え）
  junban   出てくる順（場面の頭からの秒・出方・コマ数）
  renban   積み上げの組（前の部品が残って足されていく場面の並び）
  moji     手本の文言（控え・そのまま使わない）
使い方: python3 kata_zenbu_yt.py [--dry]
"""
import collections
import glob
import json
import os
import re
import sys

BASE = os.path.expanduser('~/rin6/state/yt-anime-1014/kata')
SRC = os.path.join(BASE, 'per_full')
OUT_J = os.path.join(BASE, 'kata-zenbu-yt.json')
OUT_M = os.path.join(BASE, 'kata-zenbu-yt.md')

# 伝えたいこと（上から順に当てる・スライドの14種にそろえる）
TSUTAE = [
    ('くらべる', r'比較|比べ|違い|違う|対比|ビフォー|before|vs|ＶＳ|段階|受動|能動|名前で.*中身'),
    ('並べる', r'・.+・|一覧|列挙|リスト|つ目|ポイント'),
    ('手順', r'手順|ステップ|やり方|方法|流れ|順番|指示を出|探し|動き'),
    ('数字で示す', r'数字|金額|売上|実績|万円|円|％|%|倍|件'),
    ('証拠', r'証拠|権威|実績|事例|証明|スクショ|画面'),
    ('問いかけ', r'問題提起|問いかけ|疑問|質問|なぜ|でも|ですか|思い出|？|\?'),
    ('共感', r'共感|悩み|不安|あるある|思い込み|思って|思われ'),
    ('結論', r'結論|主張|言い切|まとめ|否定|常識破り|本質|原則|締め|本編の山|すごい|時代|捉え直'),
    ('理由', r'理由|根拠|なぜなら'),
    ('並べる', r'一覧|列挙|リスト|つ目|ポイント'),
    ('具体例', r'具体|例え|例'),
    ('つなぎ', r'つなぎ|挿入'),
    ('解決策', r'解決|改善'),
    ('呼びかけ', r'CTA|告知|宣伝|登録|申し込|案内|限定|希少|煽り|損失|特典|面談'),
    ('つかみ', r'つかみ|フック|冒頭|あいさつ|挨拶|自己紹介'),
    ('説明', r'説明|解説|定義'),
]
MISE = [
    ('画面録画', r'録画|画面の|スクショ|ページ'),
    ('実写', r'実写|写真|顔出し|カメラ'),
    ('図解', r'図解|図|矢印|フロー|表|グラフ|チャート'),
    ('アイコン', r'アイコン|ロゴ|イラスト'),
    ('人物', r'人物|キャラ|人の絵'),
    ('並べる', r'チェック|箇条|リスト'),
    ('キメ文字', r'キメ|大きな文字|大字|見出し|板書|暗い地|白字|事実の字|帯|額縁|映画風'),
    ('字幕だけ', r'字幕|テロップ|文字だけ|文字'),
]
HAICHI = [
    ('格子', r'格子|2×2|2x2|4分割|マス'),
    ('3つ横', r'3列|3つ並|三つ並|横に3'),
    ('左右', r'左右|2列|左に|右に|二分|2分割'),
    ('横に並ぶ', r'横並び|横に並|横一列'),
    ('上から積む', r'上から|積む|縦に|下へ|段'),
    ('全面', r'全面|画面いっぱい|フル'),
    ('中央', r'中央|真ん中|中心'),
    ('下', r'下に字幕|最下段|下'),
]
TSUGI = [
    ('字幕だけ', r'字幕だけ|地の画面は'),
    ('足す', r'足す|足し算|追加|残して|残す|積'),
    ('消す', r'全消し|カット|切り替|ワイプ|スライド|フェード'),
    ('なし', r'なし|そのまま'),
]
DEKATA = [
    ('pop', r'点から|ポン|ぽん|弾|バウンド|大きくなる'),
    ('zoom', r'拡大|ズーム'),
    ('blur', r'にじみ|ぼかし|ぼけ'),
    ('grow', r'伸び'),
    ('left', r'左から'),
    ('right', r'右から'),
    ('up', r'下から|せり上が'),
    ('down', r'上から落|上から'),
    ('type', r'打ち込|1文字ずつ|タイプ'),
    ('grow', r'伸び|描|線が'),
    ('fade', r'フェード|ふわっ|じわ|薄れ'),
    ('pop', r'膨らん|ポップ|拡大して'),
    ('stamp', r'スタンプ|ドン|叩き'),
]


def ate(rules, text, dflt='その他'):
    for name, pat in rules:
        if re.search(pat, text or '', re.I):
            return name
    return dflt


STEP = re.compile(r'(?:→|・(?=[^0-9]))')
KOMA = re.compile(r'約?(\d+)\s*コマ')
T = re.compile(r'^(\d+(?:\.\d+)?)\s+')


def junban(anim, t0):
    """出てくる順：最初の「／」の前を →・ で区切った1つずつ（秒が書いてあれば場面の頭からの秒）"""
    out = []
    for i, step in enumerate(STEP.split((anim or '').split('／')[0])):
        step = step.strip()
        if not step:
            continue
        m = T.match(step)
        t = round(float(m.group(1)) - t0, 2) if m else None
        desc = T.sub('', step)
        if re.search(r'全消し|切り替え', desc) and not out:
            continue
        k = KOMA.search(desc)
        out.append({'jun': len(out) + 1, 't': t, 'de': ate(DEKATA, desc, 'cut'),
                    'koma': int(k.group(1)) if k else None, 'nani': desc[:40]})
    return out


RAW = os.path.join(BASE, 'full', 'raw.noindex')


def _hako_1hon(vid_kata):
    """手本1本ぶん：場面の最後のコマの字の箱（1920×1080）と、その字が場面の中で最初に出た秒"""
    vid, rows = vid_kata
    try:
        o = json.load(open(os.path.join(RAW, vid, 'ocr_b.json')))
        fps = float(json.load(open(os.path.join(RAW, vid, 'ana.json'))).get('fps') or 29.97)
    except Exception:
        return {}
    fr = sorted((int(k), v) for k, v in o.items() if v)
    out = {}
    for kid, t0, t1 in rows:
        a, b = int(t0 * fps), int(max(t0, t1 - 0.1) * fps)
        inside = [(f, v) for f, v in fr if a <= f <= b]
        if not inside:
            continue
        last = inside[-1][1]
        hako = []
        for txt, conf, (x, y, w, h) in last:
            if conf < 0.5 or not txt.strip():
                continue
            t_de = next((round(f / fps - t0, 2) for f, v in inside
                         if any(t2 == txt or (len(txt) > 3 and t2[:4] == txt[:4]) for t2, _, _ in v)), None)
            hako.append({'moji': txt[:30], 'x': int(x * 1920), 'y': int(y * 1080), 'w': int(w * 1920), 'h': int(h * 1080),
                         'jimaku': (y + h) > 0.84 and w > 0.3, 't_de': t_de})
        hako.sort(key=lambda q: (q['t_de'] if q['t_de'] is not None else 99, q['y']))
        out[kid] = hako
    return out


def haichi_hako(b):
    """字の箱の真ん中の散らばりから置き方を決める（手本の実測）"""
    if not b:
        return '全面'
    if len(b) == 1:
        q = b[0]
        return '中央' if q['w'] > 900 or abs(q['x'] + q['w'] / 2 - 960) < 250 else '片側'
    cx = sorted(q['x'] + q['w'] / 2 for q in b)
    cy = sorted(q['y'] + q['h'] / 2 for q in b)
    dx, dy = cx[-1] - cx[0], cy[-1] - cy[0]
    hidari = sum(1 for x in cx if x < 900)
    migi = sum(1 for x in cx if x > 1020)
    if len(b) >= 4 and dx > 600 and dy > 300:
        return '格子'
    if hidari and migi and dx > 600:
        return '左右' if dy > 150 else '横に並ぶ'
    if dy > 250:
        return '上から積む'
    return '中央'


def ichi(kata):
    """置き場所を手本の字の読み取り（ocr_b）から測って型に足す・18コア並列"""
    from multiprocessing import Pool
    by = collections.defaultdict(list)
    for k in kata:
        by[k['src']].append((k['id'], k['t0'], k['t0'] + k['dur']))
    with Pool(16) as pool:
        res = {}
        for r in pool.imap_unordered(_hako_1hon, by.items()):
            res.update(r)
    for k in kata:
        h = res.get(k['id'])
        k['hako'] = h if h is not None else None
        k['hako_n'] = len([q for q in (h or []) if not q['jimaku']])
        if h:
            k['haichi_hako'] = haichi_hako([q for q in h if not q['jimaku']])
    return sum(1 for k in kata if k['hako'] is not None)


def main():
    dry = '--dry' in sys.argv
    files = sorted(glob.glob(os.path.join(SRC, '*.json')))
    kata, n = [], 0
    for f in files:
        d = json.load(open(f))
        vid = d.get('id') or os.path.basename(f)[:-5]
        kumi, prev = None, None
        for i, s in enumerate(d.get('scenes') or []):
            n += 1
            v = s.get('visual') or {}
            t0 = float(s.get('t0') or 0)
            tsugi = ate(TSUGI, s.get('transition'), 'なし')
            kid = 'Y%05d' % n
            if tsugi == '足す' and prev:
                kumi = kumi or prev
            else:
                kumi = None
            tel = s.get('telop') or {}
            kata.append({
                'id': kid, 'src': vid, 'channel': d.get('channel'), 'no': i,
                't0': t0, 'dur': round(float(s.get('t1') or t0) - t0, 2),
                'yakuwari': s.get('role'),
                'tsutae': ate(TSUTAE, '%s %s' % (s.get('role') or '', s.get('intent') or '')),
                'mise': ate(MISE, '%s %s' % (v.get('kind') or '', v.get('what') or '')),
                'haichi': ate(HAICHI, v.get('layout'), '中央'),
                'tsugi': tsugi,
                'junban': junban(s.get('anim'), t0),
                'renban': kumi,
                'moji': tel.get('shown'),
                'nani': (v.get('what') or '')[:120],
            })
            prev = kid
    for k in kata:
        k['buhin'] = len(k['junban'])
    if '--ichi' in sys.argv:
        print('置き場所を測れた型', ichi(kata), '/', len(kata))
    c = collections.Counter
    tsutae, mise, haichi, tsugi = (c(k[x] for k in kata) for x in ('tsutae', 'mise', 'haichi', 'tsugi'))
    kumi = c(k['renban'] for k in kata if k['renban'])
    hn = c(min(k.get('hako_n') or 0, 6) for k in kata if k.get('hako') is not None)
    lines = ['# YouTube 型の全取り込み（1場面＝1型）',
             '手本 %d本・型 %d個（%s〜%s）' % (len(files), len(kata), kata[0]['id'], kata[-1]['id']), '',
             '## 伝えたいこと別'] + ['- %s %d' % x for x in tsutae.most_common()] + \
            ['', '## 見せ方別'] + ['- %s %d' % x for x in mise.most_common()] + \
            ['', '## 置き方別'] + ['- %s %d' % x for x in haichi.most_common()] + \
            ['', '## 前の場面とのつなぎ'] + ['- %s %d' % x for x in tsugi.most_common()] + \
            ['', '## 積み上げの組', '- 組の数 %d・組に入る場面 %d・いちばん長い組 %d場面' % (
                len(kumi), sum(kumi.values()) + len(kumi), (max(kumi.values()) + 1) if kumi else 0)] + \
            (['', '## 字幕を除いた字の箱の数（場面の最後のコマ・6は6以上）'] + ['- %d個 %d' % x for x in sorted(hn.items())] if hn else [])
    print('\n'.join(lines))
    if not dry:
        json.dump(kata, open(OUT_J, 'w'), ensure_ascii=False, indent=0)
        open(OUT_M, 'w').write('\n'.join(lines) + '\n')
        print('書いた', OUT_J, OUT_M)


if __name__ == '__main__':
    main()
