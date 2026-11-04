# daily_notes

## Purpose

Staff daily journal/checklist and board tasks, including sticky blockers (e.g. approval rejection notices) that must be resolved before continuing.

## Key models

| Model | Role |
|-------|------|
| `DailyNote` / `DailyNoteChecklistItem` | Day journal + checklist |
| `DailyTask` | Board / sticky tasks |

## Public APIs

Prefix: `/api/daily-notes/`

## Bounds & invariants

- Sticky notes must be resolved before assignee continues system use where enforced.
- Notes keyed by calendar `note_date` + author/assignee/role.

## Audit

Create/resolve sticky paths should emit audit or be tied to the originating approval audit.

## Gaps

- Public API docstrings: **done** for ``models.py``, ``services.py``, and ``approval_notice`` public helpers; views/serializers still partial.
