#!/usr/bin/env bash
# codex_status.sh — at-a-glance view of the Claude↔Codex handoff loop.
#
# Shows:
#   - pending Codex tasks (not yet done)
#   - in-progress Codex tasks
#   - pending review requests from Codex awaiting Claude
#   - pending review responses from Claude awaiting Codex
#   - new git commits since last local main
#
# Usage:  bash scripts/codex_status.sh
# Intent: run this any time you want to know "where is the loop stuck?"
#         without paging through the whole handoff/ tree.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "═══ CLAUDE ↔ CODEX HANDOFF LOOP STATUS ═══"
echo

echo "── Tasks queued for Codex (pending/in-progress) ──"
for f in handoff/codex/[0-9]*.md; do
    [[ -e "$f" ]] || continue
    status=$(grep '^status:' "$f" | head -1 | awk '{print $2}')
    id=$(basename "$f" .md)
    echo "  [${status:-?}] $id"
done
echo

echo "── Tasks completed by Codex (done/) ──"
ls handoff/codex/done/ 2>/dev/null | sed 's/^/  [done] /' || echo "  (none)"
echo

echo "── Review requests from Codex → Claude ──"
for f in handoff/review/*_review_*.md; do
    [[ -e "$f" ]] || continue
    # Skip response files — only enumerate the original review requests.
    [[ "$f" == *_review_response.md ]] && continue
    id=$(basename "$f" .md | sed 's/_review.*//')
    response="handoff/review/${id}_review_response.md"
    if [[ -f "$response" ]]; then
        verdict=$(grep '^status:' "$response" | head -1 | awk '{print $2}')
        echo "  [responded: ${verdict:-?}] $id"
    else
        echo "  [PENDING CLAUDE REVIEW] $id"
    fi
done
echo

echo "── Local commits not pushed to origin/main ──"
git fetch origin main --quiet 2>/dev/null || true
git log origin/main..HEAD --oneline || echo "  (none)"
echo

echo "── Origin commits not pulled locally ──"
git log HEAD..origin/main --oneline || echo "  (none)"
echo

echo "═══ Quick actions ═══"
echo "  Run Codex's pending task:    read handoff/codex/00N_*.md"
echo "  Review Codex's delivery:     read handoff/review/00N_review_*.md"
echo "  Sync with remote:            git pull --ff-only"
echo "  Run quality gate:            .venv/bin/pytest tests/ -q && \\"
echo "                                .venv/bin/ruff check master_of_hwp tests && \\"
echo "                                .venv/bin/black --check master_of_hwp tests && \\"
echo "                                .venv/bin/mypy master_of_hwp"
