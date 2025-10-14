#!/bin/bash
# Script to run Settings API Lambda tests

set -e

echo "=========================================="
echo "Settings API Lambda - Test Runner"
echo "=========================================="
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing test dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements-test.txt

echo ""
echo "=========================================="
echo "Running Tests"
echo "=========================================="
echo ""

# Run pytest with coverage
pytest -v --cov=. --cov-report=term-missing --cov-report=html

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo ""
echo "✅ Tests completed!"
echo "📊 HTML coverage report: htmlcov/index.html"
echo ""
