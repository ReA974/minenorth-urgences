"""Livrées Police / Pompiers sur les bateaux du pack Belroft Motors (textures pixel-art 512 px).

Les textures « gray » sont neutres : on les recolore par classe de gris (blanc / clair / moyen / foncé), puis on pose les décalques
(bandes, textes) par coordonnées 3D comme pour les voitures (livery.bake). Les vitres, le bois et les feux (couleurs saturées)
ne sont pas touchés.

usage : python belroft.py <dossier_belroft_extrait> <sortie> describe <modele>
"""
import os, sys, re
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livery
from PIL import Image

WHITE = np.array([240, 243, 247], float)
BLUE = np.array([14, 34, 99], float)
DKBLUE = np.array([8, 20, 62], float)
RED = np.array([205, 30, 40], float)
DKRED = np.array([120, 14, 24], float)

PAINT_BOAT = re.compile(r'^(body|door_.*|cabmount)$', re.I)

# paramètres par modèle : fraction de hauteur de la ligne de pont, bande décor (fractions de hauteur), centre en z
MODELS = {
    # deck_y : hauteur du pont (au-dessus : superstructure) ; band_y : hauteur du texte sur la coque (0 = ligne de flottaison)
    'corallum': dict(deck_y=0.97, band_y=0.50, zc=1.4, tex='corallum_gray'),
    'starfish': dict(deck_y=1.10, band_y=0.55, zc=2.6, tex='starfish_gray'),
}


def lum(c):
    return c[:, 0] * 0.3 + c[:, 1] * 0.59 + c[:, 2] * 0.11


def neutral_mask(cur):
    """Texels « peinture » : gris neutres (hors vitres cyan, bois, feux)."""
    mx, mn = cur.max(1), cur.min(1)
    return ((mx - mn) < 40) & (lum(cur) >= 45)


class BoatLivery:
    def __init__(self, v, faces, kind, params):
        self.kind = kind
        pts = np.array([v[i[0]] for o, f in faces if PAINT_BOAT.match(o) for i in f])
        self.lo, self.hi = pts.min(0), pts.max(0)
        self.H = self.hi[1] - self.lo[1]
        self.zc = params['zc']
        self.deck_y = params['deck_y']
        self.band_y = (params['band_y'] - 0.2, params['band_y'] + 0.2)
        ppm = 300
        self.ppm = ppm
        label = 'POLICE' if kind == 'police' else 'POMPIERS'
        self.big = livery.text_mask(label, ppm, 0.34)
        self.small = livery.text_mask('POLICE NATIONALE' if kind == 'police' else 'SAPEURS-POMPIERS', ppm, 0.10)
        self.roof = livery.text_mask(label, ppm, 0.45)

    def color(self, P, N, objname, base):
        L = lum(base)
        hull = P[:, 1] < self.deck_y
        hullc = BLUE if self.kind == 'police' else RED
        # coque colorée sous le pont, superstructure blanche ; la luminosité d'origine garde les détails (joints, ombres)
        out = np.where(hull[:, None], hullc, WHITE)
        shade = np.clip(L / np.where(hull, 105.0, 205.0), 0.45, 1.12)
        out = out * shade[:, None]
        side = np.abs(N[:, 0]) > 0.6
        rear = N[:, 2] < -0.6
        top = N[:, 1] > 0.6
        yb0, yb1 = self.band_y
        txt = WHITE   # texte blanc sur la coque (bleue ou rouge)
        if self.kind == 'police':   # liseré tricolore sous le pont
            ym = self.deck_y
            out[side & (P[:, 1] > ym - 0.10) & (P[:, 1] <= ym - 0.04)] = RED
            out[side & (P[:, 1] > ym - 0.16) & (P[:, 1] <= ym - 0.10)] = WHITE
        else:               # liseré blanc sous le pont
            ym = self.deck_y
            out[side & (P[:, 1] > ym - 0.16) & (P[:, 1] <= ym - 0.08)] = WHITE
        # texte principal sur le flanc (lisible de l'extérieur : +x => u = -z ; -x => u = +z)
        u = np.where(P[:, 0] > 0, -P[:, 2], P[:, 2])
        uc = np.where(P[:, 0] > 0, -self.zc, self.zc)
        yc = (yb0 + yb1) / 2
        m, wm, hm = self.big
        t = livery.sample(m, wm, hm, u, P[:, 1], uc, yc, self.ppm) * side
        out = out * (1 - t[:, None]) + txt * t[:, None]
        m, wm, hm = self.small
        t = livery.sample(m, wm, hm, u, P[:, 1], uc, yc - 0.30, self.ppm) * side
        out = out * (1 - t[:, None]) + txt * t[:, None]
        # texte sur le toit (lisible depuis l'avant) et à l'arrière
        m, wm, hm = self.roof
        zr = self.hi[2] - 0.55 * (self.hi[2] - self.lo[2]) if False else self.zc
        t = livery.sample(m, wm, hm, P[:, 0], -P[:, 2], 0.0, -zr, self.ppm) * top * (P[:, 1] > self.deck_y)
        out = out * (1 - t[:, None]) + (BLUE if self.kind == 'police' else RED) * t[:, None]
        m, wm, hm = self.small
        t = livery.sample(m, wm, hm, -P[:, 0], P[:, 1], 0.0, yc, self.ppm) * rear
        out = out * (1 - t[:, None]) + txt * t[:, None]
        return np.clip(out, 0, 255)


