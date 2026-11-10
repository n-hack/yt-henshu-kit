#!/usr/bin/env python3
# 指示書の枠だけを見る道具（作業AI 10/20）：書き出しをせずに、組み立てと見張り（外枠のはみ出し・大字と人物／写真の重なり）だけを回す
#   yt-edl が指示書を渡す前に回して、止める件数0を確かめる。計算ではなく、本番と同じ edl_kumi が実際に置いた枠で数える
#   使い方：python3 edl_waku.py <指示書.json> [--proj 字幕まで済んだプロジェクト]
#   終わり：0＝止める件数0（🟡は出してよい）／1＝止める件数あり（直してから渡す）／2＝組み立て自体が止まった（言葉が見つからない・置き換え など）
import os, sys, json, shutil, subprocess, tempfile, time, argparse
ap = argparse.ArgumentParser()
ap.add_argument('edl')
ap.add_argument('--proj', default=os.path.expanduser('~/rin6/state/yt-henshu/pipe-1019/r15/proj'))
a = ap.parse_args()
PROJ = os.path.abspath(os.path.expanduser(a.proj)); EDL = os.path.abspath(os.path.expanduser(a.edl))
if not os.path.exists(os.path.join(PROJ, 'story.py')): sys.exit('🔴 %s に story.py が無い（字幕の段まで済んだプロジェクトを --proj で渡す）' % PROJ)
t0 = time.time()
# 元のプロジェクトは触らない：中身はリンクで借りて、work/edl.json だけ差し替えた写しで組む
tmp = tempfile.mkdtemp(prefix='edl-waku-', dir=os.path.expanduser('~/rin6/state/yt-henshu/pipe-1019'))
for n in os.listdir(PROJ):
    if n == 'work': continue
    os.symlink(os.path.join(PROJ, n), os.path.join(tmp, n))
os.mkdir(os.path.join(tmp, 'work'))
for n in os.listdir(os.path.join(PROJ, 'work')):
    if n in ('edl.json', 'edl_kumi.json', 'waku_dake.json'): continue
    os.symlink(os.path.join(PROJ, 'work', n), os.path.join(tmp, 'work', n))
shutil.copy(EDL, os.path.join(tmp, 'work', 'edl.json'))
env = dict(os.environ, PROJ=tmp, PIPE_WAKU_DAKE='1', PIPE_KASANARI_OK='1', PIPE_GAIWAKU_OK='1')
r = subprocess.run([sys.executable, os.path.join(tmp, 'story.py')], cwd=tmp, env=env, capture_output=True, text=True)
out = os.path.join(tmp, 'work', 'waku_dake.json')
if not os.path.exists(out):
    print('🔴 組み立てが止まった（枠まで届かず・rc=%d）：' % r.returncode)
    print('\n'.join((r.stdout + r.stderr).strip().splitlines()[-6:]))
    shutil.rmtree(tmp, ignore_errors=True); sys.exit(2)
d = json.load(open(out)); shutil.rmtree(tmp, ignore_errors=True)
def gyo(x): return '  %s「%s」 割合%.2f 字%s 相手%s %s' % (x['id'], x['text'], x['wariai'], x['ji_waku'], x.get('aite'), x.get('aite_waku'))
tomeru = d['kasanari_tomeru'] + d['gaiwaku_hamidashi']
print('指示書 %s（%.0f秒）' % (EDL, time.time() - t0))
print('🔴 重なり 0.30以上（止める）：%d' % len(d['kasanari_tomeru'])); [print(gyo(x)) for x in d['kasanari_tomeru']]
print('🔴 外枠のはみ出し（止める）：%d' % len(d['gaiwaku_hamidashi'])); [print('  ' + json.dumps(x, ensure_ascii=False)) for x in d['gaiwaku_hamidashi']]
print('🟡 重なり 0.15〜0.30：%d' % len(d['kasanari_kiiro'])); [print(gyo(x)) for x in d['kasanari_kiiro']]
print('   重なり 0.08〜0.15（記録だけ）：%d' % len(d['kasanari_hikui']))
print('   zoom の出始めを縮めた：%d %s' % (len(d['zoom']), ' '.join('%s×%s' % (z['id'], z['bai'][1]) for z in d['zoom'])))
print('✅ 渡してよい（止める件数0）' if not tomeru else '🔴 直してから渡す（止める件数 %d）' % len(tomeru))
sys.exit(1 if tomeru else 0)
