"""Gyrophare magnétique BAC (pièce MTS « gyro_bac ») : socle caoutchouc, dôme bleu, réflecteur tournant,
câble spiralé et prise allume-cigare. Invisible tant que les feux ne sont pas activés (variable `lights`).
Place 3 gyrophares sur chaque voiture BAC (toit, tableau de bord, plage arrière).

usage : python gyro.py <racine_pack> <racine_gvp_extraite>
"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw

PID = 'minenorthpolicecar'
PART = 'gyro_bac'
CELLS = {  # nom -> (couleur RGBA)
    'rubber': (22, 22, 25, 255), 'magnet': (58, 60, 68, 255), 'cable': (16, 16, 18, 255),
    'plug_red': (196, 30, 36, 255), 'plug_tip': (34, 34, 38, 255), 'dome': (28, 70, 255, 150),
    'core': (150, 190, 255, 255), 'chrome': (205, 214, 232, 255),
}
ORDER = list(CELLS)
BLUE_LIGHT = '0033FF'


def uv(name):
    i = ORDER.index(name)
    return ((i + 0.5) / len(ORDER), 0.5)


class Mesh:
    def __init__(self):
        self.v, self.vt, self.vn, self.lines = [], [], [], []

    def obj(self, name):
        self.lines.append('o ' + name)

    def tri(self, pts, color, n=None):
        a, b, c = [np.array(p, float) for p in pts]
        if n is None:
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-12 else np.array([0, 1, 0.0])
        ids = []
        u = uv(color)
        self.vt.append(u); ti = len(self.vt)
        self.vn.append(tuple(n)); ni = len(self.vn)
        for p in (a, b, c):
            self.v.append(tuple(p)); ids.append(len(self.v))
        self.lines.append('f %d/%d/%d %d/%d/%d %d/%d/%d' % (ids[0], ti, ni, ids[1], ti, ni, ids[2], ti, ni))

    def quad(self, p0, p1, p2, p3, color):
        self.tri((p0, p1, p2), color)
        self.tri((p0, p2, p3), color)

    def ring_strip(self, rings, color, close=True):
        """rings : liste d'anneaux (listes de points) de même taille ; relie deux anneaux consécutifs (normales vers l'extérieur)."""
        for r0, r1 in zip(rings, rings[1:]):
            n = len(r0)
            for i in range(n):
                j = (i + 1) % n
                self.quad(r0[i], r0[j], r1[j], r1[i], color)

    def cap(self, ring, center, color, up=True):
        n = len(ring)
        for i in range(n):
            j = (i + 1) % n
            if up:
                self.tri((center, ring[i], ring[j]), color)
            else:
                self.tri((center, ring[j], ring[i]), color)

    def text(self):
        out = ['# gyro_bac (genere par tools/gyro.py)']
        out += ['v %.5f %.5f %.5f' % p for p in self.v]
        out += ['vt %.5f %.5f' % p for p in self.vt]
        out += ['vn %.5f %.5f %.5f' % p for p in self.vn]
        return '\n'.join(out + self.lines) + '\n'


def circle(r, y, n=16, cx=0.0, cz=0.0):
    # sens horaire vu du dessus : les normales sortent vers l'extérieur avec ring_strip (r0 -> r1 vers le haut)
    return [(cx + r * math.cos(-2 * math.pi * i / n), y, cz + r * math.sin(-2 * math.pi * i / n)) for i in range(n)]


def box(m, x0, x1, y0, y1, z0, z1, color):
    P = lambda x, y, z: (x, y, z)
    m.quad(P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1), color)
    m.quad(P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), color)
    m.quad(P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), color)
    m.quad(P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0), color)
    m.quad(P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0), color)
    m.quad(P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1), color)


def tube(m, pts, r, color, sides=4):
    """Tube carré le long d'une polyligne (câble)."""
    pts = [np.array(p, float) for p in pts]
    rings = []
    for k, p in enumerate(pts):
        d = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)])
        d = d / (np.linalg.norm(d) + 1e-12)
        a = np.cross(d, [0, 1, 0]);
        if np.linalg.norm(a) < 1e-6:
            a = np.cross(d, [1, 0, 0])
        a = a / np.linalg.norm(a); b = np.cross(d, a)
        ring = [tuple(p + r * (math.cos(2 * math.pi * s / sides + math.pi / 4) * a + math.sin(2 * math.pi * s / sides + math.pi / 4) * b)) for s in range(sides)]
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            m.quad(r0[i], r1[i], r1[j], r0[j], color)
            m.quad(r0[j], r1[j], r1[i], r0[i], color)   # double face : le câble reste visible sous tous les angles


