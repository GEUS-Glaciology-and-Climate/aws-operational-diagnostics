#!/usr/bin/env bash
set -eu
cd /home/bav/aws-operational-diagnostics

CONDA=/home/bav/miniforge3/bin/conda
PYTHON="/home/bav/miniforge3/envs/bav/bin/python"

SKIP_THREDDS=${SKIP_THREDDS:-0}
THREDDS_DIR="/mnt/ice/Baptiste/geussnow01/thredds-data"
DATAVERSE_ROOT="/mnt/ice/Baptiste/geussnow01/dataverse"
DIAG_DIR="$HOME/aws-operational-diagnostics"

PID="doi:10.22008/FK2/IW73UU"
DV_BASE="https://dataverse.geus.dk"
MIN_CSV=30

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 1; }; }
need_cmd curl
need_cmd "$CONDA"
need_cmd git
need_cmd find
need_cmd wc
need_cmd jq

if [[ "$SKIP_THREDDS" -eq 1 ]]; then
  echo "[1/4] Skipping thredds update"
else
  echo "[1/4] Run thredds_download.py"
  cd "$THREDDS_DIR"
  $PYTHON "$THREDDS_DIR/thredds_download.py"
fi

echo "[2/4] Resolve latest Dataverse version for $PID"
meta_json="$(curl -fsSL "${DV_BASE}/api/datasets/:persistentId/?persistentId=${PID}")"
ver_major="$(jq -r '.data.latestVersion.versionNumber // empty' <<<"$meta_json")"
ver_minor="$(jq -r '.data.latestVersion.versionMinorNumber // 0' <<<"$meta_json")"

if [[ -z "$ver_major" || "$ver_major" == "null" ]]; then
  echo "Could not determine latest version from Dataverse API" >&2
  exit 1
fi

ver_label="V${ver_major}"
target_dir="${DATAVERSE_ROOT}/${ver_label}"
echo "Latest version: ${ver_major}.${ver_minor} -> ${target_dir}"

csv_count=0
if [[ -d "$target_dir" ]]; then
  csv_count="$(find "$target_dir" -type f -name '*.csv' | wc -l | tr -d ' ')"
fi

echo "CSV files in ${target_dir}: ${csv_count}"


echo "[3/4] Download CSVs if needed"

csv_count=0
if [[ -d "$target_dir" ]]; then
  csv_count="$(find "$target_dir" -type f -name '*.csv' | wc -l | tr -d ' ')"
fi
echo "CSV files in ${target_dir}: ${csv_count}"

if [[ ! -d "$target_dir" || "$csv_count" -le "$MIN_CSV" ]]; then
  echo "Running dataverse_download.py"
  $PYTHON $DIAG_DIR/dataverse_download.py \
    --base "$DV_BASE" \
    --pid "$PID" \
    --outroot "$DATAVERSE_ROOT" \
    --min-csv "$MIN_CSV" \
    --verbose
else
  echo "Dataverse folder looks OK; skipping download."
fi


set +x
echo "[4/5] Run diagnostics + commit/push"
cd "$DIAG_DIR"
git fetch
git pull

$PYTHON "$DIAG_DIR/plots_dataset_version_comparison.py" --dataverse_version "V$ver_major"
$PYTHON "$DIAG_DIR/climatologies.py" --path_thredds $THREDDS_DIR
$PYTHON "$DIAG_DIR/climatologies_transects.py" --path_thredds $THREDDS_DIR


git add -A
if ! git diff --cached --quiet; then
  git commit -m "Update dataset version comparison (Dataverse ${ver_major}.${ver_minor})"
  git push
else
  echo "No changes to commit."
fi
