#!/bin/bash
set -e  # Exit on error
set -u  # Exit on undefined variables
set -o pipefail  # Exit on pipe failures

echo "Setting up development environment..."

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

# Detect OS
OS="$(uname -s)"

# Install pyenv if not already installed
if ! command_exists pyenv; then
    echo "Installing pyenv..."

    if [[ "$OS" == "Darwin" ]]; then
        # macOS
        brew install pyenv
        brew install pyenv-virtualenv
    elif [[ "$OS" == "Linux" ]]; then
        # Linux
        curl https://pyenv.run | bash
    else
        log_error "Unsupported OS: $OS"
        exit 1
    fi
fi

# Add pyenv to shell if not already there
if [[ "$OS" == "Darwin" ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
else
    SHELL_CONFIG="$HOME/.bashrc"
fi

if ! grep -q "pyenv init" "$SHELL_CONFIG" 2>/dev/null; then
    echo "Adding pyenv to shell configuration..."
    echo '' >> "$SHELL_CONFIG"
    echo '# Pyenv configuration' >> "$SHELL_CONFIG"
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$SHELL_CONFIG"
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> "$SHELL_CONFIG"
    echo 'eval "$(pyenv init -)"' >> "$SHELL_CONFIG"
    echo 'eval "$(pyenv virtualenv-init -)"' >> "$SHELL_CONFIG"
fi

# Initialize pyenv for current session
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)" 2>/dev/null || true

# Install Python 3.12.10 if not already installed
PYTHON_VERSION="3.12.10"
PYTHON_MAJOR="3.12"

# Check if the exact version is available in pyenv
if pyenv versions 2>/dev/null | grep -q "^\s*\*\?\s*$PYTHON_VERSION\s*$"; then
    echo "Python $PYTHON_VERSION is already installed"
elif pyenv versions 2>/dev/null | grep -q "^\s*\*\?\s*$PYTHON_MAJOR"; then
    # Get the installed 3.12.x version
    INSTALLED_VERSION=$(pyenv versions 2>/dev/null | grep "^\s*\*\?\s*$PYTHON_MAJOR" | head -1 | sed 's/^\s*\*\?\s*\([0-9.]*\).*/\1/')
    PYTHON_VERSION="$INSTALLED_VERSION"
    echo "Python $PYTHON_MAJOR is already installed, using existing version: $PYTHON_VERSION"
else
    echo "Installing Python $PYTHON_VERSION..."
    if ! pyenv install "$PYTHON_VERSION"; then
        log_error "Failed to install Python $PYTHON_VERSION"
        exit 1
    fi
fi

# Get project name from directory
PROJECT_NAME=$(basename "$PWD")
VENV_NAME="${PROJECT_NAME}-${PYTHON_MAJOR}"

# Create virtual environment if it doesn't exist
if ! pyenv virtualenvs 2>/dev/null | grep -q "$VENV_NAME"; then
    echo "Creating virtual environment: $VENV_NAME using Python $PYTHON_VERSION"
    if ! pyenv virtualenv "$PYTHON_VERSION" "$VENV_NAME"; then
        log_error "Failed to create virtual environment: $VENV_NAME"
        exit 1
    fi
else
    echo "Virtual environment $VENV_NAME already exists"
fi

# Set local python version for this project
echo "Setting local Python environment..."
pyenv local "$VENV_NAME"

# Activate the virtual environment
eval "$(pyenv init -)"
if ! pyenv activate "$VENV_NAME" 2>/dev/null; then
    log_error "Failed to activate virtual environment: $VENV_NAME"
    exit 1
fi

# Verify Python version
echo "Python version: $(python --version)"
echo "Virtual environment: $(pyenv version-name)"

# Update pip
echo "Updating pip..."
if ! python -m pip install --upgrade pip; then
    log_error "Failed to update pip"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
if [ -f "requirements-dev.txt" ]; then
    if ! pip install -r requirements-dev.txt; then
        log_error "Failed to install requirements-dev.txt"
        exit 1
    fi
elif [ -f "requirements.txt" ]; then
    if ! pip install -r requirements.txt; then
        log_error "Failed to install requirements.txt"
        exit 1
    fi
else
    log_info "No requirements files found, skipping Python dependency installation"
fi

# Install CDK dependencies if directory exists
if [ -d "cdk" ]; then
    echo "Installing CDK dependencies..."
    if ! pip install aws-cdk-lib constructs; then
        log_error "Failed to install CDK Python dependencies"
        exit 1
    fi

    pushd cdk > /dev/null
    if [ -f "requirements.txt" ]; then
        if ! pip install -r requirements.txt; then
            log_error "Failed to install CDK requirements.txt"
            popd > /dev/null
            exit 1
        fi
    fi
    if [ -f "package.json" ]; then
        if ! command_exists npm; then
            log_error "npm not found, cannot install CDK Node.js dependencies"
            popd > /dev/null
            exit 1
        fi
        if ! npm install; then
            log_error "Failed to install CDK Node.js dependencies"
            popd > /dev/null
            exit 1
        fi
    fi
    popd > /dev/null
fi

# Install pre-commit
echo "Installing pre-commit..."
if ! pip install pre-commit; then
    log_error "Failed to install pre-commit"
    exit 1
fi

# Install gitleaks for secret scanning, updated from detect secrets
echo "Installing gitleaks..."
if [[ "$OS" == "Darwin" ]]; then
    if command_exists brew; then
        brew install gitleaks || log_info "gitleaks may already be installed"
    else
        log_info "Homebrew not found. Install gitleaks manually: https://github.com/gitleaks/gitleaks#installing"
    fi
elif [[ "$OS" == "Linux" ]]; then
    GITLEAKS_VERSION="8.21.2"
    curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" | tar -xz -C /usr/local/bin gitleaks || log_info "Failed to install gitleaks automatically. Install manually: https://github.com/gitleaks/gitleaks#installing"
fi

# Install additional tools for enhanced pre-commit hooks
echo "Installing additional pre-commit dependencies..."
if ! pip install conventional-pre-commit; then
    log_info "Some additional tools failed to install, continuing with basic setup"
fi

# Note: bandit and cfn-lint are currently disabled in pre-commit config
# Uncomment the following lines if you want to install them for manual use:
# pip install bandit cfn-lint

# Set up Git hooks chain
echo "Setting up Git hooks chain..."

# Verify we're in a git repository
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_error "Not in a git repository. Please run this script from within a git repository."
    exit 1
fi

# Save current hooks path
ORIGINAL_HOOKS_PATH=$(git config --get core.hooksPath 2>/dev/null || echo ".git/hooks")
GIT_DEFENDER_PATH="/usr/local/amazon/var/git-defender/hooks"

# Create .githooks directory
if ! mkdir -p .githooks; then
    log_error "Failed to create .githooks directory"
    exit 1
fi

# Create pre-commit wrapper that chains git-defender and pre-commit
cat > .githooks/pre-commit << 'EOF'
#!/bin/bash

echo "Running Git hooks..."

# Run git-defender hooks first (if they exist)
if [ -f "/usr/local/amazon/var/git-defender/hooks/pre-commit" ]; then
    echo "Running git-defender checks..."
    /usr/local/amazon/var/git-defender/hooks/pre-commit
    GIT_DEFENDER_EXIT=$?
    if [ $GIT_DEFENDER_EXIT -ne 0 ]; then
        echo "ERROR: git-defender checks failed"
        exit $GIT_DEFENDER_EXIT
    fi
    echo "git-defender checks passed"
fi

# Run pre-commit framework directly (without needing pre-commit install)
if command -v pre-commit &> /dev/null && [ -f ".pre-commit-config.yaml" ]; then
    echo "Running pre-commit checks..."
    # Use --all-files for initial setup, otherwise run on staged files
    if [ "${1:-}" = "--all-files" ]; then
        pre-commit run --all-files
    else
        pre-commit run --files $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || echo "")
    fi
    PRE_COMMIT_EXIT=$?
    if [ $PRE_COMMIT_EXIT -ne 0 ]; then
        echo "ERROR: pre-commit checks failed"
        exit $PRE_COMMIT_EXIT
    fi
    echo "pre-commit checks passed"
