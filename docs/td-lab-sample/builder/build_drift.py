"""drift — フィードバック系サンプル（習得フェーズ1本目 / 技法カバレッジ ③A・④A・⑤A）

7層分解の結論:
  ① 出力形式 … TOP合成のみ（3D・粒子を使わない）
  ② 生成源   … Noise TOP を Level TOP で高コントラスト化した「疎な光点」
  ③ 時間駆動 … LFO CHOP で Noise TOP の translate をゆっくり動かす（内部生成＝系統A）
  ④ 変形     … Transform TOP の微小な回転＋拡大（空間系＝系統A）
  ⑤ 反復     … Feedback TOP の自己参照ループ（自己参照＝系統A）
  ⑥ 色       … Script TOP で作った5点ランプを Lookup TOP に通す
  ⑦ 後処理   … Blur によるブルーム加算 ＋ 周辺減光

この技法の要点は「種の移動量」。1フレームあたり1〜2px を超えると軌跡が
点線に切れる。長い尾が欲しいなら種を速く動かすのではなく Decay を上げる。

MCP の run で実行する。何度実行しても同じ結果になる（冒頭で既存を削除）。
"""

# ── パラメータ（preview/preview_drift.py と同名・同値）──────────────────
RES        = 1280
DECAY      = 0.966    # フィードバックの減衰。1.0に近いほど尾が長い
DRIFTROT   = 0.85     # 1フレームあたりの回転角（度）。渦の巻き
DRIFTSCALE = 1.0060   # 1フレームあたりの拡大率。外向きの流れ
SEEDGAIN   = 0.85     # 種ノイズの注入量
SEEDTHRESH = 0.78     # 種の閾値。上げるほど点が疎になる
SPEED      = 0.15     # 種ノイズが流れる速さ
BLOOM      = 0.55     # ブルーム量
VIGNETTE   = 0.35     # 周辺減光

PALETTE = [(0.00, (0x04, 0x06, 0x0a)),
           (0.28, (0x12, 0x3a, 0x5a)),
           (0.55, (0x3f, 0xa9, 0xa6)),
           (0.80, (0xe8, 0xc2, 0x6b)),
           (1.00, (0xfd, 0xf6, 0xe8))]

ROOT = '/project1'
DX, DY = 180, 140          # ノード間隔（CLAUDE.md: X≧160 / Y≧120）


# ── ヘルパ ────────────────────────────────────────────────────────────
def setpar(o, name, value):
    """パラメータを設定する。存在しなければ即座に止める。

    TouchDesigner はパラメータ名を間違えても黙って無視するため、
    「設定したつもりで効いていない」が最も多い事故になる（運用メモ §7-3）。
    ここで落として、docs で正式名を引き直す。
    """
    if not hasattr(o.par, name):
        avail = sorted(p.name for p in o.pars())
        raise AttributeError(
            f"{o.path} ({o.type}) にパラメータ '{name}' が無い。"
            f" docs で {o.type} の正式名を確認すること。候補: {avail[:40]}")
    setattr(o.par, name, value)
    return o


def set_res(o, w, h=None):
    """解像度を指定する。

    TOP の resolutionw/h は Output Resolution が 'Custom Resolution' の時しか
    効かない。先に outputresolution を custom にしないと黙って無視される。
    """
    setpar(o, 'outputresolution', 'custom')
    setpar(o, 'resolutionw', w)
    setpar(o, 'resolutionh', h if h is not None else w)
    return o


def node(parent, kind, name, x, y):
    o = parent.create(kind, name)
    o.nodeX, o.nodeY = x, y
    return o


def chain(*ops):
    """左から右へ 0番入力で直列に繋ぐ。"""
    for src, dst in zip(ops, ops[1:]):
        dst.inputConnectors[0].connect(src)
    return ops[-1]


def fresh(root, name):
    """同名コンテナがあれば消してから作る（冪等化）。"""
    old = root.op(name)
    if old:
        old.destroy()
    return root.create(containerCOMP, name)


