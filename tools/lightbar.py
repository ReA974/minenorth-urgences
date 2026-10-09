"""Rampes bleues FR (police, pompiers, SAMU) : reprend la rampe DROITE gvp « lightbar_usa1 » (celle de la Crown Victoria)
et la passe tout en bleu, avec une plaque de texte (« POLICE NATIONALE », « SAPEURS POMPIERS », « SAMU ») devant et derrière.

usage : python lightbar.py <racine_gvp_extraite> <racine_pack>   (racine = dossier contenant assets/)
Le modèle garde les noms d'objets de usa1 (body, &white, &white2, &red1/2, &blue1/2, translucent) : les feux alternent par paires.
"""
import sys, os, re, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PID = 'minenorthpolicecar'
BASE = 'lightbar_usa1'
FONT = next(f for f in ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f))
PAL = 128                      # zone palette (px) en haut à gauche de l'atlas (palette 64x64 agrandie x2)
ATLAS = (512, 256)             # largeur, hauteur : palette en haut à gauche, plaque en bas
SIGN_Y0 = 128                  # la plaque occupe les lignes 128..255
BLUE_LIGHT = '0033FF'
WHITE_LIGHT = 'CFE0FF'
SHELL = {'translucent'}        # coque transparente : sert à poser la plaque à la surface


def recolor_palette(img, amber=False):
    """Rouge -> bleu (ou orange si amber ; alpha conservé), gris sombres des pieds et du socle -> noir."""
    a = np.asarray(img.convert('RGBA'), float).copy()
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > g + 40) & (r > b + 40)
    lum = r[red]
    if amber:
        a[..., 0][red] = np.minimum(255, lum * 1.15 + 20)
        a[..., 1][red] = np.minimum(255, lum * 0.72 + 8)
        a[..., 2][red] = lum * 0.04
    else:
        a[..., 0][red] = lum * 0.04
        a[..., 1][red] = lum * 0.24
        a[..., 2][red] = np.minimum(255, lum * 1.20 + 20)
    grey = (np.abs(r - g) < 3) & (np.abs(g - b) < 3) & (r < 200) & (r > 0) & (a[..., 3] > 250)
    a[..., :3][grey] = (a[..., :3][grey] * 0.42)
    return Image.fromarray(a.clip(0, 255).astype('uint8'), 'RGBA')


