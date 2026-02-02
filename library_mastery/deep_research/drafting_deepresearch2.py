"""
drafting_deepresearch2.py (Contract-Driven Deep Research • Indian Drafting)

This script turns a multi-stage legal drafting workflow into a contract-driven, stateful LangGraph:

1) clearly defined shared state (single source of truth),
2) strict structured outputs (per-node JSON schemas via Pydantic, extra=forbid),
3) deterministic routing / termination criteria,
4) fan-out/fan-in research with reducers to avoid INVALID_CONCURRENT_GRAPH_UPDATE,
5) interrupt-based HITL so the graph pauses for user input and resumes with state preserved.

NOT LEGAL ADVICE: This is an educational drafting assistant. Always have a qualified advocate review before filing.

Run (interactive):
  uv run library_mastery/deep_research/drafting_deepresearch2.py

Resume an interrupted run:
  uv run library_mastery/deep_research/drafting_deepresearch2.py --thread "<thread_id>" --case "<case_id>"

Resume by providing an answer directly:
  uv run library_mastery/deep_research/drafting_deepresearch2.py --thread "<thread_id>" --case "<case_id>" --resume "<answer>"

------------------------------------------------------------------------------
(1) LangGraph node map (what runs, where parallelism happens)

Legend:
  🧠 = LLM node (Structured Outputs, strict)
  🧩 = deterministic python node
  ⏸️ = interrupt/HITL

Nodes and flow:
  🧩 intake_router
  🧩 ris_builder
  🧠 validator
    - if ready_for_planning=false:
        🧠 question_gen → ⏸️ hitl_interrupt → 🧩 ingest_user_input → back to 🧠 validator
    - if ready_for_planning=true:
        🧠 planner → 🧩 research_dispatch → 🧠 researcher_worker (fan-out parallel N tasks) → 🧩 research_join → 🧠 compiler → 🧠 formatter → END

Parallelism:
  - `researcher_worker` runs N times in parallel in the same superstep (fan-out via Send API).
  - `research_results` is reducer-backed to aggregate parallel writes safely.

------------------------------------------------------------------------------
(2) Shared state schema (keys + reducers)

Reducers are mandatory for keys updated by parallel branches (research) and for append-only audit trails (qa_history/debug_log).

See `DraftingState` and reducers:
  - `qa_history`: reducer=operator.add (append-only)
  - `research_results`: reducer=merge_research_results (append + safe reorder/dedup in join)
  - `debug_log`: reducer=operator.add (append-only)

------------------------------------------------------------------------------
(3) Per-node prompts + strict JSON schemas

LLM nodes (system prompts + Pydantic schemas):
  - question_gen: `QUESTION_GEN_SYSTEM_PROMPT` + `QuestionGenOut`
  - validator: `VALIDATOR_SYSTEM_PROMPT` + `ValidatorOut`
  - planner: `PLANNER_SYSTEM_PROMPT` + `PlannerOut`
  - researcher_worker: `RESEARCHER_WORKER_SYSTEM_PROMPT` + `ResearcherWorkerOut`
  - compiler: `COMPILER_SYSTEM_PROMPT` + `CompilerOut`
  - formatter: `FORMATTER_SYSTEM_PROMPT` + `FormatterOut`
"""

from __future__ import annotations

import hashlib
import json
import operator
import os
import sys
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, Literal, Optional, TypedDict, cast

# -----------------------------
# 0) Bootstrapping for monorepo
# -----------------------------


def bootstrap_langgraph_namespace() -> None:
    """
    This repo is a monorepo; `langgraph` is built from multiple `libs/*` folders.
    If you run this script from the repo checkout, we add those libs to sys.path.
    """
    repo_root = Path(__file__).resolve().parents[2]
    lib_roots = [
        "libs/langgraph",
        "libs/checkpoint",
        "libs/prebuilt",
        "libs/checkpoint-sqlite",
        "libs/checkpoint-postgres",
    ]
    for rel in lib_roots:
        p = repo_root / rel
        if p.exists():
            sys.path.insert(0, str(p))


bootstrap_langgraph_namespace()


# -----------------------------
# 1) External deps (graph + schemas)
# -----------------------------

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover

    def load_dotenv() -> None:  # type: ignore
        return


from typing_extensions import Annotated

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, Send, interrupt
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()


# -----------------------------
# 2) UX helpers (terminal)
# -----------------------------


def title(text: str) -> None:
    line = "=" * len(text)
    print("\n" + line)
    print(text)
    print(line)


def step(text: str) -> None:
    print("\n--- " + text)


def show(label: str, value: object) -> None:
    print(f"\n{label}:")
    print(pformat(value, width=100))


def wrap(text: str) -> str:
    return textwrap.dedent(text).strip()


