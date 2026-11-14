from PIL import Image; import numpy as np
from scipy import ndimage as nd

def load(f): return np.asarray(Image.open(f).convert('RGB')).astype(np.int32)

def mask_of(a, t=50):
    m = a.max(2) > t
    m = nd.binary_opening(m, iterations=1)
    # fill small holes
    holes = nd.binary_fill_holes(m) & ~m
    lab, n = nd.label(holes)
    if n:
        sizes = nd.sum(holes, lab, range(1, n+1))
        small = np.isin(lab, np.where(sizes < 500)[0] + 1)
        m = m | small
    return m

def cuts(prof, x0, x1, n, win=0.35):
    w = (x1 - x0) / n
    ps = np.convolve(prof, np.ones(5)/5, mode='same')
    res = [x0]
    for i in range(1, n):
        e = x0 + i*w
        lo, hi = int(e - w*win), int(e + w*win)
        res.append(lo + int(np.argmin(ps[lo:hi])))
    res.append(x1)
    return res

def extract(a, m, y0, y1, x0, x1, n, keep='near', minarea=40, cut=None):
    sub = m[y0:y1]
    prof = sub.sum(0)
    cs = cut or cuts(prof, x0, x1, n)
    out = []
    for i in range(n):
        cx0, cx1 = cs[i], cs[i+1]
        mm = sub[:, cx0:cx1].copy()
        lab, k = nd.label(mm, structure=np.ones((3,3)))
        if k == 0:
            out.append(None); continue
        sizes = nd.sum(mm, lab, range(1, k+1))
        big = int(np.argmax(sizes)) + 1
        if keep == 'near':
            core = nd.binary_dilation(lab == big, iterations=10)
            ids = set(np.unique(lab[core])) - {0}
            ids = [j for j in ids if sizes[j-1] >= minarea or j == big]
        else:
            ids = [j+1 for j in range(k) if sizes[j] >= minarea]
        km = np.isin(lab, ids)
        rgb = a[y0:y1, cx0:cx1]
        rgba = np.dstack([rgb, km*255]).astype(np.uint8)
        out.append(dict(img=rgba, cell=(cx0, cx1), m=km))
    return out, cs

def normalize(frames, W, H, align='centroid', scale=1.0, pad_bottom=4):
    """place frames in WxH cells; feet at bottom; returns list of PIL images"""
    res = []
    # global bottom: use each frame's own bottom
    for fr in frames:
        m = fr['m']
        ys, xs = np.nonzero(m)
        bot = ys.max()
        if align == 'centroid':
            # body centroid in middle band of rows
            top = ys.min(); h = bot - top
            sel = (ys > top + h*0.25) & (ys < top + h*0.8)
            cx = xs[sel].mean()
        else:  # cell centre
            cx = m.shape[1] / 2
        img = Image.fromarray(fr['img'])
        if scale != 1.0:
            img = img.resize((max(1,int(img.width*scale)), max(1,int(img.height*scale))), Image.LANCZOS)
            cx *= scale; bot *= scale
        cell = Image.new('RGBA', (W, H), (0,0,0,0))
        ox = int(round(W/2 - cx)); oy = int(round(H - pad_bottom - bot))
        cell.alpha_composite(img, (max(ox,0), max(oy,0)), (max(-ox,0), max(-oy,0)))
        res.append(cell)
    return res

def strip(cells, path):
    W, H = cells[0].size
    s = Image.new('RGBA', (W*len(cells), H), (0,0,0,0))
    for i, c in enumerate(cells): s.alpha_composite(c, (i*W, 0))
    s.save(path)
    return s

