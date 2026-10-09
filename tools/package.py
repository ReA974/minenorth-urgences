"""Génère le jar du pack (assets + métadonnées Forge + classe de chargement)."""
import zipfile, os, json, sys
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = 'MineNorth_Urgences_Pack-1.0.0.jar'
MCMETA = {"pack": {"description": "MineNorth Urgences (police, pompiers, SAMU : livrees, rampes, brancard)", "pack_format": 15}}
TOML = '''modLoader="javafml"
loaderVersion="[47,)"
license="All rights reserved"

[[mods]]
modId="minenorthpolicecar"
version="1.0.0"
displayName="MineNorth Urgences (pack MTS)"
description=\'\'\'
Vehicules d'urgence : Police Nationale (livree, BAC banalises, transport de suspects), Sapeurs-Pompiers (VSAV avec brancard) et SAMU, avec rampes bleues et sirene 2 tons francaise.
Contenu base sur Kaminari Motor Work (gvp).
\'\'\'

[[dependencies.minenorthpolicecar]]
    modId="mts"
    mandatory=true
    versionRange="[22.6.0,)"
    ordering="AFTER"
    side="BOTH"

[[dependencies.minenorthpolicecar]]
    modId="belroftmotors"
    mandatory=true
    versionRange="[1,)"
    ordering="AFTER"
    side="BOTH"

[[dependencies.minenorthpolicecar]]
    modId="gvp"
    mandatory=true
    versionRange="[2.6.1,)"
    ordering="AFTER"
    side="BOTH"
'''
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('pack.mcmeta', json.dumps(MCMETA, indent=2))
    z.writestr('META-INF/mods.toml', TOML)
    z.write('tools/java/minenorthpolicecar/ForgePackLoader.class', 'minenorthpolicecar/ForgePackLoader.class')
    for r, _, fs in os.walk('assets'):
        for f in fs:
            p = os.path.join(r, f)
            z.write(p, p.replace(os.sep, '/'))
with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
    bad = [i for i in names if i.endswith('.json') and not json.loads(z.read(i))]
    print(len(names), 'fichiers,', os.path.getsize(OUT) // 1024, 'Ko,', 'json OK' if not bad else bad)
