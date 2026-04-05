#!/bin/sh

PORT_TO_USE="${PORT:-8000}"
exec gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:${PORT_TO_USE}" --timeout 600 app:app
