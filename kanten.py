#!/usr/bin/env python3
# 観点の全部の一覧と基準（作業AI・2026-10-16）
#   python3 kanten.py build     per_full（書けている分）から観点ごとの基準を作る → kata/kanten_kijun.json
#   python3 kanten.py md        基準から kanten-zenbu.md を書き直す（per_full が増えたら build → md をやり直すだけ）
#   python3 kanten.py show <id> 見本1本の観点ごとの点（基準に対して）
#   python3 kanten.py rin <プロジェクト>  作業AIの1本の場面の記録で当てられる観点を先に当てる（仕上げの途中の自己点検）
# 観点の中身・測り方は lib/kanten.py の KANTEN が正本。md はそこから作る（手で md を直さない）
import os, sys, json, datetime, statistics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import paths, kanten as KT
PER = os.path.join(paths.ENGINE, 'kata', 'per_full')
KJ = os.path.join(paths.ENGINE, 'kata', 'kanten_kijun.json')
MD = os.path.join(paths.ENGINE, 'kanten-zenbu.md')


def fmt(x, unit=''):
    if x is None: return '—'
    if unit == '' and isinstance(x, float) and 0 <= x <= 1: return '%d%%' % round(x * 100)
    if isinstance(x, float): x = round(x, 2) if abs(x) < 10 else round(x, 1)
    return '%s%s' % (x, unit)


