# Rebuilds game/assets from the sprite sheets in source/.  Run from the repo root:
#   pip install pillow numpy scipy && python3 tools/build.py
import sys, json, os; sys.path.insert(0, os.path.dirname(__file__))
from lib import *
OUT = 'game/assets'; os.makedirs(OUT, exist_ok=True)
PREV = os.environ.get('PREVIEW_DIR')
W, H, CX, FY = 288, 176, 144, 170   # cell; character centre x; foot line
TARGET = 128                          # standing height in px (horns to heels)
anims = {}

def save(name, cells, fps, loop):
    strip(cells, f'{OUT}/{name}.png')
    anims[name] = dict(frames=len(cells), fps=fps, loop=loop)
    if PREV: preview(cells, f'{PREV}/prev_{name}.png', cols=min(10, len(cells)))

def cut_row(a, m, y0, y1, x0, x1, n=None, pitch=None, keep='near'):
    cs = auto_cuts(m, y0, y1, x0, x1, n, pitch_hint=pitch)
    fr, _ = extract(a, m, y0, y1, x0, x1, len(cs)-1, keep=keep, cut=cs)
    return [f for f in fr if f is not None]

def sc(frames):  # scale so median body height == TARGET
    return TARGET / np.median([body_metrics(f['m'])['h'] for f in frames])

# --- walk / run / extras sheet
a = load('source/walk_run_extra.png'); m = mask_of(a); m[:, :140] = False
walk = cut_row(a, m, 10, 236, 140, 2172)
run = cut_row(a, m, 262, 474, 140, 2172, pitch=91)
s_walk = sc(walk)
save('walk', place(walk, W, H, s_walk, CX, FY), 14, True)
save('run', place(run, W, H, sc(run), CX, FY), 22, True)
m[486:700, 864:869] = False; m[486:700, 1160:1168] = False
extra = cut_row(a, m, 486, 700, 140, 2172, pitch=None, keep='all')[1:]
print('extra', len(extra), [f['cell'] for f in extra])
ex_cells = place(extra, W, H, s_walk, CX, FY)

# --- combo sheet
a = load('source/combo_attack.png'); m = mask_of(a)
combo = []
for y0, y1 in [(58, 212), (244, 386), (418, 542), (575, 694)]:
    r = cut_row(a, m, y0, y1, 200, 2172, n=10, keep='all')
    combo += r
print('combo', len(combo))
s_c = TARGET / body_metrics(combo[0]['m'])['h']
cc = place(combo, W, H, s_c, CX, FY)
# (superseded by v2 sheets) save('attack', cc[9:29], 30, False)
# (superseded by idle2) save('idle', cc[29:40] + cc[38:29:-1], 10, True)
# (superseded by v2 sheets) save('cast', ex_cells[9:17], 12, False)
# (superseded by v2 sheets) save('crouch', ex_cells[0:6], 14, False)
# shadow enemy: tinted walk + attack
def shade(cells):
    out = []
    for c in cells:
        x = np.asarray(c).astype(np.float32)
        l = x[..., :3].mean(2, keepdims=True) / 255
        tint = np.array([62, 36, 112], np.float32) * (0.18 + l * 1.05) + np.array([6, 0, 16])
        red = ((x[..., 0] > 120) & (x[..., 0] > x[..., 1] * 2.2))[..., None]
        accent = np.array([130, 22, 78], np.float32) * (0.45 + l * 0.7)
        tint = np.where(red, accent, tint)
        out.append(Image.fromarray(np.dstack([np.clip(tint, 0, 255), x[..., 3:]]).astype(np.uint8)))
    return out
save('shadow_walk', shade(place(walk, W, H, s_walk, CX, FY)), 10, True)
# (superseded by v2 sheets) save('shadow_attack', shade(cc[9:29]), 26, False)

# --- jump sheet
a = load('source/jump.png'); m = mask_of(a)
m[:20] = 0; m[338:] = 0; m[:100, :760] = 0; m[:, :15] = 0; m[:, 2155:] = 0
jump = blobs(a, m)
for f in jump:
    bm = body_metrics(f['m']); f['ground'] = (f['y0'] + bm['bot']) >= 328
