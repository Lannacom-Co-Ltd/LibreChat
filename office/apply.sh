#!/usr/bin/env bash
# Applies the Office Files on/off switches from the local office.env to the server.
#
#   1. Edit office.env on this machine, e.g. OFFICE_WORD=on
#   2. ./office/apply.sh
#
# The script checks the switches, copies only the on/off lines to the server's office.env
# (a backup is kept; keys and passwords there are not touched), recreates office-files and
# LibreChat's api container, and prints what is on. Nothing restarts when nothing changed.
#
# Where the server is comes from these lines in the local office.env (never committed):
#   OFFICE_REMOTE=user@host
#   OFFICE_REMOTE_KEY=~/.ssh/<key>.pem
#   OFFICE_REMOTE_DIR=/opt/librechat/<name>
#   OFFICE_REMOTE_COMPOSE=-p <project> -f docker-compose.yml -f docker-compose.override.yml -f <proxy>.yml
#   OFFICE_REMOTE_PROJECT=cmu-office        (compose project of Office Files, default cmu-office)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/office.env"
COMPOSE_FILE="$ROOT/docker-compose.office.yml"

fail() { echo "ERROR: $*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || fail "office.env not found in $ROOT"

setting() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//'; }

REMOTE="$(setting OFFICE_REMOTE)"
KEY="$(setting OFFICE_REMOTE_KEY)"
KEY="${KEY/#\~/$HOME}"
DIR="$(setting OFFICE_REMOTE_DIR)"
LIBRECHAT="$(setting OFFICE_REMOTE_COMPOSE)"
PROJECT="$(setting OFFICE_REMOTE_PROJECT)"
PROJECT="${PROJECT:-cmu-office}"
[ -n "$REMOTE" ] && [ -n "$KEY" ] && [ -n "$DIR" ] && [ -n "$LIBRECHAT" ] \
  || fail "set OFFICE_REMOTE, OFFICE_REMOTE_KEY, OFFICE_REMOTE_DIR and OFFICE_REMOTE_COMPOSE in office.env"
[ -f "$KEY" ] || fail "SSH key not found: $KEY"

# The switch names are the ones docker-compose.office.yml passes to office-files.
KNOWN=$(grep -oE '^ +OFFICE_[A-Z]+: \$\{OFFICE_[A-Z]+:-on\}' "$COMPOSE_FILE" | awk -F: '{gsub(/ /, "", $1); print $1}')
[ -n "$KNOWN" ] || fail "no switches found in docker-compose.office.yml"

SWITCHES=()
ERRORS=()
while IFS= read -r line; do
  line="${line%$'\r'}"
  name="${line%%=*}"
  value="$(echo "${line#*=}" | tr '[:upper:]' '[:lower:]' | xargs)"
  if ! grep -qx "$name" <<<"$KNOWN"; then
    case "$value" in on|off) ERRORS+=("unknown switch '$name' (known: $(echo $KNOWN | tr ' ' ','))") ;; esac
    continue
  fi
  case "$value" in
    on|off) SWITCHES+=("$name=$value") ;;
    *) ERRORS+=("$name must be on or off, not '${line#*=}'") ;;
  esac
done < <(grep -E '^[A-Za-z_]+=' "$ENV_FILE")

[ ${#ERRORS[@]} -eq 0 ] || { printf 'ERROR: %s\n' "${ERRORS[@]}" >&2; exit 1; }
[ ${#SWITCHES[@]} -gt 0 ] || fail "no OFFICE_* switches in office.env"

echo "Switches in office.env:"
printf '  %s\n' "${SWITCHES[@]}"
echo "Applying to $REMOTE:$DIR ..."

# ssh joins its arguments into one command line, so each one is quoted for the remote shell.
ARGS=$(printf ' %q' "$DIR" "$PROJECT" "$LIBRECHAT" "${SWITCHES[@]}")
ssh -i "$KEY" -o ConnectTimeout=15 "$REMOTE" "bash -s --$ARGS" <<'REMOTE_SCRIPT'
set -euo pipefail
DIR="$1"; PROJECT="$2"; LIBRECHAT="$3"; shift 3
cd "$DIR"

changed=0
for pair in "$@"; do
  name="${pair%%=*}"
  current="$(grep -E "^$name=" office.env | tail -1 | cut -d= -f2- || true)"
  [ "$current" = "${pair#*=}" ] || changed=1
done
if [ "$changed" = 0 ]; then
  echo "Nothing changed on the server; no restart."
  exit 0
fi

backup="office.env.before-switch-$(date +%Y%m%d-%H%M%S)"
cp office.env "$backup"
for pair in "$@"; do
  name="${pair%%=*}"
  if grep -qE "^$name=" office.env; then
    sed -i "s/^$name=.*/$pair/" office.env
  else
    echo "$pair" >> office.env
  fi
done
echo "Server office.env updated (backup: $backup)"

echo "Restarting office-files ..."
sudo docker compose -p "$PROJECT" -f docker-compose.office.yml --env-file office.env up -d --force-recreate office-files 2>&1 | tail -1
echo "Restarting LibreChat ..."
sudo docker compose $LIBRECHAT up -d --no-deps --force-recreate api 2>&1 | tail -1
api="$(sudo docker compose $LIBRECHAT ps -q api)"
for _ in $(seq 1 60); do
  sudo docker logs "$api" 2>&1 | grep -q 'MCP\] Initialized' && break
  sleep 2
done

echo
echo "Now on the server:"
files="$(sudo docker compose -p "$PROJECT" -f docker-compose.office.yml --env-file office.env ps -q office-files)"
sudo docker exec "$files" env 2>/dev/null | grep -E '^OFFICE_[A-Z]+=(on|off)$' | sort | sed 's/^/  /' || true
sudo docker logs "$api" 2>&1 | grep -E 'MCP\] Initialized with' | tail -1 | sed 's/.*\[MCP\]/LibreChat:/; s/\x1b\[[0-9;]*m//g'
REMOTE_SCRIPT
