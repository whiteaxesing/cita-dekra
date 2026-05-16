# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Desktop app (CustomTkinter) that monitors DEKRA Costa Rica's booking API for available vehicle inspection appointments. Can alert the user via sound/voice and auto-book the first available slot.

## Running the app

```bash
python3 app_tk.py
```

macOS only — if `_tkinter` is missing: `brew install python-tk`

## Architecture

Five files, each with a single responsibility:

| File | Role |
|------|------|
| `config.py` | Hardcoded DEKRA tenant/product IDs and API base URL |
| `api.py` | All HTTP calls to the DEKRA booking API |
| `monitor.py` | Background thread that polls availability and triggers auto-booking |
| `app_tk.py` | CustomTkinter UI — two tabs: Monitor and Mis datos |

**Customer data** is stored in `~/.cita_dekra.json` (written by the UI). It is never imported from a file at module load time. `monitor.py` receives the customer dict via `monitor.configure(..., customer=...)`.

## DEKRA booking API flow

The booking sequence must follow this exact order or the server returns `THERE_ARE_NO_LONGER_ANY_AVAILABLE_RESOURCE`:

1. `POST /filter-time-slots` — get available slots for the day (no `selectedTimeslots`)
2. `POST /filter-time-slots` — same call but with `selectedTimeslots: [chosen_slot]` — server marks the slot with `isFirstSelected: true` and returns `scheduleIds`, `combinedResourceIds`, `onlinePrice`, etc.
3. `POST /{locationId}/confirm-booking-timeslots` — send the **full slot object** from step 2 (not just minimal fields)
4. `POST /retail` — `productBookingCreateItems[0]` must use `selectedTimeSlot.timeslots` with the complete list of slots from step 2, not a flat item

A shared `requests.Session` in `api.py` maintains cookies across all calls.

## Building executables

GitHub Actions builds Mac (`.app` zipped) and Windows (`.exe`) on every tag push:

```bash
git tag v1.x
git push origin v1.x
```

Artifacts appear in the GitHub release. Build config: `.github/workflows/build.yml`.