def md(kj):
    L = ['# YouTube 編集の観点の全部（作業AI・%s 作成）' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), '',
         '見本＝委託の編集者さんの per_full（全編を1コマずつ見た記録）**%d本**（%s）から、この編集者が実際に気をつけていることを観点ごとに書き、測り方と基準値（本ごとの値の中央値と10〜90%%の幅）を付けた。' % (kj['n_videos'], '・'.join(kj['channels'])),
         '基準値は `python3 ~/rin6/tools/yt-henshu/kanten.py build && python3 ~/rin6/tools/yt-henshu/kanten.py md` で per_full が増えるたびに作り直す（この md は自動で書く。手で直さない。観点の中身の正本は `tools/yt-henshu/lib/kanten.py`）。', '',
         '## 使い方', '',
         '- 各観点を「本質のルール（外してはいけない）」と「好みで変えてよい所」に分けた（依頼主 10/16 00:35「動画編集に答えはない。元と全く同じでなくてよいが、本質的なルールはある」）。点は見本との一致率ではなく、本質のルールで見る。好みの指標は点に入れず、見本の幅を参考に並べるだけ',
         '- 見本には形式の札を付けた（%s）。作業AIの1本は講義型なので、線と中央値は講義型の見本だけで出す。常に字幕帯を出す本は、その帯の行を外して見やすさを測る。耳で確かめていない値には「未確定」の札を付けて基準に入れない（%s）' % (
             '・'.join('%s %d本' % (f_, len(ids)) for f_, ids in sorted((kj.get('formats') or {}).items(), key=lambda x: -len(x[1]))),
             '・'.join('%s の%s' % (u['id'], KT.LABEL.get(u['key'], (u['key'], ''))[0]) for u in kj.get('unsure') or []) or 'なし'),
         '- **合格（10/16 依頼主「60点は下位互換」→ 完コピか上位互換）**：①本質のルールの破りが0件 ②手本の編集者さん本人の講義型の本の下から4分の1を割る観点が k 個まで（k＝本人の本の8割が満たす最小の数）、かつ13観点を合わせた点が手本の編集者さん本人の中央値以上 ③答えのある練習では、元の動画と並べてどの観点でも答えより下にならない。練習の一致率の線（60点）は使わない',
         '- ②の観点の点：本質ルールの指標ごとに「手本の編集者さんの講義型の本の何割より良い側か」（ルールの向きで数える・同じ値は半分）を出し、観点で平均した0〜100。手本の編集者さん自身の本は自分を外して比べる。いまの線：' + '・'.join('%s %s点' % (kd['name'].split('（')[0], kj.get('joui', {}).get('p25', {}).get(kd['id'])) for kd in KT.KANTEN) + '／13観点の合計の中央値 %s点／割ってよい観点 k=%s個' % (kj.get('joui', {}).get('sum_med'), kj.get('joui', {}).get('k')),
         '- 本質のルールの線（破りの判定）は見本の本物から置いた：ルールごとに、いちばん外れた1本だけを外し残りが全部通る値。中央値は「手本の編集者さんのふつうの1本」で、合格にはこちらが要る',
         '- 見本そのものに当てると（講義型 %d本）：①破り2個まで（本人の誰より悪い指標は0個）は %d本・②（下から4分の1を割る観点が k 個まで・合計が中央値以上）は %d本・両方は %d本。②は本物でも半分ほどしか通らない＝上位互換の線' % (
             kj['self_check']['of'], kj['self_check']['pass1'], kj['self_check']['pass2'], kj['self_check']['pass']),
         '- 「過去の見本と見た目が似ているか」は測らない（依頼主 10/15 20:36「本質ではない」）。測るのは、その台本の意図が見る人に伝わる編集になっているか', '',
         '## 気をつけること（母数）', '',
         '- いまの母数は%d本で、ほとんどが @youtube.tehon。ほかのチャンネルは本数が少ない。per_full が増えたら作り直す' % kj['n_videos'],
         '- 書いた作業員ごとに測る道具が少し違う本がある（テロップのずれは、古い形の2本は±3コマに集まり、新しい形は幅が広い）。幅はそのぶん広めに出ている', '']
    bc = kj.get('by_channel') or {}; chs = sorted(bc, key=lambda c: -bc[c]['n'])
    L += ['チャンネルごとの本数：' + '・'.join('%s %d本' % (c, bc[c]['n']) for c in chs) + '（本質ルールの表に、チャンネルごとの中央値を並べた。本数の少ないチャンネルの値は目安）', '']
    chs = ['%s' % c for c in chs]
    for i, kd in enumerate(KT.KANTEN, 1):
        rs, konomi = KT.HON.get(kd['id'], ([], ''))
        L += ['## %d. %s' % (i, kd['name']), '', '**この編集者がやっていること**：' + kd['what'], '', '**測り方**：' + kd['how'], '',
              '**本質のルール（外してはいけない・点はここだけで出す）**', '', '| ルール | 指標 | 破りの線 | 合格に要る中央値（講義型） | ' + ' | '.join(chs) + ' |', '|---|---|---|---|' + '---|' * len(chs)]
        for k, dr, w in rs:
            lab, unit = KT.LABEL.get(k, (k, '')); ln = kj.get('hon_lines', {}).get(k) or {}; ds = ((kj.get('by_format') or {}).get('講義型') or {}).get('dist', kj['dist']).get(k) or {}
            lt = {'ge': '%s以上', 'le': '%s以下', 'abs_le': '±%s以内', 'zero': '%s件'}.get(dr)
            lv = ln.get('lo') if dr == 'ge' else ln.get('hi')
            line_s = ('%s〜%s' % (fmt(ln.get('lo'), unit), fmt(ln.get('hi'), unit))) if dr == 'in' else (lt % fmt(lv, unit) if lv is not None else '—')
            L.append('| %s | %s | %s | %s | %s |' % (w, lab, line_s, fmt(ds.get('p50'), unit) if ds else '—',
                                                     ' | '.join(fmt(kj['by_channel'][c].get(k), unit) for c in chs)))
        L += ['', '**好みで変えてよい所（点に入れない）**：' + konomi, '', '**指標の全部（見本の幅・参考）**', '',
              '| 指標 | 中央値 | 10〜90% | 最小〜最大 | 本数 |', '|---|---|---|---|---|']
        for k, lab, unit in kd['m']:
            ds = kj['dist'].get(k)
            if k in KT.FIXED:
                L.append('| %s | — | %s（固定の線） | — | — |' % (lab, '%s〜%s%s' % (KT.FIXED[k][0], KT.FIXED[k][1], unit)))
            elif not ds:
                L.append('| %s | 見本に記録なし | — | — | 0 |' % lab)
            else:
                L.append('| %s | %s | %s〜%s | %s〜%s | %d |' % (lab, fmt(ds['p50'], unit), fmt(ds['p10'], unit), fmt(ds['p90'], unit), fmt(ds['min'], unit), fmt(ds['max'], unit), ds['n']))
        L.append('')
    L += ['## まだ数にしていない観点（目で見て決めること）', '',
          '- サムネそのもの（作業AIはサムネを作らない前提。題の言葉と冒頭の言葉が同じかは「約束の回収」で見る）',
          '- 絵の中身が台本の訴求に合っているか（数を言う場面で数ぴったり・特典の場面は特典だけ）：出す前に全場面の静止画を並べて1つずつ目で見る（記憶 video-marketing-intent-first）',
          '- 同じ絵を同じ意味で通しているか（硬貨＝お金・虫めがね＝検索）：story.py の絵の選び方で決める',
          '- 色の役割（赤＝言い切り・青＝冷静・黄＝要点と限定・金＝山場・灰＝相手の考え）が1本の中でぶれていないか：story.py で色を役割から選ぶ形にして守る', '',
          '## 1本ずつの値', '', '`kata/kanten_kijun.json` の per_video に全指標がある。']
    return '\n'.join(L) + '\n'


