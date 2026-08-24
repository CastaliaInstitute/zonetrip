#!/usr/bin/env python3
"""Regression checks for the Zone Trip processor contract."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "processor"))

import app  # noqa: E402
import epistemic  # noqa: E402


def assert_no_hits(haystack: str, needles: list[str]) -> None:
  lowered = haystack.lower()
  hits = [needle for needle in needles if needle.lower() in lowered]
  if hits:
    raise AssertionError(f"unexpected retained text: {hits}")


def test_audio_suffixes() -> None:
  cases = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".mp4",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
  }
  for content_type, expected in cases.items():
    actual = app.audio_suffix(content_type)
    if actual != expected:
      raise AssertionError(f"{content_type}: expected {expected}, got {actual}")


def test_model_markdown_sanitization() -> None:
  transcript = (
    "I want this booth to tell the town which side is right and name the people "
    "who are wrong. Younger people cannot imagine staying."
  )
  payload = {
    "tensions": ["Younger people cannot imagine staying."],
    "rejected_content": [
      "I want this booth to tell the town which side is right and name the people who are wrong."
    ],
    "model_markdown": (
      "# Zone Trip World Model\\n\\n"
      "## Symbol,ic Patterns\\n\\n"
      "- `young peoples concern about staying`\\n\\n"
      "## Rejected Boundary Material\\n\\n"
      "- \"I want this booth to tell the town which side is right and name the people who are wrong.\""
    ),
  }
  result = app.normalize_result(transcript, payload)
  combined = "\n".join(
    [
      result.model_markdown,
      "\n".join(result.tensions),
      "\n".join(result.rejected_content),
      "\n".join(result.symbolic_patterns),
    ]
  )
  assert result.raw_transcript_retained is False
  assert "## Symbolic Patterns" in result.model_markdown
  assert_no_hits(
    combined,
    [
      "which side is right",
      "name the people",
      "younger people",
      "young people",
      "young peoples",
    ],
  )


def test_model_markdown_prose_sanitization() -> None:
  transcript = "A named committee should be blamed because the river road failed again."
  payload = {
    "model_markdown": (
      "# Zone Trip World Model\n\n"
      "## Tensions\n\n"
      "A named committee should be blamed because the river road failed again."
    )
  }
  result = app.normalize_result(transcript, payload)
  assert_no_hits(result.model_markdown, ["named committee", "river road", "failed again"])


def test_dev_stt_disabled_by_default() -> None:
  original = app.ENABLE_DEV_STT
  app.ENABLE_DEV_STT = False
  try:
    try:
      app.process_stt(app.SttRequest(transcript="temporary development input"))
    except app.HTTPException as error:
      if error.status_code != 404:
        raise AssertionError(f"expected 404, got {error.status_code}") from error
    else:
      raise AssertionError("process_stt should be unavailable by default")
  finally:
    app.ENABLE_DEV_STT = original


def test_day_notes_round_trip() -> None:
  original_path = app.DAY_NOTES_PATH
  with tempfile.TemporaryDirectory(prefix="zonetrip-day-notes-") as temp_dir:
    app.DAY_NOTES_PATH = Path(temp_dir) / "day-notes.jsonl"
    try:
      notes = app.SegmentNotes(
        transcript_chars=42,
        tensions=["Growth and continuity remain unsettled."],
        contradictions=[],
        absences=["Future belonging remains underdeveloped."],
        symbolic_patterns=[],
        minority_signals=[],
        open_questions=[],
        rejected_content=[],
      )
      app.append_day_notes(notes)
      loaded = app.read_day_notes()
      if loaded != [notes]:
        raise AssertionError("day notes did not round trip")
      markdown = app.notes_to_markdown(loaded)
      if "Growth and continuity" not in markdown:
        raise AssertionError("day notes markdown missing expected derived signal")
      app.clear_day_notes()
      if app.read_day_notes():
        raise AssertionError("day notes were not cleared")
    finally:
      app.DAY_NOTES_PATH = original_path


def test_segment_notes_sanitization() -> None:
  transcript = "The named street committee should be exposed by the booth."
  notes = app.normalize_segment_notes(
    transcript,
    {
      "tensions": ["The named street committee should be exposed by the booth."],
      "rejected_content": ["The booth should expose the named street committee."],
    },
  )
  combined = "\n".join(notes.tensions + notes.rejected_content)
  assert_no_hits(combined, ["named street committee", "should be exposed"])
  if notes.raw_transcript_retained:
    raise AssertionError("segment notes must not retain raw transcript")


def test_fallback_model_has_no_metadata() -> None:
  generated = app.bounded_markdown(
    "",
    {
      "tensions": ["Need reflection not orders"],
      "rejected_content": ["Attempted ranking"],
    },
    "Need reflection not orders. Attempted ranking.",
  )
  if "Last derived update" in generated:
    raise AssertionError("fallback model should not persist timestamps")
  if "# Zone Trip World Model" not in generated:
    raise AssertionError("fallback model is missing title")


def test_public_reflection_validator() -> None:
  unsafe = epistemic.validate_public_reflection(
    "The community wants change and organizers should publish an action plan."
  )
  failed = {check.rule_id for check in unsafe if not check.passed}
  if not {"ARU-PUBLIC-001", "ARU-PUBLIC-002", "ARU-PUBLIC-005"}.issubset(failed):
    raise AssertionError(f"expected constitutional failures, got {sorted(failed)}")

  safe = epistemic.validate_public_reflection(
    "A tension appears around continuity and change.\n\n"
    "Reflective, not representative. Interpretive, not directive. Not a mandate."
  )
  if not epistemic.checks_pass(safe):
    raise AssertionError(f"safe reflection failed checks: {safe}")

  unsupported = epistemic.build_review_packet(
    deployment_id="test",
    model_markdown="A bounded reflection.",
    supporting_object_ids=[],
  )
  if app.review_packet_passes(unsupported):
    raise AssertionError("an unsupported draft must not pass review")


def test_review_then_burn_lifecycle() -> None:
  path_names = [
    "MODEL_PATH",
    "DAY_NOTES_PATH",
    "EPISTEMIC_LEDGER_PATH",
    "REVIEW_PACKET_PATH",
    "ATTESTATIONS_PATH",
    "BURN_RECEIPT_PATH",
  ]
  original_paths = {name: getattr(app, name) for name in path_names}
  original_generate = app.daily_batch_generate
  with tempfile.TemporaryDirectory(prefix="aru-review-lifecycle-") as temp_dir:
    root = Path(temp_dir)
    for name in path_names:
      setattr(app, name, root / f"{name.lower()}.json")

    notes = app.SegmentNotes(
      transcript_chars=42,
      tensions=["Continuity and change remain in unresolved relation."],
      contradictions=[],
      absences=[],
      symbolic_patterns=[],
      minority_signals=[],
      open_questions=["What forms of belonging remain imaginable?"],
      rejected_content=[],
    )
    app.append_day_notes(notes)
    app.record_segment_notes(notes, "test-deployment")

    safe_result = app.DerivedSignals(
      transcript_chars=0,
      tensions=notes.tensions,
      contradictions=[],
      absences=[],
      symbolic_patterns=[],
      minority_signals=[],
      open_questions=notes.open_questions,
      rejected_content=[],
      raw_transcript_retained=False,
      model_markdown=(
        "# Zone Trip World Model\n\n"
        "## Tensions\n\n- Continuity and change remain in unresolved relation."
      ),
    )
    app.daily_batch_generate = lambda day_notes, persist=False: safe_result
    try:
      packet = app.finalize_day(None)
      if packet.review_status != "pending" or packet.day_notes_cleared:
        raise AssertionError("finalization must pause for semantic review before burn")
      if not app.REVIEW_PACKET_PATH.exists() or not app.DAY_NOTES_PATH.exists():
        raise AssertionError("review material disappeared before review")

      reviewed = app.review_day(
        epistemic.ReviewDecision(
          reviewer_role="independent steward",
          decision="approve",
          rationale="The reflection remains bounded and non-directive.",
        ),
        None,
      )
      if not reviewed.public_reflection_published:
        raise AssertionError("approved reflection was not published")
      if not reviewed.burn_receipt.deletion_verified:
        raise AssertionError("burn was not verified")
      for path in [app.DAY_NOTES_PATH, app.EPISTEMIC_LEDGER_PATH, app.REVIEW_PACKET_PATH]:
        if path.exists():
          raise AssertionError(f"burn-class artifact survived: {path}")
      for path in [app.MODEL_PATH, app.ATTESTATIONS_PATH, app.BURN_RECEIPT_PATH]:
        if not path.exists():
          raise AssertionError(f"durable artifact missing: {path}")
    finally:
      app.daily_batch_generate = original_generate
      for name, value in original_paths.items():
        setattr(app, name, value)


def main() -> None:
  test_audio_suffixes()
  test_model_markdown_sanitization()
  test_model_markdown_prose_sanitization()
  test_dev_stt_disabled_by_default()
  test_day_notes_round_trip()
  test_segment_notes_sanitization()
  test_fallback_model_has_no_metadata()
  test_public_reflection_validator()
  test_review_then_burn_lifecycle()
  print("processor-contract-tests-ok")


if __name__ == "__main__":
  main()
