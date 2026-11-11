# Proving a UI change

## Browser tests against the mock engine (`chromium` project)

- Specs live in `e2e/*.spec.ts`; the engine is answered in the browser by `MockApi`
  (`e2e/support/api.ts`) with fixtures from `e2e/fixtures/data.ts` — cases `KESTREL` (not ready:
  9 requirements, 2 satisfied, 2 missing, 4 insufficient, 1 in review), `SAFFRON` (ready) and
  `ORIEL` (provisional). Users `ANALYST` (default), `RM`, `MANAGER`, `ADMIN`.
- Start a test with `const api = new MockApi(); await signedIn(page, api, user?)`, then
  `page.goto(...)`. Change a fixture with `api.on("GET", /regex/, () => ({ json }))` or the helpers
  on `MockApi` (`api.cam`, `api.checklists`, `api.files` …). Assert on what the screen sent with
  `api.calls`, `api.camCalls`, `api.downloads`.
- If you add an endpoint call, add it to `MockApi.install` the way the engine answers it (status
  codes, refusals and all).
- Select by `data-testid` (kebab-case, `area-thing`, e.g. `cam-sheet-cell`, `journey-filter-missing`);
  add `data-*` attributes for state the test needs (`data-status`, `data-section`, `data-ref`).
  Prefer roles and visible text when the text is the point of the test.
- Run: `E2E_PORT=5175 npx playwright test --project=chromium e2e/<spec>.spec.ts` (port 5175 so it
  never reuses the user's dev server). The full suite: drop the file argument (~4–5 min).
- Phone layout: `MOBILE_WIDTH=320 E2E_PORT=5175 npx playwright test --project=chromium
  e2e/mobile-layout.spec.ts`, and again at 400 and 768. A failure under load that passes alone
  (`--repeat-each=3`) is timing, not a defect — say so rather than hide it.

## Engine-backed tests

`e2e/integration/**` (project `integration`) drive the real engine on port 8011 with a disposable
data root and recorded document reads. They need the engine stack; update them when you change a
test id they read, and run them when you change engine behaviour.

## Python

Engine changes: `.venv/bin/python -m pytest -q tests/<file>.py`; the whole suite takes ~3 minutes.

## Screenshots: look before you say done

Write a throwaway spec (`e2e/zz-shots.spec.ts`) that signs in with `MockApi`, opens the screen,
waits for its main test id and calls `page.screenshot({ path: <scratch dir>/x.png, fullPage })` at
1440×1000, 1920×1080 and 400×860; run it, **read every image**, then delete the spec. For the
user's own data, sign in through `e2e/support/engine.ts` `signIn()` against their engine (never type
or print a password) and screenshot their running app. Compare with the hosted original design for
that screen where one exists.

## Gates before handing back

`npx prettier --check <changed>` · `npx tsc --noEmit` · `npx eslint src e2e` (0 errors; existing
warnings are known) · `npm run check:terms` · `npm run build` · the specs you touched · the phone
layout at three widths. `npm run check` runs everything (slow).