s_j = TARGET / body_metrics(jump[0]['m'])['h']
jump = jump[:23]
# (superseded by jump2) save('jump', place(jump, W, H, s_j, CX, FY, mode='auto', stand_h=TARGET), 24, False)
print('jump', len(jump), [f['ground'] for f in jump])
json.dump(dict(cell=[W, H], anchor=[CX, FY], anims=anims), open(f'{OUT}/anims.json', 'w'), indent=1)

# HUD portrait and backgrounds
from PIL import Image as _I
_I.open('source/guide_hd.png').convert('RGB').crop((14, 20, 196, 202)).resize((128, 128), _I.LANCZOS).save(f'{OUT}/portrait.png')
_I.open('source/art_castle.png').convert('RGB').save(f'{OUT}/bg_castle.jpg', quality=88)
_I.open('source/art_priestess.png').convert('RGB').save(f'{OUT}/bg_title.jpg', quality=88)

# ---------------------------------------------------------------- v2 sheets (cleaner, one action per sheet)
def ground_flag(bs, lines):
    for b in bs:
        b['ground'] = (b['y0'] + body_metrics(b['m'])['bot']) >= lines[b['row']] - 6
    return bs

a = load('source/v2_crouch.png'); m = mask_of(a, 55)
cr = blobs_rows(a, m, 543, minsize=3000)
s2 = TARGET / body_metrics(cr[0]['m'])['h']
save('squat', place(cr, W, H, s2, CX, FY), 20, False)

a = load('source/v2_roll.png'); m = mask_of(a, 55)
ro = blobs_rows(a, m, 543, minsize=3000)
save('roll', place(ro, W, H, TARGET / body_metrics(ro[0]['m'])['h'], CX, FY), 24, False)

a = load('source/v2_jump.png'); m = mask_of(a, 55)
ju = ground_flag(blobs_rows(a, m, 500, minsize=3000), [437, 936])
print('jump2 ground', [bool(b['ground']) for b in ju])
sj = TARGET / body_metrics(ju[0]['m'])['h']
save('jump2', place(ju, W, H, sj, CX, FY, mode='auto', stand_h=TARGET), 24, False)

PX = [(40, 487), (535, 981), (1029, 1475), (1522, 1970)]
PY = [(223, 668), (762, 1206), (1300, 1746)]
for name, f in [('combo12', 'v2_combo12'), ('ritual', 'v2_ritual12')]:
    a = load(f'source/{f}.png')
    fr = panels(a, PX, PY)
    sc12 = TARGET / body_metrics(fr[0]['m'])['h']
    cells = place_fixed(fr, W, H, sc12, CX, FY)
    save(name, cells, 14, False)
    if name == 'combo12':
        save('shadow_combo', shade(cells), 14, False)
json.dump(dict(cell=[W, H], anchor=[CX, FY], anims=anims), open(f'{OUT}/anims.json', 'w'), indent=1)

# ---------------------------------------------------------------- AFK (long idle), 6 rows of a labelled sheet
def light_cx(m, rgb):
    """horizontal body centre from light pixels (hair, skin, white robe) - ignores the red magic glow"""
    ys, xs = np.nonzero(m)
    top, bot = ys.min(), ys.max(); h = bot - top
    lm = m & (rgb[..., 1] > 120) & (rgb[..., 2] > 110)
    yy, xx = np.nonzero(lm)
    sel = (yy > top + h*0.2) & (yy < top + h*0.8)
    return float(np.median(xx[sel])) if sel.any() else xs.mean()

a = load('source/v2_afk.png'); m = mask_of(a, 55); m[:, :470] = False; m[:, 1762:] = False   # label column, right border
afk_cells = []
for (y0, y1), n in zip([(70, 178), (196, 301), (320, 425), (444, 551), (568, 669), (690, 777)], [8, 8, 8, 11, 8, 4]):
    cs = auto_cuts(m, y0, y1, 470, 1774, n)
    fr, _ = extract(a, m, y0, y1, 470, 1774, n, keep='all', minarea=12, cut=cs)
    base = body_metrics(fr[0]['m'])          # the row shares one ground line: use its first, effect-free frame
    for f in fr:
        rgb = a[y0:y1, f['cell'][0]:f['cell'][1]]
        f['img'] = soft_rgba(rgb, f['m'])
        sc_ = TARGET / base['h']
        img = Image.fromarray(f['img']); img = img.resize((max(1, round(img.width*sc_)), max(1, round(img.height*sc_))), Image.LANCZOS)
        ox = int(round(CX - light_cx(f['m'], rgb)*sc_)); oy = int(round(FY - base['bot']*sc_))
        cell = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        cell.alpha_composite(img, (max(ox, 0), max(oy, 0)), (max(-ox, 0), max(-oy, 0)))
        afk_cells.append(cell)
