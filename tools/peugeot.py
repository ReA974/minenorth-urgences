"""Convertit les FBX Peugeot en véhicules MTS (OBJ + atlas + JSON) calés sur un véhicule « donneur » du pack gvp.

usage : python peugeot.py <jar_gvp_extrait> <dossier_travail> 508|2008
Produit dans <dossier_travail>/<id>/ : <id>.obj, <id>_base.png (atlas avec peinture neutre), meta.json
"""
import sys, os, re, json, bisect
import numpy as np
import pyfqmr
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbx, livery

ATLAS = 1024
PLACEHOLDER = (222, 223, 224)
SCRATCH = os.environ.get('SCRATCH', '.')

CARS = {
    '508': dict(fbx='p508/Peugeot 508 GT.fbx', donor='audi_a6_c8a', id='peugeot_508_gt', title='Peugeot 508 GT',
                paint={'carpaint'}, wheel=re.compile(r'^wheel_|^hub_'),
                door={'door_dside_f': 'doorFL', 'door_pside_f': 'doorFR', 'door_dside_r': 'doorRL', 'door_pside_r': 'doorRR'},
                mesh_obj={'steeringwheel': 'in', 'chassis': 'under', 'headlight_l': '&head', 'headlight_r': '&head',
                          'taillight_l': '&redrun', 'taillight_r': '&redrun', 'brakelight_m': '&brake'},
                mat_obj={'drl': '&head', 'taillight': '&redrun'},
                glass={'glass', 'sans titre 1'}, glass_red=set(),
                colors={'black.001': (46, 46, 50), 'gris.001': (112, 114, 120), 'black.002': (58, 58, 63), 'p508_tex': (84, 84, 90),
                        'black.003': (40, 40, 44), 'hash_1fa3ecee': (52, 52, 56), 'led': (200, 200, 205), 'hash_8a7a2bef': (44, 44, 48),
                        'cligno': (150, 70, 0), 'cligno.001': (150, 70, 0), 'whitye': (215, 215, 220), 'drl': (235, 235, 240),
                        'far': (215, 215, 220), 'taillight': (150, 10, 10), 'black': (34, 34, 38), 'gris': (130, 130, 135)}),
    '2008': dict(fbx='pe2008/Peugeot e-2008.fbx', donor='ford_focus_c170_5d16', id='peugeot_e2008', title='Peugeot e-2008',
                 paint={'p24body'}, wheel=re.compile(r'^2008p24_wheel', re.I),
                 door={'2008p24_door_FL': 'doorFL', '2008p24_door_FR': 'doorFR', '2008p24_door_RL': 'doorRL', '2008p24_door_RR': 'doorRR',
                       '2008p24_doorglass_FL': 'doorFL', '2008p24_doorglass_FR': 'doorFR', '2008p24_doorglass_RL': 'doorRL',
                       '2008p24_doorglass_RR': 'doorRR'},
                 mesh_obj={'2008p24_steering_wheel': 'in', '2008p24_floor': 'under', '2008p24_hood_a': 'hood', '2008p24_tailgate_a': 'hatch',
                           '2008p24_tailgateglass': 'hatch', '2008p24_tailgate_chmsl': '&brake',
                           '2008p24_headlight_L': '&head', '2008p24_headlight_R': '&head'},
                 mat_obj={'2008p24_lowbeam': '&head', '2008p24_highbeam': '&head', '2008p24_tail': '&redrun', '2008p24_rl': '&redrun'},
                 glass={'p24_glass'}, glass_red={'p24_redglass'},
                 colors={'p24_gray': (92, 94, 100), 'p24_chrome': (190, 192, 196), 'peugeot2008_interior': (88, 88, 94), 'p24_carbon': (44, 44, 48),
                         'mirror': (150, 160, 170), 'p24_black': (30, 30, 34), '2008p24_foglight': (220, 220, 225), 'p24_metalblack': (58, 58, 63),
                         'p24_ceiling': (160, 158, 150), 'p24_white': (225, 225, 225), 'p24_plastic': (36, 36, 40), '2008p24_signal_l': (160, 80, 0),
                         '2008p24_signal_r': (160, 80, 0), '2008p24_tail': (150, 10, 10), '2008p24_brake': (150, 10, 10), '2008p24_indicator': (150, 80, 0),
                         '2008p24_lowbeam': (225, 225, 230), '2008p24_highbeam': (225, 225, 230), 'unnamed.3': (30, 30, 32), 'bluehdi': (190, 190, 195),
                         'p24_leather': (70, 66, 62), '2008p24_intlight': (200, 200, 200), '2008p24_rl': (150, 10, 10), '2008p24_red': (160, 20, 20),
                         'unnamed.5': (40, 40, 40)}),
}
GROUP_MULT = {'cabin': 6.0, 'paint': 1.0, 'other': 0.5, 'glass': 0.3, 'light': 1.0, 'under': 0.08, 'in': 0.25}
BUDGET = 36000
PAINT_TARGET = 17000
CABIN_TARGET = 9000


