#!/bin/bash
# Patch react-markdown v8 for TypeScript 5.x compatibility
# react-markdown v8 ships .ts source files that reference the removed global JSX namespace
# This patch uses React.JSX instead. See: https://github.com/remarkjs/react-markdown/issues/772

COMPLEX_TYPES="node_modules/react-markdown/lib/complex-types.ts"

if [ -f "$COMPLEX_TYPES" ]; then
  sed \
    -e 's/keyof JSX\.IntrinsicElements/keyof React.JSX.IntrinsicElements/g' \
    -e 's/ComponentPropsWithoutRef<TagName>/Record<string, unknown>/g' \
    -e 's/import type {ReactNode, ComponentType, ComponentPropsWithoutRef}/import type {ReactNode, ComponentType}/' \
    "$COMPLEX_TYPES" > "${COMPLEX_TYPES}.tmp" && mv "${COMPLEX_TYPES}.tmp" "$COMPLEX_TYPES"
  echo "Patched react-markdown/lib/complex-types.ts for TS5.x compatibility"
fi
