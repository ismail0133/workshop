#!/bin/sh
# Blocklist reconciler (POSIX sh, sourced by entrypoint.sh).
#
#   /blocklist/blocklist.txt   one entry per line:  1.2.3.4 | 10.0.0.0/24 | ::1 | ua:token
#   /blocklist/allowlist.txt   same syntax (IPs only) - never blocked (validator, ...)
#
# Every change is rendered to an nginx geo/map file, checked with `nginx -t`,
# and only then applied with `nginx -s reload`. If the check fails the previous
# valid configuration stays active and the error is logged + exposed in
# /tmp/waf/status.json (GET :8081/blocklist-status).
#
# The remediation side only needs to write blocklist.txt (atomically: write a
# temp file then `mv`). It never touches nginx, docker or this container.

BL_DIR="${BLOCKLIST_DIR:-/blocklist}"
WORK="${WAF_WORK_DIR:-/tmp/waf}"
OUT="$WORK/blocklist.conf"
STATUS="$WORK/status.json"
INTERVAL="${BLOCKLIST_POLL_SECONDS:-1}"
MAX_ENTRIES="${BLOCKLIST_MAX_ENTRIES:-5000}"
# A ua: token that is a substring of this string would block ordinary browsers -> refused.
BROWSER_UA_SAMPLE="mozilla/5.0 (windows nt 10.0; win64; x64; linux; android; iphone; macintosh; intel mac os x) applewebkit/537.36 (khtml, like gecko) chrome/155.0.0.0 safari/537.36 edg/155 firefox/130 version/17 mobile opr/100"

_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# log EVENT DETAIL  -> JSON line on stderr (collected with the container logs)
log() {
    d=$(printf '%s' "$2" | tr -d '"\\' | tr '\n\r\t' '   ' | cut -c1-300)
    printf '{"ts":"%s","service":"waf","component":"blocklist","event":"%s","detail":"%s"}\n' \
        "$(_now)" "$1" "$d" >&2
}

valid_ipv4() {
    awk -v s="$1" 'BEGIN {
        n = split(s, a, "/"); if (n > 2) exit 1
        if (n == 2 && (a[2] !~ /^[0-9][0-9]?$/ || a[2] + 0 > 32)) exit 1
        if (split(a[1], o, ".") != 4) exit 1
        for (i = 1; i <= 4; i++) if (o[i] !~ /^[0-9][0-9]?[0-9]?$/ || o[i] + 0 > 255) exit 1
        exit 0 }'
}

valid_ipv6() {
    printf '%s' "$1" | grep -Eq '^[0-9A-Fa-f:]{2,39}(/[0-9]{1,3})?$' || return 1
    case "$1" in *:*) ;; *) return 1 ;; esac
    case "$1" in
        */*) m=${1#*/}; [ "$m" -le 128 ] 2>/dev/null || return 1 ;;
    esac
    # structure: <= 4 hex digits per group, at most one "::", 8 groups (or fewer with "::")
    awk -v s="${1%%/*}" 'BEGIN {
        t = s; dc = gsub(/::/, "::", t); if (dc > 1 || s ~ /:::/) exit 1
        n = split(s, g, ":"); ne = 0
        for (i = 1; i <= n; i++) { if (length(g[i]) > 4) exit 1; if (g[i] != "") ne++ }
        if (dc == 1 && ne > 7) exit 1
        if (dc == 0 && (n != 8 || ne != 8)) exit 1
        exit 0 }' || return 1
    return 0
}

is_ip() {
    case "$1" in
        *:*) valid_ipv6 "$1" ;;
        *)   valid_ipv4 "$1" ;;
    esac
}

# clean FILE -> comment/blank-free, unique, size-capped entries on stdout
clean() {
    [ -r "$1" ] || return 0
    tr -d '\r' < "$1" \
        | sed -e 's/#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
        | grep -v '^$' | head -n "$MAX_ENTRIES" | sort -u
}

