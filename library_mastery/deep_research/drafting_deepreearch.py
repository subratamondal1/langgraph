"""
drafting_deepreearch.py (Deep Research • Litigation Drafting • Civil Pleadings • PLAINT)

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

This script is a LEARNING PROJECT.
It is NOT legal advice. Always get a qualified advocate to review before filing.

Run (interactive):
  uv run library_mastery/deep_research/drafting_deepreearch.py

Resume an interrupted run:
  uv run library_mastery/deep_research/drafting_deepreearch.py --thread "<thread_id>" --case "<case_id>"

Resume by providing an answer directly:
  uv run library_mastery/deep_research/drafting_deepreearch.py --thread "<thread_id>" --case "<case_id>" --resume "<answer>"

Run (demo auto-answers, still uses LLM unless --mock):
  uv run library_mastery/deep_research/drafting_deepreearch.py --demo

Offline mode (no API key; uses simple mock agents):
  uv run library_mastery/deep_research/drafting_deepreearch.py --mock
"""

import hashlib
import json
import os
import sys
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Annotated, Optional, TypedDict

from dotenv import load_dotenv

load_dotenv()
# -----------------------------
# 0) Bootstrapping for monorepo
# -----------------------------


def bootstrap_langgraph_namespace() -> None:
    """
    This repo is a monorepo; `langgraph` is built from multiple `libs/*` folders.
    If you run this script from the repo checkout, we add those libs to sys.path.
    """
    # file: library_mastery/deep_research/drafting_deepreearch.py
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


from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.cache.sqlite import SqliteCache
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.store.sqlite import SqliteStore
from langgraph.types import Command, interrupt
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
    - Do not hallucinate facts. If missing, ask the user OR mark [BLANK: ...] and ask for confirmation.
    - Pleadings must be MATERIAL FACTS (no evidence, no arguments) in numbered paragraphs.
    - The goal is a filing-ready PLAINT skeleton with mandatory particulars + compliance checklist.
    - If uncertain about law/procedure, label as "TO VERIFY" instead of inventing citations.
    """
)


INTAKE_QUESTIONER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior chamber lawyer taking instructions for drafting a civil PLAINT.
    TASK: Generate the NEXT SMALL BATCH of intake questions (ordered, not random).

    IMPORTANT:
    - Ask only for missing information for this batch.
    - Keep questions short and practical.
    - Provide a key for each question so the user can answer in key:value lines.
    - After questions, include an "answer_format" instruction.
    """
)


INTAKE_EXTRACTOR_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Case file clerk.
    TASK: Extract structured facts from the user's answer into the requested keys only.

    IMPORTANT:
    - Do not guess. If not present, omit the key.
    - If user explicitly says unknown/blank, record it in `blanks`.
    - Output must be VALID JSON matching the schema.
    """
)


PLANNER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior associate.
    TASK: Create an issue-wise plan + PLAINT outline (mandatory headings first).
    - Also list any critical missing facts that should be collected before drafting.
    - Output must be VALID JSON matching the schema.
    """
)


RESEARCH_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Research associate.
    TASK: Produce an ISSUE-WISE research plan for a civil PLAINT in India.
    - Include relevant statutory hooks / procedural points as "TO VERIFY".
    - Do NOT fabricate case citations as if verified.
    - Output must be VALID JSON matching the schema.
    """
)


DRAFTER_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Senior drafting counsel.
    TASK: Draft a civil PLAINT (court-style) using the provided case file + plan + research notes.

    STRICT STYLE RULES
    - Use numbered paragraphs for material facts.
    - Do NOT include evidence (no emails, screenshots) as proof narration; only mention documents as annexures list.
    - Include mandatory particulars: parties, jurisdiction, cause of action, relief, valuation/court fee, limitation, verification, documents list.
    - If a mandatory field is missing, insert [BLANK: ...] exactly and also list it under blanks.
    - Output must be VALID JSON matching the schema (draft, brief, blanks, annexures, next_steps).
    """
)