def read_multiline(prompt: str | None = None) -> str:
    if prompt:
        print(prompt)
    print("\nPaste your answer. End with an empty line:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


# -----------------------------
# 3) Project identity (current scope)
# -----------------------------

# NOTE: This script currently ships with a single RIS for an Indian civil PLAINT.
# `intake_router` can later be expanded to support other draft types.
DEFAULT_DRAFT_TYPE = "plaint"
DEFAULT_LANGUAGE = "en"
DEFAULT_TONE = "formal"
DEFAULT_OUTPUT_FORMAT = "plain_text"

ANSWER_MODEL = "gpt-5.1"


def require_env(var: str) -> None:
    if not os.environ.get(var):
        print(f"Missing environment variable: {var}", file=sys.stderr)
        sys.exit(1)


# -----------------------------
# 4) SQLite artifacts (next to file)
# -----------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = SCRIPT_DIR / "_drafting_deepresearch_data"
ARTIFACTS_DIR.mkdir(exist_ok=True)

CHECKPOINT_DB = ARTIFACTS_DIR / "checkpoints.db"
STORE_DB = ARTIFACTS_DIR / "store.db"
CACHE_DB = ARTIFACTS_DIR / "cache.db"


# -----------------------------
# 5) System prompts (per node)
# -----------------------------

BASE_RULES = wrap(
    """
    You are an assistant in an Indian legal drafting workflow (educational only).

    Non-negotiable rules:
    - Do NOT invent facts. Only use the provided slots (facts).
    - Do NOT provide legal advice; provide drafting-oriented information and structure for lawyer review.
    - Prefer material facts in pleadings; do not narrate evidence as proof.
    - Never fabricate citations. If you cannot verify, mark that as needing verification.
    - Output MUST be valid JSON matching the provided schema exactly. No extra keys. No extra text.
    """
)


QUESTION_GEN_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are QUESTION_GEN, an intake-question generator for an Indian legal drafting workflow.

    Goal:
    - Generate the smallest set of high-impact questions needed to fill missing REQUIRED slots (from RIS) and resolve high-severity contradictions/risk flags.
    - Ask in batches (max 8 questions per batch).
    - Prioritize: (1) blocker/required, (2) risk (limitation/jurisdiction/maintainability), (3) quality.

    Rules:
    - Do NOT invent facts. If information is not present in slots, treat it as unknown.
    - Each question must map to exactly one canonical slot_key.
    - Questions must be concise, unambiguous, and answerable in a single message.
    - Include examples only when it reduces ambiguity (e.g., date formats, party names).
    """
)


VALIDATOR_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are VALIDATOR for an Indian legal drafting workflow.

    Goal:
    - Decide if the state is ready for planning (ready_for_planning=true).
    - Read RIS (required slots + conditional rules) and current slots.
    - Produce a validation_report:
      - missing_required_slots
      - contradictions (with severity + follow-up slot_key suggestions)
      - risk_flags (limitation/jurisdiction/maintainability etc.)
      - assumptions that must be confirmed (only if unavoidable)

    Rules:
    - Do NOT invent facts; only evaluate what exists in slots.
    - If any required slot is missing -> ready_for_planning must be false.
    - If any HIGH severity contradiction exists -> ready_for_planning must be false.
    - If only risks exist but required slots are complete, ready_for_planning can be true (but include risk_flags).
    """
)


PLANNER_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are PLANNER for an Indian legal drafting workflow.

    Goal:
    - Produce:
      (1) a draft_plan: ordered sections for the final legal draft
      (2) research_tasks: parallelizable tasks, each tied to a section_id

    Rules:
    - Use only information from slots + draft_type + forum/jurisdiction.
    - Do NOT perform research. Only plan what to research.
    - Each research task must be atomic, testable, and have clear expected_output.
    """
)


RESEARCHER_WORKER_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are RESEARCHER_WORKER for an Indian legal drafting workflow.

    Input:
    - You receive exactly ONE research_task plus minimal case context (draft_type, forum, jurisdiction, relevant slots).

    Goal:
    - Return ONE research result for this task, including authorities and a short "application to facts" note.

    Rules:
    - Do NOT invent authorities/citations. If you do not have access to sources in your toolchain, set needs_verification=true and explain what must be verified.
    - Prefer primary sources: statutes/rules + binding case-law for the forum/jurisdiction.
    - Keep outputs concise, structured, and directly usable by the compiler.
    - This node runs in parallel; it MUST write only to research_results as a list append update.
    """
)


