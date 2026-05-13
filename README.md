# Registre national des gels — miroir automatisé

Ce dépôt est un **miroir non officiel** du registre national des gels publié
par la **Direction générale du Trésor** (DG Trésor, ministère de l'Économie),
en application des articles **L. 562-1 et suivants** et **R. 562-2 du code
monétaire et financier**.

## Pourquoi un miroir ?

Le registre officiel est publié à l'adresse
<https://gels-avoirs.dgtresor.gouv.fr/> et exposé via une API JSON publique
(`/ApiPublic/api/v1/publication/derniere-publication-fichier-json`).

Cet endpoint **n'est pas accessible depuis tous les environnements
d'exécution sandboxés** — notamment depuis le sandbox de Claude Desktop, qui
impose une whitelist réseau restrictive. En revanche,
`raw.githubusercontent.com` est largement accessible. Ce miroir permet donc à
des outils sandboxés (typiquement la skill `lcbft-check`) d'accéder à des
données fonctionnellement équivalentes au registre officiel.

La copie est rafraîchie automatiquement **toutes les 12 heures** par une
GitHub Action. C'est conforme à la pratique du marché : tous les systèmes
LCB-FT commerciaux (Pappers, World-Check, etc.) travaillent sur copie locale
rafraîchie périodiquement, et la DG Trésor elle-même recommande dans sa FAQ
de télécharger le registre puis de filtrer en local.

## Avertissement juridique

Ce dépôt **n'est pas une publication officielle**. La seule source faisant
foi est le registre publié par la DG Trésor. Une vérification croisée avec
le registre officiel doit être effectuée pour tout dossier critique.

L'écart maximal théorique entre ce miroir et le registre officiel est de
**12 heures** ; en pratique il est généralement inférieur à 6 heures
(fréquence de publication DG Trésor irrégulière, souvent moins d'une mesure
par jour).

La date exacte de fraîcheur est lisible dans `metadata.json` (champ `as_of`).

## Fichiers publiés

| Fichier | Description | Taille |
|---|---|---|
| `registre.json` | Copie intégrale, octet pour octet, de la réponse JSON de l'API DG Trésor. | ~11 Mo |
| `index.json` | Index allégé, structuré pour le matching rapide (Nom, Prénoms, DDN, Alias, Identifications, NumeroOMI, clé normalisée). Ne contient ni MOTIFS ni FONDEMENT_JURIDIQUE — pour ces champs, se référer à `registre.json`. | ~3 Mo |
| `metadata.json` | Méta-données du snapshot : date de publication DG Trésor (`as_of`), date du dernier sync (`generated_at`), nombre de mesures, hash SHA-256 du registre brut, URL source, version du schéma. | <1 Ko |

URLs publiques (raw) :

```
https://raw.githubusercontent.com/kyros-legal/registre-gels-mirror/main/registre.json
https://raw.githubusercontent.com/kyros-legal/registre-gels-mirror/main/index.json
https://raw.githubusercontent.com/kyros-legal/registre-gels-mirror/main/metadata.json
```

## Schéma de l'index slim

Chaque entrée de `index.json` (clé `entries`, tableau) :

```json
{
  "IdRegistre": 4240,
  "Nature": "Personne physique",
  "Nom": "SHILKIN",
  "Prenoms": ["Grigory Vladimirovich"],
  "DatesNaissance": [{"jour": "20", "mois": "10", "annee": "1976"}],
  "Alias": ["Григорий Владимирович ШИЛКИН"],
  "Nationalites": [],
  "LieuxNaissance": [],
  "Identifications": [],
  "Adresses": [],
  "NumeroOMI": [],
  "_search": "SHILKIN GRIGORY VLADIMIROVICH"
}
```

Le champ `_search` est une concaténation normalisée (transliteration ASCII,
mise en majuscules, suppression des diacritiques, normalisation des espaces)
de `Nom + " " + Prenoms` (PP/Navire) ou de `Nom + Alias` (PM). Il permet un
matching simple par recherche de sous-chaîne côté consommateur, sans
re-normaliser à chaque requête.

## Fréquence de mise à jour

L'Action `sync` tourne en cron toutes les 12 heures (00:05 UTC et 12:05 UTC).
Elle peut aussi être déclenchée manuellement (`workflow_dispatch`).

Si le hash SHA-256 du registre n'a pas changé depuis le dernier snapshot,
**aucun commit n'est créé** pour limiter le bruit dans l'historique git.

## Politique de respect de la source

L'Action envoie systématiquement le header `User-Agent` requis par la DG
Trésor (obligatoire depuis le 21 janvier 2025) au format :

```
User-Agent: registre-gels-mirror/1.0 (+https://github.com/kyros-legal/registre-gels-mirror)
```

Une seule requête toutes les 12 heures, conformément à la recommandation de
filtrage local émise par la DG Trésor.

## Vérification d'intégrité

Le SHA-256 du `registre.json` est exposé dans `metadata.json`. Pour vérifier :

```bash
curl -L -o registre.json https://raw.githubusercontent.com/kyros-legal/registre-gels-mirror/main/registre.json
curl -L https://raw.githubusercontent.com/kyros-legal/registre-gels-mirror/main/metadata.json | jq -r '.sha256_registre'
shasum -a 256 registre.json
```

Les deux empreintes doivent coïncider.

## Licence

Les données publiées par la DG Trésor relèvent du régime des informations
publiques (loi CADA, licence ouverte Etalab par défaut). Ce miroir, en tant
qu'œuvre dérivée minimale (téléchargement + reformatage technique sans
altération de fond), est diffusé sous la même **licence ouverte Etalab 2.0**.

Le code des scripts et des workflows GitHub Actions de ce dépôt est diffusé
sous licence **MIT** (voir `LICENSE`).

## Lien avec la skill `lcbft-check`

Ce miroir est principalement consommé par la skill Claude `lcbft-check`,
développée par le cabinet **Kyros Avocats** (Montpellier, AARPI) pour
automatiser les diligences LCB-FT des avocats français. Voir
<https://github.com/kyros-legal/lcbft-check> (à venir).

## Contact et signalement

Pour signaler un dysfonctionnement du miroir (Action en échec, registre
obsolète, hash divergent), ouvrir une **issue** sur ce dépôt.

Pour tout problème lié aux **données elles-mêmes** (contestation d'une
mesure, erreur d'identité, demande de radiation), s'adresser **directement à
la DG Trésor** — ce miroir ne reproduit que ce qui figure dans la source
officielle.
