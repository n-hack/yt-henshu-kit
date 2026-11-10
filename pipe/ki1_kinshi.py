"""作業フォルダの ki1.py の写しから「棒人間（自社キャラの頭＋線の体）の地の線画」だけを外す（10/21・依頼主 10/20 23:45）。
写しには作業フォルダごとの直し（字幕の切れ目など）が入っているので、丸ごと差し替えずにこの部分だけ消す。"""
import re

def kesu(t):
    n0 = t
    t = re.sub(r"\n# 8版目（10/19 04:3x 作業AIの判断）[^\n]*\n_CHARA_MASK = [^\n]*\ndef chara_line\(rgb, h\):\n(?:    [^\n]*\n)+", "\n# 地の線画（自社キャラの頭＋線の体）は 10/21 に外した（依頼主 10/20 23:45・kinshi/chara-boujin）\n", t)
    t = re.sub(r"    for rgb, al, off in \(\[\(shadow, sa, 3\)\] if shadow else \[\]\) \+ \[\(main, ma, 0\)\]:\n        f = chara_line\(rgb, hh\)[^\n]*\n        im\.alpha_composite\(f[^\n]*\n", "", t)
    return t, t != n0

def nokori(t):
    return bool(re.search(r'chara_line\(|_CHARA_MASK|jimon_chara', t))
