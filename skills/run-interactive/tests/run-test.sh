#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
DRIVER="$SCRIPT_DIR/../scripts/driver.py"
SESSION="test_$$"
LOG="/tmp/interactive_${SESSION}.log"
INPUT="/tmp/interactive_${SESSION}.in"

# Inline test wizard
WIZARD=$(mktemp /tmp/wizard_XXXX.py)
cat > "$WIZARD" << 'EOF'
#!/usr/bin/env python3
import sys
print("=== Test Wizard ===", flush=True)
print("Enter name: ", end="", flush=True)
name = input()
print("Enter hobby: ", end="", flush=True)
hobby = input()
print(f"Hello {name}, you like {hobby}!", flush=True)
EOF

cleanup() {
    rm -f "$LOG" "$INPUT" "$WIZARD"
    # Kill driver if still running
    jobs -p 2>/dev/null | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting driver..."
python3 "$DRIVER" "$SESSION" python3 "$WIZARD" &
DRIVER_PID=$!

wait_for() {
    local pattern="$1"
    local timeout=5
    local elapsed=0
    while ! grep -q "$pattern" "$LOG" 2>/dev/null; do
        sleep 0.1
        elapsed=$((elapsed + 1))
        if (( elapsed > timeout * 10 )); then
            echo "FAIL: Timeout waiting for '$pattern'"
            cat "$LOG" 2>/dev/null || true
            exit 1
        fi
    done
}

# Stage 1: name
echo "Waiting for first [AWAIT]..."
wait_for '\[AWAIT\]'
echo -n "alice" > "$INPUT"

# Stage 2: hobby
echo "Waiting for second [AWAIT]..."
sleep 0.3
wait_for '\[SENT\] alice'
wait_for '\[OUT\] Enter hobby'
sleep 0.2
# Need to wait for second AWAIT after the first one was consumed
while [[ $(grep -c '\[AWAIT\]' "$LOG" 2>/dev/null) -lt 2 ]]; do
    sleep 0.1
done
echo -n "testing" > "$INPUT"

# Wait for exit
echo "Waiting for [EXIT]..."
wait_for '\[EXIT:0\]'

# Verify output
if grep -q "Hello alice, you like testing!" "$LOG"; then
    echo "PASS: Wizard completed successfully"
    exit 0
else
    echo "FAIL: Unexpected output"
    cat "$LOG"
    exit 1
fi
