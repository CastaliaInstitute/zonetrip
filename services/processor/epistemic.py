"""Typed epistemic objects, warrants, validation, review, and burn receipts.

The module deliberately contains no model calls. Models may propose derived
objects; this layer decides whether those objects have the metadata and
constitutional status required to move through the Aru pipeline.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


SCHEMA_VERSION = "aru-epistemic-v0.1"


class ObjectType(str, Enum):
  REDACTED_UTTERANCE = "redacted_utterance"
  OBSERVATION = "observation"
  CANDIDATE_INTERPRETATION = "candidate_interpretation"
  CLUSTER = "cluster"
  THEME_OR_TENSION = "theme_or_tension"
  DRAFT_SYNTHESIS = "draft_synthesis"
  PUBLIC_REFLECTION = "public_reflection"


class RetentionClass(str, Enum):
  BURN_AFTER_REVIEW = "burn_after_review"
  DURABLE_PUBLIC = "durable_public"
  DURABLE_ATTESTATION = "durable_attestation"


class LifecycleState(str, Enum):
  TEMPORARY = "temporary"
  REVIEWABLE = "reviewable"
  APPROVED = "approved"
  REJECTED = "rejected"
  PUBLISHED = "published"
  BURNED = "burned"


class ConstitutionalCheck(BaseModel):
  rule_id: str
  passed: bool
  detail: str


class EpistemicObject(BaseModel):
  schema_version: str = SCHEMA_VERSION
  id: str = Field(default_factory=lambda: f"obj_{uuid4().hex}")
  deployment_id: str
  object_type: ObjectType
  kind: str
  content: str = Field(min_length=1, max_length=48000)
  source_ids: list[str] = Field(default_factory=list)
  uncertainty: str = "unresolved"
  prohibited_claims: list[str] = Field(default_factory=list)
  retention_class: RetentionClass = RetentionClass.BURN_AFTER_REVIEW
  lifecycle_state: LifecycleState = LifecycleState.TEMPORARY
  created_by: str
  created_at: str = Field(default_factory=lambda: utc_now())


class TransformationWarrant(BaseModel):
  schema_version: str = SCHEMA_VERSION
  id: str = Field(default_factory=lambda: f"warrant_{uuid4().hex}")
  deployment_id: str
  transition: str
  source_ids: list[str]
  output_id: str
  grounds: list[str]
  uncertainty_preserved: bool
  prohibited_authority: list[str]
  validator_results: list[ConstitutionalCheck]
  created_at: str = Field(default_factory=lambda: utc_now())


class ReviewPacket(BaseModel):
  schema_version: str = SCHEMA_VERSION
  id: str = Field(default_factory=lambda: f"review_{uuid4().hex}")
  deployment_id: str
  draft: EpistemicObject
  warrant: TransformationWarrant
  checks: list[ConstitutionalCheck]
  supporting_object_ids: list[str]
  status: str = "pending"
  created_at: str = Field(default_factory=lambda: utc_now())


class ReviewDecision(BaseModel):
  reviewer_role: str = Field(min_length=2, max_length=120)
  decision: str
  rationale: str = Field(min_length=2, max_length=2000)


class ReviewAttestation(BaseModel):
  schema_version: str = SCHEMA_VERSION
  review_packet_id: str
  deployment_id: str
  reviewer_role: str
  decision: str
  rationale: str
  draft_sha256: str
  checks_passed: bool
  signed_at: str = Field(default_factory=lambda: utc_now())


class BurnReceipt(BaseModel):
  schema_version: str = SCHEMA_VERSION
  deployment_id: str
  burned_paths: list[str]
  missing_paths: list[str]
  retained_paths: list[str]
  pre_burn_manifest_sha256: str
  deletion_verified: bool
  burned_at: str = Field(default_factory=lambda: utc_now())


def utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
  if isinstance(value, BaseModel):
    data = value.model_dump(mode="json")
  else:
    data = value
  return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
  return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, value: BaseModel | dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  data = canonical_json(value) + "\n"
  with tempfile.NamedTemporaryFile(
    "w", delete=False, dir=path.parent, encoding="utf-8", prefix=f".{path.name}-"
  ) as handle:
    handle.write(data)
    temporary = Path(handle.name)
  temporary.replace(path)


def append_event(path: Path, value: BaseModel | dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("a", encoding="utf-8") as handle:
    handle.write(canonical_json(value))
    handle.write("\n")


def read_events(path: Path) -> list[dict[str, Any]]:
  try:
    lines = path.read_text(encoding="utf-8").splitlines()
  except FileNotFoundError:
    return []
  return [json.loads(line) for line in lines if line.strip()]


def make_derived_object(
  *, deployment_id: str, kind: str, content: str, source_ids: list[str], created_by: str
) -> EpistemicObject:
  object_type = (
    ObjectType.THEME_OR_TENSION
    if kind in {"tension", "contradiction", "absence"}
    else ObjectType.CANDIDATE_INTERPRETATION
  )
  return EpistemicObject(
    deployment_id=deployment_id,
    object_type=object_type,
    kind=kind,
    content=content,
    source_ids=source_ids,
    uncertainty="candidate; non-representative",
    prohibited_claims=["fact", "consensus", "prevalence", "priority", "mandate"],
    created_by=created_by,
  )


def make_warrant(
  *, deployment_id: str, source_ids: list[str], output: EpistemicObject, transition: str
) -> TransformationWarrant:
  checks = [
    ConstitutionalCheck(
      rule_id="ARU-WARRANT-001",
      passed=bool(source_ids),
      detail="A derived object must identify at least one source dependency.",
    ),
    ConstitutionalCheck(
      rule_id="ARU-WARRANT-002",
      passed=bool(output.prohibited_claims),
      detail="A derived object must carry explicit prohibited claims.",
    ),
    ConstitutionalCheck(
      rule_id="ARU-WARRANT-003",
      passed=bool(output.uncertainty.strip()),
      detail="A derived object must preserve uncertainty status.",
    ),
  ]
  return TransformationWarrant(
    deployment_id=deployment_id,
    transition=transition,
    source_ids=source_ids,
    output_id=output.id,
    grounds=[
      "The output is a bounded candidate derived from charter-filtered material.",
      "The output remains non-representative and may not silently gain authority.",
    ],
    uncertainty_preserved=True,
    prohibited_authority=["fact", "consensus", "prevalence", "priority", "mandate"],
    validator_results=checks,
  )


PUBLIC_RULES: list[tuple[str, re.Pattern[str], str]] = [
  (
    "ARU-PUBLIC-001",
    re.compile(r"\b(the|this) community (believes?|thinks?|wants?|agrees?|demands?)\b", re.I),
    "Public reflection must not claim community-wide belief or consensus.",
  ),
  (
    "ARU-PUBLIC-002",
    re.compile(r"\b(should|must|need to|ought to|recommend(?:s|ed|ation)?)\b", re.I),
    "Public reflection must not recommend or direct action.",
  ),
  (
    "ARU-PUBLIC-003",
    re.compile(r"(?:\b\d+(?:\.\d+)?\s*%|\btop\s+\d+\b|\brank(?:ed|ing)?\b|\bscore\b)", re.I),
    "Public reflection must not publish rankings, scores, or percentages.",
  ),
  (
    "ARU-PUBLIC-004",
    re.compile(r"\b(faction|demographic|voting bloc|ideological group)s?\b", re.I),
    "Public reflection must not harden participants into factions or demographic blocs.",
  ),
  (
    "ARU-PUBLIC-005",
    re.compile(r"\b(diagnos(?:e|is)|action plan|policy proposal)\b|(?<!not a )\bmandate\b", re.I),
    "Public reflection must not diagnose, mandate, or produce institutional advice.",
  ),
]


def validate_public_reflection(markdown: str) -> list[ConstitutionalCheck]:
  checks = [
    ConstitutionalCheck(
      rule_id=rule_id,
      passed=pattern.search(markdown) is None,
      detail=detail,
    )
    for rule_id, pattern, detail in PUBLIC_RULES
  ]
  checks.append(
    ConstitutionalCheck(
      rule_id="ARU-PUBLIC-006",
      passed="reflective, not representative" in markdown.lower()
      and "interpretive, not directive" in markdown.lower(),
      detail="Public output must carry explicit epistemic boundary language.",
    )
  )
  return checks


def checks_pass(checks: list[ConstitutionalCheck]) -> bool:
  return all(check.passed for check in checks)


def build_review_packet(
  *, deployment_id: str, model_markdown: str, supporting_object_ids: list[str]
) -> ReviewPacket:
  bounded_markdown = (
    model_markdown.rstrip()
    + "\n\n---\nReflective, not representative. Interpretive, not directive. Not a mandate.\n"
  )
  draft = EpistemicObject(
    deployment_id=deployment_id,
    object_type=ObjectType.DRAFT_SYNTHESIS,
    kind="daily_public_reflection",
    content=bounded_markdown,
    source_ids=supporting_object_ids,
    uncertainty="bounded synthesis; contradiction-preserving; non-representative",
    prohibited_claims=["fact", "consensus", "prevalence", "priority", "diagnosis", "mandate"],
    retention_class=RetentionClass.BURN_AFTER_REVIEW,
    lifecycle_state=LifecycleState.REVIEWABLE,
    created_by="daily-constitutional-aggregation",
  )
  checks = validate_public_reflection(draft.content)
  warrant = make_warrant(
    deployment_id=deployment_id,
    source_ids=supporting_object_ids,
    output=draft,
    transition="derived_objects_to_draft_synthesis",
  )
  return ReviewPacket(
    deployment_id=deployment_id,
    draft=draft,
    warrant=warrant,
    checks=checks,
    supporting_object_ids=supporting_object_ids,
  )


def burn_files(
  *, deployment_id: str, burn_paths: list[Path], retained_paths: list[Path]
) -> BurnReceipt:
  manifest_entries = []
  for path in burn_paths:
    if path.exists():
      manifest_entries.append(
        {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
      )
    else:
      manifest_entries.append({"path": str(path), "sha256": None})
  manifest_sha = sha256_text(canonical_json(manifest_entries))

  burned_paths = []
  missing_paths = []
  for path in burn_paths:
    if path.exists():
      path.unlink()
      burned_paths.append(str(path))
    else:
      missing_paths.append(str(path))

  return BurnReceipt(
    deployment_id=deployment_id,
    burned_paths=burned_paths,
    missing_paths=missing_paths,
    retained_paths=[str(path) for path in retained_paths],
    pre_burn_manifest_sha256=manifest_sha,
    deletion_verified=all(not path.exists() for path in burn_paths),
  )
