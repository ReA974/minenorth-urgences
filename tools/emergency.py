"""Véhicules de secours et sièges spéciaux du pack :
  - seat_brancard : siège-brancard (le brancard EST le siège : il porte le blessé et coulisse avec les portes arrière) ;
  - seat_suspect  : siège arrière du Sprinter police (le mod Police y installe les suspects) ;
  - mercedes_sprinter_ncv3lwb_vsav : Sprinter pompiers (VSAV) avec brancard ;
  - audi_a6_c8a_samu : A6 SAMU ;
  - 4 sièges suspect à l'arrière du Sprinter police.

Les noms « seat_brancard » et « seat_suspect » sont lus par les mods Secours (fr.minenorth.secours.compat.Mts)
et Police (fr.minenorth.police.compat.Mts) : ne pas les changer sans modifier ces classes.

usage : python emergency.py <racine_gvp_extraite> <racine_pack>
"""
import sys, os, json, math, shutil, tempfile
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livery

PID = 'minenorthpolicecar'
CELLS = {'chrome': (205, 210, 222, 255), 'mattress': (28, 58, 120, 255), 'pillow': (240, 240, 244, 255),
         'strap': (236, 196, 36, 255), 'wheel': (24, 24, 26, 255)}
ORDER = list(CELLS)


def uv(name):
    return ((ORDER.index(name) + 0.5) / len(ORDER), 0.5)


class Mesh:
    def __init__(self):
        self.v, self.vt, self.vn, self.lines = [], [], [], []

    def obj(self, name):
        self.lines.append('o ' + name)

    def tri(self, pts, color):
        a, b, c = [np.array(p, float) for p in pts]
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-12 else np.array([0, 1, 0.0])
        self.vt.append(uv(color)); ti = len(self.vt)
        self.vn.append(tuple(n)); ni = len(self.vn)
        ids = []
        for p in (a, b, c):
            self.v.append(tuple(p)); ids.append(len(self.v))
        self.lines.append('f %d/%d/%d %d/%d/%d %d/%d/%d' % (ids[0], ti, ni, ids[1], ti, ni, ids[2], ti, ni))

    def quad(self, p0, p1, p2, p3, color):
        self.tri((p0, p1, p2), color)
        self.tri((p0, p2, p3), color)

    def box(self, x0, x1, y0, y1, z0, z1, color):
        P = lambda x, y, z: (x, y, z)
        self.quad(P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1), color)
        self.quad(P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), color)
        self.quad(P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), color)
        self.quad(P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0), color)
        self.quad(P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0), color)
        self.quad(P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1), color)

    def text(self):
        out = ['# brancard (genere par tools/emergency.py)']
        out += ['v %.5f %.5f %.5f' % p for p in self.v]
        out += ['vt %.5f %.5f' % p for p in self.vt]
        out += ['vn %.5f %.5f %.5f' % p for p in self.vn]
        return '\n'.join(out + self.lines) + '\n'


def stretcher_mesh():
    """Brancard de transport : matelas bleu, oreiller blanc (tête côté +z, vers l'avant), sangles jaunes, châssis chromé sur roulettes.
    Origine = point d'assise du siège ; le dessus du matelas est à y = 0."""
    m = Mesh()
    m.obj('brancard')
    m.box(-0.27, 0.27, -0.07, 0.0, -0.92, 0.92, 'mattress')
    m.box(-0.20, 0.20, 0.0, 0.045, 0.55, 0.88, 'pillow')
    for z in (-0.55, -0.10, 0.35):
        m.box(-0.285, 0.285, 0.0, 0.012, z - 0.035, z + 0.035, 'strap')
    for sx in (-1, 1):                                                   # longerons
        x0, x1 = (0.27, 0.31) if sx > 0 else (-0.31, -0.27)
        m.box(x0, x1, -0.10, -0.02, -0.95, 0.95, 'chrome')
    for z in (-0.93, 0.0, 0.93):                                         # traverses
        m.box(-0.29, 0.29, -0.13, -0.09, z - 0.025, z + 0.025, 'chrome')
    m.box(-0.27, 0.27, -0.06, -0.02, -1.08, -0.95, 'chrome')            # poignée de poussée (pieds)
    for z in (-0.65, 0.65):                                              # pieds repliés + roulettes
        for x0, x1 in ((-0.27, -0.24), (0.24, 0.27)):
            m.box(x0, x1, -0.44, -0.10, z - 0.02, z + 0.02, 'chrome')
        m.box(-0.27, 0.27, -0.46, -0.42, z - 0.02, z + 0.02, 'chrome')
        for x0, x1 in ((-0.29, -0.25), (0.25, 0.29)):
            m.box(x0, x1, -0.52, -0.43, z - 0.045, z + 0.045, 'wheel')
    return m