# ── ⑥色: 5点ランプを 256x1 の Script TOP で作る ────────────────────────
PALETTE_SCRIPT = '''# drift のカラーパレット（builder/build_drift.py が生成）
import numpy as np

STOPS = {stops}

def onCook(scriptOp):
    n = 256
    xs = np.linspace(0, 1, n, dtype=np.float32)
    out = np.zeros((1, n, 4), dtype=np.float32)
    out[0, :, 3] = 1.0
    for i in range(len(STOPS) - 1):
        a, ca = STOPS[i]
        b, cb = STOPS[i + 1]
        m = (xs >= a) & (xs <= b)
        t = ((xs[m] - a) / (b - a))[:, None]
        out[0, m, :3] = (np.array(ca, np.float32) * (1 - t)
                         + np.array(cb, np.float32) * t) / 255.0
    scriptOp.copyNumpyArray(out)
    return
'''


# ── ビルド本体 ────────────────────────────────────────────────────────
def build():
    root = op(ROOT)

    # 親コンテナ。調整したい値はすべてここのカスタムパラメータに出す。
    # 子は parent().par.Xxx で参照するので、微調整はここだけ触れば済む。
    master = fresh(root, 'DRIFT')
    master.nodeX, master.nodeY = 0, 0
    page = master.appendCustomPage('Drift')
    for label, val, lo, hi in [
        ('Decay',      DECAY,      0.80, 0.999),
        ('Driftrot',   DRIFTROT,  -3.0,  3.0),
        ('Driftscale', DRIFTSCALE, 0.99, 1.02),
        ('Seedgain',   SEEDGAIN,   0.0,  2.0),
        ('Seedthresh', SEEDTHRESH, 0.0,  0.99),
        ('Speed',      SPEED,      0.0,  1.0),
        ('Bloom',      BLOOM,      0.0,  2.0),
        ('Vignette',   VIGNETTE,   0.0,  1.0),
    ]:
        p = page.appendFloat(label)[0]
        p.normMin, p.normMax, p.default, p.val = lo, hi, val, val

    base   = _build_base(master)
    motion = _build_motion(master)
    post   = _build_post(master)

    motion.inputConnectors[0].connect(base)
    post.inputConnectors[0].connect(motion)
    for i, c in enumerate((base, motion, post)):
        c.nodeX, c.nodeY = i * 260, 0
    return master


def _build_base(master):
    """② 生成源 ＋ ③ 時間の駆動。疎な光点を作って流す。"""
    c = fresh(master, 'BASE')
    x = 0

    # ③ LFO で translate を動かす。1フレーム1〜2px を超えないこと。
    lfo = node(c, lfoCHOP, 'lfo_drift', x, DY)
    setpar(lfo, 'frequency', 0.20)
    setpar(lfo, 'amplitude', 0.03)

    noise = node(c, noiseTOP, 'noise_seed', x, 0); x += DX
    set_res(noise, RES)
    setpar(noise, 'mono', True)          # Monochrome の正式名は mono
    setpar(noise, 'period', 26.0)
    # 横方向はゆっくり流し、縦は LFO で揺らす
    noise.par.t1.expr = "absTime.seconds * parent.DRIFT.par.Speed * 0.25"
    noise.par.t2.expr = "op('lfo_drift')['chan1']"

    # 閾値で疎な点にする（種が密だと尾が潰れて面になる）
    lvl = node(c, levelTOP, 'level_seed', x, 0); x += DX
    lvl.par.blacklevel.expr = 'parent.DRIFT.par.Seedthresh'
    setpar(lvl, 'gamma1', 2.0)
    lvl.par.opacity.expr = 'parent.DRIFT.par.Seedgain'

    out = node(c, outTOP, 'out_seed', x, 0)
    chain(noise, lvl, out)
    return c


