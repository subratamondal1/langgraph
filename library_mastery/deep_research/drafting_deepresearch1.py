"""
drafting_deepresearch2.py (Deep Research • Litigation Drafting • Civil Pleadings • PLAINT)

You asked for:
- REAL multi-agent system (LLM-driven), not hard-coded prompts
- explicit system prompts + user prompts per agent
- ONE combination only for now:
    category: Litigation Drafting
    sub category: Civil Pleadings
    type: Plaint
- SQLite artifacts created next to this file (checkpoint/store/cache)
- end-to-end run that produces:
    1) Draft plaint (court-style)
    2) One-page brief
    3) Blanks/assumptions list (must confirm)
    4) Annexures list
    5) Filing/compliance checklist
    6) Next steps
    7) Audit pack (facts, assumptions, risks, sources)

This script is a LEARNING PROJECT.
It is NOT legal advice. Always get a qualified advocate to review before filing.

Run (interactive):
  uv run library_mastery/deep_research/drafting_deepresearch2.py

Resume an interrupted run:
  uv run library_mastery/deep_research/drafting_deepresearch2.py --thread "<thread_id>" --case "<case_id>"

Resume by providing an answer directly:
  uv run library_mastery/deep_research/drafting_deepresearch2.py --thread "<thread_id>" --case "<case_id>" --resume "<answer>"

Run (demo auto-answers, still uses LLM unless --mock):
  uv run library_mastery/deep_research/drafting_deepresearch2.py --demo

Offline mode (no API key; uses simple mock agents):
  uv run library_mastery/deep_research/drafting_deepresearch2.py --mock
"""

import hashlib
import json
import os
import sys
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, Annotated, Literal, Optional, TypedDict

# -----------------------------
# 0) Bootstrapping for monorepo
# -----------------------------


def bootstrap_langgraph_namespace() -> None:
    """
    This repo is a monorepo; `langgraph` is built from multiple `libs/*` folders.
    If you run this script from the repo checkout, we add those libs to sys.path.
    """
    # file: library_mastery/deep_research/drafting_deepresearch2.py
    # parents[0] = deep_research
    # parents[1] = library_mastery
    # parents[2] = repo root
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
# 1) External deps (LLM + graph)
# -----------------------------

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover

    def load_dotenv() -> None:  # type: ignore
        return


from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, Send, interrupt
from pydantic import BaseModel, Field

# -----------------------------
# 2) Tiny print helpers (simple)
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


def read_multiline() -> str:
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
# 3) Project identity (fixed)
# -----------------------------

CATEGORY = "Litigation Drafting"
SUBCATEGORY = "Civil Pleadings"
DOC_TYPE = "Plaint"


# -----------------------------
# 4) SQLite artifacts (next to file)
# -----------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = SCRIPT_DIR / "_drafting_deepreearch_data"
ARTIFACTS_DIR.mkdir(exist_ok=True)

CHECKPOINT_DB = ARTIFACTS_DIR / "checkpoints.db"
STORE_DB = ARTIFACTS_DIR / "store.db"
CACHE_DB = ARTIFACTS_DIR / "cache.db"


# -----------------------------
# 5) LLM model settings
# -----------------------------

load_dotenv()

ANSWER_MODEL = "gpt-5.1"


def require_env(var: str) -> None:
    if not os.environ.get(var):
        print(f"Missing environment variable: {var}")
        print("Set it and re-run, or use --mock for offline mode.")
        sys.exit(1)


# -----------------------------
# 6) Agent prompts (REAL system prompts)
# -----------------------------

BASE_SYSTEM_PROMPT = wrap(
    """
    You are a careful Indian litigation drafting assistant (educational only).

    NON-NEGOTIABLE RULES
    - Not legal advice. Do not claim to be a lawyer.
    - Do not hallucinate facts. If missing, ask the user OR use <<PLACEHOLDER: ...>> and surface it in Missing Inputs.
    - Pleadings must be MATERIAL FACTS (not evidence, not arguments) in numbered paragraphs.
    - Never fabricate citations (especially case law). If not sure, put it under to_verify with low confidence.
    - If you cite law, prefer stable procedural sources (CPC/Rules) and state uncertainty as needed.
    - Output must follow the provided JSON schema exactly (no extra keys).
    """
)

QUESTION_GENERATOR_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior chamber lawyer taking instructions for drafting a civil PLAINT.
    TASK: Convert the provided expected_keys into a SHORT ranked batch of intake questions.

    IMPORTANT:
    - Ask ONLY for the provided expected_keys (do not invent new keys).
    - Keep questions short and practical.
    - Provide a key for each question so the user can answer in key:value lines.
    - Add category + priority (blocker/risk/quality/assumption).
    - After questions, include an "answer_format" instruction.
    """
)


ANSWER_EXTRACTOR_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Case file clerk.
    TASK: Extract structured facts from the user's answer into the requested keys only.

    IMPORTANT:
    - Do not guess. If not present, omit the key.
    - If user explicitly says unknown/blank, include that key in explicitly_unknown.
    - If user explicitly accepts proceeding with blanks, set proceed_with_blanks=true.
    - Output must be VALID JSON matching the schema.
    """
)


DRAFT_PLANNER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior associate.
    TASK: Create the Draft Plan ONLY (structure + pleading strategy) for a civil PLAINT.

    Constraints:
    - Use only user facts + procedural template requirements (no research content).
    - Keep it objective, filing-oriented, and India-appropriate.
    - Output must be VALID JSON matching the schema.
    """
)


RESEARCH_PLANNER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Research associate.
    TASK: Produce a Research Plan ONLY (tasks list) for a civil PLAINT in India.

    Constraints:
    - No drafting text. Only research tasks.
    - Prefer statutory/procedural hooks. Do NOT invent case citations.
    - task_id must be unique and stable within this run (T1, T2, ...).
    - Output must be VALID JSON matching the schema.
    """
)


RESEARCH_WORKER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Research associate (worker).
    TASK: Answer ONE research task with traceable findings and citations.

    Constraints:
    - If you cannot verify a source, mark it in to_verify and keep citations empty or low-confidence.
    - Do NOT invent case names/citations. Prefer statutes/rules. If unsure, to_verify.
    - Output must be VALID JSON matching the schema.
    """
)


COMPILER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior drafting counsel (compiler).
    TASK: Compile case_file + draft_plan + research_pack into a structured draft payload (NO free-form essay).

    Legal/technical constraints:
    - Enforce pleading discipline: material facts only; do NOT narrate evidence as proof.
    - If a required field is missing or accepted as blank, use <<PLACEHOLDER: ...>> in the relevant section and include it in missing_inputs.
    - Use citations ONLY from the provided research_pack.citations (do not invent new citations).
    - Resolve conflicts and record them as conflicts (do not silently mix contradictory points).
    - Output must be VALID JSON matching the schema.
    """
)


# -----------------------------
# 7) Pydantic schemas (structured outputs)
# -----------------------------


class IntakeRouteOut(BaseModel):
    category: str
    subcategory: str
    doc_type: str
    forum: str
    jurisdiction_scope: str = Field(default="")
    notes: str = Field(default="")


class RISField(BaseModel):
    key: str
    description: str
    required: bool = Field(default=True)
    required_if: Optional[str] = Field(default=None, description="Human-readable condition for when this is required.")
    data_type: Literal["string", "text", "date", "money", "list", "bool"] = Field(default="string")
    validation_rules: list[str] = Field(default_factory=list)
    example: Optional[str] = Field(default=None)


class RequiredInformationSchemaOut(BaseModel):
    doc_type: str
    forum: str
    mandatory: list[RISField]
    conditional_mandatory: list[RISField] = Field(default_factory=list)
    optional: list[RISField] = Field(default_factory=list)
    evidence_documents_checklist: list[str] = Field(default_factory=list)
    drafting_guidance: list[str] = Field(default_factory=list)


class ValidationReportOut(BaseModel):
    missing_required_fields: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ready_for_planning: bool = Field(
        description="True only when it is objectively safe to proceed to planning (required fields satisfied or explicitly accepted as blanks; no unresolved contradictions)."
    )


class Question(BaseModel):
    key: str = Field(description="Machine key the user should answer for.")
    question: str = Field(description="The question to ask the user.")
    required: bool = Field(default=True)
    category: Literal["blocker", "risk", "quality", "assumption"] = Field(default="blocker")
    priority: int = Field(default=1, description="1=highest priority, 3=lowest")
    example: Optional[str] = Field(default=None)


class QuestionBatchOut(BaseModel):
    batch_name: str
    questions: list[Question]
    expected_keys: list[str]
    answer_format: str


class IntakeExtractOut(BaseModel):
    updates: dict[str, str] = Field(default_factory=dict)
    explicitly_unknown: list[str] = Field(default_factory=list)
    proceed_with_blanks: Optional[bool] = Field(
        default=None, description="Whether user explicitly accepted proceeding with missing required fields."
    )
    what_i_understood: str = Field(default="")
    still_missing: list[str] = Field(default_factory=list, description="Keys (from expected_keys) not addressed.")


