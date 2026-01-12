# Implementation Plan - System Completion & Persistence Wiring

This plan focuses on fixing the "disconnected" parts of the UI identified in the system audit: Snip deletion, History view population, and Dashboard real data.

## Goal
Ensure the application shell accurately reflects the persistent state of the user's data, achieving true "feature parity" with Mathpix's management capabilities.

## User Review Required
> [!IMPORTANT]
> **Data Loss Risk**: Fixes to `Snip deletion` will effectively delete data from the disk. This is intended behavior but irreversible.
>
> **History Behavior**: I will implement "History" as a view of *all* processed extractions (automatically logging every scan), whereas "Snips" are explicitly *saved* items. This distinguishes the two features.

## Proposed Changes

### 1. Fix Snip Deletion (Critical Blocker)
**Status**: Currently UI-only. Snips reappear on restart.
**Files**: `ui/snips_page.py`, `ui/main_window.py`

#### [MODIFY] [ui/snips_page.py]
- Update `add_snip` to store `snip_id`.
- Update `_remove_snip` to emit a `snip_deleted` signal instead of just removing the widget.
- Add `snip_deleted` signal to class.

#### [MODIFY] [ui/main_window.py]
- Connect `snip_deleted` signal to a new handler `_on_snip_deleted`.
- Handler calls `self.snip_repo.delete(snip_id)`.

### 2. Implement History Wiring (Critical Blocker)
**Status**: Currently a "Ghost UI".
**Strategy**: "History" = Log of all extractions (auto-saved). "Snips" = Favorites (explicit save).
**Files**: `ui/main_window.py`, `ui/history_view.py`, `services/persistence/history_repository.py`

#### [NEW] [services/persistence/history_repository.py]
- Clone of `SnipRepository` but for `history.jsonl`.
- `add()` method for logging extractions without user intervention.

#### [MODIFY] [ui/main_window.py]
- Initialize `HistoryRepository`.
- In `_on_formula_extracted` (or `ocr_region`), automatically call `self.history_repo.add()`.
- Populate `HistoryView` on startup/tab switch using `history_repo.get_all()`.

### 3. Real Dashboard Data
**Status**: Shows hardcoded fake data.
**Files**: `ui/dashboard_view.py`, `ui/main_window.py`

#### [MODIFY] [ui/dashboard_view.py]
- Add method `update_recent_snips(snips: list)`.

#### [MODIFY] [ui/main_window.py]
- Remove `_populate_dashboard_samples`.
- Call `dashboard.update_recent_snips` with data from `SnipRepository` on load.

## Verification Plan

### Manual Verification
1.  **Delete Test**: Save a snip, restart app, verify it exists. Delete it, restart app, verify it is GONE.
2.  **History Test**: Scan an equation *without* clicking save. Go to History tab. Verify the equation appears there.
3.  **Dashboard Test**: Open app. Verify "Recent Snips" shows actual saved content, not "quadratic formula" placeholder.
