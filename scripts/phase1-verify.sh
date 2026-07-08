#!/bin/bash
# Phase 1 Verification: 验证三只猫能独立 git commit & push
set -e

TMP="/tmp/teamchat-verify"
REPO="YancyLyx/TeamChat"

echo "============================================"
echo " Phase 1 Verification — Agent Identity Test"
echo "============================================"
echo ""

# --- cici咪 ---
echo "--- Testing cici咪 (Claude Architect) ---"
if [ -z "$TEAMCHAT_CICI_TOKEN" ]; then
  echo "  ❌ FAIL: TEAMCHAT_CICI_TOKEN 未设置"
else
  rm -rf "${TMP}-cici"
  git clone "https://x-access-token:${TEAMCHAT_CICI_TOKEN}@github.com/${REPO}.git" "${TMP}-cici" 2>&1 | sed 's/^/  /'
  cd "${TMP}-cici"
  git config user.name "cici咪 (Claude Architect)"
  git config user.email "claude@teamchat.local"
  mkdir -p .teamchat
  date -u +"%Y-%m-%dT%H:%M:%SZ" > .teamchat/identity-cici.txt
  git add .teamchat/identity-cici.txt
  git commit -m "verify: cici咪 身份验证通过"
  git push 2>&1 | sed 's/^/  /'
  cd /
  rm -rf "${TMP}-cici"
  echo "  ✅ PASS"
fi
echo ""

# --- coco咪 ---
echo "--- Testing coco咪 (Codex Developer) ---"
if [ -z "$TEAMCHAT_COCO_TOKEN" ]; then
  echo "  ❌ FAIL: TEAMCHAT_COCO_TOKEN 未设置"
else
  rm -rf "${TMP}-coco"
  git clone "https://x-access-token:${TEAMCHAT_COCO_TOKEN}@github.com/${REPO}.git" "${TMP}-coco" 2>&1 | sed 's/^/  /'
  cd "${TMP}-coco"
  git config user.name "coco咪 (Codex Developer)"
  git config user.email "codex@teamchat.local"
  mkdir -p .teamchat
  date -u +"%Y-%m-%dT%H:%M:%SZ" > .teamchat/identity-coco.txt
  git add .teamchat/identity-coco.txt
  git commit -m "verify: coco咪 身份验证通过"
  git push 2>&1 | sed 's/^/  /'
  cd /
  rm -rf "${TMP}-coco"
  echo "  ✅ PASS"
fi
echo ""

# --- soso咪 ---
echo "--- Testing soso咪 (Cursor QA) ---"
if [ -z "$TEAMCHAT_SOSO_TOKEN" ]; then
  echo "  ❌ FAIL: TEAMCHAT_SOSO_TOKEN 未设置"
else
  rm -rf "${TMP}-soso"
  git clone "https://x-access-token:${TEAMCHAT_SOSO_TOKEN}@github.com/${REPO}.git" "${TMP}-soso" 2>&1 | sed 's/^/  /'
  cd "${TMP}-soso"
  git config user.name "soso咪 (Cursor QA)"
  git config user.email "cursor@teamchat.local"
  mkdir -p .teamchat
  date -u +"%Y-%m-%dT%H:%M:%SZ" > .teamchat/identity-soso.txt
  git add .teamchat/identity-soso.txt
  git commit -m "verify: soso咪 身份验证通过"
  git push 2>&1 | sed 's/^/  /'
  cd /
  rm -rf "${TMP}-soso"
  echo "  ✅ PASS"
fi
echo ""

echo "============================================"
echo " Verification Complete — check GitHub:"
echo " https://github.com/${REPO}/commits/main"
echo "============================================"