fi

echo "All Git hooks passed!"
exit 0
EOF

# Make the hook executable
chmod +x .githooks/pre-commit

# Create other git hooks if git-defender has them
for hook in commit-msg post-commit prepare-commit-msg; do
    if [ -f "$GIT_DEFENDER_PATH/$hook" ]; then
        cat > ".githooks/$hook" << EOF
#!/bin/bash
# Chain wrapper for $hook
if [ -f "$GIT_DEFENDER_PATH/$hook" ]; then
    $GIT_DEFENDER_PATH/$hook "\$@"
fi
EOF
        chmod +x ".githooks/$hook"
    fi
done

# Set git to use our combined hooks
if ! git config core.hooksPath .githooks; then
    log_error "Failed to configure git hooks path"
    exit 1
fi

# Verify gitleaks is available for secret scanning
echo "Verifying security tools..."
if command_exists gitleaks; then
    echo "gitleaks $(gitleaks version) is installed"
else
    log_info "gitleaks not found in PATH. Pre-commit will download it automatically when the hook runs."
fi

# Initialize pre-commit without installing hooks
# This ensures pre-commit downloads any needed dependencies
echo "Initializing pre-commit tools..."
if [ -f ".pre-commit-config.yaml" ]; then
    pre-commit run --all-files || log_info "Pre-commit initialization completed with warnings (this is normal for first run)"