COMPLIANCE_SYSTEM = wrap(
    f"""
    {BASE_SYSTEM_PROMPT}

    ROLE: Filing clerk / compliance checker.
    TASK: Check the draft against a civil PLAINT checklist and the case file.
    - Identify missing mandatory particulars.
    - If missing items can be answered by the user, provide a short "fix_questions" list.
    - Output must be VALID JSON matching the schema.
    """
)


# -----------------------------
# 7) Pydantic schemas (structured outputs)
# -----------------------------


class Question(BaseModel):
    key: str = Field(description="Machine key the user should answer for.")
    question: str = Field(description="The question to ask the user.")
    required: bool = Field(default=True)
    example: Optional[str] = Field(default=None)


class IntakeBatchOut(BaseModel):
    batch_name: str
    questions: list[Question]
    answer_format: str


class IntakeExtractOut(BaseModel):
    updates: dict[str, str] = Field(default_factory=dict)
    blanks: list[str] = Field(default_factory=list)
    what_i_understood: str = Field(default="")
    still_missing: list[str] = Field(default_factory=list)


class PlanOut(BaseModel):
    issues: list[str]
    outline: list[str]
    critical_missing_facts: list[str] = Field(default_factory=list)


class ResearchTask(BaseModel):
    issue: str
    to_verify: list[str]


class ResearchOut(BaseModel):
    tasks: list[ResearchTask]


class DraftOut(BaseModel):
    draft_text: str
    one_page_brief: str
    blanks: list[str]
    annexures: list[str]
    next_steps: list[str]


class ComplianceOut(BaseModel):
    ok: bool
    missing_items: list[str] = Field(default_factory=list)
    fix_questions: list[Question] = Field(default_factory=list)


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

    case_file: dict[str, str]
    blanks: list[str]

    qa_log: Annotated[list[dict], append_list]
    log: Annotated[list[str], append_str_list]

    plan: dict
    research: dict

    draft_pack: dict
    compliance: dict

    output_dir: str


# -----------------------------
# 9) Intake definition (plaint-only)
# -----------------------------

PLAIN_REQUIRED_FIELDS: list[tuple[str, str]] = [
    ("court_name", "Which court will the plaint be filed in? (name + place)"),
    ("plaintiff", "Plaintiff name + description/capacity"),
    ("defendant", "Defendant name + description/capacity"),
    ("plaintiff_address", "Plaintiff address (service address)"),
    ("defendant_address", "Defendant address (service address)"),
    ("facts_timeline", "Chronological material facts timeline with dates/places (numbered or dated lines)"),
    ("cause_of_action", "Cause of action: what legal wrong and when it arose"),
    ("jurisdiction_facts", "Territorial + pecuniary jurisdiction facts (why this court)"),
    ("reliefs", "Reliefs/prayers (main + interim if any)"),
    ("valuation", "Valuation for jurisdiction"),
    ("court_fee", "Court fee position (if known; else mark blank)"),
    ("limitation", "Limitation/delay position"),
    ("documents", "List of documents to annex (even if not yet available)"),
]


INTAKE_BATCHES: list[tuple[str, list[str]]] = [
    ("Court + Parties", ["court_name", "plaintiff", "defendant", "plaintiff_address", "defendant_address"]),
    ("Facts timeline", ["facts_timeline"]),
    ("Cause of action", ["cause_of_action"]),
    ("Jurisdiction", ["jurisdiction_facts"]),
    ("Reliefs", ["reliefs"]),
    ("Valuation + court fee", ["valuation", "court_fee"]),
    ("Documents", ["documents"]),
    ("Limitation", ["limitation"]),
]


def is_missing(case_file: dict[str, str], key: str) -> bool:
    value = (case_file.get(key) or "").strip()
    if not value:
        return True
    if value.strip().lower() in {"[blank]", "blank", "unknown"}:
        return True
    # If the user explicitly confirmed proceeding with blanks, we mark them as [BLANK_OK: ...]
    if value.strip().startswith("[BLANK_OK:"):
        return False
    if value.strip().startswith("[BLANK:"):
        return True
    return False


