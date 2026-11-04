#!/bin/bash
# macOS: bấm đúp file này trong Finder là chạy (Terminal tự mở).
# (macOS yêu cầu đuôi .command cho file bấm đúp được.)
cd "$(dirname "$0")"
exec ./chay-web.sh "$@"
