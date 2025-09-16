#!/usr/bin/env bash
# Simple SMTP mail tester
# Usage examples:
#   ./mailtester.sh -h localhost -port 1026 -e dan@danshome.net -n 500 -i 5
#   ./mailtester.sh -e user@example.com           # defaults to host=localhost port=1026 n=1 i=1
# Notes:
# - Requires bash (uses /dev/tcp). No external dependencies (nc/swaks) needed.
# - Sends plain SMTP (no TLS, no auth). Suitable for testing local/dev relays.

set -euo pipefail

HOST="localhost"
PORT=1026
TO_EMAIL=""
COUNT=1
INTERVAL=1
FROM_EMAIL="mailtester@localhost"
HELO_HOST="${HOSTNAME:-localhost}"
QUIET=0

usage() {
  cat <<EOF
Mail Tester

Options:
  -h, --host HOST         SMTP host (default: localhost)
  -p, -port, --port N     SMTP port (default: 1026)
  -e, --email ADDRESS     Recipient email address (required)
  -n, --num, --count N    Number of emails to send (default: 1)
  -i, --interval SECONDS  Interval between sends in seconds (default: 1)
  --from ADDRESS          Sender address (default: mailtester@localhost)
  --helo NAME             EHLO/HELO name (default: system hostname)
  -q, --quiet             Suppress per-message output, show only summary
  -?, -help, --help       Show this help

Examples:
  $0 -h localhost -port 1026 -e user@example.com -n 10 -i 2
  $0 -e test@example.com            # send one message to localhost:1026
EOF
}

# Parse arguments (support both -p and -port per request)
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host)
      HOST="$2"; shift 2;;
    -p|-port|--port)
      PORT="$2"; shift 2;;
    -e|--email)
      TO_EMAIL="$2"; shift 2;;
    -n|--num|--count)
      COUNT="$2"; shift 2;;
    -i|--interval)
      INTERVAL="$2"; shift 2;;
    --from)
      FROM_EMAIL="$2"; shift 2;;
    --helo)
      HELO_HOST="$2"; shift 2;;
    -q|--quiet)
      QUIET=1; shift;;
    -help|--help|-\?|--usage)
      usage; exit 0;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

# Validate inputs
if [[ -z "$TO_EMAIL" ]]; then
  echo "ERROR: --email is required" >&2
  usage
  exit 1
fi
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -lt 1 ]]; then
  echo "ERROR: --count must be a positive integer" >&2
  exit 1
fi
if ! [[ "$INTERVAL" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "ERROR: --interval must be a number (seconds)" >&2
  exit 1
fi

# Opens a TCP connection via bash's /dev/tcp and sends one SMTP message
send_one() {
  local idx="$1"
  local now subj msgid datehdr
  now="$(date -u +"%Y-%m-%d %H:%M:%S %Z")"
  subj="MailTester ${now} #${idx}"
  msgid="$(date +%s).$$.${RANDOM}@${HELO_HOST}"
  datehdr="$(LC_ALL=C date -R)"

  # Open TCP socket FD 3
  if ! exec 3<>"/dev/tcp/${HOST}/${PORT}"; then
    echo "ERROR: Failed to connect to ${HOST}:${PORT}" >&2
    return 1
  fi

  # Helper to write a line with CRLF terminator
  say() { printf '%s\r\n' "$*" >&3; }

  # Speak minimal SMTP without waiting for each reply (suitable for local testing)
  say "EHLO ${HELO_HOST}"
  say "MAIL FROM:<${FROM_EMAIL}>"
  say "RCPT TO:<${TO_EMAIL}>"
  say "DATA"
  printf 'From: %s\r\n' "${FROM_EMAIL}" >&3
  printf 'To: %s\r\n' "${TO_EMAIL}" >&3
  printf 'Subject: %s\r\n' "${subj}" >&3
  printf 'Date: %s\r\n' "${datehdr}" >&3
  printf 'Message-ID: <%s>\r\n' "${msgid}" >&3
  printf 'MIME-Version: 1.0\r\n' >&3
  printf 'Content-Type: text/plain; charset="utf-8"\r\n' >&3
  printf '\r\n' >&3
  printf 'Hello from mailtester.sh!\r\n' >&3
  printf 'This is test message #%s sent at %s.\r\n' "${idx}" "${now}" >&3
  printf 'Host: %s\r\n' "${HOST}" >&3
  printf 'Port: %s\r\n' "${PORT}" >&3
  printf '\r\n' >&3
  printf '.\r\n' >&3
  say "QUIT"

  # Close FD 3
  exec 3>&-
  exec 3<&-

  [[ "$QUIET" -eq 1 ]] || echo "Sent ${idx}/${COUNT}: '${subj}' to ${TO_EMAIL} via ${HOST}:${PORT}"
}

start_ts=$(date +%s)
for (( i=1; i<=COUNT; i++ )); do
  if ! send_one "$i"; then
    echo "ERROR: send ${i} failed" >&2
    exit 2
  fi
  if [[ "$i" -lt "$COUNT" ]]; then
    # Support fractional intervals by using sleep with decimal
    sleep "$INTERVAL"
  fi
  # Update HELO_HOST if it was defaulted and HOST changed after parse
  :
done
end_ts=$(date +%s)

echo "Done. Sent ${COUNT} message(s) to ${TO_EMAIL} via ${HOST}:${PORT} in $((end_ts-start_ts))s."