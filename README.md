# yt-henshu-kit：声＋台本 → 門を通った1本の動画

YouTube・VSL（縦長でない解説動画）を、**ジャンプカット済みのナレーション音声と台本だけ**から1本に編集する道具一式です。
書き起こし → 台本との突き合わせ → 字幕 → 場面づくり → GPU 書き出し → 機械の門 → 目視用の一覧画像、までを順に回します。

> この置き場には**コードと設定・決まりの文書だけ**が入っています。素材（絵・BGM・効果音・手本の動画）、声、書き出した動画、測った作業データは含みません。

## 入口

| 入口 | 使うとき |
|---|---|
| `pipe/yt-pipe.py` | **新しい1本はこちら**。声＋台本＋指示書（EDL）→ 書き出し → 門 → 別の目 → 報告 |
| `make.py` | 前の作り方（声＋台本 → 場面表 story.py → 書き出し → 質の門）。段ごとに回す・部分の直しに使う |

```bash
# ① 声と台本を入れて、書き起こし・行・字幕まで（声は写すだけで編集しない）
nice -n 19 python3 pipe/yt-pipe.py --koe <声.wav|mp3|m4a> --daihon <台本.txt> --out <作業フォルダ> --name <名前> --to jimaku

# ② 指示書（EDL）で場面を組み、書き出し・門・別の目まで
PIPE_EDL=1 python3 pipe/yt-pipe.py --out <作業フォルダ> --name <名前> --edl <edl.json> --from bamen --to me
```

途中で止まったら、直してから `--from <段>` で続きから回せます。段の中身は [pipe/README.md](pipe/README.md)。

## 主なファイルの役割

**流れ（pipe/）**
- `pipe/yt-pipe.py` … 全体の入口。段（junbi → okoshi → gyou → jimaku → bamen → sozai → render → mon → kensa → me → drive）を順に回す
- `pipe/koe_okoshi.py`・`align/` … 声の書き起こし（言葉ごとの時刻つき）と、台本への強制合わせ・言い直しの扱い
- `pipe/gyou_auto.py`・`pipe/jimaku_ji.py`・`pipe/kire_auto.py` … 台本の文の切れ目で行に分け、字幕に出す字と切れ目を決める
- `pipe/edl_kumi.py`・`pipe/edl_henkan.py` … 1文ずつ「絵・動き・大字・切り替え」を書いた指示書を場面に組む
- `pipe/bamen_gen.py`・`pipe/kensa_bamen.py`・`pipe/BAMEN-GUIDE.md` … 場面表を AI に書かせ、機械の検査で直させる（部品の一覧は BAMEN-GUIDE.md）
- `pipe/zukai.py`・`pipe/ki1.py` … 図解アニメーション・見た目の部品
- `pipe/jimaku_koma.py`・`pipe/jimaku_taishou.py` … 字幕のずれ（コマ単位）と台本との字の突き合わせ
- `pipe/me_ai.py`・`pipe/me_shot.py` … 書き出した動画から一覧画像を作り、別の目で見て直す所を返す

**門（出す前に機械で止める）**
- `zettai-mon.py` ＋ `ZETTAI-RULES.md` … 動画編集の絶対ルール10の門。1つでも外れたら exit 1 と理由を出す。試験は `zettai/shiken.py`
- `check.py` ＋ `kijun.json` … 質の門。見本と同じ式で測り、`kijun.json` の幅に入っているか（基準は `kijun_make.py` で作り直す）
- `rock-mon.py` … 最低ラインの門。手本15本の幅の外（多すぎ・少なすぎ）は不合格（`zettai/rock15-*.json`）
- `miyasusa-mon.py`・`hyougen-mon.py` … 見やすさ（字と地の色の差）・動きの型・見せ方・全画面挿絵の頻度
- `zure-kensa.py`・`zure-saiken.py` … 言葉と画面のずれの検算と見直し
- `kinshi_chara.py`・`kara_gamen.py` … 使ってはいけない絵・空の画面が1コマでも出たら止める
- `sekisho.py` … 出す前の関所

**描画エンジン（engine/）**
- `engine/build/anim.py`・`kit.py` … 場面の部品（字幕帯・図解・切り替え）を描く
- `engine/build/render.py`・`story.py`・`sfx_plan.py` … 場面表から1コマずつ組み、効果音を置いて書き出す
- `engine/themes/*.json` … 色・地・字の見た目の組み合わせ

**部品（lib/）**
- `lib/paths.py` … 置き場の設定。**別の場所で使うときはここだけ直す**
- `lib/render.py` … GPU 書き出し（h264_videotoolbox）・同時本数とメモリの見張り
- `lib/henshu.py`・`lib/riso_kata.py` … 場面の組み立てと型
- `lib/metrics.py`・`lib/kanten*.py`・`lib/loud.py` … 測る式（動き・観点・音量）

**そのほか**
- `narration/` … 粗い声の扱い（書き起こし・評価・時刻だけ取る形）
- `jumpcut*.py` … 生の声のジャンプカット（いまの本番では声はジャンプカット済みで来るので通さない）
- `kanpi.py`・`README-kanpi.md`・`mikai.py` … 完コピ練習（答えを見ない練習）
- `ocr.swift` … 画面の文字読み（macOS の Vision）
- `SHIAGE.md` … 仕上げの手順

## 動かすのに要る物

- macOS（Apple シリコン）。書き出しは GPU（`h264_videotoolbox`）を使う
- `ffmpeg` と `ffprobe`
- Python 3 と次のライブラリ：`numpy`・`Pillow`・`scipy`・`opencv-python`・`mlx-whisper`（書き起こし）・`demucs`（声と声以外を分ける）・`praat-parselmouth`・`soundfile`・`pykakasi`
- 描画エンジンは `engine/` に入っています（`engine/build/anim.py`・`kit.py`・`render.py`・`sfx_plan.py` ほか、見た目の設定は `engine/themes/*.json`）。既定では `lib/paths.py` がこの `engine/` を使います。別の場所に置くときは環境変数 `YT_ENGINE` で指します
- フォントのファイルは含みません。次のフォントを各配布元から入手して `engine/build/fonts/` に置いてください：
  Noto Sans JP（`NotoSansJP-VF.ttf`）・Noto Serif JP（`NotoSerifJP-VF.ttf`）・Dela Gothic One・Mochiy Pop One・M PLUS Rounded 1c ExtraBold・RocknRoll One・Shippori Mincho B1 ExtraBold・Zen Maru Gothic Black・Zen Old Mincho Black・Pacifico・Material Symbols Rounded（`MaterialSymbolsRounded.ttf` と `.codepoints`）
- 素材（`sozai/`・`assets/`）・手本の型のデータ（`kata/`）は含みません。書き出しにはこれらを `engine/` の下に用意する必要があります
- 場面表と別の目は AI のコマンドを呼びます（`pipe/bamen_gen.py`・`pipe/me_ai.py`）。外部の API 鍵は `lib/paths.py` の `ENV` が指すファイルから読みます（鍵そのものは含みません）

## 含まないもの

- 素材（絵・写真・BGM・効果音）と手本の動画
- 声（ナレーション）と書き出した動画
- 測った作業データ・記録・バックアップ・鍵

コード中のメールアドレスは `example.com` の伏せ字、ホームの絶対パスは `~` に置き換えてあります。そのままでは動かない所（置き場・宛先）は `lib/paths.py` などで自分の環境に合わせてください。