def missing_required(case_file: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key, desc in PLAIN_REQUIRED_FIELDS:
        if is_missing(case_file, key):
            missing.append(f"{key} — {desc}")
    return missing


def next_intake_batch(case_file: dict[str, str]) -> tuple[str, list[str]]:
    for batch_name, keys in INTAKE_BATCHES:
        missing_keys = [k for k in keys if is_missing(case_file, k)]
        if missing_keys:
            return batch_name, missing_keys
    return "", []


# -----------------------------
# 10) LLM wrapper (with SQLite cache)
# -----------------------------


class LLMEngine:
    def __init__(self, *, model: str, cache: Optional[SqliteCache], mock: bool) -> None:
        self._model = model
        self._cache = cache
        self._mock = mock

        if not mock:
            require_env("OPENAI_API_KEY")

        self._llm: object | None = None
        if not mock:
            try:
                from langchain_openai import ChatOpenAI  # type: ignore
            except Exception as e:  # pragma: no cover
                raise RuntimeError(
                    "Missing dependency: langchain-openai. Install it to use real LLM mode, "
                    "or run with --mock for offline mode."
                ) from e

            self._llm = ChatOpenAI(model=model, temperature=0)

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

        structured = self._llm.with_structured_output(schema)  # type: ignore[attr-defined]
        out = structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])

        if self._cache is not None:
            self._cache.set({(ns, cache_key): (out.model_dump(), 24 * 3600)})

        return out

    def _mock_structured(self, *, agent: str, user: str, schema: type[BaseModel]) -> BaseModel:
        """
        Offline mode: simple deterministic stubs so the graph can run end-to-end.
        This is intentionally basic; real behavior happens with the LLM.
        """

        def parse_json_list(after_marker: str) -> list[str]:
            if after_marker not in user:
                return []
            tail = user.split(after_marker, 1)[1]
            # Grab first JSON list in the tail
            start = tail.find("[")
            end = tail.find("]")
            if start == -1 or end == -1 or end < start:
                return []
            try:
                return json.loads(tail[start : end + 1])
            except Exception:
                return []

        def parse_user_answer() -> str:
            if "User answer:" not in user:
                return ""
            return user.split("User answer:", 1)[1].strip()

        if schema is IntakeBatchOut:
            missing_desc = parse_json_list("Missing keys for this batch:")
            questions: list[Question] = []
            for item in missing_desc:
                key = item.split(" — ", 1)[0].strip()
                questions.append(Question(key=key, question=f"Provide {key}.", required=True, example=None))
            return IntakeBatchOut(
                batch_name="Mock intake batch",
                questions=questions,
                answer_format="Answer as key: value lines (end with blank line).",
            )

        if schema is IntakeExtractOut:
            expected = parse_json_list("Expected keys (extract only these keys if present):")
            answer_text = parse_user_answer()

            updates: dict[str, str] = {}
            blanks: list[str] = []

            if len(expected) == 1:
                # Freeform answer goes into the single expected key.
                updates[expected[0]] = answer_text
            else:
                # Parse key:value lines, keep only expected keys.
                for line in answer_text.splitlines():
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if k in expected:
                        updates[k] = v
                        if v.lower() in {"blank", "unknown", "[blank]"}:
                            blanks.append(k)

            understood = "(mock) extracted: " + ", ".join(sorted(list(updates.keys())))
            still_missing = [k for k in expected if k not in updates]
            return IntakeExtractOut(
                updates=updates, blanks=blanks, what_i_understood=understood, still_missing=still_missing
            )
        if schema is PlanOut:
            return PlanOut(
                issues=["Maintainability", "Jurisdiction", "Limitation", "Merits", "Reliefs"],
                outline=["Cause title", "Facts", "Cause of action", "Jurisdiction", "Prayer", "Verification"],
                critical_missing_facts=[],
            )
        if schema is ResearchOut:
            return ResearchOut(
                tasks=[ResearchTask(issue="Jurisdiction", to_verify=["CPC territorial/pecuniary rules (TO VERIFY)"])]
            )
        if schema is DraftOut:
            return DraftOut(
                draft_text="(mock) PLAINT DRAFT\n[BLANK: replace with LLM output]\n",
                one_page_brief="(mock) brief\n",
                blanks=["replace with LLM output"],
                annexures=[],
                next_steps=["(mock) run with real LLM for full draft"],
            )
        if schema is ComplianceOut:
            return ComplianceOut(ok=True, missing_items=[], fix_questions=[])

        return schema()  # type: ignore[call-arg]