def donor_info(root, donor):
    j = json.loads(re.sub(r',(\s*[}\]])', r'\1', open(f'{root}/assets/gvp/jsondefs/vehicles/cars/{donor}.json', encoding='utf-8').read()))
    susp = [p['pos'] for p in j['parts'] if any('suspension' in t for t in p['types'])]
    zs = sorted(set(round(p[2], 4) for p in susp))
    v, vt, vn, faces = livery.load_obj(f'{root}/assets/gvp/objmodels/vehicles/cars/{donor}.obj')
    def pts(rx):
        return np.array([v[i[0]] for o, f in faces if re.match(rx, o) for i in f])
    doors = pts(r'door[FR][LR]$')
    body = pts(r'body$')
    seats = [p['pos'] for p in j['parts'] if 'seat' in p['types']]
    return j, dict(zr=zs[0], zf=zs[-1], door_ymin=doors[:, 1].min(), body_hw=np.abs(body[:, 0]).max(), seats=seats), faces


def load_meshes(path, cfg):
    models, geoms, mats, texs = fbx.load(path)
    out = []
    for i, m in models.items():
        if not m['geom']: continue
        V, T, _, tm = fbx.geometry(geoms[m['geom']])
        W = (fbx.world(models, i) @ np.c_[V, np.ones(len(V))].T).T[:, :3] * 0.01
        names = [mats[x]['name'].lower() for x in m['mats']] or ['?']
        opac = {mats[x]['name'].lower(): mats[x]['opac'] for x in m['mats']}
        tmn = [names[k] if k < len(names) else names[-1] for k in tm]
        out.append(dict(name=m['name'], V=W, T=T, mat=np.array(tmn), opac=opac))
    return out


def fit(meshes, cfg, info):
    wheels = [m for m in meshes if cfg['wheel'].search(m['name']) and len(m['V']) > 5000]
    cz = np.array([(m['V'][:, 2].min() + m['V'][:, 2].max()) / 2 for m in wheels])
    zf_p, zr_p = cz[cz > 0].mean(), cz[cz < 0].mean()
    s = (info['zf'] - info['zr']) / (zf_p - zr_p)
    doors = [m for m in meshes if m['name'] in cfg['door'] and 'glass' not in m['name']]
    y0 = min(m['V'][:, 1].min() for m in doors)
    body = [m for m in meshes if m['name'].lower().startswith(('bodyshell', '2008p24_body', '2008p24_quarter'))]
    hw_p = max(np.abs(m['V'][:, 0]).max() for m in body)
    sx = info['body_hw'] / hw_p
    sx = s * 0.5 + sx * 0.5   # compromis : on respecte à moitié la largeur du donneur
    def tf(P):
        Q = np.empty_like(P)
        Q[:, 0] = P[:, 0] * sx
        Q[:, 1] = (P[:, 1] - y0) * s + info['door_ymin']
        Q[:, 2] = (P[:, 2] - zr_p) * s + info['zr']
        return Q
    return tf, dict(s=float(s), sx=float(sx), zf_p=float(zf_p), zr_p=float(zr_p))


