#!/usr/bin/env python3
# 素材（人物イラスト・キャラ・写真）を作る。OpenAI gpt-6-astra の image_generation（鍵は ~/rin/gateway/.env）。
#   python3 build/gen_assets.py stories/xxx.json [名前...]
#   場面表の "assets" に {名前: {kind, prompt}} を書く。kind = person（人物）/ chara（テーマのキャラ・参照画像つき）/ photo（写真）/ line（キャラの線画）
#   絵の雰囲気（線・塗り・写真の調子）はテーマの asset_style で決まる＝ジャンルが変わってもテーマを替えるだけ。
#   すでにある素材は作り直さない。person / chara は白地で作り、cutout.py で背景を抜いて assets/cut/ に置く。
#   ※このモデルは透明背景に対応していない（HTTP 400）ので白地→自前で抜く。
import json, os, sys, base64, urllib.request, subprocess, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
story = json.load(open(os.path.join(BASE, sys.argv[1])))
theme = json.load(open(os.path.join(BASE, story['theme']))) if story.get('theme') else {}
ST = theme.get('asset_style', {})
key = [l.split('=', 1)[1].strip().strip('"\'') for l in open(os.path.expanduser('~/rin/gateway/.env')) if l.startswith('OPENAI_API_KEY=')][0]
OUT = os.path.join(BASE, 'assets'); os.makedirs(os.path.join(OUT, 'cut'), exist_ok=True)

def prompt_of(kind, p):
    if kind == 'person': return ST.get('person', '') + p
    if kind == 'photo': return ST.get('photo', '') + p
    if kind == 'chara': return ST.get('chara', '') + p
    if kind == 'line': return ST.get('chara', '').replace('フラットイラスト', '白地に黒の細い一本線だけの線画') + '塗りなし、線だけ。' + p
    return p

def run(name):
    out = os.path.join(OUT, name + '.png')
    if os.path.exists(out): return name, 'あり（作り直さない）'
    a = story['assets'][name]; kind = a.get('kind', 'person')
    content = [{"type": "input_text", "text": prompt_of(kind, a['prompt'])}]
    ref = a.get('ref') or (ST.get('chara_ref') if kind in ('chara', 'line') else None)
    if ref:
        content.append({"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(open(os.path.expanduser(ref), 'rb').read()).decode()})
    size = '1536x1024' if kind == 'photo' else '1024x1024'
    body = {"model": a.get('model', 'gpt-6-astra'), "input": [{"role": "user", "content": content}],
            "tools": [{"type": "image_generation", "size": size, "quality": "high"}]}
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try: d = json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e: return name, 'HTTP %s %s' % (e.code, e.read()[:200])
    except Exception as e: return name, 'ERR %r' % e
    for o in d.get('output', []):
        if o.get('type') == 'image_generation_call' and o.get('result'):
            open(out, 'wb').write(base64.b64decode(o['result']))
            if kind in ('person', 'chara'):
                subprocess.run([sys.executable, os.path.join(HERE, 'cutout.py'), out, os.path.join(OUT, 'cut', name + '.png')], check=True)
            return name, 'ok'
    return name, '画像なし ' + json.dumps(d)[:200]

names = sys.argv[2:] or list(story.get('assets', {}))
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(run, names): print(*r, flush=True)
