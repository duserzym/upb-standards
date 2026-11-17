#!/bin/sh
# Run from any directory. Requires librsvg's rsvg-convert.
# First regenerate the SVG with python3 assets/make_icon.py when geometry or
# layout changes. This script renders the generated SVG without needing Python.
# 128-1024 px use the catalogue; 32/64 px and the site's 16-42 px favicon/header
# mark use one large zircon beside three thick value bars.
set -eu
assets_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for size in 1024 512 256 128 64 32; do
    source_svg="$assets_dir/icon.svg"
    case "$size" in 64|32) source_svg="$assets_dir/icon-small.svg" ;; esac
    rsvg-convert -w "$size" -h "$size" "$source_svg" -o "$assets_dir/icon-$size.png"
done
cp "$assets_dir/icon-small.svg" "$assets_dir/../site/favicon.svg"
cp "$assets_dir/icon-32.png" "$assets_dir/../site/favicon-32.png"