def preview(cells, path, cols=12, bg=(60,70,90,255)):
    W, H = cells[0].size
    rows = (len(cells)+cols-1)//cols
    s = Image.new('RGBA', (W*cols, H*rows), bg)
    for i, c in enumerate(cells):
        s.alpha_composite(c, ((i%cols)*W, (i//cols)*H))
    s.save(path)

def auto_cuts(m, y0, y1, x0, x1, n=None, thr=2, mingap=2, minw=25, pitch_hint=None):
    prof = m[y0:y1, x0:x1].sum(0)
    on = prof > thr
    segs = []; i = 0; W = len(on)
    while i < W:
        if on[i]:
            j = i
            while j < W and on[j]: j += 1
            segs.append([i, j]); i = j
        else: i += 1
    # merge tiny gaps
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < mingap: merged[-1][1] = s[1]
        else: merged.append(s)
    ps = np.convolve(prof, np.ones(7)/7, mode='same')
    mass = [prof[s[0]:s[1]].sum() for s in merged]
    med = np.median(mass)
    merged = [s for s, ms in zip(merged, mass) if ms > 0.12*med]
    # split widest until count == n
    if n is None:
        # split segments much wider than the typical frame pitch
        pitch = pitch_hint or np.median([s[1]-s[0] for s in merged])
        out = []
        for a_, b_ in merged:
            k = int(round((b_-a_)/pitch))
            if k <= 1: out.append([a_, b_]); continue
            w = (b_-a_)/k; last = a_
            for q in range(1, k):
                e = a_ + q*w; lo, hi = int(e-w*0.3), int(e+w*0.3)
                c = lo + int(np.argmin(ps[lo:hi])); out.append([last, c]); last = c
            out.append([last, b_])
        merged = out; n = len(merged)
    while len(merged) < n:
        k = max(range(len(merged)), key=lambda q: merged[q][1]-merged[q][0])
        a_, b_ = merged[k]; w = b_ - a_
        lo, hi = a_ + w//4, b_ - w//4
        c = lo + int(np.argmin(ps[lo:hi]))
        merged[k:k+1] = [[a_, c], [c, b_]]
    while len(merged) > n:  # merge smallest into neighbour
        k = min(range(len(merged)), key=lambda q: merged[q][1]-merged[q][0])
        if k == 0: merged[0:2] = [[merged[0][0], merged[1][1]]]
        elif k == len(merged)-1 or (merged[k][0]-merged[k-1][1] < merged[k+1][0]-merged[k][1]):
            merged[k-1:k+1] = [[merged[k-1][0], merged[k][1]]]
        else: merged[k:k+2] = [[merged[k][0], merged[k+1][1]]]
    # cut points: midpoints of gaps
    cs = [x0 + max(0, merged[0][0]-3)]
    for p, q in zip(merged, merged[1:]):
        cs.append(x0 + (p[1] + q[0])//2)
    cs.append(x0 + min(x1-x0, merged[-1][1]+3))
    return cs

def blobs(a, m, minsize=1500, near=12, minarea=25):
    lab, k = nd.label(m, structure=np.ones((3,3)))
    sz = nd.sum(m, lab, range(1, k+1)); objs = nd.find_objects(lab)
    bigs = sorted([i for i in range(k) if sz[i] > minsize], key=lambda i: objs[i][1].start)
    out = []
    for i in bigs:
        ys, xs = objs[i]
        y0, y1 = max(0, ys.start-near), ys.stop+near
        x0, x1 = max(0, xs.start-near), xs.stop+near
        sl = lab[y0:y1, x0:x1]
        core = nd.binary_dilation(sl == i+1, iterations=near)
        ids = [j for j in set(np.unique(sl[core])) - {0} if j == i+1 or (sz[j-1] >= minarea and j-1 not in bigs)]
        km = np.isin(sl, ids)
        out.append(dict(img=np.dstack([a[y0:y1, x0:x1], km*255]).astype(np.uint8), m=km, y0=y0, y1=y1, x0=x0))
    return out

def body_metrics(m):
    lab, k = nd.label(m, structure=np.ones((3,3)))
    sz = nd.sum(m, lab, range(1, k+1)); big = lab == (int(np.argmax(sz))+1)
    ys, xs = np.nonzero(big)
    top, bot = ys.min(), ys.max(); h = bot - top
    sel = (ys > top + h*0.2) & (ys < top + h*0.75)
    return dict(top=top, bot=bot, cx=xs[sel].mean(), h=h)

def place(frames, W, H, scale, cx_at, foot_y, mode='bottom', stand_h=None):
    res = []
    for fr in frames:
        bm = body_metrics(fr['m'])
        img = Image.fromarray(fr['img'])
        img = img.resize((max(1,round(img.width*scale)), max(1,round(img.height*scale))), Image.LANCZOS)
        cx = bm['cx']*scale
        if mode == 'bottom' or (mode == 'auto' and fr.get('ground', True)):
            oy = foot_y - bm['bot']*scale
        else:
            oy = foot_y - stand_h - bm['top']*scale
        ox = cx_at - cx
        cell = Image.new('RGBA', (W, H), (0,0,0,0))
        ox, oy = int(round(ox)), int(round(oy))
        cell.alpha_composite(img, (max(ox,0), max(oy,0)), (max(-ox,0), max(-oy,0)))
        res.append(cell)
    return res

def soft_rgba(a, m, bg_level=30, full=70):
    """binary character mask plus soft alpha for red glow (magic arcs) outside it"""
    mx = a.max(2).astype(np.float32)
    soft = np.clip((mx - bg_level) / (full - bg_level), 0, 1)
    red = (a[..., 0] > a[..., 1] * 1.5) & (a[..., 0] > a[..., 2] * 1.2)
    alpha = np.where(m, 1.0, np.where(red, soft, 0))
    return np.dstack([a, alpha * 255]).astype(np.uint8)

def panels(a, xs, ys, inset=8, t=55):
    """cut a labelled grid of dark panels -> list of dicts with img/m in panel coordinates"""
    out = []
    for y0, y1 in ys:
        for x0, x1 in xs:
            sub = a[y0+inset:y1-inset, x0+inset:x1-inset]
            m = mask_of(sub, t)
            lab, k = nd.label(m, structure=np.ones((3, 3)))
            sz = nd.sum(m, lab, range(1, k+1))
            m = np.isin(lab, [i+1 for i in range(k) if sz[i] >= 30])
            out.append(dict(img=soft_rgba(sub, m), m=m))
    return out

def place_fixed(frames, W, H, scale, cx_at, foot_y, ref=0):
    """keep every frame's panel-relative position; anchor taken from frame `ref`'s body"""
    bm = body_metrics(frames[ref]['m'])
    res = []
    for fr in frames:
        img = Image.fromarray(fr['img'])
        img = img.resize((max(1, round(img.width*scale)), max(1, round(img.height*scale))), Image.LANCZOS)
        ox, oy = int(round(cx_at - bm['cx']*scale)), int(round(foot_y - bm['bot']*scale))
        cell = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        cell.alpha_composite(img, (max(ox, 0), max(oy, 0)), (max(-ox, 0), max(-oy, 0)))
        res.append(cell)
    return res

def blobs_rows(a, m, split_y, **kw):
    bs = blobs(a, m, **kw)
    for b in bs:
        b['row'] = int(b['y0'] > split_y)
    return sorted(bs, key=lambda b: (b['row'], b['x0']))
