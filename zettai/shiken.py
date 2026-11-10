#!/usr/bin/env python3
# zettai-mon.py の試験（作業AI・2026-10-19）：通るはずの例1つ・止まるはずの例4つを作って門にかけ、期待どおりかを表にする
#   python3 shiken.py            → ~/rin6/state/yt-henshu/zettai-mon/shiken/（作り直す）・kekka.json
#   声は loom3 の依頼主の声の頭 11 秒（読むだけ）。書き出しは GPU（render.video）
import os, sys, json, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); TOOL = os.path.dirname(HERE); sys.path.insert(0, os.path.join(TOOL, 'lib'))
ROOT = os.path.expanduser('~/rin6/state/yt-henshu/zettai-mon/shiken')
SRC = os.path.expanduser('~/rin6/state/yt-evervsl-1019/loom3')
A = os.path.expanduser('~/rin6/state/yt-anime-1014/assets'); GAMEN = os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/gamen')
REI = {'ok': (0, None), 'gaibu': (1, '3'), 'telop': (1, '5'), 'icon': (1, '6'), 'koe': (1, '2'), 'nobgm': (1, '10'), 'reigai': (0, 'reigai2'), 'reigaikara': (1, '2')}   # 期待する終了コードと、外れるはずの項目
T0, T_END = 0.35, 10.9   # 頭の「こんにちは」（0.03〜0.27秒）は外す：次の行と12コマしか離れず、ずれの測りが動画の頭の変化を拾う（10/19 試験）

