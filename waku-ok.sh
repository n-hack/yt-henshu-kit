#!/bin/bash
# YouTube書き手が新しい本を始めてよいか。0=始めてよい 1=止まる
# 10/17 19:1x 別の作業AI案②: いまいる席（~/rin/state/claude-usage.json の bots.rin6）の週が70%を超える、
# または5時間が40%以上なら止まる（各席の30%は社内業務に残す・席移りは別の作業AIの見張り）
/opt/homebrew/bin/python3 - <<'PY'
import json,sys,datetime
try:
    d=json.load(open('~/rin/state/claude-usage.json'))
    seat=d['bots']['rin6']; a=d['accounts'][seat]
    asof=datetime.datetime.strptime(a['as_of'],'%Y-%m-%d %H:%M:%S')
except Exception as e:
    print('枠が読めない→止まる',e); sys.exit(1)
age=(datetime.datetime.now()-asof).total_seconds()/60
print(f"席 {seat} ／ 5時間 {a['five']:.0f}% ／ 週 {a['week']:.0f}%（線 70%・40%）／ {age:.0f}分前の数字")
if age>30: print('数字が30分より古い→止まる'); sys.exit(1)
# 10/17 19:4x 別の作業AI案：3席の残りの合計が「社内1日分（多めに14%）×次に席が戻るまでの日数」を下回ったら止まる
SEATS=['seat1@example.com','seat2@example.com','owner@example.com','seat4@example.com']  # 10/17 19:49 依頼主の判断で gmail も担当の席に
now=datetime.datetime.now().astimezone()
nokori=0.0; modoru=[]
for s2 in SEATS:
    b=d['accounts'].get(s2)
    if not b: continue
    nokori+=max(0.0,100-b['week'])
    try: modoru.append(datetime.datetime.fromisoformat(b['week_reset']))
    except Exception: pass
hi=max(0.0,(min(modoru)-now).total_seconds()/86400) if modoru else 7.0
hitsuyou=14*hi
print(f"3席の残り {nokori:.0f}% ／ 次に席が戻るまで {hi:.1f}日 ／ 社内に残す {hitsuyou:.0f}%")
if nokori < hitsuyou:
    open('~/rin6/state/yt-henshu/waku-log.tsv','a').write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\t{seat}\t{a['five']:.0f}\t{a['week']:.0f}\t止(社内分)\n"); sys.exit(1)
if a['five']>=40 or a['week']>70:
    open('~/rin6/state/yt-henshu/waku-log.tsv','a').write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\t{seat}\t{a['five']:.0f}\t{a['week']:.0f}\t止\n"); sys.exit(1)
sys.exit(0)
PY