def bake_boat(belroft_root, model, kind, outdir):
    p = MODELS[model]
    base = os.path.join(belroft_root, 'assets', 'belroftmotors')
    v, vt, vn, faces = livery.load_obj(os.path.join(base, 'objmodels', 'vehicles', model + '.obj'))
    tex = Image.open(os.path.join(base, 'textures', 'vehicles', p['tex'] + '.png')).convert('RGBA')
    livery.Livery_color[0] = BoatLivery(v, faces, kind, p)
    img = livery.bake(v, vt, vn, faces, tex, livery.Livery_color[0], paint_re=PAINT_BOAT, mask_fn=neutral_mask)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f'{model}_{kind}.png')
    img.save(out)
    return out


if __name__ == '__main__':
    root, outdir, cmd, model = sys.argv[1:5]
    if cmd == 'describe':
        base = os.path.join(root, 'assets', 'belroftmotors')
        v, vt, vn, faces = livery.load_obj(os.path.join(base, 'objmodels', 'vehicles', model + '.obj'))
        tex = np.asarray(Image.open(os.path.join(base, 'textures', 'vehicles', MODELS[model]['tex'] + '.png')).convert('RGB'))
        H, W = tex.shape[:2]
        rows = {}
        for o, (a, b, c) in livery.tris(faces):
            if not PAINT_BOAT.match(o) or min(a[1], b[1], c[1]) < 0:
                continue
            P = np.array([v[a[0]], v[b[0]], v[c[0]]])
            n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
            if ln < 1e-9 or abs(n[0] / ln) < 0.8:
                continue
            uv = (vt[a[1]] + vt[b[1]] + vt[c[1]]) / 3
            col = tuple(int(x) for x in tex[min(H - 1, int((1 - uv[1]) * H)), min(W - 1, int(uv[0] * W))])
            rows.setdefault(col, []).append(P[:, 1].mean())
        for col, ys in sorted(rows.items(), key=lambda kv: -len(kv[1]))[:10]:
            print(col, 'n=%d' % len(ys), 'y médian %.2f  [%.2f .. %.2f]' % (np.median(ys), min(ys), max(ys)))
    else:
        print(bake_boat(root, model, cmd, outdir))


# ====================================================================== dépanneuse (harpy + plateau)
# géométrie du plateau (repère du Harpy) : partagée avec belroft_pack (points d'attache, collisions, rampe)
BED = dict(zr=-2.85, zf=2.85, xw=1.2, yt=0.95, zramp=-6.0, yramp=0.10)