COMPILER_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are COMPILER for an Indian legal drafting workflow.

    Goal:
    - Synthesize ALL research_results into a compiled_bundle aligned to draft_plan.sections.
    - Remove redundancy, resolve conflicts, and produce:
      - section_briefs (per section_id)
      - a deduped authorities_table
      - conflict_notes (if authorities conflict)
      - placeholders for missing slots (if any remain)

    Rules:
    - Do NOT change user facts in slots.
    - If research is weak/needs verification, preserve that as caveats.
    """
)


FORMATTER_SYSTEM_PROMPT = wrap(
    f"""
    {BASE_RULES}

    You are FORMATTER for an Indian legal drafting workflow.

    Goal:
    - Render the final_draft as a polished legal draft aligned to draft_plan and compiled_bundle.
    - Include placeholders (e.g., <<MISSING: slot_key>>) where inputs are missing.
    - Produce an audit_pack:
      - facts_used (from slots)
      - assumptions (from validation_report)
      - missing_inputs
      - risk_flags
      - citations (from compiled_bundle.authorities_table)

    Rules:
    - Do NOT add new facts.
    - Keep the draft court-ready in tone and structure.
    """
)


# -----------------------------
# 6) Strict output contracts (Pydantic)
# -----------------------------


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionGenQuestion(_StrictModel):
    question_id: str
    priority: Literal["blocker", "risk", "quality"]
    slot_key: str
    question: str
    expected_answer_format: Literal["free_text", "date_yyyy_mm_dd", "yes_no", "number", "choice", "list"]
    choices: list[str] = Field(default_factory=list)
    why_needed: str
    examples: list[str] = Field(default_factory=list)


class QuestionGenBatch(_StrictModel):
    batch_id: str
    batch_purpose: str
    questions: list[QuestionGenQuestion] = Field(min_length=1, max_length=8)
    user_message: str


class QuestionGenOut(_StrictModel):
    last_question_batch: QuestionGenBatch


class ValidatorContradiction(_StrictModel):
    contradiction_id: str
    severity: Literal["low", "medium", "high"]
    description: str
    slot_keys: list[str] = Field(default_factory=list)
    suggested_followup_slot_key: str = Field(default="")


class ValidatorRiskFlag(_StrictModel):
    risk_id: str
    type: Literal[
        "limitation",
        "jurisdiction",
        "court_fee",
        "maintainability",
        "party_capacity",
        "evidence_gap",
        "procedural",
        "other",
    ]
    severity: Literal["low", "medium", "high"]
    description: str
    mitigation: str = Field(default="")


class ValidatorAssumption(_StrictModel):
    assumption: str
    reason: str
    needs_user_confirmation: bool


class ValidationReport(_StrictModel):
    ready_for_planning: bool
    missing_required_slots: list[str] = Field(default_factory=list)
    missing_optional_slots: list[str] = Field(default_factory=list)
    contradictions: list[ValidatorContradiction] = Field(default_factory=list)
    risk_flags: list[ValidatorRiskFlag] = Field(default_factory=list)
    assumptions: list[ValidatorAssumption] = Field(default_factory=list)


class ValidatorOut(_StrictModel):
    validation_report: ValidationReport


class PlanSection(_StrictModel):
    section_id: str
    order: int
    title: str
    purpose: str
    slot_keys_used: list[str] = Field(default_factory=list)
    required: bool


class PlanStyleGuide(_StrictModel):
    language: str
    tone: str
    numbering: Literal["paragraph", "clause"]


class DraftPlan(_StrictModel):
    plan_id: str
    sections: list[PlanSection] = Field(min_length=3)
    style_guide: PlanStyleGuide


class ResearchTask(_StrictModel):
    task_id: str
    section_id: str
    priority: Literal["high", "medium", "low"]
    topic: str
    jurisdiction_scope: str
    queries: list[str] = Field(default_factory=list)
    must_find: list[str] = Field(default_factory=list)
    expected_output: str


class PlannerOut(_StrictModel):
    draft_plan: DraftPlan
    research_tasks: list[ResearchTask] = Field(default_factory=list)


class ResearchAuthority(_StrictModel):
    authority_type: Literal["statute", "rule", "case", "notification", "practice_direction", "commentary", "other"]
    name: str
    citation: str
    pinpoint: str = Field(default="")
    url: str = Field(default="")
    relevance: str


class DraftingSnippet(_StrictModel):
    section_id: str
    snippet: str
    caveat: str = Field(default="")


class ResearchResult(_StrictModel):
    task_id: str
    topic: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    authorities: list[ResearchAuthority] = Field(default_factory=list)
    application_to_facts: str
    drafting_snippets: list[DraftingSnippet] = Field(default_factory=list)
    confidence: float
    needs_verification: bool
    open_questions: list[str] = Field(default_factory=list)


class ResearcherWorkerOut(_StrictModel):
    research_results: list[ResearchResult] = Field(min_length=1, max_length=1)


class CompilerAuthorityRow(_StrictModel):
    authority_id: str
    authority_type: str
    name: str
    citation: str
    url: str = Field(default="")


class CompilerSectionBrief(_StrictModel):
    section_id: str
    legal_position: str
    drafting_instructions: list[str] = Field(default_factory=list)
    authority_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class CompilerConflictNote(_StrictModel):
    conflict_id: str
    description: str
    affected_section_ids: list[str] = Field(default_factory=list)
    resolution_approach: str


class CompilerPlaceholder(_StrictModel):
    slot_key: str
    placeholder_text: str
    impact: Literal["low", "medium", "high"]


class CompiledBundle(_StrictModel):
    authorities_table: list[CompilerAuthorityRow] = Field(default_factory=list)
    section_briefs: list[CompilerSectionBrief] = Field(default_factory=list)
    conflict_notes: list[CompilerConflictNote] = Field(default_factory=list)
    placeholders: list[CompilerPlaceholder] = Field(default_factory=list)


class CompilerOut(_StrictModel):
    compiled_bundle: CompiledBundle


class AuditFact(_StrictModel):
    slot_key: str
    value: str


class AuditCitation(_StrictModel):
    authority_type: str
    name: str
    citation: str
    url: str = Field(default="")


class AuditPack(_StrictModel):
    facts_used: list[AuditFact] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    citations: list[AuditCitation] = Field(default_factory=list)


class FinalOutput(_StrictModel):
    final_draft: str
    annexure_list: list[str] = Field(default_factory=list)
    audit_pack: AuditPack


class FormatterOut(_StrictModel):
    final_output: FinalOutput


# -----------------------------
# 7) Shared state schema (+ reducers)
# -----------------------------


def is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return True
        if v.lower() in {"[unknown]", "unknown", "[blank]", "blank", "n/a", "na"}:
            return True
        return False
    return False


def parse_iso_date(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    t = text.strip()
    try:
        return datetime.strptime(t, "%Y-%m-%d")
    except Exception:
        return None


def merge_research_results(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]] | list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Reducer for `research_results`.

    - Worker updates: incoming=[{...}] → append (allow parallel fan-out).
    - Join updates: incoming=[(task_id, {...}), ...] → upsert by task_id AND reorder by tuple order.

    This pattern avoids INVALID_CONCURRENT_GRAPH_UPDATE in fan-out and still enables stable ordering/dedup.
    """
    if not incoming:
        return existing

    if isinstance(incoming[0], tuple):  # join-mode upsert + reorder
        incoming_tuples = cast(list[tuple[str, dict[str, Any]]], incoming)
        by_id: dict[str, dict[str, Any]] = {}
        for item in existing:
            tid = str(item.get("task_id") or "")
            if tid:
                by_id[tid] = item
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tid, payload in incoming_tuples:
            tid = str(tid)
            if not tid or tid in seen:
                continue
            seen.add(tid)
            by_id[tid] = payload
            ordered.append(payload)
        # Append any leftovers not referenced by join (should be none in normal use).
        for tid, payload in by_id.items():
            if tid not in seen:
                ordered.append(payload)
        return ordered

    # worker-mode append
    incoming_dicts = cast(list[dict[str, Any]], incoming)
    return operator.add(existing, incoming_dicts)


class DraftingState(TypedDict, total=False):
    # ---- Identity / request ----
    user_query: str
    draft_type: str
    sub_type: Optional[str]
    forum: Optional[str]
    jurisdiction: Optional[str]
    language: str
    tone: str
    output_format: str  # "plain_text" / "markdown" / "docx_ready"

    # ---- Slots/facts store (single source of truth) ----
    slots: dict[str, Any]

    # ---- Required information schema (RIS) ----
    ris: dict[str, Any]

    # ---- Clarification loop ----
    last_question_batch: dict[str, Any]
    latest_user_input: str
    qa_history: Annotated[list[dict[str, Any]], operator.add]
    clarification_round: int

    # ---- Validation ----
    validation_report: dict[str, Any]

    # ---- Planning ----
    draft_plan: dict[str, Any]
    research_tasks: list[dict[str, Any]]

    # ---- Research (fan-out/fan-in) ----
    research_results: Annotated[list[dict[str, Any]], merge_research_results]

    # ---- Compilation & final ----
    compiled_bundle: dict[str, Any]
    final_output: dict[str, Any]

    # ---- Logging ----
    debug_log: Annotated[list[str], operator.add]


