"""drift — TouchDesigner ネットワークの見た目を、TDなしで先に確認するためのプレビュー。

builder/build_drift.py が組む7層と同じ演算を numpy で再現する。
パラメータ名は builder 側のカスタムパラメータと 1:1 で対応させてあるので、
ここで数値を詰めてから TD に持っていける。

出力: 同フォルダに drift_preview.png / drift_preview.gif
"""

import numpy as np
from PIL import Image

# ── パラメータ（builder/build_drift.py のカスタムパラメータと同名・同値）────
RES        = 640      # 解像度（TD側は Resolution）
DECAY      = 0.966    # Decay      : フィードバックの減衰。1.0に近いほど尾が長い
DRIFTROT   = 0.85     # Driftrot   : 1フレームあたりの回転角（度）。渦の巻き
DRIFTSCALE = 1.0060   # Driftscale : 1フレームあたりの拡大率。外向きの流れ
SEEDGAIN   = 0.85     # Seedgain   : 種ノイズの注入量
SEEDTHRESH = 0.78     # Seedthresh : 種の閾値。上げるほど点が疎になる
SPEED      = 0.15     # Speed      : 種ノイズが流れる速さ
BLOOM      = 0.55     # Bloom      : 後処理のにじみ量
VIGNETTE   = 0.35     # Vignette   : 周辺減光
FRAMES     = 48
FPS        = 24
SEED       = 7

# ── ②生成源: 帯域制限ノイズ（TD の Noise TOP 相当）────────────────────
def band_noise(size, scale, rng):
    """白色ノイズをFFTで帯域制限して、Noise TOP に近い有機的な斑を作る。"""
    w = rng.normal(size=(size, size))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]
    r = np.sqrt(fx**2 + fy**2) + 1e-9
    f = np.fft.fft2(w) * np.exp(-(r * size / scale) ** 2)
    n = np.real(np.fft.ifft2(f))
    return (n - n.min()) / (np.ptp(n) + 1e-9)

rng = np.random.default_rng(SEED)
NOISE = band_noise(RES, 26.0, rng)          # パンさせて使う種のもと

def sample_noise(ox, oy):
    """Noise TOP の translate 相当。ラップして無限にパンできる。"""
    return np.roll(np.roll(NOISE, int(oy) % RES, axis=0), int(ox) % RES, axis=1)

# ── ④変形: 回転＋スケール（TD の Transform TOP 相当）──────────────────
yy, xx = np.mgrid[0:RES, 0:RES].astype(np.float32)
cx = cy = (RES - 1) / 2.0

def warp(img, deg, scale):
    """中心まわりに回転・拡大してバイリニアで再サンプル。"""
    t = np.deg2rad(deg)
    ct, st = np.cos(t) / scale, np.sin(t) / scale
    dx, dy = xx - cx, yy - cy
    sx = ct * dx - st * dy + cx
    sy = st * dx + ct * dy + cy
    x0 = np.floor(sx).astype(np.int32); y0 = np.floor(sy).astype(np.int32)
    fx = (sx - x0)[..., None]; fy = (sy - y0)[..., None]
    x1, y1 = x0 + 1, y0 + 1
    ok = (x0 >= 0) & (y0 >= 0) & (x1 < RES) & (y1 < RES)
    x0c, y0c = np.clip(x0, 0, RES - 1), np.clip(y0, 0, RES - 1)
    x1c, y1c = np.clip(x1, 0, RES - 1), np.clip(y1, 0, RES - 1)
    top = img[y0c, x0c] * (1 - fx) + img[y0c, x1c] * fx
    bot = img[y1c, x0c] * (1 - fx) + img[y1c, x1c] * fx
    return np.where(ok[..., None], top * (1 - fy) + bot * fy, 0.0)

