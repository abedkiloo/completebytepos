# daily_notes

## Purpose

Staff daily journal, checklist, and kanban board (**To do / Doing / Past**), plus sticky blockers (e.g. approval rejection notices) that must be resolved before continuing.

## Key models

| Model | Role |
|-------|------|
| `DailyNote` / `DailyNoteChecklistItem` | Day journal + checklist |
| `DailyTask` | Standalone tasks (open/done) |
| `DailyNoteReview` | Ask a colleague to review a finished note |

## Board behaviour

| Column | Rule |
|--------|------|
| To do | Open and not in progress |
| Doing | Open and `in_progress` |
| Past | `is_done` (Mark done / move to Past) |

- `POST .../notes/{id}/toggle-done/` marks done and **persists** `in_progress=false` so the note stays in Past.
- Carried-over open notes appear on later days until finished; finishing them today keeps them on **today’s Past**.
- Assignees may move board column only; authors edit/delete freely.

## Public APIs

Prefix: `/api/daily-notes/`

| Surface | Endpoints |
|---------|-----------|
| Notes | CRUD, `toggle-done`, checklist `toggle-done`, `blocking`, `recent-dates`, review |
| Tasks | CRUD, `toggle-done`, `pending`, `pending-count` |

## Bounds & invariants

- Sticky notes must be resolved before assignee continues system use where enforced.
- Notes keyed by calendar `note_date` + author/assignee/role.
- Sale-return sticky notices cannot be ticked; the sale must be fixed.
- Checklist item ticks do not auto-close the parent note.

## Module packaging

Gated by `ModuleSettings` / features: sticky, checklists, priority, tasks, note review (`daily_notes.module_settings`).

## Audit

Create/resolve sticky paths should emit audit or be tied to the originating approval audit.

## Tests

- `be/daily_notes/tests/` — unit, API, board Mark-done, carry-over, security/IDOR, stress
- FE: `DailyNotes.test.js`, `dailyNotesSticky.test.js`
- Mobile: `mobile/test/features/daily_notes/`