def route(cfg, mesh, mat, centroid):
    """-> (objet MTS, groupe) pour un triangle."""
    n = mesh['name']
    obj = cfg['door'].get(n) or cfg['mesh_obj'].get(n) or 'body'
    if mat in cfg['glass'] or mat in cfg['glass_red']:
        suffix = {'doorFL': '_doorFL', 'doorFR': '_doorFR', 'doorRL': '_doorRL', 'doorRR': '_doorRR', 'hatch': '_hatch'}.get(obj, '')
        return 'translucent' + suffix, 'glass'
    if mat in cfg['paint']:
        return obj if obj in ('body', 'hood', 'hatch') or obj.startswith('door') else 'body', 'paint'
    if mat in cfg['mat_obj']:
        o = cfg['mat_obj'][mat]
        if o == '&redrun' and mat == '2008p24_brake': o = '&brake'
        return o, 'light'
    if mat in ('cligno', 'cligno.001', '2008p24_indicator', '2008p24_signal_l', '2008p24_signal_r'):
        side = 'L' if (centroid[0] > 0 if mat != '2008p24_signal_r' else False) else 'R'
        if mat == '2008p24_signal_l': side = 'L'
        return '&turn' + side, 'light'
    if mat == '2008p24_brake' and centroid[2] < 0.5:
        return '&brake', 'light'
    if mat == 'far':
        return '&brake', 'light'
    if obj.startswith('&'):
        return obj, 'light'
    if obj == 'under': return obj, 'under'
    if obj == 'in': return obj, 'in'
    return obj, 'other'


def weld(P, T):
    key = np.round(P / 1e-4).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    V = np.zeros((len(uniq), 3)); V[inv] = P
    F = inv[T]
    return V, F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]


def decimate(P, T, target, border=True):
    """Simplification quadrique (coque de peinture)."""
    V, F = weld(P, T)
    if len(F) <= max(target, 12): return V, F
    q = pyfqmr.Simplify(); q.setMesh(V, F)
    q.simplify_mesh(target_count=int(target), aggressiveness=7, preserve_border=border, verbose=False)
    v2, f2, _ = q.getMesh()
    return v2, f2


def cluster(P, T, target):
    """Regroupement de sommets sur grille (robuste aux maillages morcelés) ; la taille de cellule est ajustée au budget."""
    V, F = weld(P, T)
    if len(F) <= max(target, 12): return V, F
    lo, hi = 0.002, 0.6
    best = (V, F)
    for _ in range(14):
        c = np.sqrt(lo * hi)
        k = np.floor(V / c).astype(np.int64)
        u, inv = np.unique(k, axis=0, return_inverse=True); inv = inv.ravel()
        cnt = np.bincount(inv)
        V2 = np.zeros((len(u), 3))
        for d in range(3): V2[:, d] = np.bincount(inv, V[:, d]) / cnt
        F2 = inv[F]
        F2 = F2[(F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 0] != F2[:, 2])]
        if len(F2) > target: lo = c
        else: hi = c; best = (V2, F2)
    return best


def vnormals(V, F):
    n = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3): np.add.at(n, F[:, k], fn)
    L = np.linalg.norm(n, axis=1, keepdims=True); L[L == 0] = 1
    return n / L