# -----------------------------
# 8) Context (per run)
# -----------------------------


@dataclass
class Ctx:
    case_id: str
    user_id: str


# -----------------------------
# 9) RIS (deterministic templates)
# -----------------------------


def build_ris(*, draft_type: str, forum: str | None) -> dict[str, Any]:
    """
    Deterministic RIS builder.

    This is currently plaint-only (civil).
    """
    _ = forum
    if draft_type != "plaint":
        # Future: add other RIS templates.
        draft_type = "plaint"

    required_slots = [
        "court_name",
        "plaintiff",
        "defendant",
        "plaintiff_address",
        "defendant_address",
        "facts_timeline",
        "cause_of_action",
        "jurisdiction_facts",
        "reliefs",
        "valuation",
        "court_fee",
        "limitation",
        "documents",
    ]

    conditional_rules = [
        {
            "if_slot_key": "interim_relief_needed",
            "if_equals": "yes",
            "then_required_slots": ["interim_relief_details"],
        },
        {
            "if_slot_key": "is_commercial_dispute",
            "if_equals": "yes",
            "then_required_slots": ["commercial_value"],
        },
    ]

    validations = [
        {"slot_key": "proposed_filing_date", "rule": "date_yyyy_mm_dd"},
        {"slot_key": "cause_of_action_date", "rule": "date_yyyy_mm_dd"},
    ]

    return {
        "draft_type": "plaint",
        "required_slots": required_slots,
        "conditional_rules": conditional_rules,
        "validations": validations,
        "documents_checklist": [
            "Contract/Agreement (if any)",
            "Invoices / Bills / Statements (if any)",
            "Demand notice / Legal notice (if any)",
            "Replies / acknowledgements (if any)",
            "Authority documents (POA/board resolution), if applicable",
        ],
        "drafting_guidance": [
            "Pleadings must contain material facts (not evidence).",
            "For plaints, cover Order VII CPC particulars (TO VERIFY exact local practice).",
        ],
        "slot_descriptions": {
            "court_name": "Court name + place.",
            "plaintiff": "Plaintiff description (name/capacity).",
            "defendant": "Defendant description (name/capacity).",
            "facts_timeline": "Chronological material facts with dates/places.",
            "cause_of_action": "What wrong occurred and when it arose (material facts).",
            "jurisdiction_facts": "Territorial/pecuniary jurisdiction facts.",
            "reliefs": "Prayers sought (main + interim if any).",
            "valuation": "Suit valuation (amount/basis).",
            "court_fee": "Court fee position (amount/basis; if unknown, state unknown).",
            "limitation": "Limitation position (why within time; or delay explanation).",
            "documents": "List of documents to rely on (even if not yet available).",
        },
    }


def compute_missing_required_slots(*, ris: dict[str, Any], slots: dict[str, Any]) -> list[str]:
    required = [str(x) for x in (ris.get("required_slots") or [])]
    missing: list[str] = [k for k in required if is_missing_value(slots.get(k))]

    # Apply conditional rules (simple yes/no rules).
    for rule in ris.get("conditional_rules") or []:
        if not isinstance(rule, dict):
            continue
        if_key = str(rule.get("if_slot_key") or "")
        if_equals = str(rule.get("if_equals") or "").strip().lower()
        then_required = [str(x) for x in (rule.get("then_required_slots") or [])]
        if not if_key or not if_equals:
            continue
        actual = str(slots.get(if_key) or "").strip().lower()
        if actual == if_equals:
            for k in then_required:
                if is_missing_value(slots.get(k)) and k not in missing:
                    missing.append(k)
    return missing


# -----------------------------
# 10) LLM Engine (Structured Outputs)
# -----------------------------


class LLMEngine:
    def __init__(self, *, model: str, cache: Optional[object]) -> None:
        require_env("OPENAI_API_KEY")

        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: langchain-openai / langchain-core. Run via `uv run ...` to install deps."
            ) from e

        self._llm = ChatOpenAI(model=model, temperature=0)
        self._SystemMessage = SystemMessage
        self._HumanMessage = HumanMessage
        self._cache = cache
        self._model = model

    def _cache_key(self, agent: str, system: str, user: str, schema_name: str) -> str:
        h = hashlib.sha256()
        h.update(agent.encode("utf-8"))
        h.update(b"\n---\n")
        h.update(self._model.encode("utf-8"))
        h.update(b"\n---\n")
        h.update(schema_name.encode("utf-8"))
        h.update(b"\n---\n")
        h.update(system.encode("utf-8"))
        h.update(b"\n---\n")
        h.update(user.encode("utf-8"))
        return h.hexdigest()

    def call_structured(self, *, agent: str, system: str, user: str, schema: type[_StrictModel]) -> _StrictModel:
        cache = self._cache
        cache_key = self._cache_key(agent, system, user, schema.__name__)
        ns = ("llm", agent)

        if cache is not None:
            hit = cache.get([(ns, cache_key)]).get((ns, cache_key))
            if hit is not None:
                return schema.model_validate(hit)

        structured = self._llm.with_structured_output(schema)  # type: ignore[attr-defined]
        out = structured.invoke([self._SystemMessage(content=system), self._HumanMessage(content=user)])

        if cache is not None:
            cache.set({(ns, cache_key): (out.model_dump(), 24 * 3600)})

        return out


ENGINE: LLMEngine | None = None


# -----------------------------
# 11) Graph nodes (contract-driven)
# -----------------------------


def node_intake_router(state: DraftingState) -> DraftingState:
    """
    Reads: user_query
    Writes: draft_type, forum, jurisdiction, language, tone, output_format, clarification_round, slots (if missing)
    """
    user_query = str(state.get("user_query", "") or "").strip()
    if not user_query:
        raise ValueError("Missing user_query. Provide an initial user query to start the workflow.")

    draft_type = str(state.get("draft_type") or DEFAULT_DRAFT_TYPE).strip().lower()
    if not draft_type:
        draft_type = DEFAULT_DRAFT_TYPE

    return {
        "user_query": user_query,
        "draft_type": draft_type,
        "sub_type": state.get("sub_type"),
        "forum": state.get("forum"),
        "jurisdiction": state.get("jurisdiction"),
        "language": str(state.get("language") or DEFAULT_LANGUAGE),
        "tone": str(state.get("tone") or DEFAULT_TONE),
        "output_format": str(state.get("output_format") or DEFAULT_OUTPUT_FORMAT),
        "slots": dict(state.get("slots") or {}),
        "qa_history": [],
        "research_results": [],
        "clarification_round": int(state.get("clarification_round") or 0),
        "debug_log": [f"intake_router(draft_type={draft_type})"],
    }


