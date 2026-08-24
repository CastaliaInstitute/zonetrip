# Zone Trip Processor

The processor is the local AI boundary for speech-to-text and derived world-model updates.

It is designed to run on the same Linux booth PC as the microphone capture process. Cloud Run is only a simulator for sizing and operational review. GitHub Pages is only a visual/browser simulation of the installation.

## Local Runtime

Local path:

1. A microphone connected to the booth PC captures audio.
2. The local capture process sends temporary audio to the processor on the same Linux box.
3. Processor runs Whisper through `faster-whisper`.
4. Processor reads immutable `charter.md` and current durable `model.md`.
5. Processor sends `charter.md`, `model.md`, and the temporary STT transcript to local Ollama.
6. Ollama proposes typed derived objects; the processor attaches warrants,
   uncertainty, prohibited claims, retention classes, and deterministic checks.
7. `/finalize-day` creates a pending review packet without publishing it.
8. A steward approves or rejects the packet through `/review-day`.
9. Approval writes the bounded public reflection, signs an attestation, burns
   the daily ledger and notes, and writes a deletion receipt.
10. Temporary audio and transcript buffers die with each request.

Daily batch mode changes steps 5-7:

1. Each audio segment is converted into charter-filtered derived notes.
2. The raw audio and STT transcript die with the request.
3. The day notes are held in `ZONETRIP_DAY_NOTES_PATH`.
4. `/finalize-day` integrates those notes into a pending draft and review packet.
5. Semantic review occurs while supporting derived material still exists.
6. `/review-day` publishes only an approved draft, then clears burn-class state.

Default local endpoints:

- `GET http://127.0.0.1:8090/health`
- `POST http://127.0.0.1:8090/process-audio`

Development-only endpoint:

- `POST http://127.0.0.1:8090/process-stt`

Daily review endpoints:

- `POST http://127.0.0.1:8090/finalize-day`
- `GET http://127.0.0.1:8090/review-day`
- `POST http://127.0.0.1:8090/review-day`

`/process-stt` is disabled unless `ZONETRIP_ENABLE_DEV_STT=1` is set.

## Install On The Booth PC

Install the static site first:

```sh
sudo ./install.sh
```

Then install Ollama and the processor on the same machine:

```sh
sudo ./scripts/install-local-ai.sh
```

The installer:

- installs Ollama if missing
- creates `/opt/zonetrip/.venv`
- seeds `/var/lib/zonetrip/model.md` from the packaged model
- installs `services/processor/requirements.txt`
- pulls `gemma3:12b` by default
- installs `zonetrip-processor.service`

Override the model before installing:

```sh
sudo ZONETRIP_OLLAMA_MODEL=gemma3:4b ./scripts/install-local-ai.sh
```

By default the installed browser simulator is nearly identical to GitHub Pages:
it shows the same booth scene, starts with the same threshold, listens through
the microphone path, and keeps the text drawer hidden. The only default
difference is that local install points `worldModelEndpoint` at the localhost
processor.

## Capture From The Booth Microphone

The real booth path does not require a participant browser. For a single capture pass:

```sh
ZONETRIP_CAPTURE_SECONDS=90 ./bin/zonetrip-capture-once
```

The helper records from the local ALSA default input and posts the temporary audio to `http://127.0.0.1:8090/process-audio`. Override the input device with:

```sh
ZONETRIP_AUDIO_DEVICE=hw:1,0 ./bin/zonetrip-capture-once
```

The browser/Pages route can still simulate capture for review, but it is not the real participant interface.

## Idle Simulation

The browser simulator uses Web Audio RMS as lightweight VAD. `idlePowerdownMs: 60000` dims the eight overhead spots after one minute without detected speech. This is a visual cue for Cloud Run scale-to-zero review; the physical local booth does not need a visitor UI to enforce this state.

The processor also uses faster-whisper with `vad_filter=True`. If Whisper produces no transcript, `/process-audio` returns `422 no speech detected` and skips the `model.md` update.

## Daily Batch Mode

Gemma 3 12B is configured as the default local model and has a nominal long
context window, but a full raw day can still exceed practical local memory and
latency limits. Daily batch mode avoids reasoning over a saved full transcript.

Enable it with:

```sh
sudo ZONETRIP_DAILY_BATCH_MODE=1 ./scripts/install-local-ai.sh
```