class QAEntry(BaseModel):
    batch: str
    questions: list[Question] = Field(default_factory=list)
    answer: str
    expected_keys: list[str] = Field(default_factory=list)
    updates: dict[str, str] = Field(default_factory=dict)
    explicitly_unknown: list[str] = Field(default_factory=list)
    proceed_with_blanks: Optional[bool] = Field(default=None)
    what_i_understood: str = Field(default="")
    still_missing: list[str] = Field(default_factory=list)


class DraftPlanOut(BaseModel):
    issues: list[str] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)
    pleading_notes: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)


class ResearchTask(BaseModel):
    task_id: str
    issue: str
    research_question: str
    priority: int = Field(default=2, description="1=highest priority, 3=lowest")
    expected_authorities: list[str] = Field(default_factory=list)


class ResearchPlanOut(BaseModel):
    tasks: list[ResearchTask] = Field(default_factory=list)


class Citation(BaseModel):
    source_type: Literal["statute", "case", "rule", "treatise", "website", "unknown"] = Field(default="unknown")
    citation: str = Field(description="Human-readable citation string.")
    pinpoint: Optional[str] = Field(default=None, description="Optional pinpoint (section/order/rule/para/page).")
    url: Optional[str] = Field(default=None)
    note: Optional[str] = Field(default=None)
    confidence: Literal["high", "medium", "low"] = Field(default="low")
    verified: bool = Field(default=False, description="True only if citation was verified via a trusted source/tool.")


class ResearchResultOut(BaseModel):
    task_id: str
    issue: str
    findings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = Field(default="low")
    conflicts: list[str] = Field(default_factory=list)
    to_verify: list[str] = Field(default_factory=list)


class ResearchPackOut(BaseModel):
    synthesized_findings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    by_task: list[ResearchResultOut] = Field(default_factory=list)


class AuditPackOut(BaseModel):
    facts_as_provided: dict[str, str] = Field(default_factory=dict)
    blanks_accepted: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)


class CompiledDraftOut(BaseModel):
    court_name: str = Field(default="")
    cause_title: str = Field(default="IN THE COURT OF ...")
    parties: list[str] = Field(default_factory=list)
    facts_paragraphs: list[str] = Field(default_factory=list)
    cause_of_action_paragraphs: list[str] = Field(default_factory=list)
    jurisdiction_paragraphs: list[str] = Field(default_factory=list)
    limitation_paragraph: str = Field(default="")
    valuation_paragraph: str = Field(default="")
    reliefs: list[str] = Field(default_factory=list)
    interim_reliefs: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    verification: str = Field(default="")
    statement_of_truth: Optional[str] = Field(default=None)
    one_page_brief: str = Field(default="")
    next_steps: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    citations_used: list[Citation] = Field(default_factory=list)
    conflict_resolutions: list[str] = Field(
        default_factory=list,
        description="If authorities/conflicting positions were encountered, record the resolution reasoning (authority hierarchy) or mark as TO VERIFY.",
    )


class DraftSection(BaseModel):
    heading: str
    body: str


class DraftAssemblerOut(BaseModel):
    cause_title: str
    parties_block: str
    sections: list[DraftSection] = Field(default_factory=list)
    prayer_block: str = Field(default="")
    annexures: list[str] = Field(default_factory=list)
    verification: str = Field(default="")
    statement_of_truth: Optional[str] = Field(default=None)
    one_page_brief: str = Field(default="")
    missing_inputs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    compliance_checklist: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    conflict_resolutions: list[str] = Field(default_factory=list)


class FinalDraftPackOut(BaseModel):
    draft_text: str
    one_page_brief: str
    annexures: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    compliance_checklist: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    audit_pack: AuditPackOut


class FinalReviewDecision(BaseModel):
    approved: bool = Field(default=False)
    revision_instructions: str = Field(default="")


# -----------------------------
# 8) State (LangGraph)
# -----------------------------


def append_list(left: list[dict], right: list[dict] | None) -> list[dict]:
    return left + (right or [])


