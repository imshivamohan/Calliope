#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/calliope-backend"
FRONTEND_DIR="$REPO_ROOT/calliope-web"

function show_help() {
    echo "Usage: ./dev-run.sh [backend|frontend|health|test]"
    echo ""
    echo "Commands:"
    echo "  backend    Start the FastAPI backend server (http://127.0.0.1:8247)"
    echo "  frontend   Start the SvelteKit frontend server (http://127.0.0.1:5173)"
    echo "  health     Run the Calliope system health and diagnostic check"
    echo "  test       Run backend and frontend tests"
}

case "$1" in
    backend)
        echo "Starting Calliope Backend..."
        cd "$BACKEND_DIR"
        if [ -f ".venv/bin/python" ]; then
            .venv/bin/python -m calliope.main --host 127.0.0.1 --port 8247
        else
            python3 -m calliope.main --host 127.0.0.1 --port 8247
        fi
        ;;
    frontend)
        echo "Starting Calliope Frontend..."
        cd "$FRONTEND_DIR"
        npm run dev
        ;;
    health)
        python3 "$REPO_ROOT/.agents/skills/calliope/scripts/check-health.py"
        ;;
    test)
        echo "Running frontend SSR test..."
        cd "$FRONTEND_DIR" && npm test
        echo "Running backend test suite (fast unit tests)..."
        cd "$BACKEND_DIR" && .venv/bin/pytest tests/test_roles.py tests/test_contract_vocabulary.py tests/test_h3_profile.py
        ;;
    *)
        show_help
        exit 1
        ;;
esac
