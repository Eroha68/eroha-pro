#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'EROHA NO-GO: automatic Git sync is suspended in this draft until a separately controlled owner approves branch writes and release authority.' >&2
exit 41