# render SNAPSHOT_BL SNAPSHOT_AL OUTFILE
render() {
    : > "$WORK/ip.tmp"; : > "$WORK/ua.tmp"; : > "$WORK/al.tmp"
    clean "$1" | while read -r e; do
        case "$e" in
            ua:*)
                t=${e#ua:}
                if ! printf '%s' "$t" | grep -Eq '^[A-Za-z0-9._-]{4,64}$'; then
                    log REJECTED_ENTRY "$e"
                elif printf '%s' "$BROWSER_UA_SAMPLE" | grep -Fqi -- "$t"; then
                    log REJECTED_ENTRY "$e (matches normal browsers)"
                else
                    printf '%s\n' "$t" >> "$WORK/ua.tmp"
                fi ;;
            *)
                if is_ip "$e"; then printf '%s\n' "$e" >> "$WORK/ip.tmp"
                else log REJECTED_ENTRY "$e"; fi ;;
        esac
    done
    clean "$2" | while read -r e; do
        if is_ip "$e"; then printf '%s\n' "$e" >> "$WORK/al.tmp"
        else log REJECTED_ALLOW_ENTRY "$e"; fi
    done
    {
        echo "# generated $(_now) - DO NOT EDIT (source: $BL_DIR/blocklist.txt)"
        echo 'geo $blocked_ip {'
        echo '    default 0;'
        sed 's/.*/    & 1;/' "$WORK/ip.tmp"
        echo '}'
        echo 'geo $never_block {'
        echo '    default 0;'
        echo '    127.0.0.0/8 1;'
        echo '    ::1/128 1;'
        echo '    172.16.0.0/12 1;      # Docker bridge gateways: all clients look like this behind Docker Desktop'
        echo '    192.168.65.0/24 1;    # Docker Desktop VM gateway'
        sed 's/.*/    & 1;/' "$WORK/al.tmp"
        echo '}'
        echo 'map $http_user_agent $blocked_ua {'
        echo '    default 0;'
        sed -e 's/\./[.]/g' -e 's/.*/    "~*&" 1;/' "$WORK/ua.tmp"
        echo '}'
    } > "$3"
}

write_status() { # $1=sha $2=last_error
    e=$(printf '%s' "$2" | tr -d '"\\' | tr '\n\r\t' '   ' | cut -c1-300)
    nip=$(wc -l < "$WORK/ip.tmp" 2>/dev/null | tr -d ' '); nua=$(wc -l < "$WORK/ua.tmp" 2>/dev/null | tr -d ' ')
    nal=$(wc -l < "$WORK/al.tmp" 2>/dev/null | tr -d ' ')
    printf '{"applied_sha":"%s","blocked_ips":%s,"blocked_user_agents":%s,"allowlisted":%s,"updated_at":"%s","last_error":"%s"}\n' \
        "$APPLIED_SHA" "${nip:-0}" "${nua:-0}" "${nal:-0}" "$(_now)" "$e" > "$STATUS.tmp" && mv -f "$STATUS.tmp" "$STATUS"
}

# swap_config -> 0 if the new config passes `nginx -t` (and is now in place)
swap_config() {
    [ -f "$OUT" ] && cp -f "$OUT" "$WORK/blocklist.conf.bak"
    render "$WORK/bl.snap" "$WORK/al.snap" "$WORK/blocklist.conf.new" || return 1
    cp -f "$WORK/blocklist.conf.new" "$OUT"
    if err=$(nginx -t 2>&1); then
        return 0
    fi
    LAST_ERROR=$(printf '%s' "$err" | head -n 3)
    if [ -f "$WORK/blocklist.conf.bak" ]; then cp -f "$WORK/blocklist.conf.bak" "$OUT"; fi
    return 1
}

snapshot() {
    if [ -r "$BL_DIR/blocklist.txt" ]; then cp -f "$BL_DIR/blocklist.txt" "$WORK/bl.snap"; else : > "$WORK/bl.snap"; fi
    if [ -r "$BL_DIR/allowlist.txt" ]; then cp -f "$BL_DIR/allowlist.txt" "$WORK/al.snap"; else : > "$WORK/al.snap"; fi
    cat "$WORK/bl.snap" "$WORK/al.snap" | sha256sum | cut -d' ' -f1
}

# init_blocklist: first render before nginx starts (never fails the container)
init_blocklist() {
    mkdir -p "$WORK" /tmp/nginx
    LAST_ERROR=""; APPLIED_SHA=""
    cur=$(snapshot)
    if swap_config; then
        APPLIED_SHA=$cur; log APPLIED "startup sha=$cur"
    else
        log REJECTED_CONFIG "startup: $LAST_ERROR - starting with an EMPTY blocklist"
        : > "$WORK/bl.snap"; : > "$WORK/al.snap"
        swap_config || log FATAL "empty blocklist rejected: $LAST_ERROR"
    fi
    write_status "$APPLIED_SHA" "$LAST_ERROR"
    LAST_SEEN=$cur
}

watch_loop() {
    while :; do
        sleep "$INTERVAL"
        cur=$(snapshot)
        [ "$cur" = "$LAST_SEEN" ] && continue
        LAST_SEEN=$cur
        LAST_ERROR=""
        if swap_config; then
            if nginx -s reload 2>/dev/null; then
                APPLIED_SHA=$cur
                log APPLIED "sha=$cur ips=$(wc -l < "$WORK/ip.tmp" | tr -d ' ') ua=$(wc -l < "$WORK/ua.tmp" | tr -d ' ')"
            else
                LAST_ERROR="reload failed"
                log RELOAD_FAILED "sha=$cur"
            fi
        else
            log REJECTED_CONFIG "$LAST_ERROR - previous valid blocklist kept"
        fi
        write_status "$APPLIED_SHA" "$LAST_ERROR"
    done
}
