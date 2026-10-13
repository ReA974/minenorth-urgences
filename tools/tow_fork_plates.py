"""Depanneuse harpy_depannage : fourche de levage par les roues avant (geometrie ajoutee a l'OBJ), vrais emplacements de plaques gvp
(type generic_licenseplate), crochet WheelLift au centre de la fourche. A lancer apres belroft_pack / build_tow_truck (idempotent) :
    python tools/tow_fork_plates.py
"""
import json
import os

from PIL import Image

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OBJ = 'assets/minenorthpolicecar/objmodels/vehicles/trucks/harpy_depannage.obj'
PNG = 'assets/minenorthpolicecar/textures/vehicles/trucks/harpy_depannage.png'
JS = 'assets/minenorthpolicecar/jsondefs/vehicles/trucks/harpy_depannage.json'
MARK_PLATES = "# plaques d'immatriculation (ajoutees)"
MARK_FORK = '# fourche de levage (ajoutee)'

# --- texture : deux carres de 6 px dans un coin inutilise (x 0..11, y 250..255) : gris acier, jaune de signalisation
im = Image.open(PNG).convert('RGBA')
px = im.load()
GREY, YELLOW = (112, 114, 122, 255), (232, 190, 24, 255)
for y in range(250, 256):
    for x in range(0, 6):
        px[x, y] = GREY
    for x in range(6, 12):
        px[x, y] = YELLOW
im.save(PNG)

lines = open(OBJ, encoding='utf-8', errors='ignore').read().splitlines()
for mark in (MARK_PLATES, MARK_FORK):          # retire les anciennes plaques factices et une fourche precedente
    if mark in lines:
        lines = lines[:lines.index(mark)]
nv = sum(l.startswith('v ') for l in lines)
nvt = sum(l.startswith('vt ') for l in lines)
nvn = sum(l.startswith('vn ') for l in lines)

TEX = {'grey': (3 / 256.0, 1 - 253 / 256.0), 'yellow': (9 / 256.0, 1 - 253 / 256.0)}
out = [MARK_FORK]
vt_index = {}
for name, (u, v) in TEX.items():
    out.append('vt %.6f %.6f' % (u, v))
    nvt += 1
    vt_index[name] = nvt
NORMALS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
nbase = nvn
for n in NORMALS:
    out.append('vn %d %d %d' % n)
    nvn += 1


def box(name, x0, y0, z0, x1, y1, z1, tex):
    """Boite axe-aligne (6 faces, normales vers l'exterieur)."""
    global nv
    out.append('o ' + name)
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    for p in c:
        out.append('v %.4f %.4f %.4f' % p)
    t = vt_index[tex]
    faces = [((1, 5, 6, 2), 0), ((4, 0, 3, 7), 1), ((3, 2, 6, 7), 2), ((0, 4, 5, 1), 3), ((5, 4, 7, 6), 4), ((0, 1, 2, 3), 5)]
    for idx, ni in faces:
        for order in (idx, idx[::-1]):          # les deux sens d'enroulement : visible quel que soit le culling du moteur
            out.append('f ' + ' '.join('%d/%d/%d' % (nv + i + 1, t, nbase + ni + 1) for i in order))
    nv += 8


# fourche : cadre rectangulaire derriere le plateau (z de -3,1 a -4,7), au ras du sol, relie au chassis par deux verins
box('fork_rail_l', 0.90, 0.12, -4.70, 1.05, 0.24, -3.10, 'grey')
box('fork_rail_r', -1.05, 0.12, -4.70, -0.90, 0.24, -3.10, 'grey')
box('fork_bar_front', -1.05, 0.12, -3.25, 1.05, 0.24, -3.10, 'grey')
box('fork_bar_rear', -1.05, 0.12, -4.70, 1.05, 0.24, -4.55, 'yellow')
box('fork_ram_l', 0.62, 0.24, -3.20, 0.76, 0.62, -3.06, 'grey')
box('fork_ram_r', -0.76, 0.24, -3.20, -0.62, 0.62, -3.06, 'grey')
box('fork_cross', -0.76, 0.54, -3.20, 0.76, 0.62, -3.06, 'grey')
open(OBJ, 'w', encoding='utf-8').write('\n'.join(lines + out) + '\n')

j = json.load(open(JS, encoding='utf-8'))
# crochet roues avant : au centre de la fourche
for g in j['connectionGroups']:
    if g.get('groupName') == 'WheelLift':
        g['connections'][0]['pos'] = [0.0, 0.5, -3.9]
# vrais emplacements de plaques (le « texte » HARPY flottant est retire)
rd = j['rendering']
rd['textObjects'] = [t for t in rd.get('textObjects', []) if t.get('fieldName') != 'License Plate']
j['parts'] = [p for p in j['parts'] if not any('licenseplate' in t for t in p.get('types', []))]
types = ['generic_licenseplate_euro', 'generic_licenseplate_us', 'generic_licenseplate']
j['parts'].append({'pos': [0.0, 0.214, 5.14], 'rot': [0.0, 0.0, 0.0], 'maxValue': 1.0, 'partScale': [0.76, 0.76, 0.76], 'types': types})
j['parts'].append({'pos': [0.0, 0.265, -2.93], 'rot': [0.0, 180.0, 0.0], 'maxValue': 1.0, 'partScale': [0.76, 0.76, 0.76], 'types': types})
# --- fourche mobile : variable MTS « wheel_fork » (1 = sortie). Rangee, elle glisse de 1,55 m vers l'avant sous le chassis ; un clic sur
# l'un des deux coins arriere du plateau (bas) la sort / la range, comme la rampe (bed_ramp).
FORK_OBJECTS = ['fork_rail_l', 'fork_rail_r', 'fork_bar_front', 'fork_bar_rear', 'fork_ram_l', 'fork_ram_r', 'fork_cross']
rd['animatedObjects'] = [o for o in rd['animatedObjects'] if o.get('objectName') not in FORK_OBJECTS]
for name in FORK_OBJECTS:
    rd['animatedObjects'].append({'objectName': name, 'animations': [{
        'animationType': 'translation', 'variable': '!wheel_fork', 'axis': [0.0, 0.0, 1.55], 'duration': 40,
        'forwardsEasing': 'easeinoutsine', 'reverseEasing': 'easeinoutsine'}]})
j['collisionGroups'] = [g for g in j['collisionGroups']
                        if not any(c.get('action', {}).get('variable') == 'wheel_fork' for c in g.get('collisions', []))]
levers = [{'pos': [x, 0.4, -3.0], 'width': 0.3, 'height': 0.4, 'action': {'action': 'toggle', 'variable': 'wheel_fork', 'value': 1.0}}
          for x in (1.1, -1.1)]
j['collisionGroups'].append({'collisionTypes': ['attack', 'click'], 'collisions': levers})
json.dump(j, open(JS, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('ok')