def _build_motion(master):
    """④ 変形 ＋ ⑤ 反復。ここがこの作品の心臓部。"""
    c = fresh(master, 'MOTION')
    x = 0

    src = node(c, inTOP, 'in_seed', x, 0); x += DX

    # 種と「1フレーム前を変形したもの」を加算合成
    mix = node(c, compositeTOP, 'comp_mix', x, 0); x += DX
    setpar(mix, 'operand', 'add')

    # 減衰。ここが尾の長さを決める
    decay = node(c, levelTOP, 'level_decay', x, 0); x += DX
    decay.par.opacity.expr = 'parent.DRIFT.par.Decay'

    out = node(c, outTOP, 'out_motion', x, 0)

    # ⑤ 自己参照ループ。戻り線は1段下の行に落として引く（CLAUDE.md）
    fb = node(c, feedbackTOP, 'fb_loop', x - DX, DY)
    setpar(fb, 'top', decay)              # 前フレームの level_decay を拾う

    # ④ 微小な回転＋拡大。これが渦と外向きの流れを作る
    xf = node(c, transformTOP, 'xform_drift', x - DX * 2, DY)
    # 回転は「1フレームあたりの角度」＝定数。absTime.frame を掛けてはいけない。
    # 蓄積はフィードバックループ側がやっているので、ここで積むと二重に回る。
    xf.par.rotate.expr = 'parent.DRIFT.par.Driftrot'
    xf.par.s1.expr = 'parent.DRIFT.par.Driftscale'   # Scale の正式名は s（s1/s2）
    xf.par.s2.expr = 'parent.DRIFT.par.Driftscale'
    setpar(xf, 'extend', 'zero')          # 外周は黒で埋める（繰り返さない）

    chain(src, mix, decay, out)
    chain(fb, xf)
    mix.inputConnectors[1].connect(xf)    # 戻り線を合成の2番目へ
    return c


def _build_post(master):
    """⑥ 色 ＋ ⑦ 後処理。"""
    c = fresh(master, 'POST')
    x = 0

    src = node(c, inTOP, 'in_motion', x, 0); x += DX

    # ⑥ 輝度をパレットに通す。Lookup TOP は 入力0=索引 / 入力1=パレット
    pal = node(c, scriptTOP, 'ramp_palette', x, DY * 2)
    dat = node(c, textDAT, 'palette_src', x, DY * 3)
    dat.text = PALETTE_SCRIPT.format(stops=repr(PALETTE))
    setpar(pal, 'callbacks', dat)   # 解像度は copyNumpyArray の配列形状が決める

    lut = node(c, lookupTOP, 'lut_color', x, 0); x += DX

    # ⑦ ブルーム: 明るい所だけ抜いて → ぼかして → 元に加算
    cut = node(c, levelTOP, 'bloom_cut', x, DY); x += 0
    setpar(cut, 'blacklevel', 0.55)

    blur = node(c, blurTOP, 'bloom_blur', x, DY)
    setpar(blur, 'size', 24)

    add = node(c, compositeTOP, 'post_bloom', x, 0); x += DX
    setpar(add, 'operand', 'add')

    # ⑦ 周辺減光
    vig = node(c, rampTOP, 'vig_ramp', x, DY)
    setpar(vig, 'type', 'radial')
    set_res(vig, RES)

    mul = node(c, compositeTOP, 'post_vignette', x, 0); x += DX
    setpar(mul, 'operand', 'multiply')

    out = node(c, outTOP, 'out_final', x, 0)

    chain(src, lut)
    lut.inputConnectors[1].connect(pal)
    chain(lut, cut, blur)
    chain(lut, add)
    add.inputConnectors[1].connect(blur)
    chain(add, mul)
    mul.inputConnectors[1].connect(vig)
    chain(mul, out)
    return c


if __name__ == '__main__':
    m = build()
    print(f'built {m.path} — 出力は {m.path}/POST/out_final')
