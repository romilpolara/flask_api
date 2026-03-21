#!/bin/sh
python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:${PORT:-8000} app.main:app
