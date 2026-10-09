"""Cuit les textures (blanc/noir/gris/bleu, Police Nationale, BAC), l'icône et un rendu de contrôle. usage: peugeot_variants.py <jar> <work> <id>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livery
from PIL import Image
root, work, pid = sys.argv[1:4]
d = f'{work}/{pid}'
o, b = f'{d}/{pid}.obj', f'{d}/{pid}_base.png'
for suf, solid, bac in [('police', None, False)]:
    livery.run2(root, pid, d, bac=bac, solid=solid, suffix=suf, objdir=o, texdir=b, body_col=(222, 223, 224))
    print('bake', suf, flush=True)
livery.preview(root, pid, f'{d}/{pid}_police.png', f'{d}/{pid}_preview.png', objpath=o)
# icône d'inventaire : première vue (côté) du rendu, fond transparent
im = Image.open(f'{d}/{pid}_preview.png').convert('RGBA').crop((0, 100, 420, 320))
px = im.load()
for y in range(im.height):
    for x in range(im.width):
        r, g, bl, _ = px[x, y]
        if abs(r - 120) < 3 and abs(g - 160) < 3 and abs(bl - 200) < 3: px[x, y] = (0, 0, 0, 0)
im.resize((128, 68), Image.LANCZOS).save(f'{d}/{pid}_item.png')
print('fini', pid)
