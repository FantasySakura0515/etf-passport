#!/usr/bin/env bash
# 下載前端依賴到 demo/vendor/，讓「Mock 模式」可以在無網路環境執行（決賽現場備援）
#
# 使用：
#   bash fetch_vendor.sh
#
# 全部 4 個檔案合計約 2–3 MB，下載一次後 demo 就能完全離線跑。

set -euo pipefail

cd "$(dirname "$0")/vendor"

download() {
  local url="$1" dest="$2"
  if [ -s "$dest" ]; then
    printf '✓ %-40s (already exists)\n' "$dest"
    return
  fi
  printf '→ Downloading %s\n' "$dest"
  curl -fsSL "$url" -o "$dest"
  printf '✓ %-40s (%s)\n' "$dest" "$(du -h "$dest" | cut -f1)"
}

download "https://cdn.tailwindcss.com/3.4.16"                                    "tailwindcss.js"
download "https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"              "marked.min.js"
download "https://cdn.jsdelivr.net/npm/dompurify@3.0.9/dist/purify.min.js"       "dompurify.min.js"
download "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"       "mermaid.min.js"

echo ""
echo "✅ All vendor files ready in demo/vendor/"
echo "   現在即使無網路，python3 server.py 起來後 Mock 模式可正常 Demo。"
