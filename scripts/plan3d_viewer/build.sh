#!/bin/sh
# Rebuild viewer.bundle.js (viewer.js + three.js) after editing viewer.js.
# Needs Node.js; node_modules go to a temporary folder, not here.
# three.js is MIT-licensed; its notice is kept as the bundle banner.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
THREE_VERSION=0.187.0
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$HERE/viewer.js" "$TMP/"
cd "$TMP"
npm init -y >/dev/null
npm install --silent "three@$THREE_VERSION" esbuild
npx esbuild viewer.js --bundle --minify --format=iife --target=es2020 \
  --legal-comments=none \
  --banner:js="/*! three.js ${THREE_VERSION} | MIT License | Copyright © 2010-2026 three.js authors | https://github.com/mrdoob/three.js */" \
  --outfile="$HERE/viewer.bundle.js"
echo "viewer.bundle.js: three@$THREE_VERSION"