# ── ⑦後処理: ブラー（Blur TOP 相当。箱ブラー3回でガウス近似）───────────
def box_blur(img, r):
    """cumsum による箱ブラー。奇数幅 k=2r+1 の移動平均を縦横に1回ずつ。"""
    k = 2 * r + 1
    pad = np.pad(img, ((r + 1, r), (0, 0), (0, 0)), mode="edge")
    c = np.cumsum(pad, axis=0)
    img = (c[k:] - c[:-k]) / k
    pad = np.pad(img, ((0, 0), (r + 1, r), (0, 0)), mode="edge")
    c = np.cumsum(pad, axis=1)
    return (c[:, k:] - c[:, :-k]) / k


def blur(img, r, n=3):
    for _ in range(n):
        img = box_blur(img, r)
    return img

# ── ⑥色: ランプ＋Lookup TOP 相当 ──────────────────────────────────────
STOPS = [(0.00, (0x04, 0x06, 0x0a)),
         (0.28, (0x12, 0x3a, 0x5a)),
         (0.55, (0x3f, 0xa9, 0xa6)),
         (0.80, (0xe8, 0xc2, 0x6b)),
         (1.00, (0xfd, 0xf6, 0xe8))]

def build_lut(n=256):
    lut = np.zeros((n, 3), np.float32)
    xs = np.linspace(0, 1, n)
    for i in range(len(STOPS) - 1):
        a, ca = STOPS[i]; b, cb = STOPS[i + 1]
        m = (xs >= a) & (xs <= b)
        t = ((xs[m] - a) / (b - a))[:, None]
        lut[m] = (np.array(ca) * (1 - t) + np.array(cb) * t) / 255.0
    return lut

LUT = build_lut()

def lookup(lum):
    return LUT[np.clip(lum * 255, 0, 255).astype(np.int32)]

# ── 周辺減光 ──────────────────────────────────────────────────────────
rad = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
VIG = np.clip(1.0 - VIGNETTE * np.clip(rad - 0.35, 0, None) ** 1.6, 0, 1)[..., None]

# ── メインループ（③時間の駆動 → ④変形 → ⑤反復 → ⑥色 → ⑦後処理）─────
state = np.zeros((RES, RES, 3), np.float32)
frames = []

for f in range(FRAMES + 40):                       # 先頭40フレームは助走（尾を育てる）
    t = f / FPS

    # ③ 時間の駆動: LFO で種ノイズをパンさせる
    # 種は毎フレーム 1〜2px しか動かさない。速く動かすと軌跡が点線に切れる
    ox = t * SPEED * RES * 0.25 + np.sin(t * 0.20 * 2 * np.pi) * RES * 0.03
    oy = np.cos(t * 0.14 * 2 * np.pi) * RES * 0.03
    n = sample_noise(ox, oy)

    # 閾値で疎な点にする（Level TOP の gamma / threshold 相当）
    seed = np.clip((n - SEEDTHRESH) / (1 - SEEDTHRESH), 0, 1) ** 2.0
    seed = seed[..., None] * np.array([1.0, 0.82, 0.55], np.float32) * SEEDGAIN

    # ⑤ 反復 + ④ 変形: 前フレームを回転・拡大して減衰させ、種を足す
    state = warp(state, DRIFTROT, DRIFTSCALE) * DECAY + seed
    state = np.clip(state, 0, 4)

    if f < 40:
        continue

    # ⑥ 色: 輝度を LUT に通す
    lum = np.clip(state @ np.array([0.30, 0.59, 0.11], np.float32) * 1.15, 0, 1)
    img = lookup(lum ** 0.85)

    # ⑦ 後処理: ブルーム → 周辺減光
    bright = np.clip(img - 0.55, 0, None)
    img = np.clip(img + blur(bright, 6) * BLOOM * 6.0, 0, 1)
    img = img * VIG

    frames.append(Image.fromarray((img ** (1 / 1.05) * 255).astype(np.uint8)))

frames[len(frames) // 2].save("drift_preview.png")
frames[0].save("drift_preview.gif", save_all=True,
               append_images=frames[1:], duration=int(1000 / FPS), loop=0, optimize=True)
print(f"frames={len(frames)}  png/gif -> capture/")
