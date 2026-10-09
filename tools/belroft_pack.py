"""Bateaux Police / Pompiers et dépanneuse (modèles du pack Belroft Motors) -> pack Urgences.

Les fiches véhicule (JSON) sont celles de Belroft (moteurs, sièges, animations), avec une seule définition, un gyrophare posé d'origine
et les textures livrée. Le pack Urgences dépend donc de belroftmotors.

usage (via build_pack.py) : BELROFT_ROOT=<jar Belroft extrait> python build_pack.py <gvp> <textures> <pack>
"""
import math, os, re, json, shutil, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import belroft, livery, lightbar
from PIL import Image

PID = 'minenorthpolicecar'
KEEP = r'^(?![$]|pedal|key|gloveboxdoor|gearshift|blinker_stick|light_switch|handbrake|fire_switch|trunk_switch|lights_switch).*'

# (nom système, source Belroft, dossier, nom affiché, gyrophare, échelle du gyrophare)
BOATS = [
    ('corallum_police', 'corallum', 'boats', 'Corallum - Vedette Police Nationale', 'lightbar_fr', 0.8),
    ('starfish_police', 'starfish', 'boats', 'Starfish - Canot Police Nationale', 'lightbar_fr', 0.7),
    ('corallum_pompier', 'corallum', 'boats', 'Corallum - Bateau Sapeurs-Pompiers', 'lightbar_pompiers', 0.8),
    ('starfish_pompier', 'starfish', 'boats', 'Starfish - Canot Sapeurs-Pompiers', 'lightbar_pompiers', 0.7),
]
TOW = ('harpy_depannage', 'harpy', 'trucks', 'Harpy - Dépanneuse', 'lightbar_depannage', 0.8)


