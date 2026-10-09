"""Peint une livrée Police Nationale sur les textures du pack GVP (Kaminari Motor Work).

La livrée est définie en coordonnées 3D (axes MTS : +z avant, +x côté gauche, y haut)
puis « cuite » dans l'atlas UV : chaque texel d'un panneau de carrosserie retrouve sa position 3D.

usage : python livery.py <jar_extrait> <dossier_sortie> [modèle ...]
        python livery.py --preview <jar_extrait> <modèle> <sortie.png>   (rendu de contrôle)
"""
import sys, os, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS = 4                       # sur-échantillonnage pour l'anti-crénelage
PAINT = re.compile(r'^(body|door\w+|hood2?|hatch|slidedoor)$', re.I)
BLUE = np.array([14, 34, 99], float)
GRAPH = np.array([46, 49, 55], float)
RED = np.array([205, 30, 40], float)
WHITE = np.array([240, 243, 247], float)
FONT = next(f for f in ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f))


def load_obj(path):
    v, vt, vn, faces = [], [], [], []   # faces: (obj, [(vi,ti,ni)...])
    obj = ''
    for line in open(path, encoding='utf-8', errors='ignore'):
        p = line.split()
        if not p:
            continue
        if p[0] == 'v':
            v.append([float(x) for x in p[1:4]])
        elif p[0] == 'vt':
            vt.append([float(p[1]), float(p[2])])
        elif p[0] == 'vn':
            vn.append([float(x) for x in p[1:4]])
        elif p[0] == 'o':
            obj = p[1]
        elif p[0] == 'f':
            idx = []
            for t in p[1:]:
                a = (t.split('/') + ['', ''])[:3]
                idx.append(tuple(int(x) - 1 if x else -1 for x in a))
            faces.append((obj, idx))
    return np.array(v), np.array(vt), np.array(vn), faces


def tris(faces):
    for obj, idx in faces:
        for i in range(1, len(idx) - 1):
            yield obj, (idx[0], idx[i], idx[i + 1])


def text_mask(text, ppm, height_m, width_m=None, mirror=False):
    """Masque (H,W) float d'un texte, ppm = pixels par mètre ; renvoie (mask, largeur_m)."""
    h = int(height_m * ppm)
    font = ImageFont.truetype(FONT, h)
    w = int(font.getlength(text)) + 4
    im = Image.new('L', (w, int(h * 1.25)), 0)
    ImageDraw.Draw(im).text((2, 0), text, 255, font=font)
    box = im.getbbox()
    im = im.crop(box)
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return np.asarray(im, float) / 255, im.size[0] / ppm, im.size[1] / ppm


def sample(mask, wm, hm, u, v, u0, v0, ppm):
    """mask centré en (u0,v0). Renvoie la valeur du masque en (u,v) (0 hors masque)."""
    px = ((u - u0) / wm + 0.5) * mask.shape[1]
    py = (0.5 - (v - v0) / hm) * mask.shape[0]
    ok = (px >= 0) & (px < mask.shape[1]) & (py >= 0) & (py < mask.shape[0])
    out = np.zeros(u.shape)
    out[ok] = mask[py[ok].astype(int), px[ok].astype(int)]
    return out