def node_ris_builder(state: DraftingState) -> DraftingState:
    """
    Reads: draft_type, forum
    Writes: ris
    """
    ris = build_ris(draft_type=str(state.get("draft_type") or DEFAULT_DRAFT_TYPE), forum=state.get("forum"))
    return {"ris": ris, "debug_log": ["ris_builder(done)"]}


def node_validator(state: DraftingState) -> DraftingState:
    """
    🧠 Reads: ris, slots, draft_type, forum, jurisdiction
    🧠 Writes: validation_report
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    ris = dict(state.get("ris") or {})
    slots = dict(state.get("slots") or {})
    draft_type = str(state.get("draft_type") or DEFAULT_DRAFT_TYPE)
    forum = state.get("forum")
    jurisdiction = state.get("jurisdiction")

    user_prompt = wrap(
        f"""
        draft_type: {draft_type}
        forum: {forum if forum else ""}
        jurisdiction: {jurisdiction if jurisdiction else ""}

        RIS (JSON):
        {json.dumps(ris, indent=2)}

        slots (JSON):
        {json.dumps(slots, indent=2)}
        """
    )

    out = cast(ValidatorOut, llm.call_structured(agent="validator", system=VALIDATOR_SYSTEM_PROMPT, user=user_prompt, schema=ValidatorOut))

    # Deterministic safety: never allow "ready" if required slots are missing.
    missing_required = compute_missing_required_slots(ris=ris, slots=slots)
    report = out.validation_report.model_copy(
        update={
            "missing_required_slots": sorted(set(list(out.validation_report.missing_required_slots) + missing_required)),
        }
    )

    if report.missing_required_slots:
        report = report.model_copy(update={"ready_for_planning": False})

    if any(c.severity == "high" for c in report.contradictions):
        report = report.model_copy(update={"ready_for_planning": False})

    return {"validation_report": report.model_dump(), "debug_log": [f"validator(ready={report.ready_for_planning})"]}


def route_after_validator(state: DraftingState) -> str:
    report = dict(state.get("validation_report") or {})
    ready = bool(report.get("ready_for_planning"))
    return "planner" if ready else "question_gen"


def node_question_gen(state: DraftingState) -> DraftingState:
    """
    🧠 Reads: user_query, draft_type, ris, slots, validation_report
    🧠 Writes: last_question_batch
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    user_query = str(state.get("user_query") or "")
    draft_type = str(state.get("draft_type") or DEFAULT_DRAFT_TYPE)
    ris = dict(state.get("ris") or {})
    slots = dict(state.get("slots") or {})
    validation_report = dict(state.get("validation_report") or {})
    clarification_round = int(state.get("clarification_round") or 0)

    user_prompt = wrap(
        f"""
        user_query:
        {user_query}

        draft_type: {draft_type}

        RIS (JSON):
        {json.dumps(ris, indent=2)}

        slots (JSON):
        {json.dumps(slots, indent=2)}

        validation_report (JSON):
        {json.dumps(validation_report, indent=2)}
        """
    )
    out = cast(
        QuestionGenOut,
        llm.call_structured(agent="question_gen", system=QUESTION_GEN_SYSTEM_PROMPT, user=user_prompt, schema=QuestionGenOut),
    )

    # Enforce allowed slot keys deterministically (prevents drift).
    missing_required = [str(x) for x in (validation_report.get("missing_required_slots") or [])]
    allowed: set[str] = set(missing_required)
    for c in validation_report.get("contradictions", []) or []:
        if isinstance(c, dict):
            for k in c.get("slot_keys", []) or []:
                allowed.add(str(k))
            follow = str(c.get("suggested_followup_slot_key") or "").strip()
            if follow:
                allowed.add(follow)

    filtered_questions: list[QuestionGenQuestion] = []
    for q in out.last_question_batch.questions:
        if q.slot_key in allowed:
            filtered_questions.append(q)
        if len(filtered_questions) >= 8:
            break

    # If the LLM returned nothing usable, fall back to required-missing keys.
    if not filtered_questions and missing_required:
        filtered_questions = [
            QuestionGenQuestion(
                question_id=f"q_{k}",
                priority="blocker",
                slot_key=k,
                question=f"Provide {k}.",
                expected_answer_format="free_text",
                why_needed="Required for drafting.",
                choices=[],
                examples=[],
            )
            for k in missing_required[:8]
        ]

    batch_id = out.last_question_batch.batch_id.strip() or f"batch_{clarification_round + 1}"
    batch_purpose = out.last_question_batch.batch_purpose.strip() or "Fill missing required inputs."

    # Deterministic user_message for interactive lawyers (key:value lines).
    keys_list = "\n".join([f"- {q.slot_key}: {q.question}" for q in filtered_questions])
    user_message = wrap(
        f"""
        Please answer the following in key:value lines (one per line). If unknown, write [UNKNOWN].

        Questions:
        {keys_list}
        """
    )

    batch = out.last_question_batch.model_copy(
        update={
            "batch_id": batch_id,
            "batch_purpose": batch_purpose,
            "questions": filtered_questions,
            "user_message": user_message,
        }
    )

    return {"last_question_batch": batch.model_dump(), "debug_log": [f"question_gen(n={len(filtered_questions)})"]}


def node_hitl_interrupt(state: DraftingState) -> DraftingState:
    """
    ⏸️ Reads: last_question_batch
    ⏸️ Writes: latest_user_input (resume payload)
    """
    batch = dict(state.get("last_question_batch") or {})
    prompt = {
        "title": "Clarifying questions",
        "batch_id": batch.get("batch_id"),
        "batch_purpose": batch.get("batch_purpose"),
        "user_message": batch.get("user_message"),
        "questions": batch.get("questions", []),
        "answer_format": "Answer as key: value lines. End with an empty line.",
        "note": "Do not include sensitive personal identifiers. Use [UNKNOWN] if unknown.",
    }
    answer = interrupt(prompt)
    return {"latest_user_input": str(answer)}


