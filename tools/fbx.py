"""Lecteur FBX binaire minimal (sans Blender) : géométries, modèles, matériaux, textures, transformations."""
import struct, zlib
import numpy as np


class Node:
    __slots__ = ('name', 'props', 'children')

    def __init__(self, name):
        self.name, self.props, self.children = name, [], []

    def get(self, name):
        return next((c for c in self.children if c.name == name), None)

    def all(self, name):
        return [c for c in self.children if c.name == name]


def _prop(d, o):
    t = chr(d[o]); o += 1
    if t == 'Y': return struct.unpack_from('<h', d, o)[0], o + 2
    if t == 'C': return d[o], o + 1
    if t == 'I': return struct.unpack_from('<i', d, o)[0], o + 4
    if t == 'F': return struct.unpack_from('<f', d, o)[0], o + 4
    if t == 'D': return struct.unpack_from('<d', d, o)[0], o + 8
    if t == 'L': return struct.unpack_from('<q', d, o)[0], o + 8
    if t in 'fdilb':
        n, enc, clen = struct.unpack_from('<III', d, o); o += 12
        raw = d[o:o + clen]; o += clen
        if enc: raw = zlib.decompress(raw)
        dt = {'f': '<f4', 'd': '<f8', 'i': '<i4', 'l': '<i8', 'b': 'u1'}[t]
        return np.frombuffer(raw, dt, n), o
    if t in 'SR':
        n = struct.unpack_from('<I', d, o)[0]; o += 4
        b = d[o:o + n]
        return (b.decode('utf-8', 'replace') if t == 'S' else b), o + n
    raise ValueError(t)


def parse(path):
    d = open(path, 'rb').read()
    ver = struct.unpack_from('<I', d, 23)[0]
    wide = ver >= 7500
    o = 27

    def node(o):
        if wide:
            end, nprop, plen = struct.unpack_from('<QQQ', d, o); o += 24
        else:
            end, nprop, plen = struct.unpack_from('<III', d, o); o += 12
        nl = d[o]; o += 1
        if end == 0: return None, o
        n = Node(d[o:o + nl].decode()); o += nl
        for _ in range(nprop):
            v, o = _prop(d, o); n.props.append(v)
        while o < end:
            c, o = node(o)
            if c is None: break
            n.children.append(c)
        return n, end
    root = Node('root')
    while o < len(d) - 32:
        n, o = node(o)
        if n is None: break
        root.children.append(n)
    return root


def props70(n):
    p = n.get('Properties70')
    out = {}
    if p:
        for c in p.children:
            out[c.props[0]] = c.props[4:] if len(c.props) > 4 else None
    return out


def load(path):
    """Renvoie dict: models{id:{name,parent,t,r,s,geom,mats}}, geoms, mats{id:{name,tex}}, texs{id:file}."""
    r = parse(path)
    obj = r.get('Objects')
    geoms, models, mats, texs = {}, {}, {}, {}
    for n in obj.children:
        i = n.props[0]
        nm = str(n.props[1]).split('\x00')[0]
        if n.name == 'Geometry':
            geoms[i] = n
        elif n.name == 'Model':
            p = props70(n)
            g = lambda k, dflt: np.array(p[k], float) if p.get(k) else np.array(dflt, float)
            models[i] = dict(name=nm, parent=None, t=g('Lcl Translation', [0, 0, 0]), r=g('Lcl Rotation', [0, 0, 0]),
                             s=g('Lcl Scaling', [1, 1, 1]), pre=g('PreRotation', [0, 0, 0]), geom=None, mats=[])
        elif n.name == 'Material':
            p = props70(n)
            mats[i] = dict(name=nm, tex={}, diff=p.get('DiffuseColor'), opac=(p.get('Opacity') or [1.0])[0])
        elif n.name == 'Texture':
            fn = n.get('RelativeFilename') or n.get('FileName')
            texs[i] = str(fn.props[0]).replace('\\', '/').split('/')[-1] if fn else nm
    for c in r.get('Connections').children:
        if c.props[0] != 'OO' and c.props[0] != 'OP':
            continue
        s, d = c.props[1], c.props[2]
        if s in models and d in models: models[s]['parent'] = d
        elif s in geoms and d in models: models[d]['geom'] = s
        elif s in mats and d in models: models[d]['mats'].append(s)
        elif s in texs and d in mats:
            mats[d]['tex'][c.props[3] if len(c.props) > 3 else 'x'] = texs[s]
    return models, geoms, mats, texs


def geometry(node):
    """-> (verts (n,3), tris (m,3) indices dans verts, uv (m*3 par triangle,2), matidx (m,))"""
    V = node.get('Vertices').props[0].reshape(-1, 3)
    PV = node.get('PolygonVertexIndex').props[0]
    uvn = node.get('LayerElementUV')
    uv = uvi = None
    if uvn:
        uv = uvn.get('UV').props[0].reshape(-1, 2)
        ii = uvn.get('UVIndex')
        uvi = ii.props[0] if ii else None
        mapping = uvn.get('MappingInformationType').props[0]
    mn = node.get('LayerElementMaterial')
    mats = mn.get('Materials').props[0] if mn else None
    mmap = mn.get('MappingInformationType').props[0] if mn else None
    tris, tuv, tmat = [], [], []
    poly, start, pi = [], 0, 0
    ends = np.nonzero(PV < 0)[0]
    s = 0
    for pidx, e in enumerate(ends):
        idx = PV[s:e + 1].copy(); idx[-1] = ~idx[-1]
        for k in range(1, len(idx) - 1):
            tris.append((idx[0], idx[k], idx[k + 1]))
            loc = (s, s + k, s + k + 1)
            if uv is not None:
                tuv.append([uv[uvi[l]] if uvi is not None else uv[l] for l in loc]) if mapping == 'ByPolygonVertex' else tuv.append([uv[idx[0]], uv[idx[k]], uv[idx[k + 1]]])
            tmat.append(0 if mats is None else (mats[0] if mmap == 'AllSame' else mats[pidx]))
        s = e + 1
    return V, np.array(tris), (np.array(tuv) if uv is not None else None), np.array(tmat)


def rot(e):
    a, b, c = np.radians(e)
    rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _own(m):
    M = np.eye(4)
    M[:3, :3] = rot(m['pre']) @ rot(m['r']) @ np.diag(m['s'])
    M[:3, 3] = m['t']
    return M


def world(models, i, cache={}):
    """Matrice monde. Un ancêtre qui répète exactement la transformation (échelle != 1) du mesh est ignoré
    (export doublonné du 508 : sinon l'échelle x100 s'applique deux fois)."""
    key = (id(models), i)
    if key in cache: return cache[key]
    me = models[i]
    M = _own(me)
    k = me['parent']
    while k in models:
        a = models[k]
        dup = (np.abs(a['s'] - 1).max() > 1e-6 and np.allclose(a['s'], me['s']) and np.allclose(a['t'], me['t']) and np.allclose(a['r'], me['r']))
        if not dup:
            M = _own(a) @ M
        k = a['parent']
    cache[key] = M
    return M
