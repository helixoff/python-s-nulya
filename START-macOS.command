#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
python3 app.py
result=$?
if [ "$result" -ne 0 ]; then
    echo "Install Python 3.11+ with Tkinter. See START-HERE.html."
    read -r -p "Press Enter to close."
fi