ENGINE: LLMEngine | None = None


# -----------------------------
# 11) Agents as LangGraph nodes
# -----------------------------


def node_init(_: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    # Create a persistent namespace for this case in the SQLite store.
    runtime.store.put(
        ("cases", runtime.context.case_id),
        "meta",
        {"category": CATEGORY, "subcategory": SUBCATEGORY, "doc_type": DOC_TYPE},
    )  # type: ignore[union-attr]
    return {
        "category": CATEGORY,
        "subcategory": SUBCATEGORY,
        "doc_type": DOC_TYPE,
        "case_file": {},
        "blanks": [],
        "qa_log": [],
        "log": [f"init(case_id={runtime.context.case_id})"],
    }


def node_intake(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    case_file = dict(state.get("case_file", {}))
    blanks = list(state.get("blanks", []))

    batch_name, missing_keys = next_intake_batch(case_file)
    if not missing_keys:
        return {"case_file": case_file, "blanks": blanks, "log": ["intake complete"]}

    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    required_map = {k: desc for k, desc in PLAIN_REQUIRED_FIELDS}
    missing_desc = [f"{k} — {required_map.get(k, '')}".strip() for k in missing_keys]

    # 1) LLM asks the next batch questions (system prompt + user prompt).
    questions_user_prompt = wrap(
        f"""
        We are drafting a CIVIL PLAINT in India.

        Current case_file (JSON):
        {json.dumps(case_file, indent=2)}

        Next intake batch: {batch_name}
        Missing keys for this batch:
        {json.dumps(missing_desc, indent=2)}

        Produce questions ONLY for these missing keys.
        """
    )
    batch_out = llm.call_structured(
        agent="intake_questioner",
        system=INTAKE_QUESTIONER_SYSTEM,
        user=questions_user_prompt,
        schema=IntakeBatchOut,
    )

    prompt = {
        "title": f"Intake — {batch_out.batch_name}",
        "category": CATEGORY,
        "subcategory": SUBCATEGORY,
        "type": DOC_TYPE,
        "questions": [q.model_dump() for q in batch_out.questions],
        "answer_format": batch_out.answer_format,
        "note": "Answer in key:value lines. If unknown, write [BLANK]. End with an empty line.",
    }

    answer = interrupt(prompt)

    # 2) LLM extracts structured updates from the user's answer.
    extract_user_prompt = wrap(
        f"""
        We are drafting a CIVIL PLAINT.

        Expected keys (extract only these keys if present):
        {json.dumps(missing_keys, indent=2)}

        Existing case_file (JSON):
        {json.dumps(case_file, indent=2)}

        Return updates for the expected keys only.

        User answer:
        {str(answer)}
        """
    )
    extracted = llm.call_structured(
        agent="intake_extractor",
        system=INTAKE_EXTRACTOR_SYSTEM,
        user=extract_user_prompt,
        schema=IntakeExtractOut,
    )

    # Merge updates
    for k, v in extracted.updates.items():
        if isinstance(v, str) and v.strip():
            case_file[k] = v.strip()
    for b in extracted.blanks:
        if b not in blanks:
            blanks.append(b)

    # Persist case_file after every batch (durable).
    runtime.store.put(("cases", runtime.context.case_id), "case_file", case_file)  # type: ignore[union-attr]

    qa_entry = {
        "batch": batch_name,
        "questions": [q.model_dump() for q in batch_out.questions],
        "answer": str(answer),
        "updates": extracted.updates,
        "blanks": extracted.blanks,
        "what_i_understood": extracted.what_i_understood,
    }

    return {
        "case_file": case_file,
        "blanks": blanks,
        "qa_log": [qa_entry],
        "log": [f"intake({batch_name}) updated_keys={list(extracted.updates.keys())}"],
    }


def node_minimum_gate(state: PlaintState) -> PlaintState:
    case_file = dict(state.get("case_file", {}))
    blanks = list(state.get("blanks", []))
    missing = missing_required(case_file)
    ok = len(missing) == 0

    if ok:
        return {"log": ["minimum gate: OK"]}

    prompt = {
        "title": "Minimum Viable Case File (Gate)",
        "missing": missing,
        "instructions": wrap(
            """
            We are missing essential facts to draft a plaint.

            Reply with key:value lines to fill missing items (you can fill multiple at once).
            If you truly don't know, write [BLANK] — but confirm you want to proceed with blanks by adding:
              proceed_with_blanks: yes
            """
        ),
    }

    answer = interrupt(prompt)
    text = str(answer).strip()

    # Simple parse: key: value lines.
    updates: dict[str, str] = {}
    proceed_with_blanks = False
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k == "proceed_with_blanks" and v.lower() in {"y", "yes", "true"}:
            proceed_with_blanks = True
        else:
            updates[k] = v

    for k, v in updates.items():
        case_file[k] = v

    # If user confirmed proceed_with_blanks, fill remaining missing keys with [BLANK: ...]
    if proceed_with_blanks:
        for entry in missing_required(case_file):
            key, desc = entry.split(" — ", 1)
            if is_missing(case_file, key):
                case_file[key] = f"[BLANK_OK: {desc}]"
                if key not in blanks:
                    blanks.append(key)

    return {"case_file": case_file, "blanks": blanks, "log": ["minimum gate: not OK -> user provided updates"]}


def route_after_minimum_gate(state: PlaintState) -> str:
    missing = missing_required(dict(state.get("case_file", {})))
    return "plan" if len(missing) == 0 else "intake"


def node_plan(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    case_file = dict(state.get("case_file", {}))
    user_prompt = wrap(
        f"""
        Category: {CATEGORY}
        Subcategory: {SUBCATEGORY}
        Type: {DOC_TYPE}

        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Create:
        - issues (list)
        - plaint outline (list of headings)
        - critical_missing_facts (list)
        """
    )
    plan_out = llm.call_structured(agent="planner", system=PLANNER_SYSTEM, user=user_prompt, schema=PlanOut)
    runtime.store.put(("cases", runtime.context.case_id), "plan", plan_out.model_dump())  # type: ignore[union-attr]
    return {"plan": plan_out.model_dump(), "log": ["plan created"]}


def node_research(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    plan = dict(state.get("plan", {}))
    case_file = dict(state.get("case_file", {}))
    user_prompt = wrap(
        f"""
        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Plan issues (JSON):
        {json.dumps(plan.get("issues", []), indent=2)}

        Produce an issue-wise research plan as TO VERIFY notes.
        """
    )
    research_out = llm.call_structured(agent="researcher", system=RESEARCH_SYSTEM, user=user_prompt, schema=ResearchOut)
    runtime.store.put(("cases", runtime.context.case_id), "research", research_out.model_dump())  # type: ignore[union-attr]
    return {"research": research_out.model_dump(), "log": ["research plan created"]}


def node_draft(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    case_file = dict(state.get("case_file", {}))
    plan = dict(state.get("plan", {}))
    research = dict(state.get("research", {}))
    blanks = list(state.get("blanks", []))

    user_prompt = wrap(
        f"""
        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Plan (JSON):
        {json.dumps(plan, indent=2)}

        Research notes (JSON):
        {json.dumps(research, indent=2)}

        Draft a filing-ready PLAINT (template) and include blanks list.
        """
    )
    draft_out = llm.call_structured(agent="drafter", system=DRAFTER_SYSTEM, user=user_prompt, schema=DraftOut)

    # Merge blanks
    for b in draft_out.blanks:
        if b not in blanks:
            blanks.append(b)

    runtime.store.put(("cases", runtime.context.case_id), "draft_pack", draft_out.model_dump())  # type: ignore[union-attr]
    return {"draft_pack": draft_out.model_dump(), "blanks": blanks, "log": ["draft created"]}


def node_compliance(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    if ENGINE is None:
        raise RuntimeError("LLM engine not initialized. Run() must set ENGINE before executing the graph.")
    llm = ENGINE

    case_file = dict(state.get("case_file", {}))
    draft_pack = dict(state.get("draft_pack", {}))
    user_prompt = wrap(
        f"""
        Check this civil PLAINT draft for mandatory particulars.

        Case file (JSON):
        {json.dumps(case_file, indent=2)}

        Draft text:
        {draft_pack.get("draft_text", "")}
        """
    )
    comp = llm.call_structured(agent="compliance", system=COMPLIANCE_SYSTEM, user=user_prompt, schema=ComplianceOut)
    runtime.store.put(("cases", runtime.context.case_id), "compliance", comp.model_dump())  # type: ignore[union-attr]
    return {"compliance": comp.model_dump(), "log": [f"compliance ok={comp.ok} missing={len(comp.missing_items)}"]}


def route_after_compliance(state: PlaintState) -> str:
    comp = dict(state.get("compliance", {}))
    ok = bool(comp.get("ok"))
    return "deliver" if ok else "fix_missing"


def node_fix_missing(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    comp = dict(state.get("compliance", {}))
    fix_qs = comp.get("fix_questions", []) or []

    if not fix_qs:
        # If the compliance agent did not give structured fix questions, fall back to gate.
        return {"log": ["compliance missing but no fix_questions -> return to intake"]}

    prompt = {
        "title": "Compliance fixes needed (answer to proceed)",
        "questions": fix_qs,
        "note": "Answer in key:value lines. End with an empty line.",
    }
    answer = interrupt(prompt)
    text = str(answer).strip()

    updates: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        updates[k.strip()] = v.strip()

    case_file = dict(state.get("case_file", {}))
    case_file.update({k: v for k, v in updates.items() if v})
    runtime.store.put(("cases", runtime.context.case_id), "case_file", case_file)  # type: ignore[union-attr]
    return {"case_file": case_file, "log": ["applied compliance fixes -> redraft"]}


def route_after_fix_missing(_: PlaintState) -> str:
    return "draft"


def node_deliver(state: PlaintState, runtime: Runtime[Ctx]) -> PlaintState:
    case_id = runtime.context.case_id
    case_dir = ARTIFACTS_DIR / f"case_{case_id}"
    case_dir.mkdir(exist_ok=True)

    case_file = dict(state.get("case_file", {}))
    plan = dict(state.get("plan", {}))
    research = dict(state.get("research", {}))
    draft_pack = dict(state.get("draft_pack", {}))
    comp = dict(state.get("compliance", {}))
    blanks = list(state.get("blanks", []))

    (case_dir / "00_case_file.json").write_text(json.dumps(case_file, indent=2), encoding="utf-8")
    (case_dir / "01_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (case_dir / "02_research.json").write_text(json.dumps(research, indent=2), encoding="utf-8")

    (case_dir / "03_draft.txt").write_text(str(draft_pack.get("draft_text", "")), encoding="utf-8")
    (case_dir / "04_one_page_brief.txt").write_text(str(draft_pack.get("one_page_brief", "")), encoding="utf-8")

    (case_dir / "05_blanks_and_assumptions.txt").write_text(
        "\n".join([f"- {b}" for b in blanks]).strip() + "\n", encoding="utf-8"
    )
    (case_dir / "06_annexures.txt").write_text(
        "\n".join([f"- {a}" for a in draft_pack.get("annexures", [])]).strip() + "\n", encoding="utf-8"
    )

    checklist_lines: list[str] = []
    checklist_lines.append("PLAINT COMPLIANCE CHECKLIST (from agent)")
    checklist_lines.append(f"- ok: {comp.get('ok')}")
    for item in comp.get("missing_items", []) or []:
        checklist_lines.append(f"- MISSING: {item}")
    (case_dir / "07_compliance_checklist.txt").write_text("\n".join(checklist_lines).strip() + "\n", encoding="utf-8")

    (case_dir / "08_next_steps.txt").write_text(
        "\n".join([f"- {x}" for x in draft_pack.get("next_steps", [])]).strip() + "\n", encoding="utf-8"
    )

    # Store delivery pointer
    runtime.store.put(("cases", case_id), "delivery", {"case_dir": str(case_dir)})  # type: ignore[union-attr]

    return {"output_dir": str(case_dir), "log": [f"delivered to {case_dir}"]}


# -----------------------------
# 12) Build LangGraph workflow
# -----------------------------

builder = StateGraph(PlaintState, context_schema=Ctx)

builder.add_node("init", node_init)
builder.add_node("intake", node_intake)
builder.add_node("minimum_gate", node_minimum_gate)
builder.add_node("plan", node_plan)
builder.add_node("research", node_research)
builder.add_node("draft", node_draft)
builder.add_node("compliance", node_compliance)
builder.add_node("fix_missing", node_fix_missing)
builder.add_node("deliver", node_deliver)

builder.add_edge(START, "init")
builder.add_edge("init", "intake")
builder.add_edge("intake", "minimum_gate")
builder.add_conditional_edges("minimum_gate", route_after_minimum_gate, {"intake": "intake", "plan": "plan"})
builder.add_edge("plan", "research")
builder.add_edge("research", "draft")
builder.add_edge("draft", "compliance")
builder.add_conditional_edges(
    "compliance", route_after_compliance, {"deliver": "deliver", "fix_missing": "fix_missing"}
)
builder.add_conditional_edges("fix_missing", route_after_fix_missing, {"draft": "draft"})
builder.add_edge("deliver", END)


# -----------------------------
# 13) Runner (handles interrupts)
# -----------------------------


DEMO_ANSWERS: list[str] = [
    # Batch 1: court + parties
    "\n".join([
        "court_name: City Civil Court at Bengaluru",
        "plaintiff: Mr. A, adult Indian citizen",
        "defendant: M/s B Pvt Ltd, company incorporated under Companies Act",
        "plaintiff_address: Bengaluru, Karnataka (service address)",
        "defendant_address: Bengaluru, Karnataka (registered office/service)",
    ]),
    # Batch 2: facts
    "\n".join([
        "2024-01-10: Service contract executed at Bengaluru.",
        "2024-02-05: Invoice raised for INR 5,00,000 payable within 15 days.",
        "2024-03-01: Reminder issued; no payment received.",
    ]),
    # Batch 3: cause
    "Defendant failed to pay the invoice amount despite contractual obligation and repeated demands.",
    # Batch 4: jurisdiction
    "Cause of action arose in Bengaluru; contract executed/performed in Bengaluru; defendant carries on business in Bengaluru.",
    # Batch 5: reliefs
    "\n".join([
        "Decree for INR 5,00,000 with interest.",
        "Costs of the suit.",
        "Any other relief deemed fit.",
    ]),
    # Batch 6: valuation + court fee
    "\n".join([
        "valuation: INR 5,00,000",
        "court_fee: TO BE COMPUTED AS PER APPLICABLE COURT FEE ACT (BLANK)",
    ]),
    # Batch 7: documents
    "\n".join(["Service contract dated 2024-01-10", "Invoice dated 2024-02-05", "Reminder email dated 2024-03-01"]),
    # Batch 8: limitation
    "Within limitation as cause of action arose in 2024.",
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
    if prompt.get("missing"):
        print("\nMissing items:")
        for m in prompt["missing"]:
            print("- " + str(m))
    if prompt.get("answer_format"):
        print("\nAnswer format:")
        print(str(prompt["answer_format"]))
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

    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        with SqliteStore.from_conn_string(str(STORE_DB)) as store:
            cache = SqliteCache(path=str(CACHE_DB))
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
                    state_in = {"case_file": {}, "qa_log": [], "log": [], "blanks": []}
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
                            if isinstance(prompt, dict) and prompt.get("missing"):
                                # Minimum gate: allow continuing with blanks so the demo completes.
                                answer = "proceed_with_blanks: yes"
                            elif not demo_answers:
                                answer = "proceed_with_blanks: yes"
                            else:
                                answer = demo_answers.pop(0)
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
                        elif node_name in {"intake"} and isinstance(payload, dict):
                            # show last update summary if present
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
