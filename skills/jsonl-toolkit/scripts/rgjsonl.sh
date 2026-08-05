#!/usr/bin/env bash
# rgjsonl.sh — rectangle-sample huge-line JSONL files with ripgrep (PCRE2 only).
#
# JSONL transcript lines routinely run 100KB-500KB, so plain rg floods the
# terminal. This wraps the rectangle idiom: a literal \Q…\E anchor with a
# bounded column window, plus clipped context rows:
#
#   rg -P -o -n -C <ctx> -M <width> --max-columns-preview '.{0,B}\Qquery\E.{0,A}' FILE
#
# Match lines print exactly the window; context lines are clipped to the same
# width ("[... omitted end of long line]" suffix marks the clip).

set -uo pipefail

usage() {
  cat <<'EOF'
rgjsonl.sh — rectangle-sample huge-line JSONL files with ripgrep (PCRE2)

USAGE  rgjsonl.sh FILE.jsonl QUERY [span] [rows] [rg options...]     (any order)

  FILE.jsonl  existing file; or file=PATH
  QUERY       literal text anchor — auto-wrapped in \Q…\E, engine forced to -P;
              or query=TEXT (required when the query looks like a number or an
              existing path)
  span        column window around the anchor. B:A = B chars before + A chars
              after the anchor; a single number N means 0:N. Default 0:100.
              Also span=B:A.
  rows        total lines per hit (the match line + context above/below split
              evenly). Second bare number, or rows=N. Default 5 → 2 above +
              2 below; 1 = match lines only.
  rg options  passed through after the computed flags, so yours win (prefer
              attached form: --glob=..., -m3). Rejected because the engine is
              PCRE2-only: -E/--encoding, -F/--fixed-strings, --engine,
              -e/--regexp, -f/--file.

EXAMPLES
  rgjsonl.sh session.jsonl '"toolName":"'                 # 100-col windows, 5 rows/hit
  rgjsonl.sh '"role":"user"' session.jsonl 40:120 rows=1  # 40 before, 120 after, no context
  rgjsonl.sh session.jsonl query=162 200 1 -m5            # numeric query, 5 hits max
EOF
}

die() { printf 'rgjsonl: %s\n\n' "$*" >&2; usage >&2; exit 2; }

FILE='' QUERY='' SPAN='' ROWS=''
RGOPTS=()

for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    -E|-E*|--encoding|--encoding=*) die "'-E/--encoding' rejected: this tool is PCRE2-only" ;;
    -F|--fixed-strings)             die "'-F' rejected: the query is already literal (\\Q-wrapped)" ;;
    --engine|--engine=*)            die "'--engine' rejected: PCRE2 is forced (-P)" ;;
    -e|-e*|--regexp|--regexp=*)     die "'-e/--regexp' rejected: extra patterns would bypass \\Q-wrapping" ;;
    -f|--file|--file=*)             die "'-f/--file' rejected: pattern files would bypass \\Q-wrapping" ;;
    file=*)  FILE="${arg#file=}" ;;
    query=*) QUERY="${arg#query=}" ;;
    span=*)  SPAN="${arg#span=}" ;;
    rows=*)  ROWS="${arg#rows=}" ;;
    -*) RGOPTS+=("$arg") ;;
    *)
      if [[ -f "$arg" && -z "$FILE" ]]; then FILE="$arg"
      elif [[ "$arg" =~ ^[0-9]+:[0-9]+$ ]]; then
        [[ -n "$SPAN" ]] && die "span given twice ('$SPAN' and '$arg')"
        SPAN="$arg"
      elif [[ "$arg" =~ ^[0-9]+$ ]]; then
        if   [[ -z "$SPAN" ]]; then SPAN="0:$arg"
        elif [[ -z "$ROWS" ]]; then ROWS="$arg"
        else die "unexpected extra number '$arg' (span=$SPAN rows=$ROWS already set)"
        fi
      elif [[ -z "$QUERY" ]]; then QUERY="$arg"
      else die "cannot classify '$arg' (query already set to '$QUERY'; use file=/query=/span=/rows=)"
      fi ;;
  esac
done

[[ -n "$FILE"  ]] || die "missing JSONL path (no argument is an existing file)"
[[ -n "$QUERY" ]] || die "missing query"
case "$QUERY" in *'\E'*) die 'query may not contain \E (it terminates \Q literal quoting)' ;; esac

SPAN="${SPAN:-0:100}"
[[ "$SPAN" =~ ^[0-9]+:[0-9]+$ ]] || die "bad span '$SPAN' (expected B:A or a single number)"
BEFORE="${SPAN%%:*}"; AFTER="${SPAN##*:}"

ROWS="${ROWS:-5}"
[[ "$ROWS" =~ ^[0-9]+$ && "$ROWS" -ge 1 ]] || die "bad rows '$ROWS' (integer >= 1)"
CTX=$(( (ROWS - 1) / 2 ))

# -M counts BYTES while the PCRE2 window counts CHARACTERS; x2 keeps 2-byte
# scripts (e.g. Hebrew) from being clipped mid-window. 4-byte emoji may still clip.
CLIP=$(( (BEFORE + AFTER + ${#QUERY}) * 2 + 32 ))

exec rg -P -o -n -C "$CTX" -M "$CLIP" --max-columns-preview \
  ${RGOPTS[@]+"${RGOPTS[@]}"} \
  -- ".{0,$BEFORE}\\Q${QUERY}\\E.{0,$AFTER}" "$FILE"
