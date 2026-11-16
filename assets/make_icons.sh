#!/bin/sh
# Run from any directory. Requires librsvg's rsvg-convert.
set -eu
assets_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for size in 1024 512 256 128 64 32; do
    rsvg-convert -w "$size" -h "$size" "$assets_dir/icon.svg" -o "$assets_dir/icon-$size.png"
done
cp "$assets_dir/icon.svg" "$assets_dir/../site/favicon.svg"
cp "$assets_dir/icon-32.png" "$assets_dir/../site/favicon-32.png"
