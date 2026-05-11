#!/bin/bash
cd "$(dirname "$0")"
echo "===================================="
echo "Refreshing library availability data"
echo "===================================="
echo
python3 scrape_availability.py
echo
python3 scrape_bpl_availability.py || echo "(BPL scrape failed — keeping previous bpl_availability.json)"
echo
echo "Rebuilding HTML..."
python3 build.py
echo
echo "===================================="
echo "Done. You can now reload the browser."
echo "===================================="