def stretcher_texture():
    im = Image.new('RGBA', (len(ORDER) * 8, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, name in enumerate(ORDER):
        d.rectangle([i * 8, 0, i * 8 + 7, 15], fill=CELLS[name])
    return im


def stretcher_icon():
    S = 8
    im = Image.new('RGBA', (32 * S, 32 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(2 * S, 14 * S), (26 * S, 10 * S), (30 * S, 14 * S), (6 * S, 18 * S)], fill=(28, 58, 120, 255))
    d.polygon([(22 * S, 11 * S), (28 * S, 10 * S), (30 * S, 13 * S), (24 * S, 14 * S)], fill=(240, 240, 244, 255))
    d.line([(3 * S, 19 * S), (28 * S, 15 * S)], fill=(205, 210, 222, 255), width=S)
    d.line([(8 * S, 19 * S), (7 * S, 27 * S)], fill=(205, 210, 222, 255), width=S)
    d.line([(24 * S, 16 * S), (23 * S, 27 * S)], fill=(205, 210, 222, 255), width=S)
    d.ellipse([5 * S, 26 * S, 9 * S, 30 * S], fill=(24, 24, 26, 255))
    d.ellipse([21 * S, 26 * S, 25 * S, 30 * S], fill=(24, 24, 26, 255))
    d.line([(10 * S, 12 * S), (11 * S, 16 * S)], fill=(236, 196, 36, 255), width=S)
    return im.resize((32, 32), Image.LANCZOS)


def seat_part_json(name, title):
    return {
        'generic': {'type': 'seat', 'forwardsDamageMultiplier': 0.0},
        'seat': {'playerScale': [1.0, 1.0, 1.0]},
        'definitions': [{'subName': '', 'name': title, 'extraMaterialLists': [[]]}],
        'rendering': {'lightObjects': [], 'particles': [], 'modelType': 'obj'},
        'general': {'health': 100, 'materialLists': [['minecraft:iron_ingot:0:6', 'minecraft:wool:0:2']], 'radarWidth': 0.0, 'radarRange': 0.0},
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)


def item_model(pack, system, tex):
    p = os.path.join(pack, 'assets', 'mts', 'models', 'item', f'{PID}.{system}.json')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:{tex}'}}, open(p, 'w'), indent=2)


def build_seats(gvp, pack):
    dst = os.path.join(pack, 'assets', PID)
    src = os.path.join(gvp, 'assets', 'gvp')
    # --- brancard
    os.makedirs(os.path.join(dst, 'objmodels/parts/seats'), exist_ok=True)
    os.makedirs(os.path.join(dst, 'textures/parts/seats'), exist_ok=True)
    os.makedirs(os.path.join(dst, 'textures/item/parts/seats'), exist_ok=True)
    open(os.path.join(dst, 'objmodels/parts/seats/seat_brancard.obj'), 'w', encoding='utf-8', newline='\n').write(stretcher_mesh().text())
    stretcher_texture().save(os.path.join(dst, 'textures/parts/seats/seat_brancard.png'))
    stretcher_icon().save(os.path.join(dst, 'textures/item/parts/seats/seat_brancard.png'))
    write_json(os.path.join(dst, 'jsondefs/parts/seats/seat_brancard.json'), seat_part_json('seat_brancard', 'Brancard (secours)'))
    item_model(pack, 'seat_brancard', 'item/parts/seats/seat_brancard')
    # --- siège suspect : le siège générique gvp, sous un autre nom
    shutil.copyfile(f'{src}/objmodels/parts/seats/generic_car_seat_1.obj', os.path.join(dst, 'objmodels/parts/seats/seat_suspect.obj'))
    shutil.copyfile(f'{src}/textures/parts/seats/generic_car_seat_1.png', os.path.join(dst, 'textures/parts/seats/seat_suspect.png'))
    shutil.copyfile(f'{src}/textures/item/parts/seats/generic_car_seat_1.png', os.path.join(dst, 'textures/item/parts/seats/seat_suspect.png'))
    t = json.load(open(f'{src}/jsondefs/parts/seats/generic_car_seat_1.json', encoding='utf-8'))
    t['definitions'] = [{'subName': '', 'name': 'Siège arrière (transport de suspect)', 'extraMaterialLists': [[]]}]
    write_json(os.path.join(dst, 'jsondefs/parts/seats/seat_suspect.json'), t)
    item_model(pack, 'seat_suspect', 'item/parts/seats/seat_suspect')
    # siège équipe (RAID) : même modèle, nom différent pour que le mod Police ne le prenne pas pour un siège de suspect
    for kind, ext in (('objmodels/parts/seats', 'obj'), ('textures/parts/seats', 'png'), ('textures/item/parts/seats', 'png')):
        shutil.copyfile(os.path.join(dst, kind, 'seat_suspect.' + ext), os.path.join(dst, kind, 'seat_equipe.' + ext))
    t['definitions'] = [{'subName': '', 'name': "Siège d'équipe d'intervention", 'extraMaterialLists': [[]]}]
    write_json(os.path.join(dst, 'jsondefs/parts/seats/seat_equipe.json'), t)
    item_model(pack, 'seat_equipe', 'item/parts/seats/seat_equipe')


SEAT_TYPES = ['seat', 'seat_invisible']
TEAM_SPOTS = [(-0.52, 0.58, 0.45), (0.52, 0.58, 0.45), (-0.52, 0.58, 1.30), (0.52, 0.58, 1.30)]
SUSPECT_SPOTS = [(-0.52, 0.58, 0.45), (0.52, 0.58, 0.45), (-0.52, 0.58, 1.30), (0.52, 0.58, 1.30)]


def seat_slot(pos, default, animations=None):
    s = {'pos': list(pos), 'rot': [0.0, 0.0, 0.0], 'maxValue': 1.0, 'partScale': [1.0, 1.0, 1.0], 'defaultPart': f'{PID}:{default}', 'types': list(SEAT_TYPES)}
    if animations:
        s['animations'] = animations
    return s


def stretcher_animations():
    """Le brancard sort par les portes arrière : chaque porte ouverte le fait coulisser d'une moitié de course."""
    out = []
    for var in ('doorRR', 'doorRL'):
        out.append({'animationType': 'translation', 'variable': var, 'axis': [0.0, 0.0, -0.9], 'duration': 30,
                    'forwardsDelay': 30, 'forwardsEasing': 'easeinoutcubic', 'reverseEasing': 'easeincubic'})
    return out


BAC_MODELS = {'audi_a6_c8a': 'Audi A6 Avant', 'mercedes_glc_300_4matic': 'Mercedes GLC 300', 'ford_focus_c170_5d16': 'Ford Focus'}
BAC_COLORS = {'noir': (22, 22, 25), 'bleu': (24, 50, 132), 'rouge': (156, 24, 30)}


def bac_colors(pack, tmp):
    """Chaque voiture BAC existe en noir, bleu et rouge (l'ancienne version gris anthracite est remplacée)."""
    dst = os.path.join(pack, 'assets', PID)
    for m, label in BAC_MODELS.items():
        jp = os.path.join(dst, 'jsondefs/vehicles/cars', m + '_bac.json')
        j = json.load(open(jp, encoding='utf-8'))
        j['definitions'] = [{'subName': '_' + c, 'name': f'{label} - BAC ({c})', 'extraMaterialLists': [[]]} for c in BAC_COLORS]
        write_json(jp, j)
        icon = os.path.join(dst, 'textures/item/vehicles/cars', m + '_bac.png')
        for c in BAC_COLORS:
            shutil.copyfile(os.path.join(tmp, f'{m}_bac_{c}.png'), os.path.join(dst, 'textures/vehicles/cars', f'{m}_bac_{c}.png'))
            shutil.copyfile(icon, os.path.join(dst, 'textures/item/vehicles/cars', f'{m}_bac_{c}.png'))
            item_model(pack, f'{m}_bac_{c}', f'item/vehicles/cars/{m}_bac_{c}')
        # l'ancienne variante sans suffixe n'existe plus
        for f in (os.path.join(dst, 'textures/vehicles/cars', m + '_bac.png'), os.path.join(pack, 'assets/mts/models/item', f'{PID}.{m}_bac.json')):
            if os.path.exists(f):
                os.remove(f)


def clone_vehicle(pack, base, new, title, texture_png, light_part, extra_parts=(), drop_defaults=()):
    dst = os.path.join(pack, 'assets', PID)
    j = json.load(open(os.path.join(dst, 'jsondefs/vehicles/cars', base + '.json'), encoding='utf-8'))
    parts = [p for p in j['parts'] if p.get('defaultPart') not in drop_defaults]
    for p in parts:
        if p.get('defaultPart') == f'{PID}:lightbar_fr':
            p['defaultPart'] = f'{PID}:{light_part}'
    parts += list(extra_parts)
    j['parts'] = parts
    j['definitions'] = [{'subName': '', 'name': title, 'extraMaterialLists': [[]]}]
    write_json(os.path.join(dst, 'jsondefs/vehicles/cars', new + '.json'), j)
    shutil.copyfile(os.path.join(dst, 'objmodels/vehicles/cars', base + '.obj'), os.path.join(dst, 'objmodels/vehicles/cars', new + '.obj'))
    shutil.copyfile(texture_png, os.path.join(dst, 'textures/vehicles/cars', new + '.png'))
    icon_src = os.path.join(dst, 'textures/item/vehicles/cars', base + '_police.png')
    if not os.path.exists(icon_src):
        icon_src = os.path.join(dst, 'textures/item/vehicles/cars', base + '.png')
    shutil.copyfile(icon_src, os.path.join(dst, 'textures/item/vehicles/cars', new + '.png'))
    item_model(pack, new, f'item/vehicles/cars/{new}')


def build_vehicles(gvp, pack):
    dst = os.path.join(pack, 'assets', PID)
    police = os.path.join(dst, 'jsondefs/vehicles/cars/mercedes_sprinter_ncv3lwb.json')
    # 1) les sièges suspect ne sont ajoutés au Sprinter police qu'après le clonage du VSAV
    tmp = tempfile.mkdtemp(prefix='liv_')
    try:
        livery.run2(gvp, 'mercedes_sprinter_ncv3lwb', tmp, suffix='vsav', style='vsav')
        livery.run2(gvp, 'audi_a6_c8a', tmp, suffix='samu', style='samu')
        livery.run2(gvp, 'mercedes_sprinter_ncv3lwb', tmp, suffix='raid', style='raid')
        livery.run2(gvp, 'mercedes_glc_300_4matic', tmp, suffix='raid', style='raid')
        for m in BAC_MODELS:
            for c, rgb in BAC_COLORS.items():
                livery.run2(gvp, m, tmp, solid=rgb, suffix='bac_' + c)
        suspects = (f'{PID}:seat_suspect',)
        # VSAV
        clone_vehicle(pack, 'mercedes_sprinter_ncv3lwb', 'mercedes_sprinter_ncv3lwb_vsav', 'Mercedes Sprinter - VSAV Sapeurs-Pompiers',
                      os.path.join(tmp, 'mercedes_sprinter_ncv3lwb_vsav.png'), 'lightbar_pompiers',
                      extra_parts=[seat_slot((0.0, 0.62, 1.0), 'seat_brancard', stretcher_animations())], drop_defaults=suspects)
        # RAID : fourgon d'intervention (4 sièges d'équipe) et SUV, noirs
        clone_vehicle(pack, 'mercedes_sprinter_ncv3lwb', 'mercedes_sprinter_ncv3lwb_raid', 'Mercedes Sprinter - RAID',
                      os.path.join(tmp, 'mercedes_sprinter_ncv3lwb_raid.png'), 'lightbar_fr',
                      extra_parts=[seat_slot(pos, 'seat_equipe') for pos in TEAM_SPOTS], drop_defaults=suspects)
        clone_vehicle(pack, 'mercedes_glc_300_4matic', 'mercedes_glc_300_4matic_raid', 'Mercedes GLC 300 - RAID',
                      os.path.join(tmp, 'mercedes_glc_300_4matic_raid.png'), 'lightbar_fr')
        # BAC : trois couleurs
        bac_colors(pack, tmp)
        # SAMU
        clone_vehicle(pack, 'audi_a6_c8a', 'audi_a6_c8a_samu', 'Audi A6 Avant - SAMU',
                      os.path.join(tmp, 'audi_a6_c8a_samu.png'), 'lightbar_samu')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # 2) Sprinter police : 4 sièges arrière pour les suspects (idempotent)
    j = json.load(open(police, encoding='utf-8'))
    j['parts'] = [p for p in j['parts'] if p.get('defaultPart') != f'{PID}:seat_suspect']
    j['parts'] += [seat_slot(pos, 'seat_suspect') for pos in SUSPECT_SPOTS]
    write_json(police, j)


def build(gvp, pack):
    build_seats(gvp, pack)
    build_vehicles(gvp, pack)


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
    print('ok')
