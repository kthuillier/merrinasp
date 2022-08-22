#!/usr/bin/env bash

python -m pip install --upgrade pip
python -m pip install virtualenv
python -m virtualenv .venv

source ./.venv/bin/activate

pip install "pip>=22.0.3"

pip install -r ./requirements/requirements-python.txt
pip install -r ./requirements/requirements-linters.txt