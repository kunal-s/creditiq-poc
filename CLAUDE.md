# CreditIQ, RBL Bank instance: working rules

This repository is the RBL Bank (Business Banking Group) instance of CreditIQ. It was cloned from the generic product. The generic repository must never be modified.

## Read first

- The approved build plan, the handoff note, the reference reports and the design reviews live in `workflow/docs/` (git-ignored, never committed). Start with `HANDOFF.md`, then `plan.md`.
- Before building anything in the document-intelligence layer (intake to confidence gate), read `workflow/docs/reviews/2026-09-23-document-intelligence-review.md`; it reconciles the user's six-layer architecture (`workflow/docs/architecture/`) with the plan.
- The reference reports are long. Load one only when the stage you are on needs it.
- Work stage by stage (plan section 7) and stop for the user's sign-off at every checkpoint.

## Hard rules

1. **WSL only.** Write nothing to the Windows filesystem or under `/mnt/c`. Code, data, captures, notes and temporary files stay on the WSL filesystem (`/tmp` for scratch). The Windows `Prospects/RBL` folder (including its `RBL Poc` subfolder) is read-only source material. Copies of the FRD and the brief's OCR text live in `workflow/docs/reference/source/`. **Call transcripts are never copied into WSL**: read them in place in the Windows folder.
2. **Never push to `upstream`.** It is the generic repository and it syncs to an external hosted editor. Push is disabled on purpose. Push only to a remote the user names.
3. **Private material never enters git.** It all lives under the git-ignored `workflow/`: the stakeholder-name list and API keys (`workflow/private/`, mode 700), route captures (`workflow/captures/`; pre-strip ones contain removed names), copies of source documents (`workflow/docs/`), and all case data (`workflow/data/` is the default `CREDITIQ_DATA_ROOT`; real case files in `workflow/data/real`, mode 700). Never `git add -f` anything under `workflow/`. **Never run `git clean -x` or `-X`**: it deletes ignored files, which would wipe the data root and the audit ledger. Never read `.env` values into a conversation.
4. **Configuration governs behaviour; nothing learns at runtime.** Pipeline, review, copilot and harness code must not be able to import the configuration writer. An administrator's publish creates a new immutable version; nothing is edited in place.
5. **No wall clock in rules.** Age and window checks use the case's fixed `as_of` date.
6. **Determinism is record and replay** of model responses. Do not send sampling parameters to model APIs.
7. **Extraction is per document and context-free.** Never normalise an identifier toward another document's value.
8. **Generated documents** never describe their own defects, never name a real company or lender in a planted finding, never imitate a government seal, emblem, QR code or security feature, and carry only the single-line footer (no watermark).
9. **Nothing on screen may read as anything other than a working system at the bank**: no references to people at the bank, to meetings or to requirement rationale, and none of the excluded terms in FR-19. Every label comes from the terminology configuration.
10. **Licences**: no AGPL, GPL or LGPL runtime dependencies (for example PyMuPDF, Ghostscript, OCRmyPDF, img2pdf, docxtpl, python-Levenshtein).

## Environment

- Check `whoami` inside WSL at the start of a session; it should be `zeya`, who owns this clone. If it reports `root`, run tools with `-u zeya` and re-own anything you wrote.
- Node >= 22.12 is required. The system Node is too old; use the nvm install under `/home/zeya/.nvm` (v22.23.2). Use npm; there is no bun.
- Python 3.12 has no pip: create a virtual environment (`python3 -m venv .venv`) and pin dependencies in a lockfile.
- Tesseract 5 (English only so far) and poppler-utils are installed. `pdftoppm` writes to stdout only when no output prefix is given; a lone `-` is treated as a file-name prefix.
- From the Windows-side shell, pass multi-line or quoted scripts to WSL base64-encoded (`echo <b64> | base64 -d | bash`); inner double quotes are otherwise stripped.

## Cost discipline

Default to a smaller model for routine work. Move to a stronger model only for the three Stage C spikes, checkpoint reviews, or a problem that has resisted two attempts. Prefer scripts to retyping large content, and targeted reads to whole-file reads.