def build(root, work, key):
    cfg = CARS[key]
    jd, info, dfaces = donor_info(root, cfg['donor'])
    meshes = load_meshes(os.path.join(SCRATCH, cfg['fbx']), cfg)
    tf, fitinfo = fit(meshes, cfg, info)
    print('fit', fitinfo, 'donor', info)
    # --- habitacle : boîte (repère donneur) ; les sièges du modèle sont retirés (le pack fournit les pièces « siège »)
    dpts = np.vstack([tf(m['V']) for m in meshes if m['name'] in cfg['door'] and 'glass' not in m['name']])
    allp = np.vstack([tf(m['V'][::7]) for m in meshes if not cfg['wheel'].search(m['name'])])
    roof_y = np.percentile(allp[np.abs(allp[:, 0]) < 0.35][:, 1], 99.5)
    cab_lo = np.array([-info['body_hw'] * 0.9, dpts[:, 1].min() + 0.05, dpts[:, 2].min() - 0.05])
    cab_hi = np.array([info['body_hw'] * 0.9, roof_y - 0.08, dpts[:, 2].max() + 0.95])
    print('cabine', cab_lo.round(2), cab_hi.round(2))
    def in_cabin(c): return np.all((c > cab_lo) & (c < cab_hi), axis=1)
    def in_seat(c):
        m = np.zeros(len(c), bool)
        for sx, sy, sz in info['seats']:
            m |= (np.abs(c[:, 0] - sx) < 0.30) & (c[:, 2] > sz - 0.45) & (c[:, 2] < sz + 0.30) & (c[:, 1] > sy - 0.06) & (c[:, 1] < sy + 1.0)
        return m
    # --- collecte des triangles par (objet, groupe)
    groups = {}
    for m in meshes:
        if cfg['wheel'].search(m['name']): continue
        P = tf(m['V'])
        for mat in np.unique(m['mat']):
            sel = m['T'][m['mat'] == mat]
            if not len(sel): continue
            cent = P[sel].mean(1)
            # on route par triangle seulement pour les matériaux qui dépendent du côté
            if mat in ('cligno', 'cligno.001', '2008p24_indicator', '2008p24_signal_l', '2008p24_signal_r', '2008p24_brake'):
                for side in range(2):
                    sm = (cent[:, 0] > 0) == bool(side) if mat != '2008p24_brake' else np.ones(len(sel), bool)
                    if not sm.any(): continue
                    o, g = route(cfg, m, mat, np.array([1.0 if side else -1.0, 0, cent[sm][:, 2].mean()]))
                    groups.setdefault((o, g, mat), []).append((P, sel[sm]))
                    if mat == '2008p24_brake': break
            else:
                o, g = route(cfg, m, mat, cent.mean(0))
                if g in ('other', 'in', 'under') and m['name'] not in cfg['door'] and not o.startswith('door'):
                    cab = in_cabin(cent)
                    seat = in_seat(cent) & cab
                    keep_o = ~cab
                    if (cab & ~seat).any():
                        groups.setdefault(('in', 'cabin', mat), []).append((P, sel[cab & ~seat]))
                    sel = sel[keep_o]
                    if not len(sel): continue
                groups.setdefault((o, g, mat), []).append((P, sel))
    # --- budget : ratio commun
    sizes = {k: sum(len(t) for _, t in v) for k, v in groups.items()}
    def total(r): return sum(min(n, max(8, n * min(1.0, r * GROUP_MULT[k[1]]))) for k, n in sizes.items() if k[1] not in ('paint', 'cabin'))
    lo, hi = 1e-4, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if total(mid) > BUDGET - PAINT_TARGET - CABIN_TARGET: hi = mid
        else: lo = mid
    r = lo
    print('tris source', sum(sizes.values()), 'ratio', round(r, 4), 'cabine source', sum(n for k, n in sizes.items() if k[1] == 'cabin'))
    # --- géométrie finale
    res = {}
    # peinture : toute la coque est soudée et simplifiée d'un bloc (bords préservés = pas de fissures
    # entre portes/ailes), puis chaque triangle est rendu à l'objet source le plus proche.
    from scipy.spatial import cKDTree
    pk = [k for k in groups if k[1] == 'paint']
    srcP, srcL = [], []
    for k in pk:
        for P, t in groups[k]:
            tri = P[t]                                  # (m,3,3)
            srcP.append(tri.mean(1)); srcL += [k[0]] * len(t)
    allP = np.vstack([np.vstack([P[t].reshape(-1, 3) for P, t in groups[k]]) for k in pk])
    V, F = decimate(allP, np.arange(len(allP)).reshape(-1, 3), PAINT_TARGET)
    kd = cKDTree(np.vstack(srcP)); _, nn = kd.query(V[F].mean(1))
    lab = np.array(srcL)[nn]
    for o in np.unique(lab):
        res.setdefault(o, []).append(('paint', 'paint', V, F[lab == o]))
    # habitacle : même méthode (coque soudée, bords préservés, matériau rendu par le triangle source le plus proche)
    ck = [k for k in groups if k[1] == 'cabin']
    if ck:
        cP, cL = [], []
        for k in ck:
            for P, t in groups[k]:
                cP.append(P[t].mean(1)); cL += [k[2]] * len(t)
        allc = np.vstack([np.vstack([P[t].reshape(-1, 3) for P, t in groups[k]]) for k in ck])
        Vc, Fc = decimate(allc, np.arange(len(allc)).reshape(-1, 3), CABIN_TARGET)
        _, nn = cKDTree(np.vstack(cP)).query(Vc[Fc].mean(1))
        labc = np.array(cL)[nn]
        for mt in np.unique(labc):
            res.setdefault('in', []).append(('cabin', mt, Vc, Fc[labc == mt]))
    for k, parts in groups.items():
        o, g, mat = k
        if g in ('paint', 'cabin'): continue
        Ps = np.vstack([P[t].reshape(-1, 3) for P, t in parts])
        T = np.arange(len(Ps)).reshape(-1, 3)
        tgt = max(8, int(sizes[k] * min(1.0, r * GROUP_MULT[g])))
        V, F = cluster(Ps, T, tgt)
        res.setdefault(o, []).append((g, mat, V, F))
    for o, lst in sorted(res.items()):
        print('  ', o, [(g, mt, len(F)) for g, mt, V, F in lst])
    allV = np.vstack([V for lst in res.values() for _, _, V, _ in lst])
    lo_, hi_ = allV.min(0), allV.max(0)
    print('bbox', lo_.round(2), hi_.round(2), 'tris', sum(len(F) for lst in res.values() for _, _, _, F in lst))
    # --- atlas
    ppm = min(1000 / (hi_[2] - lo_[2] + 0.1), 1000 / (3 * (hi_[1] - lo_[1]) + (hi_[0] - lo_[0]) * 2))
    Lz, Hy, Wx = hi_[2] - lo_[2], hi_[1] - lo_[1], hi_[0] - lo_[0]
    y = 20
    reg = {}
    reg['left'] = (0, y, int(Lz * ppm), int(Hy * ppm)); y += int(Hy * ppm) + 2
    reg['right'] = (0, y, int(Lz * ppm), int(Hy * ppm)); y += int(Hy * ppm) + 2
    reg['top'] = (0, y, int(Lz * ppm), int(Wx * ppm)); y += int(Wx * ppm) + 2
    reg['front'] = (0, y, int(Wx * ppm), int(Hy * ppm))
    reg['rear'] = (int(Wx * ppm) + 4, y, int(Wx * ppm), int(Hy * ppm))
    assert y + int(Hy * ppm) <= ATLAS, (y, Hy * ppm, ppm)
    atlas = np.zeros((ATLAS, ATLAS, 4), np.uint8); atlas[..., 3] = 255; atlas[..., :3] = 12
    for name, (x0, y0, w, h) in reg.items():
        atlas[y0:y0 + h, x0:x0 + w, :3] = PLACEHOLDER
    cells = {}
    def cell(col, alpha=255):
        c = tuple(int(x) for x in col)
        if max(abs(c[i] - PLACEHOLDER[i]) for i in range(3)) < 36 and alpha == 255:
            c = tuple(int(x * 0.78) for x in c)
        k = (c, alpha)
        if k not in cells:
            i = len(cells); cells[k] = i
            cx, cy = (i % 128) * 8, (i // 128) * 8
            atlas[cy:cy + 8, cx:cx + 8] = (*c, alpha)
        i = cells[k]
        return ((i % 128) * 8 + 4) / ATLAS, 1 - ((i // 128) * 8 + 4) / ATLAS
    def proj(P, n):
        a = np.abs(n)
        ax = int(np.argmax(a))
        if ax == 0: nm = 'left' if n[0] > 0 else 'right'
        elif ax == 1: nm = 'top' if n[1] > 0 else None
        else: nm = 'front' if n[2] > 0 else 'rear'
        if nm is None: return None
        x0, y0, w, h = reg[nm]
        if nm == 'left': u, v = (P[:, 2] - lo_[2]) * ppm, (hi_[1] - P[:, 1]) * ppm
        elif nm == 'right': u, v = (hi_[2] - P[:, 2]) * ppm, (hi_[1] - P[:, 1]) * ppm
        elif nm == 'top': u, v = (P[:, 2] - lo_[2]) * ppm, (hi_[0] - P[:, 0]) * ppm
        elif nm == 'front': u, v = (hi_[0] - P[:, 0]) * ppm, (hi_[1] - P[:, 1]) * ppm
        else: u, v = (P[:, 0] - lo_[0]) * ppm, (hi_[1] - P[:, 1]) * ppm
        u = np.clip(u, 1, w - 1) + x0; v = np.clip(v, 1, h - 1) + y0
        return np.c_[u / ATLAS, 1 - v / ATLAS]
    # --- écriture OBJ
    order = ['body', 'doorFL', 'doorFR', 'doorRL', 'doorRR', 'hood', 'hatch', 'in', 'steeringwheel', 'under']
    names = sorted(res, key=lambda o: (order.index(o) if o in order else 50, o))
    vl, vtl, vnl, lines = [], [], [], []
    base_v = base_vt = base_vn = 1
    ntri = 0
    for o in names:
        lines.append(f'o {o}')
        for g, mat, V, F in res[o]:
            if g == 'cabin':   # ombrage facetté net : sommets non partagés
                V = V[F].reshape(-1, 3); F = np.arange(len(V)).reshape(-1, 3)
                fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
                fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
                N = np.repeat(fn, 3, axis=0)
            else:
                N = vnormals(V, F)
            vl.append(V); vnl.append(N)
            vt_rows = []
            flines = []
            for fi, f in enumerate(F):
                fnrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
                ln = np.linalg.norm(fnrm)
                fnrm = fnrm / ln if ln > 0 else np.array([0, 1.0, 0])
                if g == 'paint':
                    uv = proj(V[f], fnrm)
                    if uv is None:
                        c = cell((40, 40, 44)); uv = np.tile(c, (3, 1))
                else:
                    if g == 'glass':
                        col = (170, 0, 0) if mat in cfg['glass_red'] else (0, 0, 0)
                        c = cell(col, 120 if mat in cfg['glass_red'] else 113)
                    else:
                        col = cfg['colors'].get(mat, (60, 60, 64))
                        if g == 'cabin':   # habitacle : ciel de toit clair, plancher foncé, le reste suit le matériau
                            cy = (V[f][:, 1].mean())
                            if fnrm[1] < -0.5 and cy > roof_y - 0.35: col = (165, 162, 152)
                            elif fnrm[1] > 0.6 and cy < cab_lo[1] + 0.35: col = (52, 52, 56)
                            else: col = tuple(int(max(x, 42)) for x in col)
                        c = cell(col)
                    uv = np.tile(c, (3, 1))
                vt_rows.append(uv)
                ntri += 1
            VT = np.vstack(vt_rows)
            vtl.append(VT)
            for fi, f in enumerate(F):
                a, b, c = (base_v + f[0], base_v + f[1], base_v + f[2])
                t = base_vt + fi * 3
                flines.append(f'f {a}/{t}/{base_vn + f[0]} {b}/{t + 1}/{base_vn + f[1]} {c}/{t + 2}/{base_vn + f[2]}')
            lines.extend(flines)
            base_v += len(V); base_vn += len(V); base_vt += len(VT)
    out = os.path.join(work, cfg['id']); os.makedirs(out, exist_ok=True)
    with open(f'{out}/{cfg["id"]}.obj', 'w') as fh:
        fh.write('# genere par peugeot.py\n')
        for V in vl: np.savetxt(fh, V, fmt='v %.4f %.4f %.4f')
        for V in vtl: np.savetxt(fh, V, fmt='vt %.5f %.5f')
        for V in vnl: np.savetxt(fh, V, fmt='vn %.4f %.4f %.4f')
        fh.write('\n'.join(lines) + '\n')
    Image.fromarray(atlas, 'RGBA').save(f'{out}/{cfg["id"]}_base.png')
    json.dump(dict(fit=fitinfo, tris=ntri, bbox=[lo_.tolist(), hi_.tolist()], cells=len(cells)), open(f'{out}/meta.json', 'w'))
    print('ecrit', out, ntri, 'tris', len(cells), 'couleurs')


if __name__ == '__main__':
    root, work, key = sys.argv[1:4]
    SCRATCH = os.environ.get('SCRATCH', work)
    build(root, work, key)
