#!/bin/bash
set -e  # Exit on error

echo "🚀 Setting up development environment..."

# Detect OS
OS="$(uname -s)"

# Install pyenv if not already installed
if ! command -v pyenv &> /dev/null; then
    echo "📦 Installing pyenv..."

    if [[ "$OS" == "Darwin" ]]; then
        # macOS
        brew install pyenv
        brew install pyenv-virtualenv
    elif [[ "$OS" == "Linux" ]]; then
        # Linux
        curl https://pyenv.run | bash
    else
        echo "❌ Unsupported OS: $OS"
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
    echo "📝 Adding pyenv to shell configuration..."
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

# Install Python 3.12 if not already installed
if ! pyenv versions | grep -q "3.12"; then
    echo "🐍 Installing Python 3.12..."
    pyenv install 3.12
fi

# Get project name from directory
PROJECT_NAME=$(basename "$PWD")
VENV_NAME="${PROJECT_NAME}-3.12"

# Create virtual environment if it doesn't exist
if ! pyenv virtualenvs | grep -q "$VENV_NAME"; then
    echo "🔧 Creating virtual environment: $VENV_NAME"
    pyenv virtualenv 3.12 "$VENV_NAME"
fi

# Set local python version for this project
echo "🎯 Setting local Python environment..."
pyenv local "$VENV_NAME"

# Activate the virtual environment
eval "$(pyenv init -)"
pyenv activate "$VENV_NAME"

# Verify Python version
echo "✅ Python version: $(python --version)"
echo "📍 Virtual environment: $(pyenv version-name)"

# Update pip
echo "📦 Updating pip..."
python -m pip install --upgrade pip

# Install Python dependencies
echo "📚 Installing Python dependencies..."
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
elif [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Install CDK dependencies if directory exists
if [ -d "cdk" ]; then
    echo "🏗️  Installing CDK dependencies..."
    pip install aws-cdk-lib constructs
    cd cdk
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    fi
    if [ -f "package.json" ]; then
        npm install
    fi
    cd ..
fi

# Install pre-commit
echo "🔒 Installing pre-commit..."
pip install pre-commit

# Set up Git hooks chain
echo "🔗 Setting up Git hooks chain..."

# Save current hooks path
ORIGINAL_HOOKS_PATH=$(git config --get core.hooksPath || echo ".git/hooks")
GIT_DEFENDER_PATH="/usr/local/amazon/var/git-defender/hooks"

# Create .githooks directory
mkdir -p .githooks

# Create pre-commit wrapper that chains git-defender and pre-commit
cat > .githooks/pre-commit << 'EOF'
#!/bin/bash

echo "🔍 Running Git hooks..."

# Run git-defender hooks first (if they exist)
if [ -f "/usr/local/amazon/var/git-defender/hooks/pre-commit" ]; then
    echo "🛡️  Running git-defender checks..."
    /usr/local/amazon/var/git-defender/hooks/pre-commit
    GIT_DEFENDER_EXIT=$?
    if [ $GIT_DEFENDER_EXIT -ne 0 ]; then
        echo "❌ git-defender checks failed"
        exit $GIT_DEFENDER_EXIT
    fi
    echo "✅ git-defender checks passed"
fi

# Run pre-commit framework directly (without needing pre-commit install)
if command -v pre-commit &> /dev/null && [ -f ".pre-commit-config.yaml" ]; then
    echo "🔧 Running pre-commit checks..."
    pre-commit run
    PRE_COMMIT_EXIT=$?
    if [ $PRE_COMMIT_EXIT -ne 0 ]; then
        echo "❌ pre-commit checks failed"
        exit $PRE_COMMIT_EXIT
    fi
    echo "✅ pre-commit checks passed"
fi

echo "✅ All Git hooks passed!"
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
git config core.hooksPath .githooks

# Initialize pre-commit without installing hooks
# This ensures pre-commit downloads any needed dependencies
echo "🔧 Initializing pre-commit tools..."
pre-commit run --all-files || true

echo "✅ Git hooks configured to use both git-defender and pre-commit"
echo "   Current hooks path: .githooks"
echo "   Original hooks path: $ORIGINAL_HOOKS_PATH"

# Install frontend dependencies if directory exists
if [ -d "frontend" ]; then
    echo "⚛️  Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Create hooks management script
echo "📝 Creating hooks management script..."
cat > manage-hooks.sh << 'EOF'
#!/bin/bash

case "$1" in
    combined)
        git config core.hooksPath .githooks
        echo "✅ Using combined git-defender + pre-commit hooks"
        ;;
    defender)
        git config core.hooksPath /usr/local/amazon/var/git-defender/hooks
        echo "✅ Using only git-defender hooks"
        ;;
    precommit)
        git config --unset-all core.hooksPath
        pre-commit install
        echo "✅ Using only pre-commit hooks"
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
echo "✨ Setup complete!"
echo ""
echo "📌 Configuration Summary:"
echo "   - Python environment: $VENV_NAME (Python 3.12)"
echo "   - Git hooks: Combined git-defender + pre-commit in .githooks/"
echo "   - Pre-commit: Installed and configured"
echo ""
echo "🎯 Next steps:"
echo "   1. The virtual environment '$VENV_NAME' is now active"
echo "   2. Run 'pre-commit run --all-files' to test pre-commit hooks"
echo "   3. Git commits will run both git-defender and pre-commit checks"
echo ""
echo "🔧 Hook Management Commands:"
echo "   - Use combined hooks: ./manage-hooks.sh combined"
echo "   - Use only git-defender: ./manage-hooks.sh defender"
echo "   - Use only pre-commit: ./manage-hooks.sh precommit"
echo "   - Check status: ./manage-hooks.sh status"
echo "   - Run pre-commit manually: pre-commit run --all-files"
echo ""