def _parse_kv_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def node_ingest_user_input(state: DraftingState) -> DraftingState:
    """
    Reads: last_question_batch, latest_user_input
    Writes: slots (merge), qa_history append, clarification_round += 1
    """
    batch = dict(state.get("last_question_batch") or {})
    raw_answer = str(state.get("latest_user_input") or "")
    questions = batch.get("questions", []) or []

    slots = dict(state.get("slots") or {})
    parsed = _parse_kv_lines(raw_answer)

    expected_slot_keys: list[str] = []
    for q in questions:
        if isinstance(q, dict):
            expected_slot_keys.append(str(q.get("slot_key") or ""))
        elif isinstance(q, QuestionGenQuestion):
            expected_slot_keys.append(q.slot_key)

    # If user didn't use key:value lines and only one question, take whole answer.
    if not parsed and len(expected_slot_keys) == 1 and raw_answer.strip():
        parsed[expected_slot_keys[0]] = raw_answer.strip()

    updates: dict[str, str] = {}
    unknown_keys: list[str] = []
    for k in expected_slot_keys:
        if not k:
            continue
        if k not in parsed:
            continue
        v = str(parsed.get(k) or "").strip()
        if v.lower() in {"[unknown]", "unknown", "[blank]", "blank"}:
            unknown_keys.append(k)
            slots.pop(k, None)
            continue
        slots[k] = v
        updates[k] = v

    round_no = int(state.get("clarification_round") or 0) + 1
    qa_entry = {
        "batch_id": batch.get("batch_id"),
        "batch_purpose": batch.get("batch_purpose"),
        "questions": questions,
        "answer": raw_answer,
        "updates": updates,
        "unknown_keys": unknown_keys,
        "round": round_no,
    }

    return {
        "slots": slots,
        "qa_history": [qa_entry],
        "clarification_round": round_no,
        "debug_log": [f"ingest_user_input(updated={list(updates.keys())})"],
    }


def node_planner(state: DraftingState) -> DraftingState:
    """
    🧠 Reads: user_query, draft_type, ris, slots, validation_report, preferences
    🧠 Writes: draft_plan, research_tasks
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    user_query = str(state.get("user_query") or "")
    draft_type = str(state.get("draft_type") or DEFAULT_DRAFT_TYPE)
    ris = dict(state.get("ris") or {})
    slots = dict(state.get("slots") or {})
    validation_report = dict(state.get("validation_report") or {})
    forum = state.get("forum")
    jurisdiction = state.get("jurisdiction")

    user_prompt = wrap(
        f"""
        user_query:
        {user_query}

        draft_type: {draft_type}
        forum: {forum if forum else ""}
        jurisdiction: {jurisdiction if jurisdiction else ""}

        RIS (JSON):
        {json.dumps(ris, indent=2)}

        slots (JSON):
        {json.dumps(slots, indent=2)}

        validation_report (JSON):
        {json.dumps(validation_report, indent=2)}
        """
    )
    out = cast(PlannerOut, llm.call_structured(agent="planner", system=PLANNER_SYSTEM_PROMPT, user=user_prompt, schema=PlannerOut))

    # Basic deterministic guardrails: ensure section ordering is stable and unique.
    sections = sorted(out.draft_plan.sections, key=lambda s: (s.order, s.section_id))
    out = out.model_copy(update={"draft_plan": out.draft_plan.model_copy(update={"sections": sections})})

    return {
        "draft_plan": out.draft_plan.model_dump(),
        "research_tasks": [t.model_dump() for t in out.research_tasks],
        "debug_log": [f"planner(tasks={len(out.research_tasks)})"],
    }


def node_research_dispatch(state: DraftingState) -> Command["researcher_worker"]:
    """
    🧩 Reads: research_tasks
    🧩 Sends: N parallel `researcher_worker` tasks via Send
    """
    tasks = state.get("research_tasks") or []
    draft_type = str(state.get("draft_type") or DEFAULT_DRAFT_TYPE)
    forum = state.get("forum")
    jurisdiction = state.get("jurisdiction")
    slots = dict(state.get("slots") or {})

    sends: list[Send] = []
    for t in tasks:
        sends.append(
            Send(
                "researcher_worker",
                {
                    "research_task": t,
                    "draft_type": draft_type,
                    "forum": forum,
                    "jurisdiction": jurisdiction,
                    "slots": slots,
                },
            )
        )

    if not sends:
        # No research tasks: proceed directly to compiler.
        return Command(goto="compiler", update={"debug_log": ["research_dispatch(n=0) -> compiler"]})

    return Command(goto=sends, update={"debug_log": [f"research_dispatch(n={len(sends)})"]})


def node_researcher_worker(state: dict[str, Any]) -> DraftingState:
    """
    🧠 Reads: one research_task + minimal context
    🧠 Writes: research_results += [result]
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    task = state.get("research_task") or {}
    draft_type = str(state.get("draft_type") or "")
    forum = state.get("forum") or ""
    jurisdiction = state.get("jurisdiction") or ""
    slots = state.get("slots") or {}

    user_prompt = wrap(
        f"""
        draft_type: {draft_type}
        forum: {forum}
        jurisdiction: {jurisdiction}

        research_task (JSON):
        {json.dumps(task, indent=2)}

        relevant slots (JSON):
        {json.dumps(slots, indent=2)}
        """
    )
    out = cast(
        ResearcherWorkerOut,
        llm.call_structured(
            agent="researcher_worker",
            system=RESEARCHER_WORKER_SYSTEM_PROMPT,
            user=user_prompt,
            schema=ResearcherWorkerOut,
        ),
    )
    result = out.research_results[0]

    # Enforce task identity deterministically.
    task_id = str(task.get("task_id") or result.task_id)
    topic = str(task.get("topic") or result.topic)
    fixed = result.model_copy(update={"task_id": task_id, "topic": topic})

    return {"research_results": [fixed.model_dump()], "debug_log": [f"researcher_worker(done {task_id})"]}