def logo_image(size=256):
    """Logo tricolore stylisé (ruban bleu / blanc / rouge), RGBA transparent."""
    im = Image.new('RGBA', (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cols = [(24, 42, 128, 255), (250, 250, 252, 255), (200, 32, 45, 255)]
    outline = (24, 42, 128, 255)
    S2 = size * 2
    # trois rubans courbes (arcs d'ellipse épais) qui se croisent comme une vague
    for k, c in enumerate(cols):
        off = k * S2 * 0.105
        box = [S2 * 0.06 + off * 0.35, S2 * 0.10 + off, S2 * 0.94 - off * 0.2, S2 * 1.05 + off * 0.2]
        d.arc(box, 200, 355, fill=c, width=int(S2 * 0.105))
    # pointe du ruban
    d.polygon([(S2 * 0.72, S2 * 0.12), (S2 * 0.98, S2 * 0.34), (S2 * 0.86, S2 * 0.40), (S2 * 0.64, S2 * 0.20)], fill=cols[2])
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def star_image(size=256, color=(0, 70, 170, 255)):
    """Étoile de vie (six branches) bleue à liseré blanc, RGBA transparent."""
    S = size * 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    import math
    for ang in range(0, 180, 60):
        a = math.radians(ang)
        dx, dy = math.cos(a) * S * 0.46, math.sin(a) * S * 0.46
        w = S * 0.13
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        poly = [(S / 2 - dx + nx, S / 2 - dy + ny), (S / 2 + dx + nx, S / 2 + dy + ny),
                (S / 2 + dx - nx, S / 2 + dy - ny), (S / 2 - dx - nx, S / 2 - dy - ny)]
        d.polygon(poly, fill=(255, 255, 255, 255), outline=(255, 255, 255, 255))
    for ang in range(0, 180, 60):
        a = math.radians(ang)
        dx, dy = math.cos(a) * S * 0.43, math.sin(a) * S * 0.43
        w = S * 0.085
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        poly = [(S / 2 - dx + nx, S / 2 - dy + ny), (S / 2 + dx + nx, S / 2 + dy + ny),
                (S / 2 + dx - nx, S / 2 - dy - ny + 0), (S / 2 - dx - nx, S / 2 - dy - ny)]
        poly[2] = (S / 2 + dx - nx, S / 2 + dy - ny)
        d.polygon(poly, fill=color)
    return im


def sample_img(img, wm, hm, u, v, u0, v0):
    """RGBA (n,4) de l'image `img` (dont la taille réelle est wm x hm mètres) centrée en (u0,v0), vue de face (v vers le haut)."""
    arr = np.asarray(img, float)
    px = ((u - u0) / wm + 0.5) * arr.shape[1]
    py = (0.5 - (v - v0) / hm) * arr.shape[0]
    ok = (px >= 0) & (px < arr.shape[1]) & (py >= 0) & (py < arr.shape[0])
    out = np.zeros(u.shape + (4,))
    out[ok] = arr[py[ok].astype(int), px[ok].astype(int)]
    return out


def blend(out, rgba):
    a = (rgba[:, 3:4] / 255.0)
    return out * (1 - a) + rgba[:, :3] * a


class Livery:
    """Livrée Police Nationale : bande bleue (large à l'arrière, effilée vers l'aile avant), liseré blanc + rouge dessous,
    « POLICE » blanc et logo dans la bande, cadre bleu « POLICE NATIONALE » sur le capot."""
    def __init__(self, v, faces, bac=False, solid=None, style='police'):
        self.bac = bac
        self.solid = solid
        self.style = style
        pts = np.array([v[i[0]] for o, f in faces if PAINT.match(o) for i in f])
        doors = np.array([v[i[0]] for o, f in faces if re.match(r'door', o, re.I) for i in f])
        self.lo, self.hi = pts.min(0), pts.max(0)
        d = doors if len(doors) else pts
        self.zc = (d[:, 2].min() + d[:, 2].max()) / 2
        self.H = self.hi[1] - self.lo[1]
        self.L = self.hi[2] - self.lo[2]
        self.ppm = ppm = 300
        hp = np.array([v[i[0]] for o, f in faces if re.match(r'hood', o, re.I) for i in f])
        self.hood = (np.abs(hp[:, 0]).max(), hp[:, 2].min(), hp[:, 2].max()) if len(hp) else (0.8, 1.5, 3.0)
        band_h = 0.29 * self.H
        self.side_txt = text_mask('POLICE', ppm, 0.50 * band_h)
        self.rear_txt = text_mask('POLICE', ppm, 0.17)
        self.hood_txt1 = text_mask('POLICE', ppm, 0.15)
        self.hood_txt2 = text_mask('NATIONALE', ppm, 0.085)
        logo = logo_image()
        self.logo_side = (logo, 0.62 * band_h * logo.size[0] / logo.size[1], 0.62 * band_h)
        self.logo_hood = (logo, 0.11 * logo.size[0] / logo.size[1], 0.11)
        star = star_image()
        self.star_side = (star, 0.30, 0.30)
        self.star_hood = (star, 0.42, 0.42)
        self.raid_police = text_mask('POLICE', ppm, 0.17)
        self.raid_big = text_mask('RAID', ppm, 0.34)
        self.raid_rear = text_mask('RAID', ppm, 0.20)
        self.pomp_txt = text_mask('SAPEURS-POMPIERS', ppm, 0.19)
        self.samu_txt = text_mask('SAMU', ppm, 0.15)
        self.samu_rear = text_mask('SAMU', ppm, 0.17)

    def color(self, P, N, objname, base):
        """P (n,3), N (n,3) -> couleur RGB (n,3) à partir de la couleur de base (n,3)."""
        lum = base.mean(1, keepdims=True) / 220.0
        if self.solid is not None:
            return np.clip(np.tile(np.array(self.solid, float), (len(P), 1)) * np.clip(lum, 0.55, 1.0), 0, 255)
        if self.bac:   # BAC : banalisée, gris anthracite sans marquage
            return np.clip(np.tile(GRAPH, (len(P), 1)) * np.clip(lum, 0.55, 1.0), 0, 255)
        if self.style == 'vsav':
            return self.color_vsav(P, N, objname, lum)
        if self.style == 'samu':
            return self.color_samu(P, N, objname, lum)
        if self.style == 'raid':
            return self.color_raid(P, N, objname, lum)
        out = np.tile(WHITE, (len(P), 1))
        y = (P[:, 1] - self.lo[1]) / self.H
        t = (P[:, 2] - self.lo[2]) / self.L                    # 0 = arrière, 1 = avant
        side = np.abs(N[:, 0]) > 0.6
        rear = N[:, 2] < -0.6
        front = N[:, 2] > 0.6
        top = N[:, 1] > 0.6
        # --- flancs : bande bleue haute à l'arrière, qui s'effile en descendant vers l'aile avant
        y_top = np.interp(t, [0.0, 0.50, 0.62, 0.80, 0.93, 1.0], [0.50, 0.50, 0.46, 0.37, 0.33, 0.32])
        y_bot = np.interp(t, [0.0, 0.30, 0.60, 0.85, 1.0], [0.205, 0.205, 0.225, 0.265, 0.285])
        band = side & (y >= y_bot) & (y <= y_top)
        out[band] = BLUE
        out[side & (y < y_bot) & (y >= y_bot - 0.013)] = WHITE
        out[side & (y < y_bot - 0.013) & (y >= y_bot - 0.042)] = RED
        # « POLICE » blanc + logo dans la bande (lisibles de l'extérieur des deux côtés)
        u = np.where(P[:, 0] > 0, -P[:, 2], P[:, 2])
        uc = np.where(P[:, 0] > 0, -self.zc, self.zc)
        vmid = self.lo[1] + 0.357 * self.H
        m, wm, hm = self.side_txt
        t_txt = sample(m, wm, hm, u, P[:, 1], uc - 0.05, vmid, self.ppm) * side * band
        out = out * (1 - t_txt[:, None]) + WHITE * t_txt[:, None]
        lg, lw, lh = self.logo_side
        lrgba = sample_img(lg, lw, lh, u, P[:, 1], uc - 0.05 + wm / 2 + 0.07 + lw / 2, vmid)
        lrgba[:, 3] *= (side & band)
        out = blend(out, lrgba)
        # --- arrière : bande bleue + liseré + POLICE
        rband = rear & (y > 0.30) & (y < 0.50)
        out[rband] = BLUE
        out[rear & (y <= 0.30) & (y > 0.287)] = WHITE
        out[rear & (y <= 0.287) & (y > 0.258)] = RED
        m, wm, hm = self.rear_txt
        tr = sample(m, wm, hm, -P[:, 0], P[:, 1], 0.0, self.lo[1] + 0.40 * self.H, self.ppm) * rear
        out = out * (1 - tr[:, None]) + WHITE * tr[:, None]
        # --- avant : bande bleue basse + liseré
        out[front & (y > 0.30) & (y < 0.37)] = BLUE
        out[front & (y <= 0.30) & (y > 0.288)] = WHITE
        out[front & (y <= 0.288) & (y > 0.262)] = RED
        # --- capot : cadre bleu « POLICE / NATIONALE » + logo, lisible depuis l'avant (u = +x, v = -z)
        if re.match(r'hood', objname, re.I):
            hx, z0, z1 = self.hood
            za, zb = z0 + 0.05, z1 - 0.10                      # arrière (pare-brise) -> avant
            half = np.interp(P[:, 2], [za, zb], [0.82 * hx, 0.60 * hx])
            inside = top & (P[:, 2] > za) & (P[:, 2] < zb) & (np.abs(P[:, 0]) < half)
            th = 0.022
            edge = inside & ((np.abs(P[:, 0]) > half - th) | (P[:, 2] < za + th) | (P[:, 2] > zb - th))
            out[edge] = BLUE
            zm = (za + zb) / 2
            m, wm, hm = self.hood_txt1
            t1 = sample(m, wm, hm, P[:, 0], -P[:, 2], 0.0, -(zm - 0.12), self.ppm) * inside
            m, wm, hm = self.hood_txt2
            t2 = sample(m, wm, hm, P[:, 0], -P[:, 2], 0.0, -(zm + 0.04), self.ppm) * inside
            tt = np.maximum(t1, t2)
            out = out * (1 - tt[:, None]) + BLUE * tt[:, None]
            lg, lw, lh = self.logo_hood
            lrgba = sample_img(lg, lw, lh, P[:, 0], -P[:, 2], 0.0, -(zm + 0.17))
            lrgba[:, 3] *= inside
            out = blend(out, lrgba)
        return np.clip(out * np.clip(lum, 0.55, 1.0), 0, 255)


    # ------------------------------------------------------------------ pompiers (VSAV) et SAMU
    def _side_uv(self, P):
        u = np.where(P[:, 0] > 0, -P[:, 2], P[:, 2])
        uc = np.where(P[:, 0] > 0, -self.zc, self.zc)
        return u, uc

    def color_vsav(self, P, N, objname, lum):
        """VSAV : blanc, soubassement rouge, liseré jaune, « SAPEURS-POMPIERS » blanc, étoile de vie, chevrons rouges et blancs à l'arrière."""
        RED_P = np.array([196, 30, 38], float)
        YEL = np.array([240, 214, 40], float)
        out = np.tile(WHITE, (len(P), 1))
        y = (P[:, 1] - self.lo[1]) / self.H
        side = np.abs(N[:, 0]) > 0.6
        rear = N[:, 2] < -0.6
        front = N[:, 2] > 0.6
        low = (y < 0.36)
        out[(side | front) & low] = RED_P
        out[(side | front) & (y >= 0.36) & (y < 0.375)] = YEL
        # rouge sur le soubassement arrière, chevrons au-dessus
        chev = rear & (y >= 0.10) & (y < 0.52)
        stripe = (np.floor((np.abs(P[:, 0]) * 1.0 + y * self.H) / 0.16) % 2) == 0
        out[chev & stripe] = RED_P
        out[rear & (y < 0.10)] = RED_P
        u, uc = self._side_uv(P)
        m, wm, hm = self.pomp_txt
        t = sample(m, wm, hm, u, P[:, 1], uc, self.lo[1] + 0.225 * self.H, self.ppm) * side * low
        out = out * (1 - t[:, None]) + WHITE * t[:, None]
        lg, lw, lh = self.star_side
        lrgba = sample_img(lg, lw, lh, u, P[:, 1], uc, self.lo[1] + 0.50 * self.H)
        lrgba[:, 3] *= side
        out = blend(out, lrgba)
        lrgba = sample_img(lg, lw * 1.2, lh * 1.2, -P[:, 0], P[:, 1], 0.0, self.lo[1] + 0.62 * self.H)
        lrgba[:, 3] *= rear
        out = blend(out, lrgba)
        if re.match(r'hood', objname, re.I):
            top = N[:, 1] > 0.6
            lg, lw, lh = self.star_hood
            hx, z0, z1 = self.hood
            lrgba = sample_img(lg, lw * 0.6, lh * 0.6, P[:, 0], -P[:, 2], 0.0, -((z0 + z1) / 2))
            lrgba[:, 3] *= top
            out = blend(out, lrgba)
        return np.clip(out * np.clip(lum, 0.55, 1.0), 0, 255)

    def color_samu(self, P, N, objname, lum):
        """SAMU : blanc, bande vert-jaune fluo encadrée de bleu, « SAMU » bleu, étoile de vie bleue."""
        FLUO = np.array([206, 232, 24], float)
        NAVY = np.array([16, 34, 112], float)
        out = np.tile(WHITE, (len(P), 1))
        y = (P[:, 1] - self.lo[1]) / self.H
        side = np.abs(N[:, 0]) > 0.6
        rear = N[:, 2] < -0.6
        front = N[:, 2] > 0.6
        band = (y >= 0.215) & (y <= 0.375)
        out[(side | front) & band] = FLUO
        out[(side | front) & (y >= 0.203) & (y < 0.215)] = NAVY
        out[(side | front) & (y > 0.375) & (y <= 0.387)] = NAVY
        rb = rear & (y >= 0.24) & (y <= 0.44)
        out[rb] = FLUO
        out[rear & (y >= 0.228) & (y < 0.24)] = NAVY
        out[rear & (y > 0.44) & (y <= 0.452)] = NAVY
        u, uc = self._side_uv(P)
        m, wm, hm = self.samu_txt
        t = sample(m, wm, hm, u, P[:, 1], uc - 0.25, self.lo[1] + 0.295 * self.H, self.ppm) * side * band
        out = out * (1 - t[:, None]) + NAVY * t[:, None]
        lg, lw, lh = self.star_side
        lrgba = sample_img(lg, lw * 0.75, lh * 0.75, u, P[:, 1], uc + wm / 2 - 0.10 + 0.2, self.lo[1] + 0.295 * self.H)
        lrgba[:, 3] *= side & band
        out = blend(out, lrgba)
        m, wm, hm = self.samu_rear
        t = sample(m, wm, hm, -P[:, 0], P[:, 1], 0.0, self.lo[1] + 0.34 * self.H, self.ppm) * rb
        out = out * (1 - t[:, None]) + NAVY * t[:, None]
        if re.match(r'hood', objname, re.I):
            top = N[:, 1] > 0.6
            hx, z0, z1 = self.hood
            lg, lw, lh = self.star_hood
            lrgba = sample_img(lg, lw * 0.7, lh * 0.7, P[:, 0], -P[:, 2], 0.0, -((z0 + z1) / 2))
            lrgba[:, 3] *= top
            out = blend(out, lrgba)
        return np.clip(out * np.clip(lum, 0.55, 1.0), 0, 255)


    def color_raid(self, P, N, objname, lum):
        """RAID : noir mat, « POLICE » gris réfléchissant sur les flancs, liseré tricolore, « RAID » sur le capot et à l'arrière."""
        BLACK = np.array([24, 25, 29], float)
        GREY = np.array([196, 201, 210], float)
        out = np.tile(BLACK, (len(P), 1))
        y = (P[:, 1] - self.lo[1]) / self.H
        side = np.abs(N[:, 0]) > 0.6
        rear = N[:, 2] < -0.6
        top = N[:, 1] > 0.6
        # liseré bleu / blanc / rouge sur les flancs
        for lo_, hi_, col in ((0.405, 0.418, BLUE), (0.418, 0.431, WHITE), (0.431, 0.444, RED)):
            out[side & (y >= lo_) & (y < hi_)] = col
        u, uc = self._side_uv(P)
        m, wm, hm = self.raid_police
        t = sample(m, wm, hm, u, P[:, 1], uc, self.lo[1] + 0.30 * self.H, self.ppm) * side
        out = out * (1 - t[:, None]) + GREY * t[:, None]
        m, wm, hm = self.raid_rear
        t = sample(m, wm, hm, -P[:, 0], P[:, 1], 0.0, self.lo[1] + 0.40 * self.H, self.ppm) * rear
        out = out * (1 - t[:, None]) + GREY * t[:, None]
        if re.match(r'hood', objname, re.I):
            hx, z0, z1 = self.hood
            m, wm, hm = self.raid_big
            t = sample(m, wm, hm, P[:, 0], -P[:, 2], 0.0, -((z0 + z1) / 2), self.ppm) * top
            out = out * (1 - t[:, None]) + GREY * t[:, None]
        return np.clip(out * np.clip(lum * 0.75 + 0.25, 0.55, 1.0), 0, 255)


def bake(v, vt, vn, faces, tex, livery, body_col=None, paint_re=None, mask_fn=None):
    W, H = tex.size
    big = tex.resize((W * SS, H * SS), Image.NEAREST).convert('RGBA')
    arr = np.asarray(big, float).copy()
    base_all = arr.copy()
    # couleur de carrosserie dominante = mode des couleurs sous les triangles du body
    samp = []
    for o, (a, b, c) in tris(faces):
        if o.lower() == 'body' and a[1] >= 0:
            uv = (vt[a[1]] + vt[b[1]] + vt[c[1]]) / 3
            samp.append(tuple(np.asarray(tex.convert('RGB'))[min(H - 1, int((1 - uv[1]) * H)), min(W - 1, int(uv[0] * W))]))
    body_col = np.array(body_col if body_col is not None else (max(set(samp), key=samp.count) if samp else (0, 0, 0)), float)
    for o, (a, b, c) in tris(faces):
        if not (paint_re or PAINT).match(o) or min(a[1], b[1], c[1]) < 0:
            continue
        uv = np.array([vt[a[1]], vt[b[1]], vt[c[1]]])
        px = uv[:, 0] * W * SS
        py = (1 - uv[:, 1]) * H * SS
        x0, x1 = int(np.floor(px.min())), int(np.ceil(px.max()))
        y0, y1 = int(np.floor(py.min())), int(np.ceil(py.max()))
        if x1 - x0 > W * SS // 2 or y1 - y0 > H * SS // 2:
            continue
        xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1, W * SS - 1) + 1), np.arange(max(y0, 0), min(y1, H * SS - 1) + 1))
        xs, ys = xs.ravel() + 0.5, ys.ravel() + 0.5
        d = (py[1] - py[2]) * (px[0] - px[2]) + (px[2] - px[1]) * (py[0] - py[2])
        if abs(d) < 1e-9:
            continue
        l0 = ((py[1] - py[2]) * (xs - px[2]) + (px[2] - px[1]) * (ys - py[2])) / d
        l1 = ((py[2] - py[0]) * (xs - px[2]) + (px[0] - px[2]) * (ys - py[2])) / d
        l2 = 1 - l0 - l1
        ok = (l0 >= -0.01) & (l1 >= -0.01) & (l2 >= -0.01)
        if not ok.any():
            continue
        xs, ys, l0, l1, l2 = xs[ok], ys[ok], l0[ok], l1[ok], l2[ok]
        P3 = np.array([v[a[0]], v[b[0]], v[c[0]]])
        P = l0[:, None] * P3[0] + l1[:, None] * P3[1] + l2[:, None] * P3[2]
        n = np.cross(P3[1] - P3[0], P3[2] - P3[0])
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            continue
        n = n / ln
        if a[2] >= 0:                       # orienter selon la normale fournie
            nn = vn[a[2]] + vn[b[2]] + vn[c[2]]
            if np.dot(n, nn) < 0:
                n = -n
        N = np.tile(n, (len(P), 1))
        ix, iy = xs.astype(int), ys.astype(int)
        cur = arr[iy, ix, :3]
        mask = mask_fn(cur) if mask_fn else np.abs(cur - body_col).max(1) < 28    # on ne repeint que la peinture de la carrosserie
        if not mask.any():
            continue
        new = Livery_color[0].color(P[mask], N[mask], o, cur[mask])
        arr[iy[mask], ix[mask], :3] = new
    out = Image.fromarray(arr.clip(0, 255).astype('uint8'), 'RGBA').resize((W, H), Image.LANCZOS)
    # on restitue les texels non peints à l'identique (pas de flou sur les détails)
    orig = np.asarray(tex.convert('RGBA'))
    res = np.asarray(out).copy()
    changed = np.abs(np.asarray(big.resize((W, H), Image.BOX), float) - np.asarray(Image.fromarray(arr.clip(0, 255).astype('uint8'), 'RGBA').resize((W, H), Image.BOX), float)).max(2) > 1
    res[~changed] = orig[~changed]
    return Image.fromarray(res, 'RGBA')


