#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit l'index slim et les métadonnées à partir du registre brut.

Lit `registre.json` (réponse brute de l'API DG Trésor), produit :
- `index.json` : liste allégée optimisée pour le matching côté utilisateur
- `metadata.json` : méta du snapshot (as_of, count, sha256, source_url, …)

Usage :
    python3 scripts/build_index.py \\
        --input registre.json \\
        --index index.json \\
        --metadata metadata.json \\
        --source-url https://gels-avoirs.dgtresor.gouv.fr/ApiPublic/api/v1/publication/derniere-publication-fichier-json

Code de sortie :
    0 : succès
    1 : erreur (entrée illisible, structure inattendue, etc.)
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"


def normalize(text: str) -> str:
    """Normalise une chaîne pour la recherche : NFKD, sans diacritiques, ASCII upper, espaces écrasés."""
    if not text:
        return ""
    nfd = unicodedata.normalize("NFKD", text)
    no_diac = "".join(c for c in nfd if not unicodedata.combining(c))
    ascii_only = no_diac.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only.upper()).strip()


def extract_values(detail: list, type_champ: str) -> list:
    """Récupère la liste des `Valeur` pour un TypeChamp donné dans un RegistreDetail."""
    for rd in detail:
        if rd.get("TypeChamp") == type_champ:
            return rd.get("Valeur", []) or []
    return []


def build_entry(measure: dict) -> dict:
    """Construit une entrée d'index slim à partir d'une mesure du registre brut."""
    detail = measure.get("RegistreDetail", []) or []
    nature = measure.get("Nature", "")
    nom = measure.get("Nom", "") or ""

    # Prénoms (uniquement personnes physiques en pratique)
    prenoms = [v.get("Prenom", "") for v in extract_values(detail, "PRENOM") if v.get("Prenom")]

    # Dates de naissance — on conserve la structure jour/mois/année telle que publiée
    dates_naissance = []
    for v in extract_values(detail, "DATE_DE_NAISSANCE"):
        dn = {k: v.get(k, "") for k in ("jour", "mois", "annee") if v.get(k)}
        # Capitalisation variable côté DG Trésor — on normalise les clés en minuscules
        dn_norm = {}
        for k in ("Jour", "Mois", "Annee", "jour", "mois", "annee"):
            if v.get(k):
                dn_norm[k.lower()] = v[k]
        if dn_norm:
            dates_naissance.append(dn_norm)

    # Alias (toutes natures)
    alias = [v.get("Alias", "") for v in extract_values(detail, "ALIAS") if v.get("Alias")]

    # Nationalités (personnes physiques)
    nationalites = [
        v.get("Pays", "") or v.get("Nationalite", "")
        for v in extract_values(detail, "NATIONALITE")
        if v.get("Pays") or v.get("Nationalite")
    ]

    # Lieux de naissance
    lieux_naissance = [
        v.get("Lieu", "") or v.get("LieuNaissance", "")
        for v in extract_values(detail, "LIEU_DE_NAISSANCE")
        if v.get("Lieu") or v.get("LieuNaissance")
    ]

    # Identifications (personnes morales : numéros SIREN, TVA, enregistrement)
    identifications = []
    for v in extract_values(detail, "IDENTIFICATION"):
        ident = v.get("Identification", "")
        commentaire = v.get("Commentaire", "")
        if ident and ident != "/":
            identifications.append({"identification": ident, "commentaire": commentaire})

    # Adresses
    adresses = []
    for tc in ("ADRESSE_PM", "ADRESSE_PP"):
        for v in extract_values(detail, tc):
            adr = v.get("Adresse", "")
            pays = v.get("Pays", "")
            if adr or pays:
                adresses.append({"adresse": adr, "pays": pays})

    # Numéro OMI (navires)
    numero_omi = [v.get("NumeroOMI", "") for v in extract_values(detail, "NUMERO_OMI") if v.get("NumeroOMI")]

    # Passeports
    passeports = [
        v.get("NumeroPasseport", "") or v.get("Passeport", "")
        for v in extract_values(detail, "PASSEPORT")
        if v.get("NumeroPasseport") or v.get("Passeport")
    ]

    # Référence UE (personnes morales)
    references_ue = [v.get("ReferenceUe", "") for v in extract_values(detail, "REFERENCE_UE") if v.get("ReferenceUe")]

    # Clé de recherche normalisée : Nom + tous les prénoms + tous les alias
    search_components = [nom] + prenoms + alias
    search_key = " ".join(normalize(s) for s in search_components if s).strip()

    return {
        "IdRegistre": measure.get("IdRegistre"),
        "Nature": nature,
        "Nom": nom,
        "Prenoms": prenoms,
        "DatesNaissance": dates_naissance,
        "Alias": alias,
        "Nationalites": nationalites,
        "LieuxNaissance": lieux_naissance,
        "Identifications": identifications,
        "Adresses": adresses,
        "Passeports": passeports,
        "ReferencesUe": references_ue,
        "NumeroOMI": numero_omi,
        "_search": search_key,
    }


def main():
    parser = argparse.ArgumentParser(description="Construit index.json et metadata.json depuis registre.json")
    parser.add_argument("--input", required=True, help="Chemin du registre brut (JSON DG Trésor)")
    parser.add_argument("--index", required=True, help="Chemin de sortie pour index.json")
    parser.add_argument("--metadata", required=True, help="Chemin de sortie pour metadata.json")
    parser.add_argument(
        "--source-url",
        required=True,
        help="URL source du registre brut (à recopier dans metadata.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    try:
        raw_bytes = input_path.read_bytes()
    except OSError as e:
        print(f"Lecture impossible de {input_path} : {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        print(f"JSON invalide dans {input_path} : {e}", file=sys.stderr)
        sys.exit(1)

    publications = data.get("Publications") or {}
    measures = publications.get("PublicationDetail") or []
    date_publication = publications.get("DatePublication", "")

    if not measures:
        print("Aucune mesure trouvée dans le registre — abandon par sécurité.", file=sys.stderr)
        sys.exit(1)

    entries = [build_entry(m) for m in measures]

    # Comptes par nature, pour le metadata
    counts_by_nature = {}
    for e in entries:
        nat = e["Nature"] or "Inconnu"
        counts_by_nature[nat] = counts_by_nature.get(nat, 0) + 1

    # Hash SHA-256 du registre brut (sur les octets tels que reçus)
    sha256_registre = hashlib.sha256(raw_bytes).hexdigest()

    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "as_of": date_publication,
        "count": len(entries),
        "entries": entries,
    }
    metadata_payload = {
        "schema_version": SCHEMA_VERSION,
        "as_of": date_publication,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": args.source_url,
        "count": len(entries),
        "counts_by_nature": counts_by_nature,
        "sha256_registre": sha256_registre,
        "size_registre_bytes": len(raw_bytes),
    }

    Path(args.index).write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=None, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    Path(args.metadata).write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"OK — {len(entries)} mesures indexées ({counts_by_nature})")
    print(f"     as_of           : {date_publication}")
    print(f"     sha256(registre): {sha256_registre}")
    print(f"     index.json      : {args.index}")
    print(f"     metadata.json   : {args.metadata}")


if __name__ == "__main__":
    main()