else
    log_info "No .pre-commit-config.yaml found, skipping pre-commit initialization"
fi

echo "Git hooks configured to use both git-defender and pre-commit"
echo "   Current hooks path: .githooks"
echo "   Original hooks path: $ORIGINAL_HOOKS_PATH"

# Install frontend dependencies if directory exists
if [ -d "frontend" ]; then
    echo "Installing frontend dependencies..."
    if ! command_exists npm; then
        log_error "npm not found, cannot install frontend dependencies"
        exit 1
    fi
    pushd frontend > /dev/null
    if ! npm install; then
        log_error "Failed to install frontend dependencies"
        popd > /dev/null
        exit 1
    fi
    popd > /dev/null
fi

# Create hooks management script
echo "Creating hooks management script..."
cat > manage-hooks.sh << 'EOF'
#!/bin/bash

case "$1" in
    combined)
        git config core.hooksPath .githooks
        echo "Using combined git-defender + pre-commit hooks"
        ;;
    defender)
        git config core.hooksPath /usr/local/amazon/var/git-defender/hooks
        echo "Using only git-defender hooks"
        ;;
    precommit)
        git config --unset-all core.hooksPath
        pre-commit install
        echo "Using only pre-commit hooks"
        ;;
    status)
        echo "Current hooks path: $(git config --get core.hooksPath || echo '.git/hooks (default)')"
        ;;
    *)
        echo "Usage: $0 {combined|defender|precommit|status}"
        echo ""
        echo "  combined  - Use both git-defender and pre-commit"
        echo "  defender  - Use only git-defender hooks"
        echo "  precommit - Use only pre-commit hooks"
        echo "  status    - Show current hooks configuration"
        exit 1
        ;;
esac
EOF

chmod +x manage-hooks.sh

echo ""
echo "Setup complete!"
echo ""
echo "Configuration Summary:"
echo "   - Python environment: $VENV_NAME (Python $PYTHON_VERSION)"
echo "   - Git hooks: Combined git-defender + pre-commit in .githooks/"
echo "   - Pre-commit: Installed and configured"
echo ""
echo "Next steps:"
echo "   1. The virtual environment '$VENV_NAME' is now active"
echo "   2. Run 'pre-commit run --all-files' to test pre-commit hooks"
echo "   3. Git commits will run both git-defender and pre-commit checks"
echo ""
echo "Hook Management Commands:"
echo "   - Use combined hooks: ./manage-hooks.sh combined"
echo "   - Use only git-defender: ./manage-hooks.sh defender"
echo "   - Use only pre-commit: ./manage-hooks.sh precommit"
echo "   - Check status: ./manage-hooks.sh status"
echo "   - Run pre-commit manually: pre-commit run --all-files"
echo ""
