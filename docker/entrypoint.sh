#!/bin/sh

if [ ! -z "${CONFIG:-}" ]; then
    echo "Using config file $CONFIG"
    exec unifi-cam-proxy --config "$CONFIG"
fi

exec "$@"