# (superseded by afk2) save('afk', afk_cells, 6, False)
json.dump(dict(cell=[W, H], anchor=[CX, FY], anims=anims), open(f'{OUT}/anims.json', 'w'), indent=1)

# ---------------------------------------------------------------- v3: AFK yawn + AFK magic (4x2 grids), new idle
def grid_frames(path, baselines, cols=4, rows=2):
    a = load(path); Hh, Ww = a.shape[:2]; ch, cw = Hh // rows, Ww // cols
    out = []
    for r in range(rows):
        for c in range(cols):
            y0, x0 = r*ch, c*cw
            rgb = a[y0:y0+ch, x0:x0+cw]; m = mask_of(rgb, 55)
            lab, k = nd.label(m, structure=np.ones((3, 3))); sz = nd.sum(m, lab, range(1, k+1))
            m = np.isin(lab, [i+1 for i in range(k) if sz[i] >= 12])
            out.append(dict(img=soft_rgba(rgb, m), m=m, rgb=rgb, bot=baselines[r] - y0))
    return out

def place_grid(frames, scale):
    cells = []
    for f in frames:
        img = Image.fromarray(f['img']); img = img.resize((round(img.width*scale), round(img.height*scale)), Image.LANCZOS)
        ox = int(round(CX - light_cx(f['m'], f['rgb'])*scale)); oy = int(round(FY - f['bot']*scale))
        cell = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        cell.alpha_composite(img, (max(ox, 0), max(oy, 0)), (max(-ox, 0), max(-oy, 0)))
        cells.append(cell)
    return cells

yawn = grid_frames('source/v3_afk_yawn.png', [427, 900])
magic = grid_frames('source/v3_afk_magic.png', [420, 885])
s3 = TARGET / body_metrics(yawn[0]['m'])['h']
yc, mc = place_grid(yawn, s3), place_grid(magic, s3)
save('afk2', yc + mc, 3, False)
save('idle2', [yc[0], yc[3], yc[4], yc[7]], 2, True)
json.dump(dict(cell=[W, H], anchor=[CX, FY], anims=anims), open(f'{OUT}/anims.json', 'w'), indent=1)

# ---------------------------------------------------------------- unify colour: match every strip to the idle palette
# Each sheet was generated separately, so brightness and saturation drift between them.  Per-channel histogram
# matching of the character pixels against idle2 makes the animations read as one sprite.
def channel_maps(src, ref):
    maps = []
    for c in range(3):
        s_vals, s_cnt = np.unique(src[:, c], return_counts=True)
        r_vals, r_cnt = np.unique(ref[:, c], return_counts=True)
        s_cdf = np.cumsum(s_cnt) / s_cnt.sum(); r_cdf = np.cumsum(r_cnt) / r_cnt.sum()
        lut = np.interp(np.arange(256), s_vals, np.interp(s_cdf, r_cdf, r_vals))
        maps.append(lut)
    return maps

def body_px(a): return a[a[..., 3] > 200][:, :3].astype(int)
ref = np.asarray(Image.open(f'{OUT}/idle2.png'))
ref_px = body_px(ref)
for name in ['walk', 'run', 'jump2', 'squat', 'roll', 'combo12', 'ritual', 'afk2']:
    a = np.asarray(Image.open(f'{OUT}/{name}.png')).copy()
    maps = channel_maps(body_px(a), ref_px)
    vis = a[..., 3] > 0
    for c in range(3):
        a[..., c][vis] = np.clip(maps[c][a[..., c][vis]], 0, 255)
    Image.fromarray(a).save(f'{OUT}/{name}.png')
    if name == 'combo12':
        cells = [Image.fromarray(a[:, i*W:(i+1)*W]) for i in range(a.shape[1] // W)]
        strip(shade(cells), f'{OUT}/shadow_combo.png')
