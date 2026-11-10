# 置き場（ここだけ直せば別の場所でも動く）
import os
HOME = os.path.expanduser('~')
TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get('YT_ENGINE', os.path.join(TOOL, 'engine'))          # 描画エンジン（build/anim.py・kit.py・sfx_plan.py・fonts・themes）
BUILD = os.path.join(ENGINE, 'build')
VENV_PY = os.path.join(ENGINE, '.venv/bin/python')               # mlx_whisper・demucs・parselmouth 入り
SOZAI_CANDIDATES = [os.path.join(ENGINE, 'sozai2'), os.path.join(ENGINE, 'sozai')]   # 見本（委託の編集者さん）の素材。sozai2 が揃っていればそちら
KATA = os.path.join(ENGINE, 'kata', 'kata.json')                 # 場面の訴求 → 編集の手 の対応表
KIJUN = os.path.join(TOOL, 'kijun.json')                         # 質の門の基準
ENV = os.path.join(HOME, 'rin/gateway/.env')
AI_LABEL = os.path.join(HOME, 'rin6/tools/ai-label-check.py')
DRIVE_UP = os.path.join(HOME, 'rin6/tools/drive-up.py')
def sozai_dir():
    for d in SOZAI_CANDIDATES:
        if os.path.exists(os.path.join(d, 'READY')) or os.path.exists(os.path.join(d, 'se', 'index.tsv')): return d
    return SOZAI_CANDIDATES[-1]
def env(k):
    for l in open(ENV):
        if l.startswith(k + '='): return l.split('=', 1)[1].strip().strip('"\'')

os.environ.setdefault('THEME', os.path.join(ENGINE, 'themes', 'sns-cream.json'))   # 描画エンジンを読む前に見た目の設定を決める
