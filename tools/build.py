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
save('attack', cc[9:29], 30, False)
save('idle', cc[29:40] + cc[38:29:-1], 10, True)
save('cast', ex_cells[9:17], 12, False)
save('crouch', ex_cells[0:6], 14, False)
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
save('shadow_attack', shade(cc[9:29]), 26, False)

# --- jump sheet
a = load('source/jump.png'); m = mask_of(a)
m[:20] = 0; m[338:] = 0; m[:100, :760] = 0; m[:, :15] = 0; m[:, 2155:] = 0
jump = blobs(a, m)
for f in jump:
    bm = body_metrics(f['m']); f['ground'] = (f['y0'] + bm['bot']) >= 328
s_j = TARGET / body_metrics(jump[0]['m'])['h']
jump = jump[:23]
save('jump', place(jump, W, H, s_j, CX, FY, mode='auto', stand_h=TARGET), 24, False)
print('jump', len(jump), [f['ground'] for f in jump])
json.dump(dict(cell=[W, H], anchor=[CX, FY], anims=anims), open(f'{OUT}/anims.json', 'w'), indent=1)

# HUD portrait and backgrounds
from PIL import Image as _I
_I.open('source/guide_hd.png').convert('RGB').crop((14, 20, 196, 202)).resize((128, 128), _I.LANCZOS).save(f'{OUT}/portrait.png')
_I.open('source/art_castle.png').convert('RGB').save(f'{OUT}/bg_castle.jpg', quality=88)
_I.open('source/art_priestess.png').convert('RGB').save(f'{OUT}/bg_title.jpg', quality=88)
