#!/bin/sh
# If no DB exists, copy the seed DB with pre-built templates
if [ ! -f /app/data/report_engine.db ]; then
    cp /app/seed_data.db /app/data/report_engine.db
    echo "Initialized DB with 11 templates"
fi
exec uvicorn main:app --host 0.0.0.0 --port 8000
