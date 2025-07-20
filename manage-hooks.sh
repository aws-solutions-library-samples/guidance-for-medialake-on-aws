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