def sign_image(lines):
    w, h = ATLAS[0], ATLAS[1] - SIGN_Y0
    im = Image.new('RGBA', (w, h), (244, 246, 250, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(20, 30, 90, 255), width=6)
    if len(lines) == 1:
        specs = ((lines[0], 86, 18),)
    else:
        specs = ((lines[0], 58, 8), (lines[1], 46, 66))
    for text, size, y in specs:
        f = ImageFont.truetype(FONT, size)
        while d.textlength(text, font=f) > w - 24 and size > 18:      # le texte doit tenir dans la plaque
            size -= 2
            f = ImageFont.truetype(FONT, size)
        d.text(((w - d.textlength(text, font=f)) / 2, y), text, (12, 16, 40, 255), font=f)
    return im


def build_atlas(pal_img, sign_lines):
    atlas = Image.new('RGBA', ATLAS, (0, 0, 0, 0))
    atlas.paste(pal_img.resize((PAL, PAL), Image.NEAREST), (0, 0))
    atlas.paste(sign_image(sign_lines), (0, SIGN_Y0))
    return atlas


def mesh(lines):
    v, faces, cur = [], [], ''
    for l in lines:
        p = l.split()
        if not p:
            continue
        if p[0] == 'v':
            v.append([float(x) for x in p[1:4]])
        elif p[0] in ('o', 'g'):
            cur = p[1]
        elif p[0] == 'f':
            idx = [int(t.split('/')[0]) - 1 for t in p[1:]]
            for i in range(1, len(idx) - 1):
                faces.append((cur, idx[0], idx[i], idx[i + 1]))
    return np.array(v), faces


def raycast_z(v, faces, objs, x, y, front=True):
    """z de la surface extérieure de la rampe en (x,y), vue de l'avant (+z) ou de l'arrière (-z)."""
    best = None
    for o, a, b, c in faces:
        if o not in objs:
            continue
        A, B, C = v[a], v[b], v[c]
        d = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
        if abs(d) < 1e-12:
            continue
        l0 = ((B[1] - C[1]) * (x - C[0]) + (C[0] - B[0]) * (y - C[1])) / d
        l1 = ((C[1] - A[1]) * (x - C[0]) + (A[0] - C[0]) * (y - C[1])) / d
        l2 = 1 - l0 - l1
        if l0 < -1e-9 or l1 < -1e-9 or l2 < -1e-9:
            continue
        z = l0 * A[2] + l1 * B[2] + l2 * C[2]
        if best is None or (front and z > best) or (not front and z < best):
            best = z
    return best


class Out:
    def __init__(self, nv, nvt, nvn):
        self.nv, self.nvt, self.nvn = nv, nvt, nvn
        self.lines = []

    def obj(self, name):
        self.lines.append('o ' + name)

    def quad(self, p0, p1, p2, p3, uv, n):
        for p in (p0, p1, p2, p3):
            self.lines.append('v %.6f %.6f %.6f' % tuple(p))
        for t in uv:
            self.lines.append('vt %.6f %.6f' % tuple(t))
        self.lines.append('vn %.6f %.6f %.6f' % tuple(n))
        a, b, c, d = (self.nv + 1, self.nv + 2, self.nv + 3, self.nv + 4)
        ta, tb, tc, td = (self.nvt + 1, self.nvt + 2, self.nvt + 3, self.nvt + 4)
        nn = self.nvn + 1
        self.lines.append('f %d/%d/%d %d/%d/%d %d/%d/%d' % (a, ta, nn, b, tb, nn, c, tc, nn))
        self.lines.append('f %d/%d/%d %d/%d/%d %d/%d/%d' % (a, ta, nn, c, tc, nn, d, td, nn))
        self.nv += 4; self.nvt += 4; self.nvn += 1


def build(gvp_root, pack_root, part='lightbar_fr', sign_lines=('POLICE', 'NATIONALE'), title='Rampe Police Nationale (2 tons)', amber=False):
    src = os.path.join(gvp_root, 'assets', 'gvp')
    dst = os.path.join(pack_root, 'assets', PID)
    lines = open(os.path.join(src, 'objmodels', 'parts', 'others', BASE + '.obj'), encoding='utf-8', errors='ignore').read().splitlines()
    v, faces = mesh(lines)
    nv = sum(1 for l in lines if l.startswith('v '))
    nvt = sum(1 for l in lines if l.startswith('vt '))
    nvn = sum(1 for l in lines if l.startswith('vn '))
    su, sv = PAL / ATLAS[0], PAL / ATLAS[1]
    out_lines = []
    for l in lines:
        if l.startswith(('mtllib', 'usemtl', 's ')):
            continue
        if l.startswith('vt '):
            _, u, vv = l.split()[:3]
            l = 'vt %.6f %.6f' % (float(u) * su, 1 - (1 - float(vv)) * sv)     # palette en haut à gauche de l'atlas
        out_lines.append(l)

    # plaque de texte : 0,40 m x 0,10 m (4:1), plate, au centre, devant et derrière. Elle se pose au-dessus des barres
    # noires du centre (z = point le plus avancé de la coque sur sa largeur) ; vue de l'arrière, le texte est lu dans le bon sens.
    o = Out(nv, nvt, nvn)
    o.obj('sign')
    ybot, ytop, half, pad = 0.060, 0.160, 0.20, 0.005
    xs = np.linspace(-half, half, 17)
    vb, vtp = 0.02, 0.48            # moitié basse de l'atlas (plaque)
    for front in (True, False):
        zs = [raycast_z(v, faces, SHELL | {'body'}, x, y, front) for x in xs for y in (ybot, ytop)]
        zs = [z for z in zs if z is not None]
        if not zs:
            continue
        z = (max(zs) + pad) if front else (min(zs) - pad)
        if front:
            o.quad((-half, ybot, z), (half, ybot, z), (half, ytop, z), (-half, ytop, z), [(0, vb), (1, vb), (1, vtp), (0, vtp)], (0, 0, 1))
        else:
            o.quad((half, ybot, z), (-half, ybot, z), (-half, ytop, z), (half, ytop, z), [(0, vb), (1, vb), (1, vtp), (0, vtp)], (0, 0, -1))

    for d in ('objmodels/parts/others', 'textures/parts/others', 'textures/item/parts/others', 'jsondefs/parts/others'):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    open(os.path.join(dst, 'objmodels', 'parts', 'others', part + '.obj'), 'w', encoding='utf-8', newline='\n').write(
        '\n'.join(out_lines + o.lines) + '\n')
    pal = Image.open(os.path.join(src, 'textures', 'parts', 'others', BASE + '.png')).convert('RGBA')
    build_atlas(recolor_palette(pal, amber), sign_lines).save(os.path.join(dst, 'textures', 'parts', 'others', part + '.png'))
    item = Image.open(os.path.join(src, 'textures', 'item', 'parts', 'others', BASE + '.png')).convert('RGBA')
    recolor_palette(item, amber).save(os.path.join(dst, 'textures', 'item', 'parts', 'others', part + '.png'))

    # définition : celle de usa1, feux bleus, sirène française
    t = open(os.path.join(src, 'jsondefs', 'parts', 'others', BASE + '.json'), encoding='utf-8').read()
    j = json.loads(re.sub(r',(\s*[}\]])', r'\1', t))
    for lo in j['rendering']['lightObjects']:
        lo['color'] = WHITE_LIGHT if lo['color'].upper() == 'FFFFFF' else ('FF9A00' if amber else BLUE_LIGHT)
    if amber:
        j['rendering']['sounds'] = []     # gyrophare de dépannage : pas de sirène
    for snd in j['rendering'].get('sounds', []):
        snd['name'] = f'{PID}:siren_fr_2tons'
    j['definitions'] = [{'subName': '', 'name': title, 'extraMaterialLists': [[]]}]
    json.dump(j, open(os.path.join(dst, 'jsondefs', 'parts', 'others', part + '.json'), 'w', encoding='utf-8'), indent=2)
    item_json = os.path.join(pack_root, 'assets', 'mts', 'models', 'item', f'{PID}.{part}.json')
    os.makedirs(os.path.dirname(item_json), exist_ok=True)
    json.dump({'parent': 'mts:item/basic', 'textures': {'layer0': f'{PID}:item/parts/others/{part}'}}, open(item_json, 'w'), indent=2)
    return len(o.lines)


if __name__ == '__main__':
    print('lignes ajoutees :', build(sys.argv[1], sys.argv[2]))
