#!/usr/bin/env python3
# 判断カットの確かめ：残すと決めた言葉が切った声に全部あるか／消すと決めた言葉が残っていないか（作業AI 2026-10-19）
#   両方を 声の島ごとの起こし（jumpcut_shima.py）で読み、かなにして並べ比べる（difflib）。漢字の書き揺れは かなで消える
#   使い方: narration/.venv/bin/python jumpcut_kensa.py カット表 cut.json 切った声の起こし.json 出力.json
#   残すと決めた字は cut.json の nokosu_text（指示書の 窓の差し替えを当てた後の言葉）
import difflib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "narration"))
from common import kana                 # noqa: E402


def main():
    cut, ato, dst = sys.argv[1:4]
    cut = json.load(open(cut)); A = json.load(open(ato))
    ref = list(kana(cut["nokosu_text"]))     # 残すと決めた字（かな）
    hyp = list(kana("".join(w[2] for w in A)))
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    kake, fue = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("delete", "replace") and i2 - i1 >= 2:
            kake.append({"mae": "".join(ref[max(0, i1 - 12):i1]), "kieta": "".join(ref[i1:i2]), "kawari": "".join(hyp[j1:j2])})
        if op in ("insert", "replace") and j2 - j1 >= 3:
            fue.append({"mae": "".join(ref[max(0, i1 - 12):i1]), "fueta": "".join(hyp[j1:j2]), "moto": "".join(ref[i1:i2])})
    res = {"残すと決めた字": len(ref), "切った声の字": len(hyp), "一致率": round(sm.ratio(), 4),
           "欠け（2字以上の消え・置き換わり）": len(kake), "欠けた字の合計": sum(len(x["kieta"]) for x in kake),
           "増え（3字以上・消したはずの言葉が残った疑い）": len(fue), "欠け一覧": kake, "増え一覧": fue}
    json.dump(res, open(dst, "w"), ensure_ascii=False, indent=1)
    print({k: v for k, v in res.items() if "一覧" not in k})


if __name__ == "__main__":
    main()
