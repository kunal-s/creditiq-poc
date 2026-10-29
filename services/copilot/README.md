# Case assistant service

A generic chat service: it routes a question to one configured use case, lets the model call only that use case's
typed tools, and answers from what they returned. It knows nothing of the application it serves; everything specific
is in a configuration directory (`config/`, or `COPILOT_CONFIG_DIR`). It never imports `engine` (import contract).

## Run

```sh
python3.12 -m venv .venv && .venv/bin/pip-sync requirements.txt   # once; deps are locked with hashes
COPILOT_DATA_DIR=/path/outside/the/repo PYTHONPATH=. .venv/bin/python -m copilot.cli serve   # :8020
```

From the repository root: `npm run dev:copilot`, or `./scripts/start.sh` for everything.

| Variable | Default | |
|---|---|---|
| `COPILOT_DATA_DIR` / `CREDITIQ_DATA_ROOT` | required | The database (sessions, trace, recorded answers) holds case content; it must live outside git. |
| `COPILOT_MODEL_MODE` | `replay` | `replay` answers only from recordings; `record` calls the model once and stores it; `live` never stores. |
| `COPILOT_CONFIG_DIR` | `./config` | Another application's configuration. |
| `COPILOT_CORS_ORIGINS` | `host.yaml` `cors_origins` | Comma-separated browser origins allowed to call the service. |
| `COPILOT_HOST_URL` | `host.yaml` `base_url` | The application whose API the tools call. |
| `COPILOT_HOST`, `COPILOT_PORT` | `127.0.0.1`, `8020` | Loopback only. |
| `OPENAI_API_KEY` | | Name set in `llm.yaml`; needed for `record` and `live`. |

## Configuration

`host.yaml` (identity endpoint, context keys), `llm.yaml` (models, `temperature`, `seed`), `tools.yaml` (typed
bindings to the host's read endpoints; `result_fields` limits what the model sees of each row), `registry.yaml` (use cases), `runtime.yaml` (router threshold, guards, session
limits, messages), `prompts/*.md`. Check a directory with `python -m copilot.cli config-validate config`.

## API

`POST /chat` `{message, session_id?, context}` streams `session` then `result` (or `error`) as server-sent events;
`GET /sessions/{id}` returns the caller's own transcript and the action still waiting for them (if any); `GET /health`.
`POST /actions/{id}/confirm` `{session_id, context, values}` and `POST /actions/{id}/cancel` `{session_id}` settle a pending action (below). The caller's bearer token is checked against the
host's identity endpoint and forwarded on every tool call, so the host's own access rules apply.

## Acting (draft, then send)

A use case of kind `act` changes something in the host. It is never run by the model:

1. A draft use case (`draft_followup_email`) finishes; its subject and body are parsed from the reply and kept on the
   session as a pending action, bound to the open case and to a lifetime (`session.pending_action_ttl_s`).
2. The user asks to send it. The act use case (`send_followup_email`) calls no tool; it answers `confirm` with the
   values for a confirmation card (to, subject, body).
3. The user checks or edits the values and presses Send. The gateway calls the act tool with the user's own token and
   only those values, with the action id as the idempotency key. It is refused if the action has lapsed, belongs to
   another case, the user no longer holds the permission, or the text still matches `act.blocked_pattern` (unfilled
   `[Name]` placeholders). A refusal keeps the card open; a success clears the action, so it runs once.

An act use case needs an `act` block in `registry.yaml` (the tool, the draft it sends, the wording) and an `act` tool in
`tools.yaml`. The host's `POST /api/cases/{id}/messages` records the message in its outbox and the decision log;
delivery is a later step, so nothing leaves the bank yet.

## Tests

`npm run test:copilot` and `npm run lint:copilot` from the repository root.

The golden set (`tests/fixtures/golden.yaml`) lists what people say, the use case and tool calls each must lead to, and
the ending (answer, ask, cannot do). It replays from recorded model answers (`tests/fixtures/golden_recordings.json`),
so it needs no key and gives the same result every run. Changing a prompt, a use case's examples or a tool description
changes the recorded requests, so the set fails with a replay miss until you re-record:

```sh
PYTHONPATH=. .venv/bin/python scripts/record_golden.py            # report only; calls the model, needs the key
PYTHONPATH=. .venv/bin/python scripts/record_golden.py --write    # and replace the recordings
```

`tests/fixtures/e2e.yaml` holds the questions the integration screen test (`e2e/integration/assistant.spec.ts`) asks, against the
engine's real output for the files it uploads. Its recordings are loaded into the service's store with
`python -m copilot.cli import-recordings <file>` before the test starts.

Every case uses invented data. A case that differs from its expectation is shown with the reason; fix the prompt or the
examples (or the expectation, if it was wrong) and record again. A new use case needs positive cases in the set.
