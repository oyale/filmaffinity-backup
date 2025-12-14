#!/bin/bash
set -e

# If the first argument is "backup", run fa-backup
if [ "$1" = "backup" ]; then
    shift # Remove "backup" from the arguments
    exec fa-backup "$@"

# If the first argument is "upload", run fa-upload
elif [ "$1" = "upload" ]; then
    shift # Remove "upload" from the arguments
    exec fa-upload "$@"

# Fallback: If the user provides a custom command (like bash), run it
else
    exec "$@"
fi
