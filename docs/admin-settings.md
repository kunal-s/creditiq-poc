# Administration settings (F-00.6)

| | |
|---|---|
| Date | 12 October 2026 |
| Screen | Administration → Settings (`/admin/settings`) |
| Who edits | The Administrator (role `administrator`, permission `config.publish`; test user Nikhil Sawant, nikhil.sawant@rblbank.com) |
| Who reads | Credit Analysts and Credit Managers (`config.read`), read-only |

## 1. What can be changed

| Panel | What | Configuration |
|---|---|---|
| Tolerances | Every cross-check tolerance's value (turnover variance, name match, EMI and facility amounts, months shared, days to the tax return, profit variance …), with the rules that use each | `tolerances` |
| Policy norms | Each financial ratio's acceptable value (the norm) and marginal value, with the norms that use it; the threshold of every other norm (eligibility, documentation, security cover) | `policy` |
| Cross-check rules | Each rule: whether it runs, its severity, whether it blocks submission | `crosschecks` |
| Approval matrix | Each product's amount bands (entered in INR crore) and the authority of each band; each deviation category's levels above the amount authority and its minimum authority | `approval_matrix` |

Everything else (rule wording and sources, document types, the checklist, statements, alignment, the CAM) is still authored in `config/` and published from the command line.

Changing the request-against-turnover norm (EL-05) also changes the turnover method's working-capital requirement, keeping the borrower's margin. The norm is defined as requirement less margin (25% − 5% = 20%), so the two move together and the review shows both changes.

## 2. How a change is made

1. The Administrator signs in and lands on Settings (the role has no workbench and no access to appraisals).
2. Edits stay in a draft on the screen. Each changed field is marked, shows the value in force ("was 1%"), and can be undone. A bar counts the changes, with **Discard** and **Review and publish**.
3. **Review** asks the engine for a preview. It shows each change before and after, and any reason the changes cannot be published, for example:
   - a similarity outside 0.5 to 1;
   - a percentage over 100;
   - a marginal ratio stricter than the acceptable one;
   - amount bands that do not rise;
   - an unknown authority.

   Nothing is published by a preview.
4. **Publish** needs a note of at least three characters. Then:
   - The engine checks the changes as a publish from the files is checked (each section's schema, then the cross-section checks).
   - It writes a new immutable version with the Administrator's name and the note. The version is marked as edited on the screen (`origin: app`) and lists the changes.
   - It records `config.published` in the audit trail and re-runs every case's checks. The screen says how many cases were re-checked.
5. Administration → Configuration lists the new version with **Edited on screen**.

## 3. Publishing from the files afterwards

A publish from `config/` would otherwise undo an edit made on the screen. So when the version in force was edited on the screen and the files say otherwise for an edited section, `creditiq config publish` refuses and names the sections.

There are two ways forward:
- carry the values into the files (`creditiq config diff` shows them);
- publish with `--discard-app-edits` to replace them deliberately.

## 4. Rules kept

- **Configuration still governs behaviour** (CLAUDE.md rule 4). Only the command line and `engine/admin_config.py` reach the configuration writer. The API reaches it through that module, for the Administrator only. Nothing that runs on a case can import either: `.importlinter` contract 1, indirect imports included.
- **Versions are immutable.** A publish from the screen is a new version, never an edit of one.
- **Role gating is on the server.** Preview and publish need `config.publish`; reading needs `config.read`.

## 5. Code

| Part | Files |
|---|---|
| Engine | `engine/admin_config.py` (the editable view, applying and checking changes, publish and re-run); `engine/configstore/writer.py` (`publish_edited`, `app_edits_at_risk`, one write step for both publishes); `engine/configstore/reader.py` (`published_sections`, `origin` in the history); `engine/pipeline.py` (`refresh_all_cases`, shared with the command line); `engine/cli.py` (the guard); `engine/api.py` (`GET /api/admin/settings`, `POST /api/admin/settings/preview`, `POST /api/admin/settings/publish`) |
| Contracts | `engine/contracts/admin.py` (`EditableSettings`, `SettingsChanges`, `SettingsPreview`, `SettingsPublished`, `ConfigVersion.origin`); regenerated `contracts/openapi.json`, `src/api/schema.gen.ts` |
| Configuration | `config/roles.yaml` (the Administrator role and user), `.importlinter` |
| Screen | `src/routes/admin.settings.tsx`, `src/components/admin/SettingControls.tsx`, `src/components/admin/ReviewDialog.tsx`, `src/domain/settings.ts`, `src/domain/admin.ts`, `src/api/client.ts`; the landing for a user without the workbench (`src/routes/index.tsx`, `homePath` in `src/components/shell/nav.ts`); **Edited on screen** in `src/routes/admin.index.tsx`; labels in `terminology/rbl.yaml` |
| Docs | `docs/functional-requirements.md` (F-00.6, the Administrator's role, the screen map), `CLAUDE.md` rule 4 |

## 6. Tests

- **Engine:** `tests/test_admin_settings.py` (25):
  - the Administrator's sign-in and access;
  - the settings as published;
  - only the Administrator may preview or publish;
  - a preview lists each change and publishes nothing;
  - a publish makes a version from the app, re-runs every case (a 4% GST-to-bank gap fails at 1% and passes after 10% is published) and is audited;
  - a rule switched off stops running;
  - policy and matrix changes reach their screens;
  - each refused value with its reason, and a note required;
  - the command-line guard.
- **Screens:** `e2e/admin-settings.spec.ts` (9):
  - the Administrator lands on Settings;
  - a change is marked and can be undone or discarded;
  - the review formats the change and requires a note;
  - publishing, and the new version in the history;
  - problems block publishing;
  - rule changes in the review;
  - a band in crore is sent in rupees;
  - an analyst sees the page read-only.

Results on 12 October 2026:
- **Python:** 649 passed, 2 skipped (the full suite less the known Windows-only `test_f05` cases).
- **Screen tests:** 128 of 129 passed; the one failure is the known Windows-only `e2e/tc16-query-list.spec.ts`.

## 7. Also fixed

The label of the facility-amount tolerance was cut at a comma ("… between the declaration"), because the YAML label was not quoted. It now reads in full: "Sanctioned amount of one facility between the declaration, sanction letters and the bureau".

## 8. Noted

- A problem is a sentence without the field it concerns, so the screen lists problems rather than marking fields.
- Counts held as tolerances (monthly debits, months shared) have the unit `ratio` in configuration and show without a unit.
- Re-running every case happens within the publish request. It takes about a third of a second per case, so a large case store would need it moved to the job queue.
