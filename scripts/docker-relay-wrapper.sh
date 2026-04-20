#!/bin/sh
set -eu

REAL_DOCKER="/usr/local/bin/docker-real"
RELAY_DIR="/tmp/docker-port-relays"

mkdir -p "$RELAY_DIR"

extract_port() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -p|--publish)
                shift
                [ "$#" -gt 0 ] || break
                value="$1"
                host_part="${value%%:*}"
                if [ "$host_part" != "$value" ] && [ -n "$host_part" ]; then
                    printf '%s\n' "$host_part"
                    return 0
                fi
                ;;
        esac
        shift
    done
    return 1
}

start_relay() {
    port="$1"
    pidfile="$RELAY_DIR/$port.pid"
    if [ -f "$pidfile" ]; then
        existing_pid="$(cat "$pidfile" 2>/dev/null || true)"
        if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pidfile"
    fi

    nohup socat "TCP-LISTEN:${port},fork,reuseaddr" "TCP:host.docker.internal:${port}" \
        >/tmp/docker-relay-"$port".log 2>&1 &
    echo "$!" >"$pidfile"
}

stop_relays() {
    while [ "$#" -gt 0 ]; do
        target="$1"
        case "$target" in
            *[!0-9]*|"")
                ;;
            *)
                pidfile="$RELAY_DIR/$target.pid"
                if [ -f "$pidfile" ]; then
                    relay_pid="$(cat "$pidfile" 2>/dev/null || true)"
                    if [ -n "$relay_pid" ]; then
                        kill "$relay_pid" 2>/dev/null || true
                    fi
                    rm -f "$pidfile"
                fi
                ;;
        esac
        shift
    done
}

subcommand="${1:-}"

case "$subcommand" in
    run)
        relay_port="$(extract_port "$@" || true)"
        "$REAL_DOCKER" "$@"
        status=$?
        if [ "$status" -eq 0 ] && [ -n "${relay_port:-}" ]; then
            start_relay "$relay_port"
        fi
        exit "$status"
        ;;
    rm)
        shift
        "$REAL_DOCKER" rm "$@"
        status=$?
        stop_relays "$@"
        exit "$status"
        ;;
    *)
        exec "$REAL_DOCKER" "$@"
        ;;
esac
