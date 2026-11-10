#!/usr/bin/env python3
# 最低ラインは手本の編集者さんの門（依頼主 10/20 14:4x「最低ラインは手本の編集者さん。これを下回ったらアウト」・絶対ルール）
#   python3 rock-mon.py <動画.mp4> [--t1 171] [--out kekka.json] [--nozoku <手本の名前>]
#   手本の編集者さん（手本の作者さんのチャンネルの編集者）の手本15本を、pipe/kurabe3.py と同じ式・同じ頭の秒数で測った値（zettai/rock15-<秒>.json）と並べ、
#   項目ごとに「下／同じ／上」を付ける。1項目でも「下」なら不合格（exit 1）。
#   決め方（手本15本の幅＝手本の編集者さんが実際に作った範囲）
#     多いほど上の項目（KAZU）  ：手本の最小より少ない＝下／最小〜最大＝同じ／最大より多い＝上
#     幅の項目（HABA）          ：手本の最小〜最大の外（多すぎ・少なすぎ）＝下／中＝同じ（多すぎも手本と違う＝v14 の切り替わり 39/分）
#     参考（判定しない）        ：字幕帯の有無・背景の色の種類・明るさ・色のある所の割合・字の位置 下
#   --nozoku は陽性対照用：その手本を除いた14本の幅で測る（自分を物差しに入れない）
import os, sys, json, argparse, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('kurabe3', os.path.join(HERE, 'pipe', 'kurabe3.py')); K3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(K3)
KAZU = {}   # team-lead 10/20：18項目すべて「手本の範囲（最小〜最大）の中」を合格（多すぎる側も止める）
HABA0 = {'ji_kazu': '画面の字の数/コマ', 'ji_ari': '画面に字があるコマの割合', 'mitsudo': '絵の密度（線の量）', 'd_move_pm': '動く要素/分', 'b_fill': '埋まり方（字・絵の量）', 'bg_kinds': '背景の色の種類', 'iro_wariai': '画面の色のある所の割合', 'ji_haba': '1行の字の幅（画面の横幅の割合）'}
HABA = {'c_big_pm': '大きな切り替わり/分', 'cut_pm': '場面が丸ごと替わる回数/分', 'shot_med_s': '1場面の長さ（秒）', 'a_diff': '動きの量', 'ji_takasa': '一番大きい字の高さ',
        'ji_ue': '字の位置 上の割合', 'ji_naka': '字の位置 中ほどの割合', 'bg_flat': '背景が無地1色の度合い', 'bg_change_pm': '背景が替わる回数/分', 'bg_sat': '背景の色の濃さ'}
HABA = dict(HABA0, **HABA)
# 判定から外す項目（例外の記録）：字幕帯があるコマの割合＝依頼主の動画編集の絶対ルール「テロップは全部」（yt-henshu-zettai-rules・10/19）が手本の型6（紺の字幕帯は補足だけ）より上なので外す（team-lead 10/20）。値は参考として残す
# 手数の項目は多い側を合格（上）にする：依頼主 10/21 0:34「動くものが多い分にはいい。手本の編集者さんは人間だからアニメーションに限界がある。そこは限界突破していい」・0:35「センスは彼のが上だけど、やれることはあなたのが上」。少なすぎる側は今までどおり不合格
UE_OK = {'d_move_pm': '動く要素/分', 'a_diff': '動きの量'}
REIGAI = {'jimaku_ari': '字幕帯があるコマの割合：依頼主の絶対ルール「テロップは全部」が手本の型6より上（team-lead 10/20）'}

