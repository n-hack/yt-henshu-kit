#!/usr/bin/env python3
"""指示書（EDL）の場面ごとに、手本の型（kata-zenbu-yt.json）から一番近い型を選ぶ。

近さ：①伝えたいこと（同じ決まりで付ける）が同じ ②字の箱の数が部品の数に近い ③手本の作者さんの本編を先に。
出す：場面ごとに 型の番号（上位3）・置き方・前とのつなぎ・出方の順（手本でいちばん多い並び）
使い方: python3 kata_ate.py <edl.json> <出力.json>
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kata_zenbu_yt as K  # noqa: E402

KATA = os.path.join(K.BASE, 'kata-zenbu-yt.json')
SOTO = {'jinbutsu', 'bg', 'haikei', 'jimaku'}   # 置き方の数に入れない部品


def main(edl_p, out_p):
    kata = [k for k in json.load(open(KATA)) if k.get('hako') is not None]
    by = collections.defaultdict(list)
    for k in kata:
        by[k['tsutae']].append(k)
    e = json.load(open(edl_p))
    plan, kazu = {}, collections.Counter()
    # 同じ話題（wadai の先頭 T番号・章ごと）で決まった「伝えたいこと」を、決まらなかった続きの場面へ回す
    import re
    tsg = {}
    for s in e['shots']:
        ts = K.ate(K.TSUTAE, '%s %s' % (s.get('wadai') or '', s.get('imi') or ''))
        m = re.match(r'(T\d+)', s.get('wadai') or '')
        if m and ts != 'その他':
            tsg.setdefault((s.get('ch'), m.group(1)), collections.Counter())[ts] += 1
    mae = None
    nokori = 0   # keep の場面は前の部品が画面に残る → 画面に出ている数で型を選ぶ
    for s in e['shots']:
        ts = K.ate(K.TSUTAE, '%s %s' % (s.get('wadai') or '', s.get('imi') or ''))
        m = re.match(r'(T\d+)', s.get('wadai') or '')
        if ts == 'その他' and m and (s.get('ch'), m.group(1)) in tsg:
            ts = tsg[(s.get('ch'), m.group(1))].most_common(1)[0][0]
        elif ts == 'その他' and mae and '続き' in (s.get('wadai') or ''):
            ts = mae
        mae = ts
        jibun = len([p for p in s.get('parts') or [] if p.get('kind') not in SOTO])
        nokori = (nokori if s.get('kirikae') == 'keep' else 0) + jibun
        n = nokori
        pool = by.get(ts) if ts != 'その他' else kata   # 伝えたいことが決まらない場面は全部の型から
        pool = pool or kata
        pool = sorted(pool, key=lambda k: (abs(k['hako_n'] - n), k.get('channel') != 'youtube.tehon', k['id']))[:30]
        if not pool:
            continue
        de = []   # 位置ごとに、手本でいちばん多い出方（1コマで出る cut は数えない）
        for i in range(max(n, 1)):
            c = collections.Counter(k['junban'][i]['de'] for k in pool if len(k['junban']) > i and k['junban'][i]['de'] != 'cut')
            de.append(c.most_common(1)[0][0] if c else 'cut')
        plan[s['id']] = {
            'tsutae': ts, 'buhin': n, 'jibun': jibun,
            'kata': [k['id'] for k in pool[:3]],
            'haichi': collections.Counter(k.get('haichi_hako') or k['haichi'] for k in pool).most_common(1)[0][0],
            'tsugi': collections.Counter(k['tsugi'] for k in pool).most_common(1)[0][0],
            'dekata': de,
            'hako_rei': [{a: q[a] for a in ('x', 'y', 'w', 'h', 't_de')} for q in pool[0]['hako'] if not q['jimaku']][:6],
        }
        kazu[ts] += 1
    json.dump(plan, open(out_p, 'w'), ensure_ascii=False, indent=1)
    print('場面 %d に型を当てた → %s' % (len(plan), out_p))
    print('伝えたいこと別', dict(kazu.most_common()))
    print('置き方別', dict(collections.Counter(v['haichi'] for v in plan.values()).most_common()))
    print('つなぎ別', dict(collections.Counter(v['tsugi'] for v in plan.values()).most_common()))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