In this mode, `/process-audio` and development `/process-stt` generate
charter-filtered segment notes instead of immediately rewriting `model.md`.
The segment notes are derived material, not raw transcript. End the day with:

```sh
./bin/zonetrip-finalize-day
```

The processor then reads `charter.md`, current `model.md`, and the segment
notes and creates a pending review packet. It does not publish or clear the
supporting objects. Open `/review/` or query `GET /review-day`, inspect the
draft, warrant, sources, and checks, then submit a decision. Approval publishes
the reflection; either approval or rejection burns the notes, epistemic ledger,
and review packet after writing an attestation and verified burn receipt.

## Cloud Run Simulator

Cloud Run can simulate the one-box booth PC with an L4 GPU:

```sh
./scripts/deploy-cloud-run-processor.sh PROJECT_ID us-central1 zonetrip-processor
```

The simulator container runs:

- Ollama
- `faster-whisper`
- FastAPI processor endpoints

Use it to estimate latency, memory, model size, and cold-start behavior for the equivalent local Linux box. It is not the default participant-material runtime.

## API

Raw audio:

```sh
curl -X POST http://127.0.0.1:8090/process-audio \
  -H 'Content-Type: audio/webm' \
  --data-binary @sample.webm
```

Existing STT text, after starting the processor with
`ZONETRIP_ENABLE_DEV_STT=1`:

```sh
curl -X POST http://127.0.0.1:8090/process-stt \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"I feel the community is changing, but I am not sure what we are losing."}'
```

Finalize and approve a reviewed day:

```sh
curl -X POST http://127.0.0.1:8090/finalize-day
curl http://127.0.0.1:8090/review-day
curl -X POST http://127.0.0.1:8090/review-day \
  -H 'Content-Type: application/json' \
  -d '{"reviewer_role":"independent steward","decision":"approve","rationale":"Bounded, non-directive, and adequately supported."}'
```

## Development Text Input

The installed local simulator can enable a drawer text form for development:

```sh
sudo ZONETRIP_ENABLE_DEV_TEXT=1 ./scripts/install-local-ai.sh
```

That opt-in writes this local browser configuration:

```js
window.ZoneTripBoothConfig = {
  worldModelEndpoint: "http://127.0.0.1:8090/process-audio",
  textModelEndpoint: "http://127.0.0.1:8090/process-stt",
  reviewEndpoint: "http://127.0.0.1:8090/review-day",
  devTextInput: true,
};
```

The installer also writes `/etc/default/zonetrip-processor` with
`ZONETRIP_ENABLE_DEV_STT=1`, so the API and browser shortcut are enabled
together. Without that opt-in, `/process-stt` returns 404 and the drawer form
stays hidden. The form is only a developer shortcut for testing the STT-output
side of the loop. It posts text to `/process-stt`, renders the returned
`model_markdown`, and clears the textarea after a successful update. The real
booth remains microphone-only.

Response fields are limited to constitutionally allowed derived signals:

- `tensions`
- `contradictions`
- `absences`
- `symbolic_patterns`
- `minority_signals`
- `open_questions`
- `rejected_content`
- `raw_transcript_retained`
- `model_markdown`

`model_markdown` is the complete current derived `model.md`. It is generated under `charter.md` and must not contain transcript text.

## Contract Regression Test

Run the local processor contract checks with a Python environment that has
`services/processor/requirements.txt` installed:

```sh
python scripts/test-processor-contract.py
```

The test covers audio content-type handling, model Markdown normalization, raw
transcript scrubbing, subgroup-term scrubbing, deterministic constitutional
validation, human review gating, publication, and verified burn behavior.

## Community Simulation

Run the synthetic community simulation with:

```sh
python -m pip install -r services/processor/requirements.txt
python scripts/simulate-community.py
```

The harness uses deterministic fixtures in `simulations/community-fixtures/` to
evaluate whether simulated temporary inputs become durable model structure
without transcript retention, representational claims, recommendations, ranking,
identity exposure, or faction adjudication. It writes the current evaluation to
`simulations/reports/community-evaluation.md`.

To compare per-utterance updates with end-of-day batch reasoning:

```sh
python scripts/test-daily-batch-hypothesis.py
```

That experiment writes `simulations/reports/daily-batch-hypothesis.md`.
