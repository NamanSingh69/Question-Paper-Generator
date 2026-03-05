#!/bin/sh
gunicorn app:app --workers 1 --bind 0.0.0.0:${PORT:-8000} --timeout 120