def build_tow_truck(belroft_root, outdir):
    """Harpy (châssis-cabine) + plateau de dépanneuse. Écrit harpy_depannage.obj / .png dans outdir."""
    from PIL import ImageDraw, ImageFont
    base = os.path.join(belroft_root, 'assets', 'belroftmotors')
    lines = open(os.path.join(base, 'objmodels', 'vehicles', 'harpy.obj'), encoding='utf-8', errors='ignore').read().splitlines()
    nv = sum(1 for l in lines if l.startswith('v '))
    nvt = sum(1 for l in lines if l.startswith('vt '))
    nvn = sum(1 for l in lines if l.startswith('vn '))
    tex = Image.open(os.path.join(base, 'textures', 'vehicles', 'harpy_yellow.png')).convert('RGBA')
    W, H = tex.size
    assert (W, H) == (256, 256)
    px = tex.load()
    # --- bande libre x 205..255 : ridelles peintes + nuancier
    ORANGE, STEEL, BLACK, AMBER = (223, 137, 0, 255), (104, 112, 118, 255), (33, 33, 39, 255), (255, 191, 29, 255)
    sw = {}
    for k, (cx, cy) in enumerate([(238, 0), (238, 10), (238, 20), (238, 30)]):
        c = [ORANGE, STEEL, BLACK, AMBER][k]
        for x in range(cx, cx + 8):
            for y in range(cy, cy + 8):
                px[x, y] = c
        sw[['orange', 'steel', 'black', 'amber'][k]] = (cx + 4, cy + 4)
    L, PH, PPM = 5.7, 0.35, 40.0
    Wp, Hp = int(L * PPM), int(PH * PPM)          # 228 x 14 : panneau vu de l'extérieur, texte de gauche à droite
    panel = Image.new('RGBA', (Wp, Hp), ORANGE)
    d = ImageDraw.Draw(panel)
    font = ImageFont.truetype(livery.FONT, 10)
    txt = 'DÉPANNAGE 24H/24'
    tw = d.textlength(txt, font=font)
    d.text(((Wp - tw) / 2, 1), txt, fill=BLACK, font=font)
    d.rectangle([0, 0, Wp, 1], fill=BLACK); d.rectangle([0, Hp - 2, Wp, Hp], fill=BLACK)
    pa = np.asarray(panel).transpose(1, 0, 2)      # (Wp lignes, Hp colonnes) : le long du panneau = lignes de l'atlas
    X0 = {'left': 205, 'right': 221}
    for side, x0 in X0.items():
        for r in range(Wp):
            for c in range(Hp):
                px[x0 + c, r] = tuple(int(t) for t in pa[r, c])
    # --- géométrie
    V, VT, VN, F = [], [], [], []

    def uv(col, row):
        return (col / 256.0, 1.0 - row / 256.0)

    def quad(obj, p, uvs, flip=False):
        """p : 4 points dans l'ordre antihoraire vu de l'extérieur ; uvs : 4 (col,row) en texels."""
        p = [np.array(q, float) for q in p]
        n = np.cross(p[1] - p[0], p[2] - p[0]); n = n / np.linalg.norm(n)
        i0 = len(V)
        for q in p: V.append(q)
        for t in uvs: VT.append(uv(*t))
        VN.append(n)
        F.append((obj, i0, len(VT) - 4, len(VN) - 1))

    def swatch(name):
        c, r = sw[name]
        return [(c, r)] * 4

    def box(obj, x0, x1, y0, y1, z0, z1, color, skip=()):
        s = swatch(color)
        if 'top' not in skip: quad(obj, [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], s)
        if 'bottom' not in skip: quad(obj, [(x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1)], s)
        if 'front' not in skip: quad(obj, [(x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1)], s)
        if 'rear' not in skip: quad(obj, [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], s)
        if 'right' not in skip: quad(obj, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], s)
        if 'left' not in skip: quad(obj, [(x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0)], s)

    ZR, ZF, XW, YB, YT = BED['zr'], BED['zf'], BED['xw'], 0.60, BED['yt']
    box('bed_deck', -XW, XW, YT - 0.12, YT, ZR, ZF, 'steel')
    box('bed_frame', -0.85, 0.85, 0.28, YT - 0.12, ZR + 0.2, ZF - 0.2, 'black')
    # ridelles peintes (texte lisible de l'extérieur : côté gauche (+x) de l'arrière vers l'avant = z décroissant)
    for side, x, order in (('left', XW + 0.01, (1, 0)), ('right', -XW - 0.01, (0, 1))):
        z_start, z_end = (ZF, ZR) if side == 'left' else (ZR, ZF)       # s croissant
        col0 = X0[side]
        def at(s_frac, t_down):      # -> (colonne, ligne) dans l'atlas
            return (col0 + t_down * (Hp - 1), s_frac * (Wp - 1))
        yt, yb = YT, YB
        if side == 'left':
            pts = [(x, yb, z_start), (x, yb, z_end), (x, yt, z_end), (x, yt, z_start)]    # normale vers +x
            # vu depuis +x : l'avant (z+) est à gauche => s = 0 à z = ZF (z_start)
            uvs = [at(0, 1), at(1, 1), at(1, 0), at(0, 0)]
        else:
            pts = [(x, yb, z_start), (x, yb, z_end), (x, yt, z_end), (x, yt, z_start)]
            uvs = [at(0, 1), at(1, 1), at(1, 0), at(0, 0)]
        quad('bed_side', pts, uvs)
    # tête de plateau (protège la cabine), treuil, rampe arrière
    box('bed_head', -XW, XW, YT, 1.95, ZF - 0.10, ZF, 'steel', skip=('bottom',))
    box('bed_winch', -0.45, 0.45, YT, 1.30, 1.95, ZF - 0.12, 'orange')
    box('bed_rail', -XW, XW, YT, YT + 0.10, ZR, ZR + 0.08, 'black', skip=('bottom',))
    s = swatch('steel')
    ZRAMP, YRAMP = BED['zramp'], BED['yramp']
    quad('bed_ramp', [(-XW, YT, ZR), (-XW, YRAMP, ZRAMP), (XW, YRAMP, ZRAMP), (XW, YT, ZR)], s)           # dessus (normale vers le haut et l'arrière)
    quad('bed_ramp', [(-XW, YT - 0.12, ZR), (XW, YT - 0.12, ZR), (XW, YRAMP - 0.10, ZRAMP), (-XW, YRAMP - 0.10, ZRAMP)], s)   # dessous
    quad('bed_ramp', [(-XW, YRAMP - 0.10, ZRAMP), (XW, YRAMP - 0.10, ZRAMP), (XW, YRAMP, ZRAMP), (-XW, YRAMP, ZRAMP)], s)      # tranche
    # --- écriture OBJ : on ajoute à la fin du fichier d'origine
    out = list(lines)
    out.append('# plateau de depanneuse (genere par belroft.py)')
    for q in V: out.append('v %.4f %.4f %.4f' % tuple(q))
    for t in VT: out.append('vt %.5f %.5f' % t)
    for n in VN: out.append('vn %.4f %.4f %.4f' % tuple(n))
    cur = None
    for obj, i0, t0, n0 in F:
        if obj != cur:
            out.append('o ' + obj); cur = obj
        out.append('f ' + ' '.join('%d/%d/%d' % (nv + i0 + k + 1, nvt + t0 + k + 1, nvn + n0 + 1) for k in range(4)))
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, 'harpy_depannage.obj'), 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    tex.save(os.path.join(outdir, 'harpy_depannage.png'))
    return os.path.join(outdir, 'harpy_depannage.obj')