def node_research_join(state: DraftingState) -> DraftingState:
    """
    🧩 Fan-in reducer stage:
    - Sort/dedup by task_id because parallel updates may be unordered.
    - Uses reducer (merge_research_results) to reorder safely via tuple-upserts.
    """
    results = [dict(x) for x in (state.get("research_results") or [])]
    tasks = [dict(x) for x in (state.get("research_tasks") or [])]

    # Desired order: research_tasks order (fallback: task_id).
    order_index: dict[str, int] = {}
    for idx, t in enumerate(tasks):
        tid = str(t.get("task_id") or "")
        if tid:
            order_index[tid] = idx

    def sort_key(r: dict[str, Any]) -> tuple[int, str]:
        tid = str(r.get("task_id") or "")
        return (order_index.get(tid, 10**9), tid)

    # Dedup: keep highest confidence if duplicates exist.
    best: dict[str, dict[str, Any]] = {}
    for r in results:
        tid = str(r.get("task_id") or "")
        if not tid:
            continue
        conf = float(r.get("confidence") or 0.0)
        prev = best.get(tid)
        if prev is None:
            best[tid] = r
        else:
            prev_conf = float(prev.get("confidence") or 0.0)
            if conf >= prev_conf:
                best[tid] = r

    ordered = sorted(best.values(), key=sort_key)
    upserts: list[tuple[str, dict[str, Any]]] = [(str(r.get("task_id") or ""), r) for r in ordered]

    return {"research_results": upserts, "debug_log": [f"research_join(n={len(ordered)})"]}


