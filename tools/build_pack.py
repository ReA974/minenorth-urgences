"""Assemble le pack MTS « MineNorth Urgences » (id minenorthpolicecar) : police, pompiers, SAMU.
usage : python build_pack.py <jar_gvp_extrait> <textures_police_dir> <racine_pack>
"""
import sys, os, json, shutil, re
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import livery
root, texdir, pack = sys.argv[1:4]
PID = 'minenorthpolicecar'
MODELS = {  # systemName -> nom affiché
    'audi_a6_c8a': 'Audi A6 Avant - Police Nationale',
    'mercedes_glc_300_4matic': 'Mercedes GLC 300 - Police Nationale',
    'mercedes_sprinter_ncv3lwb': 'Mercedes Sprinter - Police Nationale',
    'polestar2': 'Polestar 2 - Police Nationale',
    'ford_focus_c170_5d16': 'Ford Focus - Police Nationale',
}
src = f'{root}/assets/gvp'
dst = f'{pack}/assets/{PID}'
def cp(a, b):
    os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copyfile(a, b)
def loadj(p):
    t = open(p, encoding='utf-8').read()
    return json.loads(re.sub(r',(\s*[}\]])', r'\1', t))
for m, name in MODELS.items():
    j = loadj(f'{src}/jsondefs/vehicles/cars/{m}.json')
    v, _, _, faces = livery.load_obj(f'{src}/objmodels/vehicles/cars/{m}.obj')
    body = np.array([v[i[0]] for o, f in faces if re.match(r'(body|hatch|door\w+)$', o, re.I) for i in f])
    door = np.array([v[i[0]] for o, f in faces if re.match(r'door', o, re.I) for i in f])
    roof_y = body[np.abs(body[:, 0]) < 0.35][:, 1].max()
    zc = (door[:, 2].min() + door[:, 2].max()) / 2
    j['parts'] = [p for p in j['parts'] if 'generic_roofdevice' not in p.get('types', [])]
    j['parts'].append({'pos': [0.0, round(float(roof_y) - 0.03, 3), round(float(zc) - 0.25, 3)], 'rot': [0.0, 0.0, 0.0],
                       'maxValue': 1.163, 'partScale': [1.0, 1.0, 1.0], 'defaultPart': f'{PID}:lightbar_fr',
                       'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
    j['definitions'] = [{'subName': '_police', 'name': name, 'extraMaterialLists': [[]]}]
    os.makedirs(f'{dst}/jsondefs/vehicles/cars', exist_ok=True)
    json.dump(j, open(f'{dst}/jsondefs/vehicles/cars/{m}.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    cp(f'{src}/objmodels/vehicles/cars/{m}.obj', f'{dst}/objmodels/vehicles/cars/{m}.obj')
    cp(f'{texdir}/{m}_police.png', f'{dst}/textures/vehicles/cars/{m}_police.png')
    cp(f'{src}/textures/item/vehicles/cars/{m}.png', f'{dst}/textures/item/vehicles/cars/{m}_police.png')
    os.makedirs(f'{pack}/assets/mts/models/item', exist_ok=True)
    json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/vehicles/cars/{m}_police'}},
              open(f'{pack}/assets/mts/models/item/{PID}.{m}_police.json', 'w'), indent=2)
# rampe lumineuse police FR (même modèle que la jpn1, sirène 2 tons)
j = loadj(f'{src}/jsondefs/parts/others/lightbar_jpn1.json')
j['definitions'][0]['name'] = 'Rampe Police Nationale (2 tons)'
for s in j['rendering']['sounds']:
    if s['name'] == 'gvp:jpn_standard_police':
        s['name'] = f'{PID}:siren_fr_2tons'
os.makedirs(f'{dst}/jsondefs/parts/others', exist_ok=True)
json.dump(j, open(f'{dst}/jsondefs/parts/others/lightbar_fr.json', 'w', encoding='utf-8'), indent=2)
# rampe bleue (modèle jpn1 recoloré + boîtier central + plaque POLICE NATIONALE), voir tools/lightbar.py
import lightbar
os.makedirs(f'{dst}/textures/item/parts/others', exist_ok=True)
lightbar.build(root, pack)
json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/parts/others/lightbar_fr'}},
          open(f'{pack}/assets/mts/models/item/{PID}.lightbar_fr.json', 'w'), indent=2)
json.dump({'packID': PID, 'packName': 'MineNorth Urgences', 'packItem': 'lightbar_fr', 'fileStructure': 1},
          open(f'{dst}/packdefinition.json', 'w'), indent=2)

# --- BAC : véhicules banalisés avec mini-rampe/sirène activable (propre véhicule, modèle copié) ---
BAC = {
    'audi_a6_c8a': 'Audi A6 Avant - BAC',
    'mercedes_glc_300_4matic': 'Mercedes GLC 300 - BAC',
    'ford_focus_c170_5d16': 'Ford Focus - BAC',
}
for m, name in BAC.items():
    j = json.load(open(f'{dst}/jsondefs/vehicles/cars/{m}.json', encoding='utf-8'))
    for p in j['parts']:
        if p.get('defaultPart') == f'{PID}:lightbar_fr':
            p['partScale'] = [0.45, 0.45, 0.45]       # mini-rampe discrète
    j['definitions'] = [{'subName': '', 'name': name, 'extraMaterialLists': [[]]}]
    json.dump(j, open(f'{dst}/jsondefs/vehicles/cars/{m}_bac.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    cp(f'{dst}/objmodels/vehicles/cars/{m}.obj', f'{dst}/objmodels/vehicles/cars/{m}_bac.obj')
    cp(f'{texdir}/{m}_bac.png', f'{dst}/textures/vehicles/cars/{m}_bac.png')
    cp(f'{src}/textures/item/vehicles/cars/{m}.png', f'{dst}/textures/item/vehicles/cars/{m}_bac.png')
    json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/vehicles/cars/{m}_bac'}},
              open(f'{pack}/assets/mts/models/item/{PID}.{m}_bac.json', 'w'), indent=2)

# --- BAC : 3 gyrophares magnétiques par voiture (toit, tableau de bord, plage arrière), visibles feux activés ---
import gyro
gyro.build(pack, root)

# --- Secours : rampes pompiers / SAMU, sièges (brancard, suspect), Sprinter VSAV, A6 SAMU, sièges arrière du Sprinter police ---
lightbar.build(root, pack, 'lightbar_pompiers', ('SAPEURS', 'POMPIERS'), 'Rampe Sapeurs-Pompiers (2 tons)')
lightbar.build(root, pack, 'lightbar_samu', ('SAMU',), 'Rampe SAMU (2 tons)')
import emergency
emergency.build(root, pack)

# --- Peugeot 508 GT / e-2008 (convertis depuis FBX par peugeot.py ; texturés par peugeot_variants.py) ---
PEUGEOT = {  # id -> (donneur, titre)
    'peugeot_508_gt': ('audi_a6_c8a', 'Peugeot 508 GT'),
    'peugeot_e2008': ('ford_focus_c170_5d16', 'Peugeot e-2008'),
}
COLORS = {'': 'blanc', '_noir': 'noir', '_gris': 'gris', '_bleu': 'bleu'}   # suffixe -> libellé
pw = os.environ.get('PEUGEOT_WORK')
if pw:
    for pid, (donor, title) in PEUGEOT.items():
        d = f'{pw}/{pid}'
        if not os.path.isdir(d):
            continue
        j0 = loadj(f'{src}/jsondefs/vehicles/cars/{donor}.json')
        v, _, _, faces = livery.load_obj(f'{d}/{pid}.obj')
        body = np.array([v[i[0]] for o, f in faces if re.match(r'(body|hatch|door\w+)$', o, re.I) for i in f])
        door = np.array([v[i[0]] for o, f in faces if re.match(r'door', o, re.I) for i in f])
        roof_y = body[np.abs(body[:, 0]) < 0.35][:, 1].max()
        zc = (door[:, 2].min() + door[:, 2].max()) / 2
        def vehicle(sysname, defs, lightbar=None, scale=1.0, desc=None, gyros=False):
            j = json.loads(json.dumps(j0))
            j['parts'] = [p for p in j['parts'] if 'generic_roofdevice' not in p.get('types', [])]
            if gyros:   # BAC : 3 gyrophares magnétiques (toit, tableau de bord, plage arrière), positions du donneur
                spots = [(0.0, round(float(roof_y) - 0.03, 3), round(float(zc) - 0.25, 3))] + [tuple(s_) for s_ in gyro.SPOTS[donor][1:]]
                for pos in spots:
                    j['parts'].append({'pos': [round(c, 3) for c in pos], 'rot': [0.0, 0.0, 0.0], 'maxValue': 1.163,
                                       'partScale': [1.0, 1.0, 1.0], 'defaultPart': f'{PID}:{gyro.PART}',
                                       'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
            elif lightbar:
                j['parts'].append({'pos': [0.0, round(float(roof_y) - 0.03, 3), round(float(zc) - 0.25, 3)], 'rot': [0.0, 0.0, 0.0],
                                   'maxValue': 1.163, 'partScale': [scale] * 3, 'defaultPart': f'{PID}:lightbar_fr',
                                   'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
            else:
                j['parts'].append({'pos': [0.0, round(float(roof_y) - 0.03, 3), round(float(zc) - 0.25, 3)], 'rot': [0.0, 0.0, 0.0],
                                   'maxValue': 1.163, 'partScale': [1.0, 1.0, 1.0],
                                   'types': ['generic_lightbar', 'generic_gyrophare', 'generic_roofdevice']})
            j['definitions'] = [{'subName': s, 'name': n, 'extraMaterialLists': [[]]} for s, n in defs]
            if 'general' in j: j['general']['description'] = desc or f'{title} (modele converti, MineNorth).'
            os.makedirs(f'{dst}/jsondefs/vehicles/cars', exist_ok=True)
            json.dump(j, open(f'{dst}/jsondefs/vehicles/cars/{sysname}.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            cp(f'{d}/{pid}.obj', f'{dst}/objmodels/vehicles/cars/{sysname}.obj')
            for s, _ in defs:
                tex = {'': 'white'}.get(s, s.lstrip('_')) if sysname == pid else ('police' if sysname.endswith('_pn') else 'bac')
                cp(f'{d}/{pid}_{tex}.png', f'{dst}/textures/vehicles/cars/{sysname}{s}.png')
                cp(f'{d}/{pid}_item.png', f'{dst}/textures/item/vehicles/cars/{sysname}{s}.png')
                json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/vehicles/cars/{sysname}{s}'}},
                          open(f'{pack}/assets/mts/models/item/{PID}.{sysname}{s}.json', 'w'), indent=2)
        vehicle(pid + '_pn', [('', f'{title} - Police Nationale')], lightbar=True)