def append_str_list(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


@dataclass
class Ctx:
    case_id: str
    user_id: str


class PlaintState(TypedDict, total=False):
    category: str
    subcategory: str
    doc_type: str
    forum: str
    route: dict

    case_file: dict[str, str]
    blanks: list[str]  # keys user explicitly marked unknown
    blanks_accepted: list[str]  # keys user explicitly accepted leaving blank (assumptions)

    qa_log: Annotated[list[dict], append_list]
    log: Annotated[list[str], append_str_list]

    ris: dict
    validation: dict

    intake_batch: dict
    last_user_answer: str

    draft_plan: dict
    research_plan: dict
    research_results: Annotated[list[dict], append_list]
    research_pack: dict

    compiled: dict
    assembled: dict
    final_draft: dict
    audit_pack: dict

    final_review: dict
    revision_count: int

    output_dir: str


# -----------------------------
# 9) Intake definition (plaint-only)
# -----------------------------

FORUM = "Civil Court (India)"
MAX_QUESTIONS_PER_BATCH = 6


def is_yes(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"y", "yes", "true", "1"}


def is_missing_value(value: str | None) -> bool:
    if value is None:
        return True
    v = value.strip()
    if not v:
        return True
    if v.lower() in {"[blank]", "blank", "unknown", "[unknown]", "n/a", "na"}:
        return True
    return False


def parse_iso_date(text: str | None) -> datetime | None:
    if not text:
        return None
    t = text.strip()
    try:
        return datetime.strptime(t, "%Y-%m-%d")
    except Exception:
        return None


def build_plaint_ris() -> RequiredInformationSchemaOut:
    """
    Required Information Schema (RIS) for an Indian civil plaint.
    This is the contract the intake + validator enforce before planning.
    """
    mandatory = [
        RISField(
            key="court_name",
            description="Which court will the plaint be filed in? (name + place)",
            data_type="string",
            validation_rules=["Should include court + place."],
            example="City Civil Court at Bengaluru",
        ),
        RISField(
            key="plaintiff",
            description="Plaintiff name + description/capacity (e.g., individual/company, age, occupation, address reference).",
            data_type="text",
        ),
        RISField(
            key="defendant",
            description="Defendant name + description/capacity (individual/company; include registered office if company).",
            data_type="text",
        ),
        RISField(key="plaintiff_address", description="Plaintiff service address (complete).", data_type="text"),
        RISField(key="defendant_address", description="Defendant service address (complete).", data_type="text"),
        RISField(
            key="facts_timeline",
            description="Chronological material facts timeline with dates/places (material facts, not evidence).",
            data_type="text",
            validation_rules=["Prefer dated lines or numbered paragraphs."],
        ),
        RISField(
            key="cause_of_action",
            description="Cause of action: what legal wrong occurred and when it arose (material facts).",
            data_type="text",
        ),
        RISField(
            key="jurisdiction_facts",
            description="Territorial + pecuniary jurisdiction facts (why this court).",
            data_type="text",
        ),
        RISField(
            key="reliefs",
            description="Reliefs/prayers sought (main reliefs; include interim reliefs if any).",
            data_type="text",
        ),
        RISField(
            key="interim_relief_needed",
            description="Is any interim/temporary injunction or urgent relief needed? (yes/no/unknown)",
            data_type="bool",
            validation_rules=["Answer yes/no/unknown."],
            example="no",
        ),
        RISField(key="valuation", description="Suit valuation for jurisdiction (amount/basis).", data_type="money"),
        RISField(
            key="court_fee",
            description="Court fee position (amount or basis; if unknown, state unknown).",
            data_type="text",
        ),
        RISField(
            key="limitation",
            description="Limitation/delay position (why within time; or delay and condonation basis if any).",
            data_type="text",
        ),
        RISField(
            key="documents",
            description="List of documents/annexures to rely on (list even if not yet available).",
            data_type="list",
        ),
        RISField(
            key="is_commercial_dispute",
            description="Is this a commercial dispute under commercial courts framework? (yes/no/unknown)",
            data_type="bool",
            validation_rules=["Answer yes/no/unknown."],
            example="no",
        ),
    ]

    conditional_mandatory = [
        RISField(
            key="commercial_value",
            description="If commercial dispute: specified value/approximate amount (and basis).",
            required_if="Required if is_commercial_dispute=yes",
            data_type="money",
        ),
        RISField(
            key="interim_reliefs",
            description="If interim relief needed: interim relief prayer + urgency reasons (material facts).",
            required_if="Required if interim_relief_needed=yes",
            data_type="text",
        ),
    ]

    optional = [
        RISField(
            key="proposed_filing_date",
            description="Proposed filing date (YYYY-MM-DD) for basic contradiction checks.",
            data_type="date",
            validation_rules=["YYYY-MM-DD."],
            example="2026-02-02",
        ),
        RISField(
            key="cause_of_action_date",
            description="If easy to state separately: date cause of action arose (YYYY-MM-DD).",
            data_type="date",
            validation_rules=["YYYY-MM-DD."],
            example="2024-03-01",
        ),
    ]

    evidence_documents_checklist = [
        "Contract/Agreement (if any)",
        "Invoices / Bills / Statements (if any)",
        "Demand notice / Legal notice (if any)",
        "Acknowledgements / Replies (if any)",
        "Authority documents (Board resolution/POA, if company/agent)",
        "Court fee computation basis (as applicable)",
    ]

    drafting_guidance = [
        "Pleadings: state material facts (not evidence) in numbered paragraphs.",
        "For plaints, ensure particulars expected in Order VII CPC are covered (court, parties, facts, cause of action, relief, valuation, etc.).",
        "If commercial dispute, consider statement of truth / affidavit-style verification requirements (varies; TO VERIFY).",
    ]

    return RequiredInformationSchemaOut(
        doc_type=DOC_TYPE,
        forum=FORUM,
        mandatory=mandatory,
        conditional_mandatory=conditional_mandatory,
        optional=optional,
        evidence_documents_checklist=evidence_documents_checklist,
        drafting_guidance=drafting_guidance,
    )


def _ris_field_map(ris: RequiredInformationSchemaOut) -> dict[str, RISField]:
    m: dict[str, RISField] = {}
    for f in ris.mandatory + ris.conditional_mandatory + ris.optional:
        m[f.key] = f
    return m


def _conditional_required_keys(ris: RequiredInformationSchemaOut, case_file: dict[str, str]) -> list[str]:
    keys: list[str] = []
    if is_yes(case_file.get("is_commercial_dispute")):
        keys.append("commercial_value")
    if is_yes(case_file.get("interim_relief_needed")):
        keys.append("interim_reliefs")
    return keys


def validate_case_file(
    *, ris: RequiredInformationSchemaOut, case_file: dict[str, str], blanks_accepted: list[str]
) -> ValidationReportOut:
    field_map = _ris_field_map(ris)

    required_keys = [f.key for f in ris.mandatory] + _conditional_required_keys(ris, case_file)
    missing_required: list[str] = []
    for key in required_keys:
        if key in blanks_accepted:
            continue
        if is_missing_value(case_file.get(key)):
            desc = field_map.get(key).description if key in field_map else key
            missing_required.append(f"{key} — {desc}")

    contradictions: list[str] = []
    # Basic date sanity checks if user provided structured dates.
    filing_dt = parse_iso_date(case_file.get("proposed_filing_date"))
    coa_dt = parse_iso_date(case_file.get("cause_of_action_date"))
    if filing_dt and coa_dt and coa_dt > filing_dt:
        contradictions.append("cause_of_action_date is after proposed_filing_date.")

    risk_flags: list[str] = []
    if is_missing_value(case_file.get("jurisdiction_facts")):
        risk_flags.append("Jurisdiction facts unclear (territorial/pecuniary).")
    if is_missing_value(case_file.get("limitation")):
        risk_flags.append("Limitation position unclear; risk of time-bar.")
    if is_missing_value(case_file.get("court_fee")):
        risk_flags.append("Court fee position unclear; verify applicable court-fee computation.")
    if is_yes(case_file.get("is_commercial_dispute")) and is_missing_value(case_file.get("commercial_value")):
        risk_flags.append("Commercial dispute indicated but specified value not provided.")
    if is_yes(case_file.get("interim_relief_needed")) and is_missing_value(case_file.get("interim_reliefs")):
        risk_flags.append("Interim relief needed but interim relief details not provided.")

    # Assumptions are any accepted blanks (explicit user consent).
    assumptions: list[str] = []
    for key in blanks_accepted:
        desc = field_map.get(key).description if key in field_map else key
        assumptions.append(f"{key} — accepted blank (placeholder) pending confirmation. ({desc})")

    ready_for_planning = len(missing_required) == 0 and len(contradictions) == 0
    return ValidationReportOut(
        missing_required_fields=missing_required,
        contradictions=contradictions,
        risk_flags=risk_flags,
        assumptions=assumptions,
        ready_for_planning=ready_for_planning,
    )


def select_next_question_keys(*, report: ValidationReportOut) -> list[str]:
    """
    Deterministic question selection. Rank:
    1) blockers (missing required + contradictions),
    2) risk reducers,
    3) quality improvements (not used yet for plaint-only demo).
    """
    keys: list[str] = []

    for entry in report.missing_required_fields:
        key = entry.split(" — ", 1)[0].strip()
        if key and key not in keys:
            keys.append(key)

    # If contradictions mention specific keys, try to include them.
    if report.contradictions:
        for c in report.contradictions:
            # Naive heuristic: add likely keys mentioned in contradiction string.
            for candidate in ("cause_of_action_date", "proposed_filing_date"):
                if candidate in c and candidate not in keys:
                    keys.append(candidate)

    return keys[:MAX_QUESTIONS_PER_BATCH]


# -----------------------------
# 10) LLM wrapper (with SQLite cache)
# -----------------------------


class LLMEngine:
    def __init__(self, *, model: str, cache: Optional[object], mock: bool) -> None:
        self._model = model
        self._cache = cache
        self._mock = mock
        self._SystemMessage: type | None = None
        self._HumanMessage: type | None = None

        if not mock:
            require_env("OPENAI_API_KEY")

        self._llm: object | None = None
        if not mock:
            try:
                from langchain_openai import ChatOpenAI  # type: ignore
                from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "Missing dependency: langchain-openai / langchain-core. Install them to use real LLM mode, "
                    "or run with --mock for offline mode."
                ) from e

            self._llm = ChatOpenAI(model=model, temperature=0)
            self._SystemMessage = SystemMessage
            self._HumanMessage = HumanMessage

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

    def call_structured(self, *, agent: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """
        Returns an instance of `schema` (Pydantic model).
        Uses SQLite cache if available.
        """
        if self._mock:
            return self._mock_structured(agent=agent, user=user, schema=schema)

        cache_key = self._cache_key(agent, system, user, schema.__name__)
        ns = ("llm", agent)
        if self._cache is not None:
            hit = self._cache.get([(ns, cache_key)]).get((ns, cache_key))
            if hit is not None:
                return schema.model_validate(hit)

        if self._llm is None:
            raise RuntimeError("LLM is not initialized (mock mode should have returned earlier).")
        if self._SystemMessage is None or self._HumanMessage is None:
            raise RuntimeError("Message classes are not initialized (missing langchain-core).")

        structured = self._llm.with_structured_output(schema)  # type: ignore[attr-defined]
        out = structured.invoke([self._SystemMessage(content=system), self._HumanMessage(content=user)])

        if self._cache is not None:
            self._cache.set({(ns, cache_key): (out.model_dump(), 24 * 3600)})

        return out

    def _mock_structured(self, *, agent: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """
        Offline mode: simple deterministic stubs so the graph can run end-to-end.
        This is intentionally basic; real behavior happens with the LLM.
        """

        def extract_json_block(after_marker: str, open_ch: str, close_ch: str) -> str | None:
            if after_marker not in user:
                return None
            tail = user.split(after_marker, 1)[1]
            start = tail.find(open_ch)
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(tail)):
                ch = tail[i]
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        return tail[start : i + 1]
            return None

        def parse_json_list(after_marker: str) -> list[Any]:
            block = extract_json_block(after_marker, "[", "]")
            if not block:
                return []
            try:
                val = json.loads(block)
            except Exception:
                return []
            return val if isinstance(val, list) else []

        def parse_json_object(after_marker: str) -> dict[str, Any]:
            block = extract_json_block(after_marker, "{", "}")
            if not block:
                return {}
            try:
                val = json.loads(block)
            except Exception:
                return {}
            return val if isinstance(val, dict) else {}

        def parse_user_answer() -> str:
            if "User answer:" not in user:
                return ""
            return user.split("User answer:", 1)[1].strip()

        if schema is QuestionBatchOut:
            expected = parse_json_list("expected_keys (ask ONLY these keys):") or parse_json_list("expected_keys:")
            expected_keys = [str(x) for x in expected if isinstance(x, (str, int, float))]
            questions: list[Question] = []
            for key in expected_keys:
                if key == "proceed_with_blanks":
                    questions.append(
                        Question(
                            key=key,
                            question="If you want to proceed with placeholders for missing required items, answer yes/no.",
                            required=False,
                            category="assumption",
                            priority=1,
                            example="no",
                        )
                    )
                else:
                    questions.append(
                        Question(
                            key=key,
                            question=f"Provide {key}.",
                            required=True,
                            category="blocker",
                            priority=1,
                            example=None,
                        )
                    )
            return QuestionBatchOut(
                batch_name="Mock intake batch",
                questions=questions,
                expected_keys=expected_keys,
                answer_format="Answer as key: value lines (end with blank line). If unknown, write [UNKNOWN].",
            )

        if schema is IntakeExtractOut:
            expected_any = parse_json_list("Expected keys (extract only these keys if present):")
            expected = [str(x) for x in expected_any if isinstance(x, (str, int, float))]
            answer_text = parse_user_answer()

            updates: dict[str, str] = {}
            explicitly_unknown: list[str] = []
            proceed_with_blanks: Optional[bool] = None

            # Parse key:value lines, keep only expected keys.
            for line in answer_text.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k not in expected:
                    continue
                if k == "proceed_with_blanks":
                    vv = v.lower()
                    if vv in {"y", "yes", "true", "1"}:
                        proceed_with_blanks = True
                    elif vv in {"n", "no", "false", "0"}:
                        proceed_with_blanks = False
                    continue
                updates[k] = v
                if v.lower() in {"blank", "unknown", "[blank]", "[unknown]"}:
                    explicitly_unknown.append(k)

            understood = "(mock) extracted: " + ", ".join(sorted(list(updates.keys())))
            still_missing = [k for k in expected if k not in updates]
            return IntakeExtractOut(
                updates=updates,
                explicitly_unknown=explicitly_unknown,
                proceed_with_blanks=proceed_with_blanks,
                what_i_understood=understood,
                still_missing=still_missing,
            )
        if schema is DraftPlanOut:
            return DraftPlanOut(
                issues=["Jurisdiction", "Limitation", "Reliefs"],
                outline=["CAUSE TITLE", "FACTS", "CAUSE OF ACTION", "JURISDICTION", "PRAYER", "VERIFICATION"],
                pleading_notes=[
                    "Keep pleadings to material facts; list documents separately as annexures.",
                    "Ensure Order VII plaint particulars are covered (TO VERIFY).",
                ],
                missing_inputs=[],
            )
        if schema is ResearchPlanOut:
            return ResearchPlanOut(
                tasks=[
                    ResearchTask(
                        task_id="T1",
                        issue="Pleading requirements",
                        research_question="What are the key plaint particulars and pleading discipline points under CPC? (TO VERIFY)",
                        priority=1,
                        expected_authorities=["CPC Order VI Rule 2", "CPC Order VII"],
                    ),
                    ResearchTask(
                        task_id="T2",
                        issue="Limitation",
                        research_question="Which limitation period likely applies on these facts? (TO VERIFY)",
                        priority=2,
                        expected_authorities=["Limitation Act, 1963 (TO VERIFY)"],
                    ),
                ]
            )
        if schema is ResearchResultOut:
            task_obj = parse_json_object("Research task (JSON):")
            task_id = str(task_obj.get("task_id") or "T?")
            issue = str(task_obj.get("issue") or "Issue")
            return ResearchResultOut(
                task_id=task_id,
                issue=issue,
                findings=[
                    "Pleadings should contain material facts and not evidence (TO VERIFY).",
                    "Plaint should contain particulars required by CPC Order VII (TO VERIFY).",
                ],
                citations=[
                    Citation(
                        source_type="statute",
                        citation="Code of Civil Procedure, 1908 (CPC)",
                        pinpoint="Order VI Rule 2; Order VII (plaint particulars) (TO VERIFY)",
                        confidence="low",
                        verified=False,
                    )
                ],
                confidence="low",
                conflicts=[],
                to_verify=["Verify exact CPC rule text and local rules."],
            )
        if schema is CompiledDraftOut:
            case_file = parse_json_object("Case file (JSON):")
            missing_inputs_any = parse_json_list("Missing inputs (placeholders accepted) (JSON list):")
            missing_inputs = [str(x) for x in missing_inputs_any if isinstance(x, (str, int, float))]

            def as_lines(v: Any) -> list[str]:
                if v is None:
                    return []
                if isinstance(v, list):
                    return [str(x).strip() for x in v if str(x).strip()]
                s = str(v).strip()
                if not s:
                    return []
                return [ln.strip() for ln in s.splitlines() if ln.strip()]

            court_name = str(case_file.get("court_name") or "IN THE COURT OF ...").strip()
            plaintiff = str(case_file.get("plaintiff") or "<<PLACEHOLDER: plaintiff>>").strip()
            defendant = str(case_file.get("defendant") or "<<PLACEHOLDER: defendant>>").strip()
            facts = as_lines(case_file.get("facts_timeline")) or ["<<PLACEHOLDER: facts_timeline>>"]
            reliefs = as_lines(case_file.get("reliefs")) or ["<<PLACEHOLDER: reliefs>>"]
            docs = as_lines(case_file.get("documents"))
            return CompiledDraftOut(
                court_name=court_name,
                cause_title=f"IN THE COURT OF {court_name}",
                parties=[f"PLAINTIFF: {plaintiff}", f"DEFENDANT: {defendant}"],
                facts_paragraphs=facts,
                cause_of_action_paragraphs=[
                    str(case_file.get("cause_of_action") or "<<PLACEHOLDER: cause_of_action>>")
                ],
                jurisdiction_paragraphs=[
                    str(case_file.get("jurisdiction_facts") or "<<PLACEHOLDER: jurisdiction_facts>>")
                ],
                limitation_paragraph=str(case_file.get("limitation") or "<<PLACEHOLDER: limitation>>"),
                valuation_paragraph=f"Valuation: {case_file.get('valuation', '<<PLACEHOLDER: valuation>>')}. Court fee: {case_file.get('court_fee', '<<PLACEHOLDER: court_fee>>')}.",
                reliefs=reliefs,
                interim_reliefs=as_lines(case_file.get("interim_reliefs")),
                documents=docs,
                verification="Verified at ____ on ____ that the contents are true to my knowledge (TO VERIFY local form).",
                statement_of_truth=(
                    "Statement of Truth / affidavit as applicable (TO VERIFY)."
                    if str(case_file.get("is_commercial_dispute") or "").strip().lower() in {"y", "yes", "true", "1"}
                    else None
                ),
                one_page_brief="(mock) One-page brief: parties, dispute, reliefs.",
                next_steps=["(mock) Have an advocate review and finalize court fee/limitation/jurisdiction."],
                missing_inputs=missing_inputs,
                assumptions_used=missing_inputs,
                risk_flags=[],
                citations_used=[],
                conflict_resolutions=[],
            )

        return schema()  # type: ignore[call-arg]


ENGINE: LLMEngine | None = None


# -----------------------------
# 11) Agents as LangGraph nodes
# -----------------------------


def store_put(runtime: Runtime[Ctx], namespace: tuple[str, str], key: str, value: object) -> None:
    store = getattr(runtime, "store", None)
    if store is None:
        return
    store.put(namespace, key, value)  # type: ignore[union-attr]


def node_init(_: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    # Create a persistent namespace for this case in the SQLite store.
    store_put(
        runtime,
        ("cases", runtime.context.case_id),
        "meta",
        {"category": CATEGORY, "subcategory": SUBCATEGORY, "doc_type": DOC_TYPE, "forum": FORUM},
    )
    return {
        "category": CATEGORY,
        "subcategory": SUBCATEGORY,
        "doc_type": DOC_TYPE,
        "forum": FORUM,
        "route": {},
        "ris": {},
        "validation": {},
        "intake_batch": {},
        "last_user_answer": "",
        "case_file": {},
        "blanks": [],
        "blanks_accepted": [],
        "qa_log": [],
        "draft_plan": {},
        "research_plan": {},
        "research_results": [],
        "research_pack": {},
        "compiled": {},
        "assembled": {},
        "final_draft": {},
        "audit_pack": {},
        "final_review": {},
        "revision_count": 0,
        "log": [f"init(case_id={runtime.context.case_id})"],
    }


def node_intake_router(_: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    """
    Intake Router: classify document type + forum + jurisdiction scope.
    For this learning script we keep it fixed to plaint, but still emit a typed contract.
    """
    route = IntakeRouteOut(
        category=CATEGORY,
        subcategory=SUBCATEGORY,
        doc_type=DOC_TYPE,
        forum=FORUM,
        jurisdiction_scope="India (civil courts) — forum depends on territorial/pecuniary facts (TO VERIFY).",
        notes="Plaint-only demo router.",
    )
    store_put(runtime, ("cases", runtime.context.case_id), "route", route.model_dump())
    return {"route": route.model_dump(), "forum": route.forum, "log": ["router: classified plaint workflow"]}


def node_ris_builder(_: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    ris = build_plaint_ris()
    store_put(runtime, ("cases", runtime.context.case_id), "ris", ris.model_dump())
    return {"ris": ris.model_dump(), "log": ["ris built"]}


def node_validator(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    ris = RequiredInformationSchemaOut.model_validate(state.get("ris") or build_plaint_ris().model_dump())
    case_file = dict(state.get("case_file", {}))
    blanks_accepted = list(state.get("blanks_accepted", []))
    report = validate_case_file(ris=ris, case_file=case_file, blanks_accepted=blanks_accepted)
    store_put(runtime, ("cases", runtime.context.case_id), "validation", report.model_dump())
    return {"validation": report.model_dump(), "log": [f"validated ready={report.ready_for_planning}"]}


def route_after_validator(state: PlaintState) -> str:
    report = ValidationReportOut.model_validate(state.get("validation") or {})
    return "draft_plan" if report.ready_for_planning else "question_generator"


def node_question_generator(state: PlaintState) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    ris = RequiredInformationSchemaOut.model_validate(state.get("ris") or build_plaint_ris().model_dump())
    field_map = _ris_field_map(ris)
    report = ValidationReportOut.model_validate(state.get("validation") or {})
    case_file = dict(state.get("case_file", {}))

    expected_keys = select_next_question_keys(report=report)

    # Add risk-reducer (optional) keys if there's room.
    for candidate in ("cause_of_action_date", "proposed_filing_date"):
        if len(expected_keys) >= MAX_QUESTIONS_PER_BATCH:
            break
        if candidate in expected_keys:
            continue
        if is_missing_value(case_file.get(candidate)):
            expected_keys.append(candidate)

    if report.missing_required_fields and "proceed_with_blanks" not in expected_keys:
        expected_keys = expected_keys + ["proceed_with_blanks"]

    blocker_keys: set[str] = set()
    for entry in report.missing_required_fields:
        k = entry.split(" — ", 1)[0].strip()
        if k:
            blocker_keys.add(k)

    expected_desc: list[str] = []
    for k in expected_keys:
        if k == "proceed_with_blanks":
            expected_desc.append(
                "proceed_with_blanks — If you want to proceed with placeholders for missing required items, answer yes/no."
            )
            continue
        desc = field_map.get(k).description if k in field_map else k
        expected_desc.append(f"{k} — {desc}")

    user_prompt = wrap(
        f"""
        We are drafting a CIVIL PLAINT in India.

        Current case_file (JSON):
        {json.dumps(case_file, indent=2)}

        Validation report (JSON):
        {json.dumps(report.model_dump(), indent=2)}

        expected_keys (ask ONLY these keys):
        {json.dumps(expected_keys, indent=2)}

        Key descriptions:
        {json.dumps(expected_desc, indent=2)}

        Output a short ranked question batch.
        """
    )
    batch = llm.call_structured(
        agent="question_generator",
        system=QUESTION_GENERATOR_SYSTEM,
        user=user_prompt,
        schema=QuestionBatchOut,
    )

    # Enforce deterministic expected_keys and prevent drift: we sanitize LLM output.
    questions_by_key = {q.key: q for q in batch.questions}
    sanitized_questions: list[Question] = []
    for k in expected_keys:
        q = questions_by_key.get(k)
        if q is None:
            q = Question(key=k, question=f"Provide {k}.", required=True)
        if k == "proceed_with_blanks":
            sanitized_questions.append(
                Question(
                    key=k,
                    question=q.question or "Proceed with placeholders for missing required items? (yes/no)",
                    required=False,
                    category="assumption",
                    priority=1,
                    example="no",
                )
            )
        elif k in blocker_keys:
            sanitized_questions.append(
                Question(
                    key=k,
                    question=q.question or f"Provide {k}.",
                    required=True,
                    category="blocker",
                    priority=1,
                    example=q.example,
                )
            )
        else:
            sanitized_questions.append(
                Question(
                    key=k,
                    question=q.question or f"Provide {k}.",
                    required=False,
                    category="risk",
                    priority=2,
                    example=q.example,
                )
            )

    sanitized_batch = QuestionBatchOut(
        batch_name=batch.batch_name or "Intake questions",
        questions=sanitized_questions,
        expected_keys=expected_keys,
        answer_format=batch.answer_format
        or "Answer as key: value lines (end with blank line). If unknown, write [UNKNOWN].",
    )
    return {"intake_batch": sanitized_batch.model_dump(), "log": [f"questions generated ({len(sanitized_questions)})"]}


def node_wait_for_user(state: PlaintState) -> PlaintState:
    batch = dict(state.get("intake_batch", {}))
    report = dict(state.get("validation", {}))
    prompt = {
        "title": f"Intake — {batch.get('batch_name', 'Questions')}",
        "questions": batch.get("questions", []),
        "answer_format": batch.get(
            "answer_format", "Answer as key: value lines (end with blank line). If unknown, write [UNKNOWN]."
        ),
        "missing_required_fields": report.get("missing_required_fields", []),
        "risk_flags": report.get("risk_flags", []),
        "note": "Answer in key:value lines. If unknown, write [UNKNOWN]. End with an empty line.",
    }
    answer = interrupt(prompt)
    return {"last_user_answer": str(answer), "log": ["user answered intake batch"]}


def _parse_proceed_with_blanks_fallback(answer_text: str) -> Optional[bool]:
    for line in answer_text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip() != "proceed_with_blanks":
            continue
        vv = v.strip().lower()
        if vv in {"y", "yes", "true", "1"}:
            return True
        if vv in {"n", "no", "false", "0"}:
            return False
    return None


def node_answer_extractor(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    ris = RequiredInformationSchemaOut.model_validate(state.get("ris") or build_plaint_ris().model_dump())
    field_map = _ris_field_map(ris)
    report = ValidationReportOut.model_validate(state.get("validation") or {})

    batch = dict(state.get("intake_batch", {}))
    expected_keys = list(batch.get("expected_keys") or [])
    answer_text = str(state.get("last_user_answer", "") or "")
    case_file = dict(state.get("case_file", {}))
    blanks = list(state.get("blanks", []))
    blanks_accepted = list(state.get("blanks_accepted", []))

    expected_desc: list[str] = []
    for k in expected_keys:
        if k == "proceed_with_blanks":
            expected_desc.append(
                "proceed_with_blanks — If you want to proceed with placeholders for missing required items, answer yes/no."
            )
            continue
        desc = field_map.get(k).description if k in field_map else k
        expected_desc.append(f"{k} — {desc}")

    extract_user_prompt = wrap(
        f"""
        We are drafting a CIVIL PLAINT.

        Expected keys (extract only these keys if present):
        {json.dumps(expected_keys, indent=2)}

        Key descriptions:
        {json.dumps(expected_desc, indent=2)}

        Existing case_file (JSON):
        {json.dumps(case_file, indent=2)}

        User answer:
        {answer_text}
        """
    )
    extracted = llm.call_structured(
        agent="answer_extractor",
        system=ANSWER_EXTRACTOR_SYSTEM,
        user=extract_user_prompt,
        schema=IntakeExtractOut,
    )

    allowed_case_keys = set(expected_keys) - {"proceed_with_blanks"}
    extracted_updates = {k: v for k, v in extracted.updates.items() if k in allowed_case_keys}
    extracted_unknowns = [k for k in extracted.explicitly_unknown if k in allowed_case_keys]

    # Apply updates
    for k, v in extracted_updates.items():
        if isinstance(v, str) and v.strip():
            case_file[k] = v.strip()
            if k in blanks:
                blanks.remove(k)
            if k in blanks_accepted:
                blanks_accepted.remove(k)

    for k in extracted_unknowns:
        if k not in blanks:
            blanks.append(k)

    proceed = extracted.proceed_with_blanks
    if proceed is None:
        proceed = _parse_proceed_with_blanks_fallback(answer_text)

    if proceed:
        for entry in report.missing_required_fields:
            k = entry.split(" — ", 1)[0].strip()
            if k and k not in blanks_accepted:
                blanks_accepted.append(k)

    store_put(runtime, ("cases", runtime.context.case_id), "case_file", case_file)
    store_put(
        runtime, ("cases", runtime.context.case_id), "blanks", {"blanks": blanks, "blanks_accepted": blanks_accepted}
    )

    qa = QAEntry(
        batch=str(batch.get("batch_name", "") or ""),
        questions=[Question.model_validate(q) for q in (batch.get("questions", []) or [])],
        answer=answer_text,
        expected_keys=expected_keys,
        updates=extracted_updates,
        explicitly_unknown=extracted_unknowns,
        proceed_with_blanks=bool(proceed) if proceed is not None else None,
        what_i_understood=extracted.what_i_understood,
        still_missing=list(extracted.still_missing or []),
    )

    return {
        "case_file": case_file,
        "blanks": blanks,
        "blanks_accepted": blanks_accepted,
        "qa_log": [qa.model_dump()],
        "log": [f"intake applied updates={list(extracted_updates.keys())} proceed_with_blanks={proceed}"],
    }


def node_draft_plan(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    case_file = dict(state.get("case_file", {}))
    ris = dict(state.get("ris", {}))
    report = dict(state.get("validation", {}))
    user_prompt = wrap(
        f"""
        Category: {CATEGORY}
        Subcategory: {SUBCATEGORY}
        Type: {DOC_TYPE}

        RIS (JSON):
        {json.dumps(ris, indent=2)}

        Validation report (JSON):
        {json.dumps(report, indent=2)}

        Case file (JSON):
        {json.dumps(case_file, indent=2)}
        """
    )
    out = llm.call_structured(agent="draft_planner", system=DRAFT_PLANNER_SYSTEM, user=user_prompt, schema=DraftPlanOut)
    store_put(runtime, ("cases", runtime.context.case_id), "draft_plan", out.model_dump())
    return {"draft_plan": out.model_dump(), "log": ["draft plan created"]}


def node_research_plan(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    case_file = dict(state.get("case_file", {}))
    draft_plan = dict(state.get("draft_plan", {}))
    user_prompt = wrap(
        f"""
        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Draft plan (JSON):
        {json.dumps(draft_plan, indent=2)}

        Output a research plan with task_id values like T1, T2, ... (unique).
        """
    )
    out = llm.call_structured(
        agent="research_planner",
        system=RESEARCH_PLANNER_SYSTEM,
        user=user_prompt,
        schema=ResearchPlanOut,
    )
    store_put(runtime, ("cases", runtime.context.case_id), "research_plan", out.model_dump())
    # Reset map-reduce accumulators for this run segment.
    return {
        "research_plan": out.model_dump(),
        "research_results": [],
        "research_pack": {},
        "log": ["research plan created"],
    }


def route_to_research_workers(state: PlaintState) -> list[Send] | str:
    plan = dict(state.get("research_plan", {}))
    tasks = plan.get("tasks", []) or []
    if not tasks:
        return "research_reduce"

    case_file = dict(state.get("case_file", {}))
    draft_plan = dict(state.get("draft_plan", {}))
    ris = dict(state.get("ris", {}))
    return [
        Send(
            "research_worker",
            {"task": t, "case_file": case_file, "draft_plan": draft_plan, "ris": ris},
        )
        for t in tasks
    ]


def node_research_worker(state: dict[str, Any]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    task = ResearchTask.model_validate(state.get("task") or {})
    case_file = state.get("case_file") or {}
    draft_plan = state.get("draft_plan") or {}
    ris = state.get("ris") or {}

    user_prompt = wrap(
        f"""
        Research task (JSON):
        {json.dumps(task.model_dump(), indent=2)}

        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Draft plan (JSON):
        {json.dumps(draft_plan, indent=2)}

        RIS (JSON):
        {json.dumps(ris, indent=2)}
        """
    )
    out = llm.call_structured(
        agent="research_worker",
        system=RESEARCH_WORKER_SYSTEM,
        user=user_prompt,
        schema=ResearchResultOut,
    )
    # Enforce task identity (prevents drift across fan-out workers).
    if out.task_id != task.task_id or out.issue != task.issue:
        out = out.model_copy(update={"task_id": task.task_id, "issue": task.issue})
    return {"research_results": [out.model_dump()], "log": [f"research done {out.task_id}"]}


def node_research_reduce(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    results_raw = list(state.get("research_results", []) or [])
    results: list[ResearchResultOut] = []
    citations: list[Citation] = []
    conflicts: list[str] = []
    synthesized: list[str] = []

    for r in results_raw:
        rr = ResearchResultOut.model_validate(r)
        results.append(rr)
        synthesized.extend([f"[{rr.task_id}] {f}" for f in rr.findings])
        conflicts.extend(rr.conflicts)
        citations.extend(rr.citations)

    # Deduplicate citations (best-effort).
    seen: set[tuple[str, str, str | None, str | None]] = set()
    deduped: list[Citation] = []
    for c in citations:
        key = (c.source_type, c.citation.strip(), (c.pinpoint or "").strip() or None, (c.url or "").strip() or None)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    pack = ResearchPackOut(
        synthesized_findings=synthesized,
        citations=deduped,
        unresolved_conflicts=conflicts,
        by_task=results,
    )
    store_put(runtime, ("cases", runtime.context.case_id), "research_pack", pack.model_dump())
    return {"research_pack": pack.model_dump(), "log": [f"research reduced tasks={len(results)}"]}


def node_compiler(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    ris = RequiredInformationSchemaOut.model_validate(state.get("ris") or build_plaint_ris().model_dump())
    field_map = _ris_field_map(ris)

    case_file = dict(state.get("case_file", {}))
    blanks_accepted = list(state.get("blanks_accepted", []))
    report = dict(state.get("validation", {}))
    draft_plan = dict(state.get("draft_plan", {}))
    research_pack = dict(state.get("research_pack", {}))
    final_review = dict(state.get("final_review", {}))

    # For accepted blanks, inject explicit placeholders so the compiler can't "fill in" by guessing.
    cf_for_compiler = dict(case_file)
    missing_inputs: list[str] = []
    for key in blanks_accepted:
        desc = field_map.get(key).description if key in field_map else key
        placeholder = f"<<PLACEHOLDER: {key} — {desc}>>"
        if is_missing_value(cf_for_compiler.get(key)):
            cf_for_compiler[key] = placeholder
        missing_inputs.append(f"{key} — {desc}")

    revision_instructions = str(final_review.get("revision_instructions", "") or "").strip()
    user_prompt = wrap(
        f"""
        Case file (JSON):
        {json.dumps(cf_for_compiler, indent=2)}

        Missing inputs (placeholders accepted) (JSON list):
        {json.dumps(missing_inputs, indent=2)}

        Validation report (JSON):
        {json.dumps(report, indent=2)}

        Draft plan (JSON):
        {json.dumps(draft_plan, indent=2)}

        Research pack (JSON):
        {json.dumps(research_pack, indent=2)}

        Revision instructions (if any):
        {revision_instructions if revision_instructions else "(none)"}
        """
    )
    out = llm.call_structured(
        agent="compiler",
        system=COMPILER_SYSTEM,
        user=user_prompt,
        schema=CompiledDraftOut,
    )
    # Enforce "audit pack" invariants deterministically (prevents silent omission).
    merged_missing_inputs: list[str] = []
    for item in list(out.missing_inputs or []) + missing_inputs:
        s = str(item).strip()
        if s and s not in merged_missing_inputs:
            merged_missing_inputs.append(s)

    report_risk_flags = [str(x).strip() for x in (report.get("risk_flags", []) or []) if str(x).strip()]
    merged_risk_flags: list[str] = []
    for item in report_risk_flags + list(out.risk_flags or []):
        s = str(item).strip()
        if s and s not in merged_risk_flags:
            merged_risk_flags.append(s)

    allowed_citations: list[Citation] = [
        Citation.model_validate(c) for c in (research_pack.get("citations", []) or []) if isinstance(c, dict)
    ]
    allowed_keys = {
        (c.source_type, c.citation.strip(), (c.pinpoint or "").strip(), (c.url or "").strip())
        for c in allowed_citations
    }

    filtered_used: list[Citation] = []
    for c in out.citations_used or []:
        key = (c.source_type, c.citation.strip(), (c.pinpoint or "").strip(), (c.url or "").strip())
        if key in allowed_keys:
            filtered_used.append(c)

    # Fill obvious defaults from the case file.
    court_name = out.court_name.strip() or str(case_file.get("court_name") or "").strip()
    cause_title = out.cause_title.strip()
    if (not cause_title or cause_title == "IN THE COURT OF ...") and court_name:
        cause_title = f"IN THE COURT OF {court_name}"

    out = out.model_copy(
        update={
            "court_name": court_name,
            "cause_title": cause_title or out.cause_title,
            "missing_inputs": merged_missing_inputs,
            "assumptions_used": merged_missing_inputs,
            "risk_flags": merged_risk_flags,
            "citations_used": filtered_used,
        }
    )
    store_put(runtime, ("cases", runtime.context.case_id), "compiled", out.model_dump())
    return {"compiled": out.model_dump(), "log": ["compiled draft payload created"]}


def _render_numbered(paras: list[str], start: int = 1) -> str:
    lines: list[str] = []
    n = start
    for p in paras:
        t = str(p).strip()
        if not t:
            continue
        lines.append(f"{n}. {t}")
        n += 1
    return "\n".join(lines).strip()


def _render_bullets(items: list[str]) -> str:
    return "\n".join([f"- {str(x).strip()}" for x in items if str(x).strip()]).strip()


def _build_compliance_checklist(
    *, ris: RequiredInformationSchemaOut, case_file: dict[str, str], blanks_accepted: list[str]
) -> list[str]:
    field_map = _ris_field_map(ris)
    required_keys = [f.key for f in ris.mandatory] + _conditional_required_keys(ris, case_file)
    lines: list[str] = []
    for key in required_keys:
        desc = field_map.get(key).description if key in field_map else key
        if key in blanks_accepted:
            lines.append(f"PLACEHOLDER ACCEPTED: {key} — {desc}")
            continue
        if is_missing_value(case_file.get(key)):
            lines.append(f"MISSING: {key} — {desc}")
        else:
            lines.append(f"OK: {key}")
    return lines


def node_assembler(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    compiled = CompiledDraftOut.model_validate(state.get("compiled") or {})
    case_file = dict(state.get("case_file", {}))
    blanks_accepted = list(state.get("blanks_accepted", []))
    ris = RequiredInformationSchemaOut.model_validate(state.get("ris") or build_plaint_ris().model_dump())

    parties_block = ""
    if compiled.parties:
        parties_block = "\n".join([str(x).strip() for x in compiled.parties if str(x).strip()])
    else:
        p = case_file.get("plaintiff", "<<PLACEHOLDER: plaintiff>>")
        d = case_file.get("defendant", "<<PLACEHOLDER: defendant>>")
        parties_block = f"Plaintiff: {p}\nDefendant: {d}"

    sections: list[DraftSection] = []
    sections.append(DraftSection(heading="FACTS (MATERIAL FACTS)", body=_render_numbered(compiled.facts_paragraphs)))
    sections.append(DraftSection(heading="CAUSE OF ACTION", body=_render_numbered(compiled.cause_of_action_paragraphs)))
    sections.append(DraftSection(heading="JURISDICTION", body=_render_numbered(compiled.jurisdiction_paragraphs)))
    if compiled.limitation_paragraph.strip():
        sections.append(DraftSection(heading="LIMITATION", body=compiled.limitation_paragraph.strip()))
    if compiled.valuation_paragraph.strip():
        sections.append(DraftSection(heading="VALUATION AND COURT FEE", body=compiled.valuation_paragraph.strip()))

    prayer_lines: list[str] = []
    if compiled.reliefs:
        prayer_lines.append("Main reliefs:")
        prayer_lines.append(_render_bullets(compiled.reliefs))
    if compiled.interim_reliefs:
        prayer_lines.append("\nInterim reliefs (if any):")
        prayer_lines.append(_render_bullets(compiled.interim_reliefs))
    prayer_block = "\n".join([x for x in prayer_lines if x.strip()]).strip()

    compliance = _build_compliance_checklist(ris=ris, case_file=case_file, blanks_accepted=blanks_accepted)

    assembled = DraftAssemblerOut(
        cause_title=compiled.cause_title or "IN THE COURT OF ...",
        parties_block=parties_block,
        sections=sections,
        prayer_block=prayer_block,
        annexures=list(compiled.documents or []),
        verification=compiled.verification or "",
        statement_of_truth=compiled.statement_of_truth,
        one_page_brief=compiled.one_page_brief or "",
        missing_inputs=list(compiled.missing_inputs or []),
        citations=list(compiled.citations_used or []),
        compliance_checklist=compliance,
        next_steps=list(compiled.next_steps or []),
        risk_flags=list(compiled.risk_flags or []),
        conflict_resolutions=list(compiled.conflict_resolutions or []),
    )
    store_put(runtime, ("cases", runtime.context.case_id), "assembled", assembled.model_dump())
    return {"assembled": assembled.model_dump(), "log": ["assembled template sections"]}


def node_formatter(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    assembled = DraftAssemblerOut.model_validate(state.get("assembled") or {})
    case_file = dict(state.get("case_file", {}))
    blanks_accepted = list(state.get("blanks_accepted", []))
    report = dict(state.get("validation", {}))

    draft_lines: list[str] = []
    draft_lines.append(assembled.cause_title.strip())
    if case_file.get("court_name"):
        draft_lines.append(str(case_file.get("court_name")).strip())
    draft_lines.append("")
    draft_lines.append("CIVIL SUIT NO. ____ OF 20__")
    draft_lines.append("")
    draft_lines.append("BETWEEN")
    draft_lines.append(assembled.parties_block.strip())
    draft_lines.append("")
    draft_lines.append("PLAINT")
    draft_lines.append("")
    draft_lines.append("MOST RESPECTFULLY SHOWETH:")
    draft_lines.append("")

    for s in assembled.sections:
        draft_lines.append(s.heading.strip())
        draft_lines.append(s.body.strip())
        draft_lines.append("")

    draft_lines.append("PRAYER")
    draft_lines.append(assembled.prayer_block.strip())
    draft_lines.append("")

    if assembled.annexures:
        draft_lines.append("LIST OF DOCUMENTS / ANNEXURES")
        draft_lines.append(_render_bullets(assembled.annexures))
        draft_lines.append("")

    if assembled.verification.strip():
        draft_lines.append("VERIFICATION")
        draft_lines.append(assembled.verification.strip())
        draft_lines.append("")

    if assembled.statement_of_truth and assembled.statement_of_truth.strip():
        draft_lines.append("STATEMENT OF TRUTH / AFFIDAVIT (AS APPLICABLE)")
        draft_lines.append(assembled.statement_of_truth.strip())
        draft_lines.append("")

    draft_text = "\n".join(draft_lines).rstrip() + "\n"

    audit = AuditPackOut(
        facts_as_provided={k: str(v) for k, v in case_file.items()},
        blanks_accepted=blanks_accepted,
        missing_inputs=list(assembled.missing_inputs or []),
        contradictions=list(report.get("contradictions", []) or []),
        risk_flags=list(report.get("risk_flags", []) or []),
        sources=list(assembled.citations or []),
    )

    final_pack = FinalDraftPackOut(
        draft_text=draft_text,
        one_page_brief=assembled.one_page_brief or "",
        annexures=list(assembled.annexures or []),
        missing_inputs=list(assembled.missing_inputs or []),
        citations=list(assembled.citations or []),
        compliance_checklist=list(assembled.compliance_checklist or []),
        next_steps=list(assembled.next_steps or []),
        audit_pack=audit,
    )

    store_put(runtime, ("cases", runtime.context.case_id), "final_draft", final_pack.model_dump())
    store_put(runtime, ("cases", runtime.context.case_id), "audit_pack", audit.model_dump())
    return {"final_draft": final_pack.model_dump(), "audit_pack": audit.model_dump(), "log": ["formatted final draft"]}


def node_final_review(state: PlaintState) -> PlaintState:
    final_pack = dict(state.get("final_draft", {}))
    one_page_brief = str(final_pack.get("one_page_brief", "") or "").strip()
    missing_inputs = final_pack.get("missing_inputs", []) or []
    risk_flags = (
        (state.get("validation") or {}).get("risk_flags", []) if isinstance(state.get("validation"), dict) else []
    )

    preview = str(final_pack.get("draft_text", "") or "")
    preview = preview[:1200] + ("\n...\n" if len(preview) > 1200 else "")

    prompt = {
        "title": "Final Review (HITL)",
        "one_page_brief": one_page_brief,
        "missing_inputs": missing_inputs,
        "risk_flags": risk_flags,
        "draft_preview": preview,
        "instructions": wrap(
            """
            Reply with:
              approved: yes
            OR:
              approved: no
              revision_instructions: <what to change>

            If you reply without 'approved: yes', the text will be treated as revision instructions.
            """
        ),
    }
    answer = interrupt(prompt)
    text = str(answer).strip()

    approved = False
    revision_instructions = ""
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip() == "approved" and is_yes(v):
            approved = True
        if k.strip() == "revision_instructions":
            revision_instructions = v.strip()

    if not approved and not revision_instructions:
        revision_instructions = text

    decision = FinalReviewDecision(approved=approved, revision_instructions=revision_instructions)
    return {"final_review": decision.model_dump(), "log": [f"final_review approved={approved}"]}


def route_after_final_review(state: PlaintState) -> str:
    decision = FinalReviewDecision.model_validate(state.get("final_review") or {})
    revision_count = int(state.get("revision_count") or 0)
    if decision.approved:
        return "deliver"
    if decision.revision_instructions.strip() and revision_count < 2:
        return "compiler"
    return "final_review"


def node_bump_revision(state: PlaintState) -> PlaintState:
    decision = FinalReviewDecision.model_validate(state.get("final_review") or {})
    revision_count = int(state.get("revision_count") or 0)
    if not decision.approved and decision.revision_instructions.strip():
        revision_count += 1
    return {"revision_count": revision_count, "log": [f"revision_count={revision_count}"]}


def node_deliver(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    case_id = runtime.context.case_id
    case_dir = ARTIFACTS_DIR / f"case_{case_id}"
    case_dir.mkdir(exist_ok=True)

    def write_json(name: str, obj: object) -> None:
        (case_dir / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")

    write_json("00_route.json", state.get("route", {}))
    write_json("01_required_information_schema.json", state.get("ris", {}))
    write_json("02_case_file.json", state.get("case_file", {}))
    write_json("03_validation_report.json", state.get("validation", {}))
    write_json("04_draft_plan.json", state.get("draft_plan", {}))
    write_json("05_research_plan.json", state.get("research_plan", {}))
    write_json("06_research_results.json", state.get("research_results", []))
    write_json("07_research_pack.json", state.get("research_pack", {}))
    write_json("08_compiled.json", state.get("compiled", {}))
    write_json("09_audit_pack.json", state.get("audit_pack", {}))

    final_pack = dict(state.get("final_draft", {}))
    (case_dir / "10_draft.txt").write_text(str(final_pack.get("draft_text", "")), encoding="utf-8")
    (case_dir / "11_one_page_brief.txt").write_text(str(final_pack.get("one_page_brief", "")), encoding="utf-8")
    (case_dir / "12_annexures.txt").write_text(
        _render_bullets(final_pack.get("annexures", []) or []) + "\n", encoding="utf-8"
    )
    (case_dir / "13_compliance_checklist.txt").write_text(
        _render_bullets(final_pack.get("compliance_checklist", []) or []) + "\n", encoding="utf-8"
    )
    (case_dir / "14_next_steps.txt").write_text(
        _render_bullets(final_pack.get("next_steps", []) or []) + "\n", encoding="utf-8"
    )

    store_put(runtime, ("cases", case_id), "delivery", {"case_dir": str(case_dir)})
    return {"output_dir": str(case_dir), "log": [f"delivered to {case_dir}"]}


# -----------------------------
# 12) Build LangGraph workflow
# -----------------------------

builder = StateGraph(PlaintState, context_schema=Ctx)

builder.add_node("init", node_init)
builder.add_node("router", node_intake_router)
builder.add_node("ris_builder", node_ris_builder)
builder.add_node("validator", node_validator)
builder.add_node("question_generator", node_question_generator)
builder.add_node("wait_for_user", node_wait_for_user)
builder.add_node("answer_extractor", node_answer_extractor)
builder.add_node("draft_plan", node_draft_plan)
builder.add_node("research_plan", node_research_plan)
builder.add_node("research_worker", node_research_worker)
builder.add_node("research_reduce", node_research_reduce, defer=True)
builder.add_node("compiler", node_compiler)
builder.add_node("assembler", node_assembler)
builder.add_node("formatter", node_formatter)
builder.add_node("final_review", node_final_review)
builder.add_node("bump_revision", node_bump_revision)
builder.add_node("deliver", node_deliver)

builder.add_edge(START, "init")
builder.add_edge("init", "router")
builder.add_edge("router", "ris_builder")
builder.add_edge("ris_builder", "validator")
builder.add_conditional_edges(
    "validator",
    route_after_validator,
    {"question_generator": "question_generator", "draft_plan": "draft_plan"},
)
builder.add_edge("question_generator", "wait_for_user")
builder.add_edge("wait_for_user", "answer_extractor")
builder.add_edge("answer_extractor", "validator")
builder.add_edge("draft_plan", "research_plan")

builder.add_conditional_edges("research_plan", route_to_research_workers)
builder.add_edge("research_worker", "research_reduce")
builder.add_edge("research_reduce", "compiler")
builder.add_edge("compiler", "assembler")
builder.add_edge("assembler", "formatter")
builder.add_edge("formatter", "final_review")
builder.add_conditional_edges(
    "final_review",
    route_after_final_review,
    {"deliver": "deliver", "compiler": "bump_revision", "final_review": "final_review"},
)
builder.add_edge("bump_revision", "compiler")
builder.add_edge("deliver", END)


# -----------------------------
# 13) Runner (handles interrupts)
# -----------------------------


DEMO_ANSWERS: list[str] = [
    # Batch 1: first 6 mandatory keys (+ proceed_with_blanks asked by the system)
    "\n".join([
        "court_name: City Civil Court at Bengaluru",
        "plaintiff: Mr. A, adult Indian citizen",
        "defendant: M/s B Pvt Ltd, company incorporated under Companies Act",
        "plaintiff_address: Bengaluru, Karnataka (service address)",
        "defendant_address: Bengaluru, Karnataka (registered office/service)",
        "facts_timeline: 2024-01-10 contract executed at Bengaluru; 2024-02-05 invoice for INR 5,00,000; 2024-03-01 reminder; non-payment continues.",
        "proceed_with_blanks: no",
    ]),
    # Batch 2: next mandatory keys
    "\n".join([
        "cause_of_action: Defendant failed to pay the invoice amount despite contractual obligation and repeated demands.",
        "jurisdiction_facts: Cause of action arose in Bengaluru; contract executed/performed in Bengaluru; defendant carries on business in Bengaluru.",
        "reliefs: Decree for INR 5,00,000 with interest; costs; any other relief deemed fit.",
        "interim_relief_needed: no",
        "valuation: INR 5,00,000",
        "court_fee: TO BE COMPUTED AS PER APPLICABLE COURT FEE ACT (TO VERIFY)",
        "proceed_with_blanks: no",
    ]),
    # Batch 3: remaining mandatory keys
    "\n".join([
        "limitation: Within limitation based on 2024 cause of action (TO VERIFY).",
        "documents: Service contract dated 2024-01-10; Invoice dated 2024-02-05; Reminder email dated 2024-03-01.",
        "is_commercial_dispute: no",
        "proceed_with_blanks: no",
    ]),
    # Final review
    "approved: yes",
]


def print_interrupt_prompt(prompt: dict) -> None:
    title(str(prompt.get("title", "INTERRUPT")))
    if prompt.get("questions"):
        print("\nAnswer these:")
        for q in prompt["questions"]:
            key = q.get("key")
            question = q.get("question")
            example = q.get("example")
            required = q.get("required", True)
            suffix = " (required)" if required else " (optional)"
            print(f"- {key}{suffix}: {question}")
            if example:
                print(f"  example: {example}")
    if prompt.get("missing_required_fields"):
        print("\nMissing required fields (blockers):")
        for m in prompt["missing_required_fields"]:
            print("- " + str(m))
    if prompt.get("risk_flags"):
        print("\nRisk flags:")
        for r in prompt["risk_flags"]:
            print("- " + str(r))
    if prompt.get("answer_format"):
        print("\nAnswer format:")
        print(str(prompt["answer_format"]))
    if prompt.get("one_page_brief"):
        print("\nOne-page brief:")
        print(str(prompt["one_page_brief"]))
    if prompt.get("missing_inputs"):
        print("\nMissing inputs (placeholders):")
        for m in prompt["missing_inputs"]:
            print("- " + str(m))
    if prompt.get("draft_preview"):
        print("\nDraft preview:")
        print(str(prompt["draft_preview"]))
    if prompt.get("instructions"):
        print("\nInstructions:")
        print(str(prompt["instructions"]))
    if prompt.get("note"):
        print("\nNote:")
        print(str(prompt["note"]))


def run(*, demo: bool, mock: bool, thread_id: str | None, case_id: str | None, resume_answer: str | None) -> None:
    global ENGINE

    if case_id is None:
        case_id = str(uuid.uuid4())[:8]
    if thread_id is None:
        thread_id = f"plaint-{case_id}"

    config = {"configurable": {"thread_id": thread_id}}
    context = Ctx(case_id=case_id, user_id="u1")

    title("Deep Research: Litigation Drafting → Civil Pleadings → PLAINT")
    show("case_id", case_id)
    show("thread_id", thread_id)
    show("artifacts_dir", str(ARTIFACTS_DIR))

    try:
        from langgraph.cache.sqlite import SqliteCache  # type: ignore
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
        from langgraph.store.sqlite import SqliteStore  # type: ignore
    except Exception as e:  # pragma: no cover
        title("Missing dependencies for SQLite persistence")
        print(
            wrap(
                """
                This script uses SQLite-backed persistence (checkpointer/store/cache) so it can pause for HITL interrupts
                and resume later. Those SQLite components require optional dependencies that are usually installed via `uv`.

                Fix:
                - Run via `uv run library_mastery/deep_research/drafting_deepresearch2.py ...`, or
                - Install the repo's locked dependencies in an environment where `langgraph` deps are available.
                """
            )
        )
        raise SystemExit(1) from e

    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        with SqliteStore.from_conn_string(str(STORE_DB)) as store:
            cache = SqliteCache(path=str(CACHE_DB)) if not mock else None
            ENGINE = LLMEngine(model=ANSWER_MODEL, cache=cache, mock=mock)

            graph = builder.compile(checkpointer=checkpointer, store=store)

            # If resuming, try to resume from an outstanding interrupt.
            if resume_answer is not None:
                state_in: object = Command(resume=resume_answer)
            else:
                try:
                    snap = graph.get_state(config)
                except Exception:
                    snap = None
                if snap is not None and getattr(snap, "interrupts", None):
                    # Interactive resume: show pending interrupt prompt
                    intr = snap.interrupts[0]
                    prompt = intr.value
                    if not isinstance(prompt, dict):
                        prompt = {"title": "INTERRUPT", "note": str(prompt)}
                    step("Found a pending interrupt for this thread_id. Answer to resume.")
                    print_interrupt_prompt(prompt)
                    ans = read_multiline()
                    state_in = Command(resume=ans)
                else:
                    state_in = {}
            demo_answers = list(DEMO_ANSWERS)

            while True:
                interrupted = False
                for chunk in graph.stream(state_in, config, context=context, stream_mode="updates"):
                    if "__interrupt__" in chunk:
                        interrupted = True
                        intr = chunk["__interrupt__"][0]
                        prompt = intr.value
                        if not isinstance(prompt, dict):
                            prompt = {"title": "INTERRUPT", "note": str(prompt)}

                        print_interrupt_prompt(prompt)

                        if demo:
                            if demo_answers:
                                answer = demo_answers.pop(0)
                            else:
                                title_text = str(prompt.get("title", "")).lower()
                                if "final review" in title_text:
                                    answer = "approved: yes"
                                else:
                                    answer = "proceed_with_blanks: yes"
                            step("Demo answer used")
                            print(answer)
                        else:
                            answer = read_multiline()

                        state_in = Command(resume=answer)
                        break

                    # Show node updates (compact)
                    if isinstance(chunk, dict) and len(chunk) == 1:
                        node_name = next(iter(chunk.keys()))
                        payload = chunk[node_name]
                        step(f"node: {node_name}")
                        if node_name in {"init"}:
                            show("meta", payload)
                        elif node_name in {"answer_extractor"} and isinstance(payload, dict):
                            show("case_file_keys", sorted(list((payload.get("case_file") or {}).keys())))
                        elif node_name in {"deliver"} and isinstance(payload, dict):
                            show("output_dir", payload.get("output_dir"))
                        else:
                            show("update", payload)
                    else:
                        show("update", chunk)

                if not interrupted:
                    break

            snap = graph.get_state(config)
            step("DONE")
            show("output_dir", snap.values.get("output_dir"))
            print("\nOpen the folder above to see the full delivery pack.")


# -----------------------------
# 14) CLI
# -----------------------------

if __name__ == "__main__":
    demo = "--demo" in sys.argv
    mock = "--mock" in sys.argv

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

    if not mock:
        # Real LLM mode requires API key.
        require_env("OPENAI_API_KEY")

    run(demo=demo, mock=mock, thread_id=thread_id, case_id=case_id, resume_answer=resume_answer)