Livery_color = [None]


def run(root, model, outdir, bac=False):
    return run2(root, model, outdir, bac=bac)


def run2(root, model, outdir, bac=False, solid=None, suffix=None, objdir=None, texdir=None, body_col=None, style='police'):
    base = os.path.join(root, 'assets/gvp')
    v, vt, vn, faces = load_obj(objdir or f'{base}/objmodels/vehicles/cars/{model}.obj')
    tex = Image.open(texdir or f'{base}/textures/vehicles/cars/{model}.png').convert('RGBA')
    Livery_color[0] = Livery(v, faces, bac, solid, style)
    img = bake(v, vt, vn, faces, tex, Livery_color[0], body_col)
    os.makedirs(outdir, exist_ok=True)
    img.save(f'{outdir}/{model}_{suffix or ("bac" if bac else "police")}.png')
    return img


def preview(root, model, tex_path, out, objpath=None, views=None, hide=None, ycut=None, keep_re=None):
    """Rendu orthographique texturé (z-buffer) : côté gauche, avant 3/4, arrière 3/4, dessus."""
    base = os.path.join(root, 'assets/gvp')
    v, vt, vn, faces = load_obj(objpath or f'{base}/objmodels/vehicles/cars/{model}.obj')
    tex = np.asarray(Image.open(tex_path).convert('RGB'))
    TH, TW = tex.shape[:2]
    keep = re.compile(keep_re or r'^(body|door\w+|hood2?|hatch|slidedoor|under|in|&.*|translucent.*)$', re.I)
    views = views or [(90, 0), (35, 20), (145, 20), (0, 85)]  # (azimut, élévation)
    S = 420
    sheet = Image.new('RGB', (S * len(views), S), (120, 160, 200))
    hide_re = re.compile(hide, re.I) if hide else None
    ctr = (v.min(0) + v.max(0)) / 2
    ext = (v.max(0) - v.min(0)).max()
    for k, (az, el) in enumerate(views):
        a, e = np.radians(az), np.radians(el)
        # caméra : tourne autour de y, puis inclinaison
        ry = np.array([[np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, np.cos(a)]])
        rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
        R = rx @ ry
        zb = np.full((S, S), -1e9)
        img = np.full((S, S, 3), (120, 160, 200), np.uint8)
        for o, (i0, i1, i2) in tris(faces):
            if not keep.match(o) or min(i0[1], i1[1], i2[1]) < 0:
                continue
            if hide_re and hide_re.match(o):
                continue
            P = np.array([v[i0[0]], v[i1[0]], v[i2[0]]]) - ctr
            if ycut is not None and P[:, 1].mean() + ctr[1] > ycut:
                continue
            Q = P @ R.T
            nrm = np.cross(Q[1] - Q[0], Q[2] - Q[0])
            L = np.linalg.norm(nrm)
            if L < 1e-12:
                continue
            nrm /= L
            if i0[2] >= 0:
                nv = (vn[i0[2]] + vn[i1[2]] + vn[i2[2]]) @ R.T
                if np.dot(nrm, nv) < 0:
                    nrm = -nrm
            if nrm[2] <= 0:
                continue  # dos
            sx = S / 2 + Q[:, 0] / ext * S * 0.9
            sy = S / 2 - Q[:, 1] / ext * S * 0.9
            x0, x1 = int(max(sx.min(), 0)), int(min(sx.max() + 1, S - 1))
            y0, y1 = int(max(sy.min(), 0)), int(min(sy.max() + 1, S - 1))
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            xs, ys = xs.ravel() + 0.5, ys.ravel() + 0.5
            d = (sy[1] - sy[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy[0] - sy[2])
            if abs(d) < 1e-9:
                continue
            l0 = ((sy[1] - sy[2]) * (xs - sx[2]) + (sx[2] - sx[1]) * (ys - sy[2])) / d
            l1 = ((sy[2] - sy[0]) * (xs - sx[2]) + (sx[0] - sx[2]) * (ys - sy[2])) / d
            l2 = 1 - l0 - l1
            ok = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not ok.any():
                continue
            xs, ys, l0, l1, l2 = xs[ok], ys[ok], l0[ok], l1[ok], l2[ok]
            z = l0 * Q[0, 2] + l1 * Q[1, 2] + l2 * Q[2, 2]
            uvs = np.array([vt[i0[1]], vt[i1[1]], vt[i2[1]]])
            uu = l0 * uvs[0, 0] + l1 * uvs[1, 0] + l2 * uvs[2, 0]
            vv = l0 * uvs[0, 1] + l1 * uvs[1, 1] + l2 * uvs[2, 1]
            ix, iy = xs.astype(int), ys.astype(int)
            better = z > zb[iy, ix]
            if not better.any():
                continue
            ix, iy, uu, vv, z = ix[better], iy[better], uu[better], vv[better], z[better]
            col = tex[np.clip(((1 - vv) * TH).astype(int), 0, TH - 1), np.clip((uu * TW).astype(int), 0, TW - 1)]
            shade = 0.55 + 0.45 * nrm[2]
            img[iy, ix] = (col * shade).astype(np.uint8)
            zb[iy, ix] = z
        sheet.paste(Image.fromarray(img), (k * S, 0))
    sheet.save(out)


if __name__ == '__main__':
    if sys.argv[1] == '--preview':
        _, _, root, model, tex_path, out = sys.argv
        preview(root, model, tex_path, out)
    else:
        root, outdir, *models = sys.argv[1:]
        for m in models:
            run(root, m, outdir)
            run(root, m, outdir, bac=True)
            print('ok', m)
