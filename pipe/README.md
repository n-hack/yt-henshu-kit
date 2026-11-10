# yt-henshu-pipe：声＋台本 → 1本の完成動画（作業AI 2026-10-19）

依頼主は「ナレーション（ジャンプカット済みの声）＋台本」だけを渡す。そこからコマンド1つで、門を通った mp4・目視の一覧画像・報告・Drive まで出す。

```
python3 ~/rin6/tools/yt-henshu/pipe/yt-pipe.py --koe <声.wav|mp3|m4a> --daihon <台本.txt> --out <作業フォルダ> \
        [--kind VSL|YouTube] [--name 名前] [--drive <DriveのフォルダID>] [--from 段] [--to 段] [--gpu 2]
```
- 新しい1本は指示書（EDL）で組む：`PIPE_EDL=1 python3 ~/rin6/tools/yt-henshu/pipe/yt-pipe.py --out <作業フォルダ> --name <名前> --edl <edl.json> --from bamen --to me`（入口の説明は ../README.md の「最短の手順」）。`--edl` が無いと bamen は AI が場面表を書く（10/20 に「壊滅的」と言われた形）
- 途中で止まったら、直してから `--from <段>` で続きから回せる（作った物は作業フォルダに残る）
- 依頼主へは送らない。報告は `<作業フォルダ>/out/<名前>-houkoku.md`。作業AIが確かめてから送る

## 段（順番）と、面談前VSL v12 で手でやっていた所の置き換え
| 段 | 道具 | v12 で手でやっていたこと → ここでは |
|---|---|---|
| junbi | yt-pipe.py | 声は wav に写すだけ（絶対ルール2・長さが1コマ以上ずれたら止める） |
| okoshi | koe_okoshi.py | 20秒ずつ起こし直し（kiru_zen.py の手の刻み）→ 間で切ったかたまりごと。声があるのに言葉が無い所が1秒を超えたら割って起こし直す |
| gyou | gyou_auto.py＋align/kotoba_align.py | 行の頭の言葉を手で70個並べた（loomzen/gyou.py）→ 台本の文の切れ目を話した字へ当て、強制合わせの頭と静かな長さで切り直す。言葉の途中では切らない（文節） |
| jimaku | jimaku_ji.py＋kire_auto.py | 聞き違いの直し表（ki1.py の JIMAKU_FIX 60件余り）→ 台本と違う所を1件ずつ AI が「聞き違い／言い換え」で判断（判断は work/jimaku_ji_ai.json に残し使い回す）。切れ目の表（v12/kire_heads.py）→ 毎回自動。名詞の並びの中黒（投稿・リサーチ）、5字未満の札は前後とつなぐ |
| bamen | bamen_gen.py＋BAMEN-GUIDE.md＋kensa_bamen.py | 場面表を手で書いた → 章割り・訴求・部品を AI（claude -p・opus）が章ごとに書き、機械の検査（重なり5%・字幕帯・5秒の空き・帯と字幕の食い違い・種類）で最大3回直させる |
| sozai | sozai_auto.py | 素材一覧を手で書いた → 置いた部品の記録から出どころ・使った秒を自動で |
| render | lib/render.py | GPU（h264_videotoolbox）・nice 19・同時2本・メモリの圧力が1の時だけ始める |
| mon | ../zettai-mon.py | 1コマ超の取り違えを例外の記録で通した（140.35秒）→ 門のルール5が zure-saiken.py で見直し、本当のずれだけ止める |
| kensa | jimaku_koma.py・wari_kazoe・jimaku_taishou.py | 字幕のずれ全件・割れ・台本との突き合わせ（v12 で手で走らせた3つ）→ 毎回。ずれ1コマ超・割れ1件でも止める |
| me | me_ai.py | 一覧画像を作業AIが見た → 60コマの一覧を AI の別の目が見て、直す所があれば場面表へ戻して書き出しからやり直す（最大3回）。通れば ai-label-check --mokushi-ok |
| drive | tools/drive-up.py | 見られる人が依頼主と you@ だけか確かめる（ほかがいれば止める） |

## 使う素材（手元に要る物）
- 部品：pipe/ki1.py（面談前VSL loomzen/ki1.py の写し＋字幕の字を表から取る節）・lib/henshu.py・riso_kata.py
- 実際の画面：state/yt-evervsl-1019/e/gamen/（14枚・gamen.json に中身）。元の画面録画は内蔵から Drive へ移った（10/19）
- 自社キャラのアイコン：pipe/sozai/chara_icon1024.png（元は xtep-vtuber-buzz-1017・Drive へ移って読めなくなったので写した）。ロゴ・背景：state/yt-evervsl-1019/e/・yt-anime-1014/sozai（手本の作者さんの素材は許可済み）。junbi と render の前に素材が読めるかを確かめる
- BGM：sozai/bgm の honpen_gray・honpen_gray_b・kokuchi（Afterglow は依頼主の購入待ちで使わない）

## 戻し方
- このフォルダ（pipe/）を消せば元の道具に戻る（ほかの道具は呼ぶだけで書き換えていない）
- 門のルール5の見直し：`zettai-mon.py.bak-20261019-saiken` を zettai-mon.py に戻す（zure-saiken.py は残っても使われない）
