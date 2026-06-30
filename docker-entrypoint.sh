#!/bin/sh
set -e

# PUID/PGID: the uid/gid hm-api will run as after the entrypoint drops root.
# Defaults to 1000:1000, matching the typical non-root user on NAS/Linux hosts,
# so a bind-mounted cred directory works without a manual chown.
PUID="${PUID:-1000}"
PGID="${PGID:-$PUID}"
CRED_DIR="${HM_API_CRED_DIR:-/data/cred}"
mkdir -p "$CRED_DIR"

# The app writes credential files with 0600 (owner-only). For the container
# process to read/write them -- whether on a named volume or a bind-mounted
# host directory -- the cred dir must be owned by the uid we drop to. When
# started as root, fix ownership here then drop privileges via gosu before
# exec'ing hm-api.
if [ "$(id -u)" = "0" ]; then
    chown -R "$PUID:$PGID" "$CRED_DIR"
    : "${HOME:=/tmp}"
    export HOME
    exec gosu "$PUID:$PGID" "$@"
fi

# Already non-root (e.g. `user:` set in compose) -- run as-is, no chown.
exec "$@"
