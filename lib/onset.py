# 言葉の始まりのコマ（vsl-yt-1・10/18 依頼主の絶対ルール「テロップと動きは言葉にフレーム単位で合わせる」）
#   字ごとの時刻（work/timing_fa.json：声に貼り直した字の時刻／無ければ work/timing.json：Whisper の単語時刻を台本の字に合わせたもの）で言葉の頭を取り、
#   そこから前後0.10秒の中で声の大きさが一番立ち上がった10msを探して、立ち上がりが6dB以上ならそこへ寄せる。
#   返すのは「コマ番号 / FPS」ちょうどの秒（秒の丸めで置かない）。置いた所は EV に残して検算に使う
import os, json, subprocess, re
import numpy as np
FPS = 30000 / 1001
class Onset:
    def __init__(self, proj):
        fa = os.path.join(proj, 'work', 'timing_fa.json')   # 声に貼り直した字の時刻（align/kotoba_align.py）があればそちらを使う
        self.fa = os.path.exists(fa)
        J = json.load(open(fa if self.fa else os.path.join(proj, 'work', 'timing.json')))
        self.ref = J['ref']; self.T = J['starts']; self.L0 = {int(k): v for k, v in J['line0'].items()}
        self.KIND = J.get('kind') or ['whisper'] * len(self.ref); self.WS = J.get('starts_whisper') or self.T
        self.N = lambda s: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】%％]', '', s)
        sr = 16000; x = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(proj, 'work', 'vocals.wav'), '-f', 's16le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True).stdout
        x = np.frombuffer(x, np.int16).astype(np.float32) / 32768; n = len(x) // 160
        self.db = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-9)   # 10ms ごと
        self.EV = []
    def raw(self, piece, n):
        a = self.L0[n]; b = min((v for k, v in self.L0.items() if v > a), default=len(self.ref))
        p = self.N(piece); k = self.ref[a:b].find(p)
        if k < 0: raise KeyError('その行に無い言葉: %s（%d行目）' % (piece, n))
        self._i = a + k
        return self.T[a + k]
    def refine(self, t):
        if self.fa: return t   # 声に貼り直した時刻は寄せ済み（間のあとの頭は声の大きさで寄せてある）
        i = int(t * 100); lo, hi = max(1, i - 10), min(len(self.db) - 1, i + 10)
        d = np.diff(self.db[lo - 1:hi + 1]); j = int(np.argmax(d))
        return (lo + j) / 100.0 if d[j] >= 6 else t
    def at(self, piece, n, what=''):
        t0 = self.raw(piece, n); t1 = self.refine(t0); fr = int(round(t1 * FPS))
        self.EV.append({'what': what or piece, 'line': n, 'word': piece, 'whisper': round(self.WS[self._i], 3), 'voice': round(t1, 3), 'how': self.KIND[self._i], 'frame': fr})
        return fr / FPS
    def line(self, n, what=''):
        return self.at(self.ref[self.L0[n]:self.L0[n] + 2], n, what or 'L%d' % n)
