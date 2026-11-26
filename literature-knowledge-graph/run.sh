#!/usr/bin/env bash
# Resolve the skill directory and run one pipeline stage.
#   ./run.sh prepare  [args...]   ./run.sh build [args...]   ./run.sh query [args...]
#   ./run.sh export   [args...]   ./run.sh finalize [args...] ./run.sh all [args...]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stage="${1:-all}"; shift || true
case "$stage" in
  prepare)  exec python3 "$HERE/scripts/prepare_case.py" "$@" ;;
  build)    exec python3 "$HERE/scripts/build_graph.py" "$@" ;;
  query)    exec python3 "$HERE/scripts/query_graph.py" "$@" ;;
  export)   exec python3 "$HERE/scripts/export_graph.py" "$@" ;;
  finalize) exec python3 "$HERE/scripts/finalize.py" "$@" ;;
  extract)  exec python3 "$HERE/scripts/heuristic_extract.py" "$@" ;;
  test)     exec python3 "$HERE/tests/selftest.py" ;;
  all)      exec python3 "$HERE/scripts/run_all.py" "$@" ;;
  *) echo "usage: $0 {prepare|build|query|export|finalize|extract|test|all} [args...]" >&2; exit 2 ;;
esac