def node_compiler(state: DraftingState) -> DraftingState:
    """
    🧠 Reads: draft_plan, research_results, slots, validation_report
    🧠 Writes: compiled_bundle
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    draft_plan = dict(state.get("draft_plan") or {})
    research_results = list(state.get("research_results") or [])
    slots = dict(state.get("slots") or {})
    validation_report = dict(state.get("validation_report") or {})

    user_prompt = wrap(
        f"""
        draft_plan (JSON):
        {json.dumps(draft_plan, indent=2)}

        research_results (JSON):
        {json.dumps(research_results, indent=2)}

        slots (JSON):
        {json.dumps(slots, indent=2)}

        validation_report (JSON):
        {json.dumps(validation_report, indent=2)}
        """
    )
    out = cast(CompilerOut, llm.call_structured(agent="compiler", system=COMPILER_SYSTEM_PROMPT, user=user_prompt, schema=CompilerOut))
    return {"compiled_bundle": out.compiled_bundle.model_dump(), "debug_log": ["compiler(done)"]}


def node_formatter(state: DraftingState) -> DraftingState:
    """
    🧠 Reads: draft_plan, compiled_bundle, slots, validation_report
    🧠 Writes: final_output
    """
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized.")
    llm = ENGINE

    draft_plan = dict(state.get("draft_plan") or {})
    compiled_bundle = dict(state.get("compiled_bundle") or {})
    slots = dict(state.get("slots") or {})
    validation_report = dict(state.get("validation_report") or {})

    user_prompt = wrap(
        f"""
        draft_plan (JSON):
        {json.dumps(draft_plan, indent=2)}

        compiled_bundle (JSON):
        {json.dumps(compiled_bundle, indent=2)}

        slots (JSON):
        {json.dumps(slots, indent=2)}

        validation_report (JSON):
        {json.dumps(validation_report, indent=2)}
        """
    )
    out = cast(FormatterOut, llm.call_structured(agent="formatter", system=FORMATTER_SYSTEM_PROMPT, user=user_prompt, schema=FormatterOut))
    return {"final_output": out.final_output.model_dump(), "debug_log": ["formatter(done)"]}


# -----------------------------
# 12) Graph build (matches node map)
# -----------------------------


builder = StateGraph(DraftingState, context_schema=Ctx)

builder.add_node("intake_router", node_intake_router)
builder.add_node("ris_builder", node_ris_builder)
builder.add_node("validator", node_validator)
builder.add_node("question_gen", node_question_gen)
builder.add_node("hitl_interrupt", node_hitl_interrupt)
builder.add_node("ingest_user_input", node_ingest_user_input)
builder.add_node("planner", node_planner)
builder.add_node("research_dispatch", node_research_dispatch)
builder.add_node("researcher_worker", node_researcher_worker)
builder.add_node("research_join", node_research_join, defer=True)
builder.add_node("compiler", node_compiler)
builder.add_node("formatter", node_formatter)

builder.add_edge(START, "intake_router")
builder.add_edge("intake_router", "ris_builder")
builder.add_edge("ris_builder", "validator")
builder.add_conditional_edges(
    "validator",
    route_after_validator,
    {"question_gen": "question_gen", "planner": "planner"},
)

builder.add_edge("question_gen", "hitl_interrupt")
builder.add_edge("hitl_interrupt", "ingest_user_input")
builder.add_edge("ingest_user_input", "validator")

builder.add_edge("planner", "research_dispatch")
builder.add_edge("researcher_worker", "research_join")
builder.add_edge("research_join", "compiler")
builder.add_edge("compiler", "formatter")
builder.add_edge("formatter", END)

# NOTE:
# The `research_dispatch` node returns a `Command(goto=[Send(...)...])` which triggers N parallel `researcher_worker` runs.
# Each worker appends to `research_results` (reducer-backed). `research_join` is deferred so it triggers after fan-out finishes.


# -----------------------------
# 13) Runner (handles interrupts + persistence)
# -----------------------------


def print_interrupt_prompt(prompt: dict[str, Any]) -> None:
    title(str(prompt.get("title", "INTERRUPT")))
    if prompt.get("user_message"):
        print("\n" + str(prompt["user_message"]))
    if prompt.get("questions"):
        print("\nQuestions:")
        for q in prompt["questions"]:
            if isinstance(q, dict):
                print(f"- {q.get('slot_key')}: {q.get('question')}")
    if prompt.get("answer_format"):
        print("\nAnswer format:")
        print(str(prompt["answer_format"]))
    if prompt.get("note"):
        print("\nNote:")
        print(str(prompt["note"]))


def write_case_artifacts(*, case_id: str, state: dict[str, Any]) -> str:
    case_dir = ARTIFACTS_DIR / f"case_{case_id}"
    case_dir.mkdir(exist_ok=True)

    def write_json(name: str, obj: object) -> None:
        (case_dir / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")

    (case_dir / "00_user_query.txt").write_text(str(state.get("user_query", "") or ""), encoding="utf-8")
    write_json("01_ris.json", state.get("ris", {}))
    write_json("02_slots.json", state.get("slots", {}))
    write_json("03_validation_report.json", state.get("validation_report", {}))
    write_json("04_last_question_batch.json", state.get("last_question_batch", {}))
    write_json("05_qa_history.json", state.get("qa_history", []))
    write_json("06_draft_plan.json", state.get("draft_plan", {}))
    write_json("07_research_tasks.json", state.get("research_tasks", []))
    write_json("08_research_results.json", state.get("research_results", []))
    write_json("09_compiled_bundle.json", state.get("compiled_bundle", {}))
    write_json("10_final_output.json", state.get("final_output", {}))
    write_json("11_debug_log.json", state.get("debug_log", []))

    final_output = dict(state.get("final_output") or {})
    (case_dir / "12_final_draft.txt").write_text(str(final_output.get("final_draft", "") or ""), encoding="utf-8")
    audit_pack = final_output.get("audit_pack", {}) or {}
    write_json("13_audit_pack.json", audit_pack)
    annex = final_output.get("annexure_list", []) or []
    (case_dir / "14_annexure_list.txt").write_text("\n".join([f"- {x}" for x in annex]) + "\n", encoding="utf-8")

    return str(case_dir)


def run(*, thread_id: str | None, case_id: str | None, resume_answer: str | None) -> None:
    global ENGINE

    if case_id is None:
        case_id = str(uuid.uuid4())[:8]
    if thread_id is None:
        thread_id = f"draft-{case_id}"

    config = {"configurable": {"thread_id": thread_id}}
    context = Ctx(case_id=case_id, user_id="u1")

    title("Deep Research Drafting (Contract-Driven) — India")
    show("case_id", case_id)
    show("thread_id", thread_id)
    show("artifacts_dir", str(ARTIFACTS_DIR))

    # Import optional persistence deps at runtime (keeps import errors readable).
    try:
        from langgraph.cache.sqlite import SqliteCache  # type: ignore
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
        from langgraph.store.sqlite import SqliteStore  # type: ignore
    except Exception as e:  # pragma: no cover
        title("Missing dependencies for SQLite persistence")
        print(
            wrap(
                """
                This script uses SQLite-backed persistence so it can pause for HITL interrupts and resume later.
                Run via `uv run ...` to install optional dependencies.
                """
            )
        )
        raise SystemExit(1) from e

    cache = SqliteCache(path=str(CACHE_DB))
    ENGINE = LLMEngine(model=ANSWER_MODEL, cache=cache)

    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        with SqliteStore.from_conn_string(str(STORE_DB)) as store:
            graph = builder.compile(checkpointer=checkpointer, store=store)

            if resume_answer is not None:
                state_in: object = Command(resume=resume_answer)
            else:
                try:
                    snap = graph.get_state(config)
                except Exception:
                    snap = None

                if snap is not None and getattr(snap, "interrupts", None):
                    intr = snap.interrupts[0]
                    prompt = intr.value
                    if not isinstance(prompt, dict):
                        prompt = {"title": "INTERRUPT", "user_message": str(prompt)}
                    step("Found a pending interrupt. Answer to resume.")
                    print_interrupt_prompt(prompt)
                    ans = read_multiline()
                    state_in = Command(resume=ans)
                else:
                    # New run: ask for initial user_query interactively.
                    intro = wrap(
                        """
                        Provide the initial drafting instruction for your client matter.
                        Include (if available): court/forum, parties, dates, material facts timeline, reliefs, jurisdiction facts,
                        valuation/court-fee position, limitation position, and documents list.
                        """
                    )
                    user_query = read_multiline(prompt=intro)
                    state_in = {"user_query": user_query}

            while True:
                interrupted = False
                for chunk in graph.stream(state_in, config, context=context, stream_mode="updates"):
                    if "__interrupt__" in chunk:
                        interrupted = True
                        intr = chunk["__interrupt__"][0]
                        prompt = intr.value
                        if not isinstance(prompt, dict):
                            prompt = {"title": "INTERRUPT", "user_message": str(prompt)}
                        print_interrupt_prompt(prompt)
                        ans = read_multiline()
                        state_in = Command(resume=ans)
                        break

                    if isinstance(chunk, dict) and len(chunk) == 1:
                        node_name = next(iter(chunk.keys()))
                        payload = chunk[node_name]
                        step(f"node: {node_name}")
                        if node_name in {"validator"} and isinstance(payload, dict):
                            show("ready_for_planning", payload.get("validation_report", {}).get("ready_for_planning"))
                        elif node_name in {"formatter"} and isinstance(payload, dict):
                            show("final_output_keys", sorted(list((payload.get("final_output") or {}).keys())))
                        else:
                            show("update", payload)
                    else:
                        show("update", chunk)

                if not interrupted:
                    break

            snap = graph.get_state(config)
            step("DONE")
            values = cast(dict[str, Any], snap.values if isinstance(snap.values, dict) else {})
            case_dir = write_case_artifacts(case_id=case_id, state=values)
            show("case_dir", case_dir)
            final_output = dict(values.get("final_output") or {})
            final_draft = str(final_output.get("final_draft", "") or "")
            if final_draft.strip():
                print("\nFINAL DRAFT:\n")
                print(final_draft)


# -----------------------------
# 14) CLI
# -----------------------------


if __name__ == "__main__":
    require_env("OPENAI_API_KEY")

    thread_id: str | None = None
    case_id: str | None = None
    resume_answer: str | None = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--thread":
            thread_id = args[i + 1]
            i += 2
            continue
        if args[i] == "--case":
            case_id = args[i + 1]
            i += 2
            continue
        if args[i] == "--resume":
            resume_answer = args[i + 1]
            i += 2
            continue
        i += 1

    run(thread_id=thread_id, case_id=case_id, resume_answer=resume_answer)
