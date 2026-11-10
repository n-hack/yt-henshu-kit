# 音量（LUFS）を測る：1本全体の大きさ・声の大きさ・声以外（BGM＋効果音）の大きさ・その差（作業AI・2026-10-15・抜けE）
#   見本は demucs で分けた stems（vocals.wav＝声／bg.wav＝声以外）を測る。作業AIの1本は mp4 の音から編集後の声（work/vocals.wav）を
#   最小二乗で引いて「声以外」を取り出す（見本と同じ分け方になる）。測る式は ffmpeg の ebur128（BS.1770・ゲートつき）
import os, re, subprocess, tempfile
import numpy as np

SR = 48000


def _dec(p, sr=SR):
    return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                                        capture_output=True, check=True).stdout, np.float32).copy()


def lufs_arr(y, sr=SR):
    """配列の Integrated LUFS（無音だけなら None）"""
    if y is None or len(y) < sr * 0.5 or float(np.max(np.abs(y))) < 1e-5: return None
    with tempfile.NamedTemporaryFile(suffix='.f32') as f:
        f.write(y.astype(np.float32).tobytes()); f.flush()
        r = subprocess.run(['ffmpeg', '-v', 'info', '-nostats', '-f', 'f32le', '-ar', str(sr), '-ac', '1', '-i', f.name,
                            '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'], capture_output=True, text=True)
    m = re.findall(r'I:\s+(-?[\d.]+|-inf)\s+LUFS', r.stderr)
    if not m or m[-1] == '-inf': return None
    return float(m[-1])


def peak_db(y):
    return round(20 * np.log10(float(np.max(np.abs(y))) + 1e-12), 2)


def split(mix, voice):
    """mix ≈ g·voice ＋ 声以外。g を最小二乗で出して 声・声以外 に分ける（長さは短い方に合わせる）"""
    n = min(len(mix), len(voice)); a = mix[:n]; v = voice[:n]
    g = float(np.dot(a, v) / (np.dot(v, v) + 1e-12))
    return g * v, a - g * v, g


def measure(mix, voice, bg=None):
    """→ {'I': 全体, 'voice': 声, 'bg': 声以外, 'diff': 声−声以外（dB）, 'peak': 全体のピーク dBFS}"""
    if bg is None: v, b, _ = split(mix, voice)
    else:
        n = min(len(voice), len(bg)); v, b = voice[:n], bg[:n]; mix = v + b
    I, Lv, Lb = lufs_arr(mix), lufs_arr(v), lufs_arr(b)
    return {'I': I, 'voice': Lv, 'bg': Lb, 'diff': round(Lv - Lb, 2) if Lv is not None and Lb is not None else None, 'peak': peak_db(mix)}


def lufs_files(paths):
    """ファイルを元のチャンネルのまま足して Integrated LUFS（YouTube と同じく、左右の音をそのまま測る。1本にまとめると 約3dB 小さく出るため）"""
    ins = sum([['-i', p] for p in paths], [])
    # 1本（モノラル）の音は左右に同じ音を置いてから測る（見本の stems は 22kHz モノラル。元の動画の音 -17.5 LUFS と合うのを _fcqpW8-3X8 で確かめた）
    ch = int(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels', '-of', 'csv=p=0', paths[0]],
                            capture_output=True, text=True).stdout.strip() or 2)
    flt = ('amix=inputs=%d:normalize=0,' % len(paths) if len(paths) > 1 else '') + ('pan=stereo|c0=c0|c1=c0,' if ch == 1 else '') + 'ebur128=framelog=quiet'
    r = subprocess.run(['ffmpeg', '-v', 'info', '-nostats'] + ins + ['-filter_complex' if len(paths) > 1 else '-af', flt, '-f', 'null', '-'], capture_output=True, text=True)
    m = re.findall(r'I:\s+(-?[\d.]+)\s+LUFS', r.stderr)
    return float(m[-1]) if m else None


def measure_sample(stem_dir):
    """見本1本（stems/<id>/vocals.wav・bg.wav）。I は左右のまま、声と声以外の差は1本にまとめて測る（作業AIの1本と同じ式）"""
    vp, bp = os.path.join(stem_dir, 'vocals.wav'), os.path.join(stem_dir, 'bg.wav')
    m = measure(None, _dec(vp), _dec(bp)); m['I'] = lufs_files([vp, bp]); return m


def measure_video(mp4, vocals_wav):
    """作業AIの1本（書き出した mp4 と 編集後の声）"""
    m = measure(_dec(mp4), _dec(vocals_wav)); m['I'] = lufs_files([mp4]); return m
