#!/usr/bin/env python3
# 質の門の基準 kijun.json を作る（見本の実測 → 合格の幅）。測り直したら: python3 kijun_make.py
#   実測の元：~/rin6/state/yt-anime-1014/kata/kijun_measured.json（build/kijun_make.py が見本 60本を 30fps で測ったもの）
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')); import paths
M = json.load(open(os.path.join(paths.ENGINE, 'kata', 'kijun_measured.json')))['by_win']
F = 1 / 29.97
def med(k, sub): return sum(M[w][k][sub] for w in ('hook', 'mid', 'end')) / 3
K = {
 '_説明': '質の門の基準。見本（委託の編集者さん）60本を同じ式（lib/metrics.py）で 30fps で測った分布から作った。区間＝hook30（最初30秒）・hook（最初90秒）・mid（真ん中60秒）・end（最後45秒）。'
          '1つでも外れたら check.py が不合格で止める。',
 'frame': round(F, 4),
 'telop': {'offset_target': round(med('telop_offset', 'p50'), 3), 'tol': round(2 * F, 3),
           '_': '画面の変化−声の立ち上がり（秒）。見本の中央値に合わせ、作業AIの部品は「声の立ち上がり＋この値」に置く。中央値がこの±2コマ、部品が描かれるコマも±2コマ'},
 'sfx': {'offset_target': round(med('sfx_offset', 'p50'), 3), 'tol': round(2 * F, 3), '_': '効果音−画面の変化（秒）。効果音は部品が動き出すコマに置く'},
 'pause': {'line_keep': 0.13, 'inner_keep': 0.05, 'ma_keep': 0.6,
           'p50_max': round(max(M[w]['pause_len']['p50'] for w in M) + 0.03, 3), 'p90_max': round(max(M[w]['pause_len']['p90'] for w in M) + 0.03, 3),
           'pm_max': {w: M[w]['pauses_pm']['p90'] for w in M}, 'ma_max_count': 4,
           '_': '声の無音（0.08秒以上）の長さと数。行の切れ目だけ残し、行の中は詰める（ジャンプカット）。台本の【間】は強調の前だけ'},
 'motion': {'scene_zoom': None, 'share_min': {w: M[w]['motion_share']['p25'] for w in M}, '_': 'ゆっくり動いているコマの割合（寄り・揺れ・流れる光）'},
 'changes_pm': {'min': {w: M[w]['changes_pm']['p25'] for w in M}, 'max': {w: M[w]['changes_pm']['p90'] for w in M}, '_': '画面の変化の回数/分（30fpsで差が閾値を越えた回数）'},
 'longest_static': {'max': {w: M[w]['longest_static']['p75'] for w in M}, '_': '何も変わらない画面の最長（秒）'},
 'sfx_pm': {'min': {w: M[w]['sfx_pm']['p10'] for w in M}, 'max': {w: M[w]['sfx_pm']['p90'] for w in M}, '_': '効果音の回数/分'},
 'telop_selection': {'full_share_max': 0.3, 'full_run_max': 2, '_': '台本を全部テロップで出さない（依頼主 10/15 絶対ルール）。全文の割合と連続の上限は仮。kata/per_full の numbers が揃ったら見本の割合に置き換える'},
 'hook30_density': {'changes_pm_min': M['hook30']['changes_pm']['p50'], 'sfx_pm_min': M['hook30']['sfx_pm']['p25'],
                    '_': '冒頭30秒は離脱が一番多い→見本の中央値以上の密度を求める'},
}
json.dump(K, open(paths.KIJUN, 'w'), ensure_ascii=False, indent=1); print(json.dumps(K, ensure_ascii=False, indent=1))
