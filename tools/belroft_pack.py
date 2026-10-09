"""Bateaux Police / Pompiers et dépanneuse (modèles du pack Belroft Motors) -> pack Urgences.

Les fiches véhicule (JSON) sont celles de Belroft (moteurs, sièges, animations), avec une seule définition, un gyrophare posé d'origine
et les textures livrée. Le pack Urgences dépend donc de belroftmotors.

usage (via build_pack.py) : BELROFT_ROOT=<jar Belroft extrait> python build_pack.py <gvp> <textures> <pack>
"""
import os, re, json, shutil, sys, tempfile
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
