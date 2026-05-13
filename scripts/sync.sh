#!/usr/bin/env bash
# Synchronise le registre national des gels depuis l'API DG Trésor,
# construit l'index slim et les métadonnées, et signale s'il y a un changement.
#
# Sortie standard : "CHANGED" si le hash diffère de l'ancien metadata.json,
#                   "UNCHANGED" sinon.
# Code de retour  : 0 dans tous les cas où le téléchargement+parse a réussi,
#                   non nul sinon.

set -euo pipefail

SOURCE_URL="${SOURCE_URL:-https://gels-avoirs.dgtresor.gouv.fr/ApiPublic/api/v1/publication/derniere-publication-fichier-json}"
USER_AGENT="${USER_AGENT:-registre-gels-mirror/1.0 (+https://github.com/kyros-legal/registre-gels-mirror)}"
ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

REGISTRE_PATH="${ROOT_DIR}/registre.json"
INDEX_PATH="${ROOT_DIR}/index.json"
METADATA_PATH="${ROOT_DIR}/metadata.json"
TMP_REGISTRE="$(mktemp -t registre.XXXXXX.json)"
trap 'rm -f "${TMP_REGISTRE}"' EXIT

echo "→ Téléchargement du registre depuis ${SOURCE_URL}"
HTTP_CODE=$(curl --silent --show-error --location \
    --user-agent "${USER_AGENT}" \
    --header "Accept: application/json" \
    --retry 3 --retry-delay 5 \
    --max-time 180 \
    --write-out "%{http_code}" \
    --output "${TMP_REGISTRE}" \
    "${SOURCE_URL}")

if [[ "${HTTP_CODE}" != "200" ]]; then
    echo "Échec téléchargement : HTTP ${HTTP_CODE}" >&2
    exit 2
fi

SIZE=$(wc -c < "${TMP_REGISTRE}" | tr -d ' ')
echo "✓ Téléchargé ${SIZE} octets (HTTP 200)"

# Validation JSON sanity check
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "${TMP_REGISTRE}"
echo "✓ JSON valide"

NEW_SHA256=$(shasum -a 256 "${TMP_REGISTRE}" | awk '{print $1}')
echo "  sha256 nouveau snapshot : ${NEW_SHA256}"

PREVIOUS_SHA256=""
if [[ -f "${METADATA_PATH}" ]]; then
    PREVIOUS_SHA256=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('sha256_registre',''))" "${METADATA_PATH}" 2>/dev/null || echo "")
    echo "  sha256 snapshot précédent : ${PREVIOUS_SHA256:-(absent)}"
fi

if [[ -n "${PREVIOUS_SHA256}" && "${NEW_SHA256}" == "${PREVIOUS_SHA256}" ]]; then
    echo "→ Aucun changement détecté — aucune mise à jour à committer."
    echo "UNCHANGED"
    exit 0
fi

# Le snapshot a changé : on remplace les fichiers publiés et on régénère l'index
mv "${TMP_REGISTRE}" "${REGISTRE_PATH}"
trap - EXIT  # on a déplacé le fichier, pas besoin de le supprimer

echo "→ Régénération de index.json et metadata.json"
python3 "${ROOT_DIR}/scripts/build_index.py" \
    --input "${REGISTRE_PATH}" \
    --index "${INDEX_PATH}" \
    --metadata "${METADATA_PATH}" \
    --source-url "${SOURCE_URL}"

echo "CHANGED"
