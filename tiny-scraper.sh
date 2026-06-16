#!/bin/bash

progdir="$(cd $(dirname "$0") || exit; pwd)/tiny_scraper"

export PYSDL2_DLL_PATH="/usr/lib"

program="python3 -u ${progdir}/main.py ${progdir}/config.json"
log_file="${progdir}/log.txt"

$program >> "$log_file" 2>&1

exit 0
