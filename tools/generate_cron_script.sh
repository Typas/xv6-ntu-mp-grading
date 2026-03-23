#!/bin/bash
# ==========================================================
# GitHub Invitation Automation Generator
# This script generates a cron script based on parameters.
# ==========================================================

# --- Default Parameters (MP2 Example) ---
SHEET_ID="..."
SHEET_GID="..."
MP_NAME="ntuos2026-mpX"
START_TIME="YYYY-MM-DD HH:MM:SS"
END_TIME="YYYY-MM-DD HH:MM:SS"
INTERVAL="0 * * * *"
WORKING_DIR="$(pwd)"
OUTPUT_PATH="../mpX/result/students_mpX.json"
DEPLOY_FLAG=false

# --- Usage ---
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --sheet-id ID      Google Sheet ID"
    echo "  --sheet-gid GID    Google Sheet GID"
    echo "  --mp-name NAME     MP identifier (keyword)"
    echo "  --start-time TIME  Start window (YYYY-MM-DD HH:MM:SS)"
    echo "  --end-time TIME    End window (YYYY-MM-DD HH:MM:SS)"
    echo "  --interval CRON    Cron schedule (e.g., \"0 * * * *\")"
    echo "  --wd DIR           Working directory"
    echo "  --output PATH      Output JSON path"
    echo "  --deploy           Automatically add to current user's crontab"
    exit 1
}

# --- Parse Arguments ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --sheet-id) SHEET_ID="$2"; shift ;;
        --sheet-gid) SHEET_GID="$2"; shift ;;
        --mp-name) MP_NAME="$2"; shift ;;
        --start-time) START_TIME="$2"; shift ;;
        --end-time) END_TIME="$2"; shift ;;
        --interval) INTERVAL="$2"; shift ;;
        --wd) WORKING_DIR="$2"; shift ;;
        --output) OUTPUT_PATH="$2"; shift ;;
        --deploy) DEPLOY_FLAG=true ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

TEMPLATE_FILE="cron_accept_invites.sh.template"
OUTPUT_FILE="cron_accept_invites.sh"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file $TEMPLATE_FILE not found."
    exit 1
fi

echo "--- Generating Cron Script ---"
sed -e "s|__SHEET_ID__|$SHEET_ID|g" \
    -e "s|__SHEET_GID__|$SHEET_GID|g" \
    -e "s|__MP_NAME__|$MP_NAME|g" \
    -e "s|__START_TIME__|$START_TIME|g" \
    -e "s|__END_TIME__|$END_TIME|g" \
    -e "s|__WORKING_DIR__|$WORKING_DIR|g" \
    -e "s|__OUTPUT_PATH__|$OUTPUT_PATH|g" \
    "$TEMPLATE_FILE" > "$OUTPUT_FILE"

chmod +x "$OUTPUT_FILE"
echo "✅ Generated: $OUTPUT_FILE"
echo "WD: $WORKING_DIR"
echo "MP: $MP_NAME"
echo "Window: $START_TIME ~ $END_TIME"

# --- Deployment ---
if [[ "$DEPLOY_FLAG" == true ]]; then
    echo "--- Deploying to Crontab ---"
    SCRIPT_PATH="$(realpath "$OUTPUT_FILE")"
    CRON_ENTRY="$INTERVAL $SCRIPT_PATH"
    
    # Check if entry already exists to avoid duplicates
    (crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH") > /dev/null
    if [[ $? -eq 0 ]]; then
        echo "⚠️  Entry already exists in crontab. Skipping."
    else
        (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
        echo "✅ Added to crontab: $CRON_ENTRY"
    fi
else
    echo "--- Suggestion ---"
    echo "To deploy manually, add the following to 'crontab -e':"
    echo "$INTERVAL $(realpath "$OUTPUT_FILE")"
fi
