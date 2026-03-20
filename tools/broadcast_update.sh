#!/bin/bash
# Front-end wrapper for broadcast_update.py (Hot-Sync Broadcast)

DEFAULT_REPO_URL="https://github.com/Shiritai/xv6-ntu-mp.git"

usage() {
    echo "Usage: $0 --mp <mp_id> --message <commit_message> [options]"
    echo ""
    echo "Required:"
    echo "  --mp <mp_id>       Assignment ID (e.g., mp0). Sources from mpX/public/"
    echo "  --message <msg>    Public commit message for students"
    echo ""
    echo "Targeting (choose one):"
    echo "  --repo <url>       Target a single template repo (default: $DEFAULT_REPO_URL)"
    echo "  --repos-list <js>  Target a JSON array of repositories (from accept_invite.sh)"
    echo ""
    echo "Options:"
    echo "  --workers <num>    Number of parallel workers (default: 4, applies to --repos-list)"
    echo "  --prefix <str>     Course prefix for branch (default: ntuos2026)"
    echo "  --dry-run          Preview changes locally without pushing"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Note: This tool broadcasts PUBLIC assets only. Do NOT use for private payloads."
    exit 1
}

MP=""
MESSAGE=""
TARGET_ARGS=""
DRY_RUN=""
WORKERS=""
PREFIX=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --mp) MP="$2"; shift ;;
        --message) MESSAGE="$2"; shift ;;
        --repo) TARGET_ARGS="--repo $2"; shift ;;
        --repos-list) TARGET_ARGS="--repos-list $2"; shift ;;
        --workers) WORKERS="--workers $2"; shift ;;
        --prefix) PREFIX="--prefix $2"; shift ;;
        --dry-run) DRY_RUN="--dry-run" ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

if [ -z "$MP" ] || [ -z "$MESSAGE" ]; then
    echo "Error: Missing required parameters."
    usage
fi

if [ -z "$TARGET_ARGS" ]; then
    TARGET_ARGS="--repo $DEFAULT_REPO_URL"
fi

PYTHON_SCRIPT="$(dirname "$0")/broadcast_update.py"

python3 "$PYTHON_SCRIPT" --mp "$MP" --message "$MESSAGE" $TARGET_ARGS $WORKERS $PREFIX $DRY_RUN
