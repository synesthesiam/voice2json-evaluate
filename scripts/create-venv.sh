#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

venv="${src_dir}/.venv"
rm -rf "${venv}"

: "${PYTHON=python3}"
"${PYTHON}" -m venv "${venv}"
source "${venv}/bin/activate"

pip3 install --upgrade pip
pip3 install --upgrade wheel setuptools
pip3 install -r "${src_dir}/requirements.txt"
pip3 install -r "${src_dir}/requirements_dev.txt" || true

echo "OK"