def build(h):
    P = os.path.join(ROOT, h); shutil.rmtree(P, ignore_errors=True); os.makedirs(os.path.join(P, 'work')); os.makedirs(os.path.join(P, 'input')); os.makedirs(os.path.join(P, 'out'))
    nar, vo = os.path.join(P, 'input', 'narration.wav'), os.path.join(P, 'work', 'vocals.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(T0), '-i', os.path.join(SRC, 'work', 'vocals.wav'), '-t', str(T_END - T0), '-c:a', 'pcm_s24le', nar], check=True)   # 依頼主から来たジャンプカット済みの声（とする）
    if h in ('koe', 'reigai', 'reigaikara'):   # koe：9.37〜9.50 秒の間を詰めた（reigai＝同じ声＋例外の記録が全部ある／reigaikara＝同じ声＋例外の記録の理由が空）
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', nar, '-af', "aselect='not(between(t,%.2f,%.2f))'" % (9.37 - T0, 9.50 - T0) + ",asetpts=N/SR/TB", '-c:a', 'pcm_s24le', vo], check=True)
    else: shutil.copy(nar, vo)
    dv = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', vo], capture_output=True, text=True).stdout)
    TJ = json.load(open(os.path.join(SRC, 'work', 'timing.json')))
    lines = [dict(l, start=round(l['start'] - T0, 3), end=round(l['end'] - T0, 3)) for l in TJ['lines'] if T0 <= l['start'] and l['end'] <= T_END]
    json.dump({'lines': lines, 'duration': round(dv - 0.02, 3), 'speed': 1.0, 'source': '試験（loom3 の頭11秒）'}, open(os.path.join(P, 'work', 'timing.json'), 'w'), ensure_ascii=False)
    if h in ('reigai', 'reigaikara'):
        json.dump([{'項目': 2, '理由': '' if h == 'reigaikara' else '試験：依頼主の指示 10/19 02:54『一旦今は俺のVSLの素材でテストして』による試し', '決めた人': '作業AI', '日時': '2026-10-19 05:00'}],
                  open(os.path.join(P, 'reigai.json'), 'w'), ensure_ascii=False)
    json.dump({'henkei': 'koe' if h.startswith('reigai') else h}, open(os.path.join(P, 'work', 'henkei.json'), 'w'))
    shutil.copy(os.path.join(HERE, 'shiken_story.py'), os.path.join(P, 'story.py'))
    t = [round(l['start'], 2) for l in lines]
    sozai = {'narration_moto': os.path.join(P, 'input', 'narration.wav'),
             'tehon': ['crlzmL2m4sE', 'NzjnSa2FrxU', 'kUPDyQA1pNs'],
             'sozai': [
                 {'name': '自社キャラのアイコン', 'file': os.path.join(A, 'chara_flat.png'), 'shurui': '話し手アイコン', 'deguchi': '自作', 'moto': '自社キャラのキャラ（自社）'},
                 {'name': '考える人', 'file': os.path.join(A, 'p_man_think.png'), 'shurui': 'イラスト', 'deguchi': '自作', 'moto': '画像生成（assets/gen2.log）', 'basho': t[0:1]},
                 {'name': '机の写真風の絵', 'file': os.path.join(A, 'ph_desk.png'), 'shurui': '挿絵', 'deguchi': '自作', 'moto': '画像生成', 'basho': t[3:4]},
                 {'name': 'オフィスの全画面', 'file': os.path.join(A, 'p_office.png'), 'shurui': '全画面挿絵', 'deguchi': '自作', 'moto': '画像生成', 'basho': t[2:3]},
                 {'name': '指示→実行→完成', 'file': None, 'shurui': '図解', 'deguchi': '自作', 'moto': '場面表で描いた', 'basho': t[1:2]},
                 {'name': 'うちの画面録画', 'file': os.path.join(GAMEN, '01_55.png'), 'shurui': '実際の画面', 'deguchi': '自作', 'moto': 'seminar-canva-douga の画面録画', 'basho': t[2:3]}]}
    if h == 'icon': sozai['sozai'][0] = {'name': '自社キャラのアイコン（のつもり）', 'file': os.path.join(A, 'v1_mascot_line.png'), 'shurui': '話し手アイコン', 'deguchi': '手本の作者さん', 'moto': '右下の丸いロゴの写し'}
    json.dump(sozai, open(os.path.join(P, 'sozai-ichiran.json'), 'w'), ensure_ascii=False, indent=1)
    return P

def main():
    os.makedirs(ROOT, exist_ok=True); rows = []
    import render
    for h, (want, rule) in REI.items():
        P = build(h); mp4 = os.path.join(P, 'out', h + '.mp4')
        r = subprocess.run(['nice', '-n', '19', sys.executable, '-c', ('import sys,os,json;sys.path.insert(0,%r);import render,anim\nP,o=%r,%r;S=render.load_story(P);f1=int(round(S.END*anim.FPS));t=os.path.join(P,"out","tmp");os.makedirs(t,exist_ok=True)\n'
                            'J=[(P,i,a,b,os.path.join(t,"part%%03d.mp4"%%i)) for i,a,b in render._parts(f1,1)]\n[render._chunk(j) for j in J];render._join(P,S,t,J,o)\n'
                            'json.dump({"end":S.END,"f1":f1,"parts":[j[1:] for j in J],"out":o},open(os.path.join(t,"parts.json"),"w"))') % (os.path.join(TOOL, 'lib'), P, mp4)],
                           capture_output=True, text=True, env=dict(os.environ, PROJ=P))
        if r.returncode: print(r.stderr[-3000:]); sys.exit('書き出せなかった ' + h)
        g = subprocess.run([sys.executable, os.path.join(TOOL, 'zettai-mon.py'), P, '--mp4', mp4, '--out', os.path.join(P, 'mon')], capture_output=True, text=True)
        K = json.load(open(os.path.join(P, 'mon', 'kekka.json')))
        hazure = sorted(K['外れ'].keys(), key=int)
        if rule == 'reigai2': okk = g.returncode == 0 and [r['項目'] for r in K.get('例外で通過', [])] == [2] and bool(K.get('依頼主への報告に書く行'))   # 例外で通過（ルール2）が kekka.json に残る
        else: okk = (g.returncode == want) and (rule is None or rule in hazure)
        rows.append({'例': h, '期待': ('例外で通る（ルール2）' if rule == 'reigai2' else '通る') if want == 0 else '止まる（%s）' % rule, '終了コード': g.returncode, '外れた項目': hazure,
                     '理由': {k: v for k, v in K['外れ'].items()}, '例外で通過': K.get('例外で通過', []), '期待どおり': okk})
        print('%-6s 期待 %-10s 終了 %d 外れ %s → %s' % (h, rows[-1]['期待'], g.returncode, ','.join(hazure) or 'なし', '✅' if okk else '🔴'), flush=True)
        if g.returncode and want == 0: print(g.stdout[-4000:])
    json.dump(rows, open(os.path.join(ROOT, 'kekka.json'), 'w'), ensure_ascii=False, indent=1)
    print('期待どおり %d / %d' % (sum(r['期待どおり'] for r in rows), len(rows)))
    sys.exit(0 if all(r['期待どおり'] for r in rows) else 1)

if __name__ == '__main__': main()
