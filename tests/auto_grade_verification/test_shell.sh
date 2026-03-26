#!/bin/bash
set -e

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SDIR")")"
TOOLS_DIR="${REPO_ROOT}/tools"
# Using a unique MP_ID to avoid conflicts
MP_ID="test_mp_999"
GRADING_WORKSPACE="$REPO_ROOT"
RESULT_DIR="${GRADING_WORKSPACE}/${MP_ID}/result"
mkdir -p "$RESULT_DIR"

echo "Testing auto_grade_mp.sh skip logic..."

# Create a mock trigger_grading.py that creates .push_occurred
# It must create the file in the ACTUAL path that auto_grade_mp.sh expects
cat <<EOF > "${TOOLS_DIR}/mock_trigger_grading.py"
import os
import sys
import json
print("Mock Phase 1: Creating .push_occurred")
res_dir = "$RESULT_DIR"
os.makedirs(res_dir, exist_ok=True)
with open(os.path.join(res_dir, "grading_targets.json"), "w") as f:
    json.dump([{"repo": "test/repo", "commit_sha": "testsha"}], f)
with open(os.path.join(res_dir, ".push_occurred"), "w") as f:
    f.write("true")
EOF

# Create a mock grading_crawler.py that should NOT be called
cat <<EOF > "${TOOLS_DIR}/mock_grading_crawler.py"
import sys
print("FEALURE: Crawler should NOT have been called!")
sys.exit(1)
EOF

# Run auto_grade_mp.sh using mocks
# We can swap the python command or just temp replace the files
mv "${TOOLS_DIR}/trigger_grading.py" "${TOOLS_DIR}/trigger_grading.py.bak"
mv "${TOOLS_DIR}/grading_crawler.py" "${TOOLS_DIR}/grading_crawler.py.bak"
cp "${TOOLS_DIR}/mock_trigger_grading.py" "${TOOLS_DIR}/trigger_grading.py"
cp "${TOOLS_DIR}/mock_grading_crawler.py" "${TOOLS_DIR}/grading_crawler.py"

# Run it
set +e
"${TOOLS_DIR}/auto_grade_mp.sh" --mp "$MP_ID" --repo "test/repo" | tee test_output.log
EXIT_CODE=$?
set -e

# Restore
mv "${TOOLS_DIR}/trigger_grading.py.bak" "${TOOLS_DIR}/trigger_grading.py"
mv "${TOOLS_DIR}/grading_crawler.py.bak" "${TOOLS_DIR}/grading_crawler.py"
rm "${TOOLS_DIR}/mock_trigger_grading.py" "${TOOLS_DIR}/mock_grading_crawler.py"

if grep -q "New Push or Force Trigger detected" test_output.log; then
    echo "SUCCESS: Skip logic verified."
else
    echo "FAILURE: Skip logic NOT detected in output."
    exit 1
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo "FAILURE: Script exited with $EXIT_CODE"
    exit 1
fi

echo "All integration tests passed."
rm -rf "${GRADING_WORKSPACE}/${MP_ID}" test_output.log