def build_model():
    m = Mesh()
    # --- socle magnétique : cône tronqué caoutchouc + plateau
    m.obj('base')
    r0, r1, r2 = 0.085, 0.079, 0.072
    rings = [circle(r0, 0.0), circle(r1, 0.026), circle(r1, 0.030), circle(r2, 0.036), circle(0.068, 0.050)]
    m.ring_strip(rings, 'rubber')
    m.cap(rings[0], (0, 0.0, 0), 'rubber', up=False)
    # --- dôme translucide (demi-sphère aplatie)
    m.obj('translucent_dome')
    R, y0, H, steps = 0.066, 0.050, 0.078, 7
    dome = [circle(R * math.cos(math.pi / 2 * k / steps), y0 + H * math.sin(math.pi / 2 * k / steps)) for k in range(steps)]
    top = (0, y0 + H, 0)
    m.ring_strip(dome, 'dome')
    m.cap(dome[-1], top, 'dome', up=True)
    # --- réflecteur tournant (deux lamelles chromées face à face) + cœur lumineux
    m.obj('rolll')
    box(m, 0.022, 0.034, 0.056, 0.100, -0.020, 0.020, 'chrome')
    box(m, -0.034, -0.022, 0.056, 0.100, -0.020, 0.020, 'chrome')
    m.obj('&rolll')
    box(m, 0.012, 0.022, 0.060, 0.096, -0.016, 0.016, 'core')
    box(m, -0.022, -0.012, 0.060, 0.096, -0.016, 0.016, 'core')
    # --- câble spiralé + prise
    m.obj('cable')
    pts = []
    n_turns, length, rad, cy = 9, 0.20, 0.012, 0.016
    N = 90
    pts.append((0.075, cy, 0.0))
    for i in range(N + 1):
        s = i / N
        x = 0.085 + length * s
        ang = 2 * math.pi * n_turns * s
        z = 0.06 * s * s + rad * math.sin(ang)       # le câble s'écarte doucement
        y = cy + rad * math.cos(ang)
        pts.append((x, y, z))
    end = pts[-1]
    tube(m, pts, 0.0032, 'cable')
    m.obj('plug_red')
    ex, ey, ez = end
    box(m, ex, ex + 0.040, ey - 0.011, ey + 0.011, ez - 0.011, ez + 0.011, 'plug_red')
    m.obj('plug_black')
    box(m, ex + 0.040, ex + 0.056, ey - 0.006, ey + 0.006, ez - 0.006, ez + 0.006, 'plug_tip')
    return m


