# MineNorth Urgences (pack MTS/IV : police, pompiers, SAMU)

Police Nationale (livrée, BAC, transport de suspects), Sapeurs-Pompiers (VSAV avec brancard) et SAMU, avec rampes bleues et sirène 2 tons FR, basés sur *Kaminari Motor Work* (gvp). Identifiant interne du pack : `minenorthpolicecar` (ne pas le changer : les objets `mts:minenorthpolicecar.*` en dépendent).

- Items : `mts:minenorthpolicecar.<modele>_police`, `mts:minenorthpolicecar.<modele>_bac`, `mts:minenorthpolicecar.lightbar_fr`
- Modèles livrée : audi_a6_c8a, mercedes_glc_300_4matic, mercedes_sprinter_ncv3lwb, polestar2, ford_focus_c170_5d16
- BAC (banalisés, en **noir, bleu ou rouge** : `…_bac_noir`, `…_bac_bleu`, `…_bac_rouge` ; 3 gyrophares magnétiques bleus : toit, tableau de bord, plage arrière ; ils n'apparaissent que feux activés) : audi_a6_c8a, mercedes_glc_300_4matic, ford_focus_c170_5d16
- Pièces : `mts:minenorthpolicecar.lightbar_fr` (rampe bleue + plaque POLICE NATIONALE), `mts:minenorthpolicecar.gyro_bac` (gyrophare magnétique)
- Nécessite mts + gvp (jar Kaminari). Régénération : `tools/livery.py` (livrée), `tools/lightbar.py` (rampe), `tools/gyro.py` (gyrophare BAC), `tools/build_pack.py`, puis `tools/package.py` (jar).

## Peugeot 508 GT et e-2008 (convertis depuis les FBX, sans Blender)
- Items : `mts:minenorthpolicecar.peugeot_508_gt_pn` et `mts:minenorthpolicecar.peugeot_e2008_pn` (Police Nationale, rampe 2 tons posée d'origine). Pas de variantes civiles ni BAC.
- Calés sur le véhicule donneur (Audi A6 pour le 508, Ford Focus pour l'e-2008) : suspensions, sièges (pièces gvp), moteur, portes et feux sont ceux du donneur. Roues = roues gvp par défaut.
- Habitacle : planche de bord, console, plancher, ciel de toit repris du modèle ; sièges du modèle retirés (doublon avec les pièces siège).
- ~39 000 (508) et ~55 000 (e-2008) triangles ; couleurs unies + peinture sur atlas 1024 (textures d'origine non reprises).
- Régénération : `tools/fbx.py`, `tools/peugeot.py <jar> <work> 508|2008`, `tools/peugeot_variants.py <jar> <work> <id>`, puis `PEUGEOT_WORK=<work> python tools/build_pack.py …` et `tools/package.py`.

## Bateaux Police / Pompiers et dépanneuse (modèles Belroft Motors)
- Items : `mts:minenorthpolicecar.corallum_police`, `starfish_police`, `corallum_pompier`, `starfish_pompier` (bateaux, rampe posée d'origine) et `harpy_depannage` (dépanneuse à plateau, gyrophare orange `lightbar_depannage`, sans sirène).
- Les fiches (moteurs, sièges, animations) sont celles de Belroft : **le pack dépend de `belroftmotors`** (jar Belroft Motors Mk 10).
- Livrées par recoloration des textures « gray » + décalques en coordonnées 3D (`tools/belroft.py`) ; plateau de dépanneuse construit par `build_tow_truck` (ridelles « DÉPANNAGE 24H/24 », tête de plateau, treuil, rampe fixe). Plateau fixe : ni bascule ni collision propre.
- Régénération : `BELROFT_ROOT=<jar Belroft extrait> python tools/build_pack.py …` (voir `tools/belroft_pack.py`), puis `tools/package.py`.
