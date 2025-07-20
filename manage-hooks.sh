#!/bin/bash
set -e  # Exit on error
set -u  # Exit on undefined variables
set -o pipefail  # Exit on pipe failures

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to log errors
log_error() {
    echo "ERROR: $1" >&2
}

# Function to log info
log_info() {
    echo "INFO: $1"
}

# Verify we're in a git repository
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_error "Not in a git repository. Please run this script from within a git repository."
    exit 1
fi

# Define paths
GIT_DEFENDER_PATH="/usr/local/amazon/var/git-defender/hooks"
GITHOOKS_PATH=".githooks"

case "${1:-}" in
    combined)
        if [ ! -d "$GITHOOKS_PATH" ]; then
            log_error "Combined hooks directory '$GITHOOKS_PATH' not found. Please run setup-dev.sh first."
            exit 1
        fi
        if ! git config core.hooksPath "$GITHOOKS_PATH"; then
            log_error "Failed to configure git hooks path to '$GITHOOKS_PATH'"
            exit 1
        fi
        echo "Using combined git-defender + pre-commit hooks"
        ;;
    defender)
        if [ ! -d "$GIT_DEFENDER_PATH" ]; then
            log_error "Git-defender hooks directory '$GIT_DEFENDER_PATH' not found."
            exit 1
        fi
        if ! git config core.hooksPath "$GIT_DEFENDER_PATH"; then
            log_error "Failed to configure git hooks path to '$GIT_DEFENDER_PATH'"
            exit 1
        fi
        echo "Using only git-defender hooks"
        ;;
    precommit)
        if ! command_exists pre-commit; then
            log_error "pre-commit is not installed. Please install it first."
            exit 1
        fi
        if ! [ -f ".pre-commit-config.yaml" ]; then
            log_error ".pre-commit-config.yaml not found. Please create it first."
            exit 1
        fi
        if ! git config --unset-all core.hooksPath 2>/dev/null; then
            log_info "No custom hooks path was set"
        fi
        if ! pre-commit install; then
            log_error "Failed to install pre-commit hooks"
            exit 1
        fi
        echo "Using only pre-commit hooks"
        ;;
    status)
        echo "Current hooks path: $(git config --get core.hooksPath 2>/dev/null || echo '.git/hooks (default)')"

        # Show what's available
        echo ""
        echo "Available hook configurations:"

        if [ -d "$GITHOOKS_PATH" ]; then
            echo "  - combined: Available (git-defender + pre-commit)"
        else
            echo "  - combined: Not available (run setup-dev.sh first)"
        fi

        if [ -d "$GIT_DEFENDER_PATH" ]; then
            echo "  - defender: Available (git-defender only)"
        else
            echo "  - defender: Not available (git-defender not installed)"
        fi

        if command_exists pre-commit && [ -f ".pre-commit-config.yaml" ]; then
            echo "  - precommit: Available (pre-commit only)"
        else
            echo "  - precommit: Not available (pre-commit not installed or no config)"
        fi

        # Show security tools status
        echo ""
        echo "Security tools status:"

        if command_exists detect-secrets; then
            if [ -f ".secrets.baseline" ]; then
                echo "  - detect-secrets: Available with baseline"
            else
                echo "  - detect-secrets: Available but no baseline (run setup-dev.sh)"
            fi
        else
            echo "  - detect-secrets: Not installed"
        fi

        if command_exists bandit; then
            echo "  - bandit: Available but disabled in pre-commit config"
        else
            echo "  - bandit: Not installed"
        fi

        if command_exists cfn-lint; then
            echo "  - cfn-lint: Available but disabled in pre-commit config"
        else
            echo "  - cfn-lint: Not installed"
        fi
        ;;
    test)
        echo "Testing current hook configuration..."
        current_path=$(git config --get core.hooksPath 2>/dev/null || echo '.git/hooks')
        echo "Current hooks path: $current_path"

        if [ -f "$current_path/pre-commit" ]; then
            echo "Pre-commit hook found, testing..."
            if [ -x "$current_path/pre-commit" ]; then
                echo "Pre-commit hook is executable"
                # Test with a dry run if possible
                if command_exists pre-commit && [ -f ".pre-commit-config.yaml" ]; then
                    echo "Running pre-commit dry run..."
                    pre-commit run --all-files --dry-run || log_info "Pre-commit test completed with warnings"
                fi
            else
                log_error "Pre-commit hook is not executable"
            fi
        else
            echo "No pre-commit hook found in current configuration"
        fi

        # Test security tools
        echo ""
        echo "Testing security tools..."

        if command_exists detect-secrets && [ -f ".secrets.baseline" ]; then
            echo "Testing detect-secrets..."
            detect-secrets scan --baseline .secrets.baseline --quiet && echo "  - detect-secrets: PASS" || echo "  - detect-secrets: FAIL (new secrets detected)"
        fi

        if command_exists bandit; then
            echo "  - bandit: SKIP (disabled in pre-commit config)"
            echo "    To test manually: bandit -r . -f json -o /tmp/bandit-test.json"
        fi

        if command_exists cfn-lint; then
            echo "  - cfn-lint: SKIP (disabled in pre-commit config)"
            echo "    To test manually: cfn-lint medialake.template"
        fi
        ;;

    security)
        echo "Running security-focused checks..."

        if command_exists detect-secrets; then
            echo "Running detect-secrets scan..."
            if [ -f ".secrets.baseline" ]; then
                echo "Using existing baseline..."
                detect-secrets scan --baseline .secrets.baseline
            else
                echo "No secrets baseline found. Creating one..."
                detect-secrets scan --baseline .secrets.baseline --force-use-all-plugins
                echo "Baseline created at .secrets.baseline"
            fi
        else
            log_error "detect-secrets not installed. Run setup-dev.sh first."
        fi

        if command_exists bandit; then
            echo "Note: bandit is installed but currently disabled in pre-commit config"
            echo "To run bandit manually: bandit -r . -f json -o bandit-report.json"
        else
            log_info "bandit not installed. Python security scanning skipped."
        fi

        if command_exists cfn-lint; then
            echo "Note: cfn-lint is installed but currently disabled in pre-commit config"
            echo "To run cfn-lint manually on medialake.template: cfn-lint medialake.template"
        else
            log_info "cfn-lint not installed. CloudFormation validation skipped."
        fi
        ;;
    *)
        echo "Usage: $0 {combined|defender|precommit|status|test|security}"
        echo ""
        echo "  combined  - Use both git-defender and pre-commit"
        echo "  defender  - Use only git-defender hooks"
        echo "  precommit - Use only pre-commit hooks"
        echo "  status    - Show current hooks configuration and availability"
        echo "  test      - Test current hook configuration"
        echo "  security  - Run security-focused scans manually"
        exit 1
        ;;
esac