def build_texture():
    n = len(ORDER)
    im = Image.new('RGBA', (n * 8, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, name in enumerate(ORDER):
        d.rectangle([i * 8, 0, i * 8 + 7, 15], fill=CELLS[name])
    return im


def build_icon():
    """Icône d'objet 32x32 : gyrophare bleu vu de 3/4."""
    S = 8
    im = Image.new('RGBA', (32 * S, 32 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([4 * S, 20 * S, 28 * S, 28 * S], fill=(20, 20, 24, 255))                  # socle
    d.rectangle([4 * S, 21 * S, 28 * S, 24 * S], fill=(20, 20, 24, 255))
    d.ellipse([4 * S, 17 * S, 28 * S, 25 * S], fill=(48, 50, 58, 255))
    d.pieslice([6 * S, 5 * S, 26 * S, 29 * S], 180, 360, fill=(30, 74, 255, 235))       # dôme
    d.ellipse([6 * S, 16 * S, 26 * S, 23 * S], fill=(30, 74, 255, 235))
    d.rectangle([13 * S, 12 * S, 19 * S, 21 * S], fill=(170, 205, 255, 255))            # cœur
    d.arc([6 * S, 5 * S, 26 * S, 29 * S], 200, 340, fill=(190, 215, 255, 255), width=S)  # reflet
    d.line([(25 * S, 26 * S), (29 * S, 29 * S), (26 * S, 30 * S)], fill=(18, 18, 20, 255), width=S)  # câble
    d.rectangle([26 * S, 29 * S, 31 * S, 31 * S], fill=(196, 30, 36, 255))
    return im.resize((32, 32), Image.LANCZOS)


def build_json(template_path):
    import re
    t = json.loads(re.sub(r',(\s*[}\]])', r'\1', open(template_path, encoding='utf-8').read()))
    for snd in t['rendering'].get('sounds', []):
        snd['name'] = f'{PID}:siren_fr_2tons'
    on = {'animationType': 'visibility', 'variable': 'lights', 'clampMin': 1.0, 'clampMax': 1.0}
    anim = []
    for name in ('base', 'translucent_dome', 'cable', 'plug_red', 'plug_black'):
        anim.append({'objectName': name, 'animations': [dict(on)]})
    rot = [a for a in [o for o in t['rendering']['animatedObjects'] if o['objectName'] == 'rolll'][0]['animations'] if a['animationType'] == 'rotation']
    for a in rot:
        a['centerPoint'] = [0.0, 0.08, 0.0]
        a['axis'] = [0.0, -360.0, 0.0]
    anim.append({'objectName': 'rolll', 'animations': [dict(on), {'animationType': 'inhibitor', 'variable': 'lights'}] + rot})
    anim.append({'objectName': '&rolll', 'applyAfter': 'rolll', 'animations': [dict(on)]})
    light = [o for o in t['rendering']['lightObjects'] if o['objectName'] == '&rolll'][0]
    light['color'] = BLUE_LIGHT
    light['blendableComponents'] = [
        {'pos': [0.028, 0.080, 0.0], 'axis': [0.0, 0.0, 0.0], 'flareHeight': 0.35, 'flareWidth': 0.35},
        {'pos': [-0.028, 0.080, 0.0], 'axis': [0.0, 0.0, 0.0], 'flareHeight': 0.35, 'flareWidth': 0.35},
    ]
    out = {
        'generic': {'type': 'generic_roofdevice', 'forwardsDamageMultiplier': 0.0, 'width': 0.2, 'height': 0.2},
        'general': {'health': 100, 'materialLists': [['mts:mtsofficialpack.headlight:4', 'minecraft:iron_ingot:0:2']],
                    'radarWidth': 0.0, 'radarRange': 0.0},
        'definitions': [{'subName': '', 'name': 'Gyrophare magnetique BAC', 'extraMaterialLists': [[]]}],
        'rendering': {'animatedObjects': anim, 'lightObjects': [light], 'customVariables': ['siren', 'lights'],
                      'sounds': t['rendering']['sounds'], 'particles': [], 'modelType': 'obj'},
    }
    return out


# positions (x, y, z) dans le repère MTS (+z avant) : toit, tableau de bord, plage arrière
SPOTS = {
    'audi_a6_c8a': [(0.0, 1.309, 1.156), (0.0, 0.77, 2.32), (0.0, 0.82, -0.50)],
    'mercedes_glc_300_4matic': [(0.0, 1.466, 1.05), (0.0, 0.93, 2.30), (0.0, 0.95, -0.50)],
    'ford_focus_c170_5d16': [(0.0, 1.328, 1.10), (0.0, 0.78, 2.32), (0.0, 0.80, -0.35)],
}


def place_on_vehicles(dst):
    for model, spots in SPOTS.items():
        p = os.path.join(dst, 'jsondefs', 'vehicles', 'cars', model + '_bac.json')
        j = json.load(open(p, encoding='utf-8'))
        j['parts'] = [q for q in j['parts'] if q.get('defaultPart') not in (f'{PID}:lightbar_fr', f'{PID}:{PART}')]
        for pos in spots:
            j['parts'].append({'pos': [round(c, 3) for c in pos], 'rot': [0.0, 0.0, 0.0], 'maxValue': 1.163,
                               'partScale': [1.0, 1.0, 1.0], 'defaultPart': f'{PID}:{PART}',
                               'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
        json.dump(j, open(p, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)


def build(pack_root, gvp_root):
    dst = os.path.join(pack_root, 'assets', PID)
    for d in ('objmodels/parts/others', 'textures/parts/others', 'textures/item/parts/others', 'jsondefs/parts/others'):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    open(os.path.join(dst, 'objmodels/parts/others', PART + '.obj'), 'w', encoding='utf-8', newline='\n').write(build_model().text())
    build_texture().save(os.path.join(dst, 'textures/parts/others', PART + '.png'))
    build_icon().save(os.path.join(dst, 'textures/item/parts/others', PART + '.png'))
    j = build_json(os.path.join(gvp_root, 'assets', 'gvp', 'jsondefs', 'parts', 'others', 'lightbar_jpn1.json'))
    json.dump(j, open(os.path.join(dst, 'jsondefs/parts/others', PART + '.json'), 'w', encoding='utf-8'), indent=2)
    item = os.path.join(pack_root, 'assets', 'mts', 'models', 'item', f'{PID}.{PART}.json')
    json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/parts/others/{PART}'}}, open(item, 'w'), indent=2)
    place_on_vehicles(dst)
    return dst


if __name__ == '__main__':
    print(build(sys.argv[1], sys.argv[2]))
