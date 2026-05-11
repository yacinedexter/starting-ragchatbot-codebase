#!/bin/bash
# Frontend code quality checks

set -e

echo "=== Frontend Quality Checks ==="

echo ""
echo "[1/2] Checking formatting with Prettier..."
npx prettier --check frontend/
echo "  Formatting OK"

echo ""
echo "[2/2] Checking for common JS issues..."

JS_FILE="frontend/script.js"

# Check for console.log left in production code (warn only)
if grep -n "console\.log" "$JS_FILE" > /dev/null 2>&1; then
    echo "  WARNING: console.log statements found in $JS_FILE:"
    grep -n "console\.log" "$JS_FILE" | sed 's/^/    /'
else
    echo "  No console.log statements found"
fi

echo ""
echo "=== All checks passed ==="
echo ""
echo "To auto-fix formatting run: npm run format"
