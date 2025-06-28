#!/usr/bin/env zsh

# test rig for FastAPI router
poetry run uvicorn route:app --host 0.0.0.0 --port 8080 --workers 4