def main():
    a = sys.argv[1:] or ['build']
    if a[0] == 'build':
        HO = os.path.join(paths.ENGINE, 'kata', 'holdout.txt')
        skip = {l.split()[0] for l in open(HO) if l.strip() and not l.startswith('#')} if os.path.exists(HO) else set()
        kj = KT.build(PER, skip); line = json.load(open(paths.KIJUN))['kanten']; ok = []
        # 線は作業AIの1本と同じ形式（講義型）の見本だけで置く。対談型・字幕帯型は作りが違うので混ぜない（10/16 作業AIの指示）。未確定の値は外す
        pv = {i: {k: x for k, x in v.items() if k != 'channel' and k != 'format'} for i, v in kj['per_video'].items() if v.get('format') == line.get('format', '講義型')}
        for i in pv:
            d_ = json.load(open(os.path.join(PER, i + '.json'))); v_ = KT.from_per_full(d_)
            pv[i] = {k: x for k, x in v_.items() if (i, k) not in KT.UNSURE}
        kj['hon_lines'] = KT.hon_lines(pv, line.get('drop', 1))
        kj['hon_max_broken'] = line.get('max_broken', 0)
        # 本人（講義型）が1本も破っていない観点：ここを破ったら①は1個でも不合格（10/16 作業AIの判断）
        # 外の線（10/16 作業AIの判断）：手本の編集者さん本人のいちばん外れた1本の値（drop=0）。これより外れたら本人の誰よりも悪い＝1個でも①不合格
        kj['hon_lines_outer'] = KT.hon_lines(pv, 0)
        kj['joui'] = KT.joui_ref(pv)   # 新しい②の物差し：観点ごとの下から4分の1・13観点の合計の中央値（手本の編集者さん本人の講義型）
        for i, v in pv.items():
            g = KT.gate(v, kj, line.get('format', '講義型'), skip_self=i)
            ok.append((i, g['破り'], g['①破り0'], g['②中央値以上'], [b for x in g['hon'] for b in x['broken']], g['中央値に届かない観点']))
        kj['self_check'] = {'line': line, 'format': line.get('format', '講義型'), 'of': len(ok), 'pass1': sum(1 for x in ok if x[2]), 'pass2': sum(1 for x in ok if x[3]),
                            'pass': sum(1 for x in ok if x[2] and x[3]), 'rows': ok}
        # チャンネルごとの差（本質ルールの指標の中央値・本数）
        ch = {}
        for i, v in pv.items(): ch.setdefault(kj['per_video'][i]['channel'] or '不明', []).append(v)
        kj['by_channel'] = {c: {'n': len(vs), **{k: round(statistics.median([v[k] for v in vs if isinstance(v.get(k), (int, float))]), 3)
                                               for k in KT.HON_KEYS if any(isinstance(v.get(k), (int, float)) for v in vs)}} for c, vs in ch.items()}
        json.dump(kj, open(KJ, 'w'), ensure_ascii=False, indent=1)
        print('見本 %d本 → %s（指標 %d）' % (kj['n_videos'], KJ, len(kj['dist'])))
    elif a[0] == 'md':
        open(MD, 'w').write(md(json.load(open(KJ)))); print(MD)
    elif a[0] == 'rin':
        # 作業AIの1本を書き出す前に、場面の記録（story_meta・video_marketing・theme_used）から出せる観点だけ先に当てる（仕上げの途中で何度でも）
        kj = json.load(open(KJ)); P = os.path.abspath(a[1])
        for r in KT.score_hon(KT.from_project(P), kj):
            if not r['measured']: continue
            print('%-30s %5s点（%d/%d）' % (r['name'], r['score'], r['measured'], r['of']))
            for it in r['items']:
                if it['kept'] is False: print('    破り %s：%s 今 %s ／ 線 %s〜%s → %s点' % (it['rule'], it['label'], it['value'], it['line'][0], it['line'][1], it['pt']))
        G = KT.gate(KT.from_project(P), kj, json.load(open(paths.KIJUN))['kanten'].get('format', '講義型'))
        J = G['②'] or {}
        print('合格の門：①破り0 %s（%d個）／②上位互換 %s（13観点の合計 %s・手本の編集者さんの中央値 %s）' % (G['①破り0'], G['破り'], G['②上位互換'], J.get('sum'), J.get('sum_med')))
        for r in J.get('rows', []):
            if r['reached'] is not True: print('  ② %s：%s点＜手本の編集者さんの下から4分の1 %s点' % (r['name'], r['score'], r['p25']))
        for r in G['median']:
            if r['reached'] is True: continue
            print('    （中央値に届かない指標）%s：%s' % (r['name'], '・'.join('%s %s＜中央値 %s' % (i['label'], i['value'], i['median']) for i in r['short']) or ('未測定：' + '・'.join(r['unmeasured']))))
        print('（テンポ・音・見やすさ・字幕のずれ・声は、書き出した mp4 を check.py ⑮ で見本と同じ道具で測る）')
    elif a[0] == 'show':
        kj = json.load(open(KJ)); d = json.load(open(os.path.join(PER, a[1] + '.json')))
        for r in KT.score_hon(KT.from_per_full(d), kj):
            print('%-28s %s  （%d/%d）' % (r['name'], r['score'], r['measured'], r['of']))
            for it in r['items']:
                if it['kept'] is False: print('    破り %s %s 線 %s → %s点' % (it['rule'], it['value'], it['line'], it['pt']))


if __name__ == '__main__':
    main()