def load_lenient(path):
    """JSON de Belroft : commentaires // et virgules finales tolérés par Immersive Vehicles."""
    t = open(path, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    out = []
    for line in t.split('\n'):
        in_str, cut = False, None
        for i, ch in enumerate(line):
            if ch == '"' and (i == 0 or line[i - 1] != '\\'):
                in_str = not in_str
            elif not in_str and line.startswith('//', i):
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    t = '\n'.join(out)
    t = re.sub(r',(\s*[}\]])', r'\1', t)
    t = re.sub(r'(?<=[\[,:\s])(-?)0{2,}(?=[.\d])', r'\g<1>0', t)   # 00.0 -> 0.0 (toléré par Gson, pas par json)
    return json.loads(t)


def ramp_toggle(j):
    """Rampe rangée par défaut (repliée à plat sur le plateau) ; un clic sur le coin arrière du plateau la sort / la range.
    Variable MTS « bed_ramp » : 1 = rampe sortie. Les collisions de la rampe n'existent que sortie."""
    if any(a.get('objectName') == 'bed_ramp' for a in j['rendering']['animatedObjects']):
        return
    B = belroft.BED
    # angle du bout de la rampe dans le plan (z, y) autour de la charnière ; un repli à plat vers l'avant = rotation +x de cet angle
    fold = math.degrees(math.atan2(B['yramp'] - B['yt'], B['zramp'] - B['zr'])) % 360.0
    j['rendering']['animatedObjects'].append({
        'objectName': 'bed_ramp',
        'animations': [{'animationType': 'rotation', 'variable': '!bed_ramp', 'centerPoint': [0.0, B['yt'], B['zr']],
                        'axis': [round(fold, 2), 0.0, 0.0], 'duration': 50,
                        'forwardsEasing': 'easeinoutsine', 'reverseEasing': 'easeinoutsine'}]})
    for g in j['collisionGroups']:       # marches de la rampe : seulement quand elle est sortie
        if g.get('collisionTypes') and 'vehicle' in g['collisionTypes'] and g['collisions']                 and all(c['pos'][2] < B['zr'] for c in g['collisions']):
            g['animations'] = [{'animationType': 'visibility', 'variable': 'bed_ramp', 'clampMin': 1.0, 'clampMax': 1.0}]
    levers = [{'pos': [x, round(B['yt'] + 0.1, 3), round(B['zr'] + 0.05, 3)], 'width': 0.25, 'height': 0.3,
               'action': {'action': 'toggle', 'variable': 'bed_ramp', 'value': 1.0}} for x in (B['xw'] - 0.1, -(B['xw'] - 0.1))]
    j['collisionGroups'].append({'collisionTypes': ['attack', 'click'], 'collisions': levers})


def tow_extras(j):
    """Dépanneuse : roues posées d'origine, point d'attache « plateau » (tow_flatbed) et collisions du plateau et de la rampe,
    sur le modèle de la remorque porte-voitures Belroft (trailer_cars) : on monte la voiture en conduisant sur la rampe."""
    B = belroft.BED
    for p in j['parts']:
        if any(t.startswith('ground_wheel') for t in p.get('types', [])):
            p['defaultPart'] = 'gvp:commonbudwheel'      # roue de camion gvp ; la plage d'emplacement est élargie pour l'accepter
            p['minValue'] = 0.4
            p['maxValue'] = 1.1
    j.setdefault('connectionGroups', []).append({
        'groupName': 'Flatbed', 'canInitiateConnections': True, 'canInitiateSubConnections': True, 'isHitch': True,
        'connections': [{'type': 'tow_flatbed', 'pos': [0.0, B['yt'], round(B['zf'] - 0.25, 3)], 'rot': [0.0, 0.0, 0.0],
                         'mounted': True, 'distance': 2.0}]})
    types = ['entity', 'attack', 'click', 'vehicle']
    deck = [{'width': 2.4, 'height': 0.125, 'pos': [0.0, round(B['yt'] - 0.0625, 4), z]} for z in (-1.9, 0.0, 1.9)]
    steps = []
    z = B['zr'] - 0.30
    while z > B['zramp'] + 0.15:
        y = B['yramp'] + (z - B['zramp']) * (B['yt'] - B['yramp']) / (B['zr'] - B['zramp'])    # surface de la rampe en z
        for x in (0.6, -0.6):
            steps.append({'width': 1.1, 'height': 0.25, 'pos': [x, round(y - 0.125, 4), round(z, 4)]})
        z -= 0.45
    j.setdefault('collisionGroups', []).append({'collisionTypes': types, 'collisions': deck})
    j['collisionGroups'].append({'collisionTypes': types, 'collisions': steps})
    ramp_toggle(j)


def top_spot(obj_path, objs):
    """Point le plus haut de la coque (x = 0) : centre en z des sommets du dernier ~6 % de hauteur."""
    v, vt, vn, faces = livery.load_obj(obj_path)
    pts = np.array([v[i[0]] for o, f in faces if re.match(objs, o) for i in f])
    ymax = pts[:, 1].max()
    top = pts[pts[:, 1] >= ymax - 0.06 * (ymax - pts[:, 1].min())]
    return [0.0, round(float(ymax), 3), round(float(top[:, 2].mean()), 3)]


def make_icon(obj_path, tex_path, out_png, model):
    tmp = tempfile.mkdtemp(prefix='icon_')
    try:
        sheet = os.path.join(tmp, 'p.png')
        livery.preview('', model, tex_path, sheet, objpath=obj_path, views=[(35, 18)], keep_re=KEEP)
        im = Image.open(sheet).convert('RGBA')
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, _ = px[x, y]
                if abs(r - 120) < 3 and abs(g - 160) < 3 and abs(b - 200) < 3:
                    px[x, y] = (0, 0, 0, 0)
        box = im.getbbox()
        if box:
            im = im.crop(box)
        im.thumbnail((128, 128), Image.LANCZOS)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        im.save(out_png)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(bel_root, pack):
    dst = os.path.join(pack, 'assets', PID)
    base = os.path.join(bel_root, 'assets', 'belroftmotors')
    tmp = tempfile.mkdtemp(prefix='bel_')
    try:
        jobs = []
        for system, src, sub, title, light, scale in BOATS:
            kind = 'police' if system.endswith('police') else 'pompier'
            png = belroft.bake_boat(bel_root, src, kind, tmp)
            jobs.append((system, src, sub, title, light, scale, os.path.join(base, 'objmodels', 'vehicles', src + '.obj'), png,
                         r'^(body|door_.*)$'))
        obj = belroft.build_tow_truck(bel_root, tmp)
        jobs.append((TOW[0], TOW[1], TOW[2], TOW[3], TOW[4], TOW[5], obj, os.path.join(tmp, 'harpy_depannage.png'), r'^cabmount$'))
        for system, src, sub, title, light, scale, obj, png, roof_objs in jobs:
            j = load_lenient(os.path.join(base, 'jsondefs', 'vehicles', src + '.json'))
            j['definitions'] = [{'subName': '', 'name': title, 'extraMaterialLists': [[]]}]
            j['parts'] = [p for p in j['parts'] if 'generic_roofdevice' not in p.get('types', [])]
            j['parts'].append({'pos': top_spot(obj, roof_objs), 'rot': [0.0, 0.0, 0.0], 'maxValue': 1.163,
                               'partScale': [scale] * 3, 'defaultPart': f'{PID}:{light}',
                               'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
            if system == TOW[0]:
                tow_extras(j)
            if 'general' in j:
                j['general']['description'] = title + ' (MineNorth).'
            for d in ('jsondefs', 'objmodels', 'textures', os.path.join('textures', 'item')):
                os.makedirs(os.path.join(dst, d, 'vehicles', sub), exist_ok=True)
            json.dump(j, open(os.path.join(dst, 'jsondefs', 'vehicles', sub, system + '.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            shutil.copyfile(obj, os.path.join(dst, 'objmodels', 'vehicles', sub, system + '.obj'))
            shutil.copyfile(png, os.path.join(dst, 'textures', 'vehicles', sub, system + '.png'))
            make_icon(obj, png, os.path.join(dst, 'textures', 'item', 'vehicles', sub, system + '.png'), src)
            item = os.path.join(pack, 'assets', 'mts', 'models', 'item', f'{PID}.{system}.json')
            os.makedirs(os.path.dirname(item), exist_ok=True)
            json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/vehicles/{sub}/{system}'}}, open(item, 'w'), indent=2)
            print('belroft :', system)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
