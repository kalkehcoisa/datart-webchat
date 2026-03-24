#!/usr/bin/env bash

cd backend || exit 1

poetry install
poetry run pytest tests/ -v "$@"