def hantei(mine, ref):
    rows, ng = [], []
    for k, nm in list(KAZU.items()) + list(HABA.items()):
        v = sorted(r[k] for r in ref if r.get(k) is not None); lo, hi, x = v[0], v[-1], mine.get(k)
        if x is None: h = '下'; why = '測れない'
        elif x < lo: h = '下'; why = '手本の最小 %s より少ない' % lo
        elif x > hi: h, why = ('上', '手本の最大 %s より多い' % hi + ('（手数は上限なし・依頼主 10/21 0:34）' if k in UE_OK else '')) if (k in KAZU or k in UE_OK) else ('下', '手本の最大 %s より多い（多すぎ）' % hi)
        else: h, why = '同じ', '手本の幅 %s〜%s の中' % (lo, hi)
        rows.append({'項目': nm, 'key': k, '自分': x, '手本 最小': lo, '手本 最大': hi, '判定': h, 'わけ': why})
        if h == '下': ng.append(nm)
    return rows, ng

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mp4'); ap.add_argument('--t1', type=float, default=171); ap.add_argument('--out'); ap.add_argument('--nozoku')
    a = ap.parse_args()
    REF = json.load(open(os.path.join(HERE, 'zettai', 'rock15-%d.json' % int(a.t1))))
    ref = [v for k, v in REF.items() if k != a.nozoku]
    mine = K3.hakaru(a.mp4, a.t1)
    rows, ng = hantei(mine, ref)
    sys.path.insert(0, HERE); import kinshi_chara as KC   # 依頼主 10/20 23:45「この棒人間みたいなやつ…一生使わないで」：1コマでも出たら不合格（手本と比べる項目とは別）
    kc = KC.video_check(a.mp4, 2, 0.0, a.t1)
    if kc['deta']:
        ng.append('使ってはいけないキャラ（棒人間）')
        print('🔴 使ってはいけないキャラ（棒人間）が %d コマに出る（%s 秒〜）→ ~/rin6/state/yt-henshu/kinshi/chara-boujin' % (len(kc['deta']), kc['deta'][0][0]))
    jc = KC.jimon_check(a.mp4, 15, a.t1)
    if jc['deta']:
        ng.append('使ってはいけないキャラ（地の線画）')
        print('🔴 使ってはいけないキャラの線画が地（背景）に入っている：%s' % {k: v for k, v in jc.items() if k != 'deta'})
    mine['kinshi_jimon'] = jc
    import kara_gamen as KG   # team-lead 10/21：字幕・札以外の部品が何もないコマが0.5秒以上続いたら不合格（MJrC edl-j 25.0〜26.3秒の空の画面を門が通した）。動画の全長を見る
    kg = KG.kara_check(a.mp4, None, 0.5)
    if kg['deta']:
        ng.append('空の画面（字幕と札だけ）')
        print('🔴 空の画面（字幕と札だけ）が0.5秒以上：%s 秒' % '・'.join('%s〜%s' % x for x in kg['deta']))
    mine['kara_gamen'] = kg
    sys.path.insert(0, os.path.join(HERE, 'zettai')); import telop_rock as TR   # 2026-10-23 作業AIの判断：テロップの出/分（講義型37本・頭171秒・ゆとり0.1）。字が多すぎる v14（96/分）を止める。頭が120秒未満の試験では測らない（記録 ~/rin6/state/mon-yutori-20261023.md）
    tr, tr_ng = TR.check(a.mp4, a.t1, a.nozoku)
    if tr:
        rows.append(tr); mine['telop_pm'] = tr['自分']
        if tr_ng: ng.append(tr['項目'])
    mine['kinshi_chara'] = {'deta_koma': len(kc['deta']), 'saisho': kc['deta'][0][0] if kc['deta'] else None, 'mihon_betsu': kc['mihon_betsu']}
    for r in rows: print('%s %-24s 自分 %-8s 手本 %s〜%s  %s' % ({'下': '🔴', '同じ': '✅', '上': '⬆️'}[r['判定']], r['項目'], r['自分'], r['手本 最小'], r['手本 最大'], r['わけ'] if r['判定'] != '同じ' else ''))
    res = {'例外（判定から外した項目）': [dict(key=k, 理由=v, 自分=mine.get(k)) for k, v in REIGAI.items()], '動画': a.mp4, '頭の秒': a.t1, '手本': sorted(k for k in REF if k != a.nozoku), '合格': not ng, '下の項目': ng, '項目': rows, '測った値': mine}
    if a.out: json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('手本の編集者さんの門：%s' % ('合格（全項目 同じ以上）' if not ng else '不合格（下 %d 項目：%s）' % (len(ng), '・'.join(ng))))
    sys.exit(0 if not ng else 1)
