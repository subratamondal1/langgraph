"""
drafting_deepreearch.py

Boss-level learning project (single file):
An end-to-end "Gated Drafting" agent for Indian litigation-style drafting.

This is NOT legal advice. It is an educational workflow + drafting template generator.
Always get a qualified advocate to review anything before filing/serving.

How to run (demo, no typing):
  ./.venv/bin/python drafting_deepreearch.py --demo

How to run (interactive):
  ./.venv/bin/python drafting_deepreearch.py

Pause + resume (to learn durability):
  ./.venv/bin/python drafting_deepreearch.py --pause
  ./.venv/bin/python drafting_deepreearch.py --thread "<thread_id>" --case "<case_id>" --resume "<answer>"

SQLite files are created in: ./_drafting_deepreearch_data/
"""

from dataclasses import dataclass
import json
from pathlib import Path
from pprint import pformat
import sys
import textwrap
import uuid
from typing import Annotated, TypedDict


# -----------------------
# 0) Tiny printing helpers
# -----------------------

def title(text: str) -> None:
    line = "=" * len(text)
    print("\n" + line)
    print(text)
    print(line)


def show(label: str, value: object) -> None:
    print(f"\n{label}:")
    print(pformat(value, width=100))


def step(text: str) -> None:
    print("\n--- " + text)


def wrap(text: str) -> str:
    return textwrap.dedent(text).strip()


# ---------------------------------------------
# 1) Bootstrap LangGraph from a monorepo checkout
# ---------------------------------------------

def bootstrap_langgraph_namespace() -> None:
    repo_root = Path(__file__).resolve().parent
    libs = [
        "libs/langgraph",
        "libs/checkpoint",
        "libs/prebuilt",
        "libs/checkpoint-sqlite",
        "libs/checkpoint-postgres",
    ]
    for rel in libs:
        path = repo_root / rel
        if path.exists():
            sys.path.insert(0, str(path))


bootstrap_langgraph_namespace()


# -------------------------
# 2) LangGraph core imports
# -------------------------

from langgraph.cache.sqlite import SqliteCache
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.store.sqlite import SqliteStore
from langgraph.types import Command, interrupt


# ----------------------------------------
# 3) Data directory (SQLite lives on disk)
# ----------------------------------------

DATA_DIR = Path(__file__).with_name("_drafting_deepreearch_data")
DATA_DIR.mkdir(exist_ok=True)

CHECKPOINT_DB = DATA_DIR / "checkpoints.db"
STORE_DB = DATA_DIR / "store.db"
CACHE_DB = DATA_DIR / "cache.db"


# ---------------------------------------
# 4) Reducers (merge rules for state keys)
# ---------------------------------------

def append_list(left: list[str], right: list[str] | None) -> list[str]:
    return left + (right or [])


# ----------------------------
# 5) State + Context (schemas)
# ----------------------------

@dataclass
class Ctx:
    user_id: str
    case_id: str


class DraftState(TypedDict, total=False):
    # Stage A (classification)
    document_type: str
    forum: str
    stage: str

    # Document-type mandatory particulars (collected in Stage D)
    # Civil plaint
    valuation: str
    court_fee: str
    nature_of_suit: str

    # Writ/SLP
    questions_of_law: str
    declarations: str
    interim_relief: str

    # Legal notice
    from_address: str
    to_address: str
    subject: str
    notice_deadline_days: str

    # Stage B (intake batches)
    intake_batch: int
    last_understood: str
    last_missing: list[str]

    client_name: str
    client_description: str
    opposite_party_name: str
    opposite_party_description: str
    special_status: str

    timeline: str
    grievance: str
    jurisdiction_facts: str
    reliefs: str
    documents: str
    prior_proceedings: str
    limitation: str

    # Stage C (minimum gate)
    minimum_gate_ok: bool
    minimum_missing: list[str]
    case_file_confirmed: bool

    # Stage D (plan)
    issues: list[str]
    outline: list[str]
    plan_confirmed: bool

    # Stage E (research)
    research_i: int
    research_notes: dict[str, str]

    # Stage F (compile)
    case_file: dict
    assumptions_or_blanks: list[str]

    # Stage G (draft)
    draft: str
    brief: str
    annexures: list[str]

    # Stage H (compliance)
    compliance_missing: list[str]
    needs_fix: bool

    # Stage I (delivery)
    next_steps: list[str]
    output_path: str

    # Always-on debug log
    log: Annotated[list[str], append_list]


# -------------------------------
# 6) "Forms" (what we ask users)
# -------------------------------

DOC_TYPE_OPTIONS = [
    ("civil_plaint", "Civil suit plaint (District Court / Civil Court)"),
    ("written_statement", "Written Statement (reply in a civil suit)"),
    ("legal_notice", "Legal Notice (pre-litigation)"),
    ("writ_petition", "Writ Petition (High Court / Supreme Court)"),
    ("slp", "SLP (Special Leave Petition) — Supreme Court"),
    ("bail", "Bail application (criminal)"),
    ("other", "Other (type your own)"),
]

FORUM_OPTIONS = [
    "District Court / Civil Court",
    "High Court",
    "Supreme Court",
    "Tribunal / Other",
]

STAGE_OPTIONS = [
    "Pre-litigation",
    "Filing",
    "Interim relief",
    "Appeal",
    "Execution",
    "Compliance",
]


INTAKE_BATCHES: dict[int, dict] = {
    1: {
        "title": "Parties & capacity",
        "required": ["client_name", "opposite_party_name"],
        "fields": [
            "client_name",
            "client_description",
            "opposite_party_name",
            "opposite_party_description",
            "special_status",
        ],
        "instructions": wrap(
            """
            Provide party names + short descriptions (capacity).

            Keep it simple. If you don't know a detail, write [BLANK].

            Answer format (key: value lines):
              client_name: ...
              client_description: ...
              opposite_party_name: ...
              opposite_party_description: ...
              special_status: minors/company/govt/firm/trust? (yes/no + details)
            """
        ),
    },
    2: {
        "title": "Facts and timeline (material facts only)",
        "required": ["timeline"],
        "freeform_key": "timeline",
        "instructions": wrap(
            """
            Paste a chronological timeline (material facts only, not evidence).

            Example:
              2024-01-10: Agreement executed at Bengaluru.
              2024-02-05: Invoice raised for INR 5,00,000.
              2024-03-01: Notice issued demanding payment within 15 days.
            """
        ),
    },
    3: {
        "title": "Cause of action / grievance",
        "required": ["grievance"],
        "freeform_key": "grievance",
        "instructions": wrap(
            """
            What is the legal wrong / grievance?
            4–8 lines, material facts only.

            Example:
              The opposite party failed to pay despite repeated demands,
              causing financial loss and breach of contractual obligations.
            """
        ),
    },
    4: {
        "title": "Forum & jurisdiction facts",
        "required": ["jurisdiction_facts"],
        "freeform_key": "jurisdiction_facts",
        "instructions": wrap(
            """
            Why does the chosen forum/court have jurisdiction?
            Mention: where events happened, where parties reside/carry on business,
            where contract was executed/performed, where property is located, etc.
            """
        ),
    },
    5: {
        "title": "Reliefs (what outcome you want)",
        "required": ["reliefs"],
        "freeform_key": "reliefs",
        "instructions": wrap(
            """
            List the reliefs you want (money / injunction / declaration / quashing / directions / bail etc).
            If you want interim relief, mention it clearly as "Interim relief".
            """
        ),
    },
    6: {
        "title": "Documents list (annexures you can attach)",
        "required": ["documents"],
        "freeform_key": "documents",
        "instructions": wrap(
            """
            List documents you have (even if not uploaded).
            If none, write: none

            Example:
              - Agreement dated ...
              - Invoices ...
              - Email chain ...
              - Legal notice + postal receipt ...
            """
        ),
    },
    7: {
        "title": "Previous proceedings / existing orders",
        "required": ["prior_proceedings"],
        "freeform_key": "prior_proceedings",
        "instructions": wrap(
            """
            Any prior case/complaint/appeal/settlement? Any existing order?
            If none, write: none
            """
        ),
    },
    8: {
        "title": "Limitation / delay",
        "required": ["limitation"],
        "freeform_key": "limitation",
        "instructions": wrap(
            """
            Are we within limitation? Any delay? Any reason for condonation?
            If unknown, write: unknown (we will mark as a blank and ask later).
            """
        ),
    },
}


MINIMUM_REQUIRED: list[tuple[str, str, int]] = [
    ("document_type", "Document type (Stage A)", 0),
    ("forum", "Forum (Stage A)", 0),
    ("stage", "Stage (Stage A)", 0),
    ("client_name", "Client name (Batch 1)", 1),
    ("opposite_party_name", "Opposite party name (Batch 1)", 1),
    ("timeline", "Timeline (Batch 2)", 2),
    ("reliefs", "Reliefs (Batch 5)", 5),
    ("jurisdiction_facts", "Jurisdiction facts (Batch 4)", 4),
    ("documents", "Documents list (Batch 6)", 6),
]


# ---------------------------------
# 7) Parsing helpers (simple on purpose)
# ---------------------------------

def is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def parse_kv_or_raw(answer: object) -> dict:
    """
    Accept either:
      - JSON (object)
      - key: value lines
      - raw text
    """
    if isinstance(answer, dict):
        return answer
    text = "" if answer is None else str(answer)
    text = text.strip()
    if not text:
        return {}

    if text.startswith("{") or text.startswith("["):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
            return {"_raw": text}
        except Exception:
            pass

    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("-*• ").strip()
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip()

    if data:
        data["_raw"] = text
        return data

    return {"_raw": text}


def pick_option(value: str, options: list[tuple[str, str]]) -> str:
    """
    If user types "1" pick options[0][0], etc.
    Otherwise, return the original value.
    """
    v = value.strip()
    if v.isdigit():
        idx = int(v) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    return value.strip()


def normalize_doc_type(value: str) -> str:
    v = value.strip().lower()
    if v in {"civil_plaint", "plaint"}:
        return "civil_plaint"
    if v in {"written_statement", "ws", "written statement"}:
        return "written_statement"
    if "legal notice" in v or v == "notice":
        return "legal_notice"
    if "writ" in v:
        return "writ_petition"
    if "slp" in v:
        return "slp"
    if "bail" in v:
        return "bail"
    if v in {"other"}:
        return "other"
    return value.strip()


def lines_from_text(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        line = line.lstrip("-*• ").strip()
        if line:
            out.append(line)
    return out


# -------------------------
# 8) SQLite cache "tool"
# -------------------------

CACHE: SqliteCache | None = None


def research_tool(query: str) -> str:
    """
    A very simple "research" tool:
    - caches results in SQLite by query
    - returns a deterministic placeholder result

    In real life you'd plug in: statutes DB, case-law DB, search API, LLM, etc.
    """
    if CACHE is None:
        return f"[no-cache] Research TODO for: {query}"

    ns = ("research",)
    hit = CACHE.get([(ns, query)]).get((ns, query))
    if hit is not None:
        return f"[cache hit] {hit['text']}"

    result = (
        "Research TODO (paste your sources here):\n"
        f"- Statutory provision(s) for: {query}\n"
        f"- Leading case law for: {query}\n"
        f"- Procedural rules/checklist for: {query}\n"
    )
    CACHE.set({(ns, query): ({"text": result}, 24 * 3600)})
    return f"[cache miss] {result}"


# ------------------------------------
# 9) Draft templates (structure varies)
# ------------------------------------

def outline_for(document_type: str) -> list[str]:
    doc = normalize_doc_type(document_type)
    if doc == "civil_plaint":
        return [
            "Cause Title (Court + Parties)",
            "Intro / Nature of Suit",
            "Jurisdiction",
            "Facts (Numbered, material facts only)",
            "Cause of Action",
            "Limitation",
            "Reliefs / Prayer",
            "Interim Relief (if any)",
            "Valuation + Court Fee (BLANK if unknown)",
            "List of Documents / Annexures",
            "Verification / Statement of Truth",
            "Affidavit (if required by forum practice)",
        ]
    if doc == "writ_petition":
        return [
            "Cause Title (Court + Parties)",
            "Synopsis",
            "List of Dates and Events",
            "Facts (Material facts only)",
            "Questions of Law",
            "Grounds",
            "Prayer (Main + Interim if any)",
            "Declaration / No-other-petition averment (as applicable)",
            "Verification",
            "Affidavit + Annexures + Index (filing set)",
        ]
    if doc == "slp":
        return [
            "Cause Title (Supreme Court)",
            "Synopsis + List of Dates",
            "Questions of Law",
            "Declarations",
            "Grounds (SLP)",
            "Grounds for Interim Relief",
            "Main Prayer + Interim Prayer",
            "Verification / Affidavit / Vakalatnama / Annexures / Index (filing set)",
        ]
    if doc == "legal_notice":
        return [
            "From/To + Addresses",
            "Subject",
            "Facts (Material facts only)",
            "Legal basis (high level, no wild claims)",
            "Demand / Relief sought",
            "Time to comply",
            "Consequences (proposed action if not complied)",
            "Enclosures list",
        ]
    if doc == "written_statement":
        return [
            "Cause Title",
            "Preliminary Objections",
            "Para-wise reply (admit/deny)",
            "Additional facts (material facts only)",
            "Legal defences",
            "Prayer",
            "Verification / Affidavit (as required)",
        ]
    if doc == "bail":
        return [
            "Cause Title",
            "Brief facts (FIR/Crime No., sections, custody date)",
            "Grounds for bail",
            "Undertakings",
            "Prayer",
            "Verification / Affidavit (as required)",
        ]
    return [
        "Cause Title",
        "Facts (Material facts only)",
        "Grounds / Legal basis",
        "Prayer",
        "Verification / Affidavit",
        "Annexures",
    ]


def numbered_facts_from_timeline(timeline_text: str, blanks: list[str]) -> tuple[str, list[str]]:
    facts_lines = lines_from_text(timeline_text)
    if not facts_lines:
        blanks.append("timeline (no facts provided)")
        return ("1. [BLANK: add numbered material facts timeline]\n", [])
    numbered = []
    for i, line in enumerate(facts_lines, start=1):
        numbered.append(f"{i}. {line}")
    return ("\n".join(numbered) + "\n", facts_lines)


def build_generic_petition_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    blanks: list[str] = []

    def get_or_blank(key: str, label: str) -> str:
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        blanks.append(label)
        return f"[BLANK: {label}]"

    doc_type = get_or_blank("document_type", "document_type")
    forum = get_or_blank("forum", "forum")
    stage = get_or_blank("stage", "stage")

    client_name = get_or_blank("client_name", "client_name")
    client_desc = get_or_blank("client_description", "client_description")
    opp_name = get_or_blank("opposite_party_name", "opposite_party_name")
    opp_desc = get_or_blank("opposite_party_description", "opposite_party_description")

    grievance = get_or_blank("grievance", "grievance")
    jurisdiction = get_or_blank("jurisdiction_facts", "jurisdiction_facts")
    reliefs = get_or_blank("reliefs", "reliefs")

    documents = state.get("documents", "")
    limitation = state.get("limitation", "")

    issues = state.get("issues", [])
    research_notes = state.get("research_notes", {})

    annexure_lines = lines_from_text(documents if isinstance(documents, str) else "")

    header = wrap(
        f"""
        IN THE {forum.upper()}

        Document Type: {doc_type}
        Stage: {stage}
        """
    )

    parties = wrap(
        f"""
        BETWEEN:
        {client_name}
        {client_desc}
        ... Applicant / Petitioner / Plaintiff

        AND:
        {opp_name}
        {opp_desc}
        ... Respondent / Defendant
        """
    )

    facts_numbered, _ = numbered_facts_from_timeline(str(state.get("timeline", "")), blanks)

    issues_lines = issues if isinstance(issues, list) else []
    if not issues_lines:
        issues_lines = ["[Optional] Add issues/questions."]

    grounds_lines: list[str] = []
    if research_notes:
        for k, v in research_notes.items():
            if v.strip():
                grounds_lines.append(f"- {k}: {v.strip()}")
    if not grounds_lines:
        grounds_lines = ["- [BLANK] Add statute/case-law grounds issue-wise."]
        blanks.append("legal grounds (statute/case law)")

    draft = []
    draft.append(header)
    draft.append("")
    draft.append(parties)
    draft.append("")
    draft.append("MOST RESPECTFULLY SHOWETH:")
    draft.append("")
    draft.append("A. JURISDICTION")
    draft.append(jurisdiction)
    draft.append("")
    draft.append("B. MATERIAL FACTS (NUMBERED)")
    draft.append(facts_numbered)
    draft.append("")
    draft.append("C. GRIEVANCE / CAUSE OF ACTION")
    draft.append(grievance)
    draft.append("")
    draft.append("D. ISSUES / QUESTIONS")
    for i, line in enumerate(issues_lines, start=1):
        draft.append(f"{i}. {line}")
    draft.append("")
    draft.append("E. GROUNDS (ISSUE-WISE)")
    draft.extend(grounds_lines)
    draft.append("")
    draft.append("F. LIMITATION / DELAY")
    if isinstance(limitation, str) and limitation.strip():
        draft.append(limitation.strip())
    else:
        draft.append("[BLANK: limitation/delay position]")
        blanks.append("limitation/delay")
    draft.append("")
    draft.append("G. RELIEFS / PRAYER")
    draft.append(reliefs)
    draft.append("")
    draft.append("H. LIST OF DOCUMENTS / ANNEXURES")
    if annexure_lines:
        for i, line in enumerate(annexure_lines, start=1):
            draft.append(f"Annexure-{i}: {line}")
    else:
        draft.append("[BLANK] No documents listed yet.")
    draft.append("")
    draft.append("VERIFICATION")
    draft.append(
        wrap(
            """
            I, [NAME], the [Applicant/Petitioner/Plaintiff], do hereby verify that the
            contents of the above are true and correct to my knowledge/belief and
            nothing material has been concealed.

            Place:
            Date:
            """
        )
    )
    draft.append("")
    draft.append("SIGNATURE: ____________________")

    return ("\n".join(draft).strip() + "\n", blanks, annexure_lines)


def build_legal_notice_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    blanks: list[str] = []

    def get_or_blank(key: str, label: str) -> str:
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        blanks.append(label)
        return f"[BLANK: {label}]"

    from_name = get_or_blank("client_name", "client_name")
    from_address = get_or_blank("from_address", "from_address")
    to_name = get_or_blank("opposite_party_name", "opposite_party_name")
    to_address = get_or_blank("to_address", "to_address")
    subject = get_or_blank("subject", "subject")
    deadline_days = get_or_blank("notice_deadline_days", "notice_deadline_days")

    grievance = get_or_blank("grievance", "grievance")
    reliefs = get_or_blank("reliefs", "reliefs")
    documents = state.get("documents", "")
    annexure_lines = lines_from_text(documents if isinstance(documents, str) else "")

    facts_numbered, _ = numbered_facts_from_timeline(str(state.get("timeline", "")), blanks)

    lines: list[str] = []
    lines.append("LEGAL NOTICE")
    lines.append("Date: [BLANK: date]")
    blanks.append("date")
    lines.append("")
    lines.append("From:")
    lines.append(from_name)
    lines.append(from_address)
    lines.append("")
    lines.append("To:")
    lines.append(to_name)
    lines.append(to_address)
    lines.append("")
    lines.append(f"Subject: {subject}")
    lines.append("")
    lines.append("Sir/Madam,")
    lines.append("")
    lines.append(
        wrap(
            """
            Under instructions from and on behalf of my client named above, I hereby issue you
            the present notice. This is a template for learning; please get an advocate to
            review before sending.
            """
        )
    )
    lines.append("")
    lines.append("1) MATERIAL FACTS (NUMBERED)")
    lines.append(facts_numbered.strip())
    lines.append("")
    lines.append("2) GRIEVANCE")
    lines.append(grievance)
    lines.append("")
    lines.append("3) DEMAND / RELIEF SOUGHT")
    lines.append(reliefs)
    lines.append("")
    lines.append("4) TIME TO COMPLY")
    lines.append(f"You are called upon to comply within {deadline_days} days of receipt of this notice.")
    lines.append("")
    lines.append("5) RESERVATION OF RIGHTS")
    lines.append(
        wrap(
            """
            In case of non-compliance, my client will be constrained to consider appropriate
            legal remedies at your risk as to costs and consequences, without further notice.
            """
        )
    )
    lines.append("")
    lines.append("Enclosures:")
    if annexure_lines:
        for i, a in enumerate(annexure_lines, start=1):
            lines.append(f"{i}. {a}")
    else:
        lines.append("[BLANK] No enclosures listed.")
    lines.append("")
    lines.append("Yours faithfully,")
    lines.append("Signature: ____________________")
    lines.append("Name: [BLANK]")
    blanks.append("notice signatory name")

    return ("\n".join(lines).strip() + "\n", blanks, annexure_lines)


def build_civil_plaint_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    blanks: list[str] = []

    def get_or_blank(key: str, label: str) -> str:
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        blanks.append(label)
        return f"[BLANK: {label}]"

    forum = get_or_blank("forum", "forum")
    client_name = get_or_blank("client_name", "client_name")
    client_desc = get_or_blank("client_description", "client_description")
    opp_name = get_or_blank("opposite_party_name", "opposite_party_name")
    opp_desc = get_or_blank("opposite_party_description", "opposite_party_description")

    nature_of_suit = get_or_blank("nature_of_suit", "nature_of_suit (e.g., recovery/injunction/declaration)")
    jurisdiction = get_or_blank("jurisdiction_facts", "jurisdiction_facts")
    grievance = get_or_blank("grievance", "grievance")
    reliefs = get_or_blank("reliefs", "reliefs")
    valuation = get_or_blank("valuation", "valuation")
    court_fee = get_or_blank("court_fee", "court_fee")
    interim_relief = state.get("interim_relief", "")

    limitation = state.get("limitation", "")
    documents = state.get("documents", "")
    annexure_lines = lines_from_text(documents if isinstance(documents, str) else "")

    facts_numbered, _ = numbered_facts_from_timeline(str(state.get("timeline", "")), blanks)

    lines: list[str] = []
    lines.append(f"IN THE {forum.upper()}")
    lines.append("")
    lines.append("CIVIL PLAINT")
    lines.append(f"Nature of Suit: {nature_of_suit}")
    lines.append("")
    lines.append("BETWEEN:")
    lines.append(client_name)
    lines.append(client_desc)
    lines.append("... Plaintiff")
    lines.append("")
    lines.append("AND:")
    lines.append(opp_name)
    lines.append(opp_desc)
    lines.append("... Defendant")
    lines.append("")
    lines.append("PLAINT (Material facts only)")
    lines.append("")
    lines.append("1. Jurisdiction")
    lines.append(jurisdiction)
    lines.append("")
    lines.append("2. Facts (Numbered)")
    lines.append(facts_numbered.strip())
    lines.append("")
    lines.append("3. Cause of Action / Grievance")
    lines.append(grievance)
    lines.append("")
    lines.append("4. Limitation")
    if isinstance(limitation, str) and limitation.strip():
        lines.append(limitation.strip())
    else:
        lines.append("[BLANK: limitation/delay position]")
        blanks.append("limitation/delay")
    lines.append("")
    lines.append("5. Valuation and Court Fee")
    lines.append(f"Valuation: {valuation}")
    lines.append(f"Court Fee: {court_fee}")
    lines.append("")
    lines.append("6. Prayer")
    lines.append(reliefs)
    if isinstance(interim_relief, str) and interim_relief.strip():
        lines.append("")
        lines.append("Interim Relief (if any):")
        lines.append(interim_relief.strip())
    lines.append("")
    lines.append("7. List of Documents / Annexures")
    if annexure_lines:
        for i, a in enumerate(annexure_lines, start=1):
            lines.append(f"Annexure-{i}: {a}")
    else:
        lines.append("[BLANK] No documents listed yet.")
    lines.append("")
    lines.append("VERIFICATION")
    lines.append(
        wrap(
            """
            Verified at [PLACE] on [DATE] that the contents of this plaint are true and correct
            to my knowledge/belief and nothing material has been concealed.
            """
        )
    )
    blanks.append("verification place/date")
    lines.append("")
    lines.append("Signature of Plaintiff: ____________________")

    return ("\n".join(lines).strip() + "\n", blanks, annexure_lines)


def build_writ_petition_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    blanks: list[str] = []

    def get_or_blank(key: str, label: str) -> str:
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        blanks.append(label)
        return f"[BLANK: {label}]"

    forum = get_or_blank("forum", "forum")
    client_name = get_or_blank("client_name", "client_name")
    opp_name = get_or_blank("opposite_party_name", "opposite_party_name")
    jurisdiction = get_or_blank("jurisdiction_facts", "jurisdiction_facts")
    reliefs = get_or_blank("reliefs", "reliefs")
    questions = get_or_blank("questions_of_law", "questions_of_law")
    declarations = state.get("declarations", "")
    interim_relief = state.get("interim_relief", "")

    documents = state.get("documents", "")
    annexure_lines = lines_from_text(documents if isinstance(documents, str) else "")

    facts_numbered, facts_lines = numbered_facts_from_timeline(str(state.get("timeline", "")), blanks)

    grounds_lines: list[str] = []
    for k, v in (state.get("research_notes", {}) or {}).items():
        if v.strip():
            grounds_lines.append(f"- {k}: {v.strip()}")
    if not grounds_lines:
        grounds_lines = ["- [BLANK] Add issue-wise legal grounds with statutes/case-law."]
        blanks.append("legal grounds (statute/case law)")

    lines: list[str] = []
    lines.append(f"IN THE {forum.upper()}")
    lines.append("")
    lines.append("WRIT PETITION (TEMPLATE)")
    lines.append(f"Petitioner: {client_name}")
    lines.append(f"Respondent(s): {opp_name}")
    lines.append("")
    lines.append("SYNOPSIS")
    lines.append(str(state.get("grievance", "")).strip() or "[BLANK: synopsis]")
    if not is_filled(state.get("grievance")):
        blanks.append("synopsis/grievance")
    lines.append("")
    lines.append("LIST OF DATES AND EVENTS")
    if facts_lines:
        for i, x in enumerate(facts_lines, start=1):
            lines.append(f"{i}. {x}")
    else:
        lines.append("[BLANK] Add dates/events.")
    lines.append("")
    lines.append("A. JURISDICTION / MAINTAINABILITY FACTS")
    lines.append(jurisdiction)
    lines.append("")
    lines.append("B. MATERIAL FACTS (NUMBERED)")
    lines.append(facts_numbered.strip())
    lines.append("")
    lines.append("C. QUESTIONS OF LAW")
    lines.append(questions)
    lines.append("")
    lines.append("D. GROUNDS")
    lines.extend(grounds_lines)
    lines.append("")
    lines.append("E. PRAYER")
    lines.append(reliefs)
    if isinstance(interim_relief, str) and interim_relief.strip():
        lines.append("")
        lines.append("Interim Prayer (if any):")
        lines.append(interim_relief.strip())
    lines.append("")
    lines.append("F. DECLARATION / AVERMENTS (as applicable)")
    if isinstance(declarations, str) and declarations.strip():
        lines.append(declarations.strip())
    else:
        lines.append("[BLANK: add required declarations (e.g., no other petition) as applicable]")
        blanks.append("declarations/averments")
    lines.append("")
    lines.append("ANNEXURES / INDEX")
    if annexure_lines:
        for i, a in enumerate(annexure_lines, start=1):
            lines.append(f"Annexure-{i}: {a}")
    else:
        lines.append("[BLANK] No annexures listed.")
    lines.append("")
    lines.append("VERIFICATION / AFFIDAVIT (as per forum requirements)")
    lines.append("[BLANK: verification + affidavit text]")
    blanks.append("verification/affidavit text")
    lines.append("")
    lines.append("Signature: ____________________")

    return ("\n".join(lines).strip() + "\n", blanks, annexure_lines)


def build_slp_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    blanks: list[str] = []

    def get_or_blank(key: str, label: str) -> str:
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        blanks.append(label)
        return f"[BLANK: {label}]"

    forum = get_or_blank("forum", "forum")
    client_name = get_or_blank("client_name", "client_name")
    opp_name = get_or_blank("opposite_party_name", "opposite_party_name")

    questions = get_or_blank("questions_of_law", "questions_of_law")
    declarations = get_or_blank("declarations", "declarations")
    reliefs = get_or_blank("reliefs", "reliefs")
    interim_relief = state.get("interim_relief", "")

    documents = state.get("documents", "")
    annexure_lines = lines_from_text(documents if isinstance(documents, str) else "")

    facts_numbered, facts_lines = numbered_facts_from_timeline(str(state.get("timeline", "")), blanks)

    grounds_lines: list[str] = []
    for k, v in (state.get("research_notes", {}) or {}).items():
        if v.strip():
            grounds_lines.append(f"- {k}: {v.strip()}")
    if not grounds_lines:
        grounds_lines = ["- [BLANK] Add SLP grounds (statutes/case-law)."]
        blanks.append("legal grounds (statute/case law)")

    lines: list[str] = []
    lines.append(f"IN THE {forum.upper()}")
    lines.append("")
    lines.append("SPECIAL LEAVE PETITION (TEMPLATE)")
    lines.append(f"Petitioner: {client_name}")
    lines.append(f"Respondent(s): {opp_name}")
    lines.append("")
    lines.append("SYNOPSIS / LIST OF DATES")
    if facts_lines:
        for i, x in enumerate(facts_lines, start=1):
            lines.append(f"{i}. {x}")
    else:
        lines.append("[BLANK] Add dates/events.")
    lines.append("")
    lines.append("QUESTIONS OF LAW")
    lines.append(questions)
    lines.append("")
    lines.append("DECLARATIONS")
    lines.append(declarations)
    lines.append("")
    lines.append("GROUNDS")
    lines.extend(grounds_lines)
    lines.append("")
    lines.append("MAIN PRAYER")
    lines.append(reliefs)
    if isinstance(interim_relief, str) and interim_relief.strip():
        lines.append("")
        lines.append("INTERIM PRAYER (if any)")
        lines.append(interim_relief.strip())
    lines.append("")
    lines.append("ANNEXURES / INDEX (filing set)")
    if annexure_lines:
        for i, a in enumerate(annexure_lines, start=1):
            lines.append(f"Annexure-{i}: {a}")
    else:
        lines.append("[BLANK] No annexures listed.")
    lines.append("")
    lines.append("VERIFICATION / AFFIDAVIT / VAKALATNAMA (as per Supreme Court requirements)")
    lines.append("[BLANK]")
    blanks.append("filing accompaniments (vakalatnama, memo, affidavit, etc.)")
    lines.append("")
    lines.append("Signature: ____________________")

    return ("\n".join(lines).strip() + "\n", blanks, annexure_lines)


def build_draft_text(state: DraftState) -> tuple[str, list[str], list[str]]:
    """
    Returns: (draft_text, blanks, annexure_lines)
    """
    doc = normalize_doc_type(str(state.get("document_type", "")))
    if doc == "legal_notice":
        return build_legal_notice_text(state)
    if doc == "civil_plaint":
        return build_civil_plaint_text(state)
    if doc == "writ_petition":
        return build_writ_petition_text(state)
    if doc == "slp":
        return build_slp_text(state)
    return build_generic_petition_text(state)


def build_one_page_brief(state: DraftState) -> str:
    lines: list[str] = []
    lines.append("ONE-PAGE BRIEF (for filing junior)")
    lines.append("")
    lines.append("1) Classification")
    lines.append(f"- Document: {state.get('document_type')}")
    lines.append(f"- Forum: {state.get('forum')}")
    lines.append(f"- Stage: {state.get('stage')}")
    lines.append("")
    lines.append("2) Parties")
    lines.append(f"- Client: {state.get('client_name')}")
    lines.append(f"- Opposite: {state.get('opposite_party_name')}")
    lines.append("")
    lines.append("3) Timeline (high level)")
    tl = lines_from_text(state.get("timeline", ""))
    for line in tl[:6]:
        lines.append(f"- {line}")
    if len(tl) > 6:
        lines.append("- ...")
    lines.append("")
    lines.append("4) Reliefs (as asked)")
    rel = lines_from_text(state.get("reliefs", ""))
    for line in rel[:6]:
        lines.append(f"- {line}")
    if len(rel) > 6:
        lines.append("- ...")
    if is_filled(state.get("questions_of_law")):
        lines.append("")
        lines.append("4b) Questions of Law (as provided)")
        ql = lines_from_text(state.get("questions_of_law", ""))
        for line in ql[:6]:
            lines.append(f"- {line}")
        if len(ql) > 6:
            lines.append("- ...")
    if is_filled(state.get("valuation")) or is_filled(state.get("court_fee")):
        lines.append("")
        lines.append("4c) Valuation / Court Fee")
        lines.append(f"- Valuation: {state.get('valuation')}")
        lines.append(f"- Court fee: {state.get('court_fee')}")
    lines.append("")
    lines.append("5) Documents (annexures)")
    docs = lines_from_text(state.get("documents", ""))
    for line in docs[:6]:
        lines.append(f"- {line}")
    if len(docs) > 6:
        lines.append("- ...")
    return "\n".join(lines).strip() + "\n"


def compliance_rules_for(document_type: str) -> list[tuple[str, str]]:
    doc = normalize_doc_type(document_type)
    if doc == "civil_plaint":
        return [
            ("client_name", "Party details present"),
            ("opposite_party_name", "Party details present"),
            ("timeline", "Material facts timeline present"),
            ("jurisdiction_facts", "Jurisdiction facts present"),
            ("reliefs", "Prayer/reliefs stated"),
            ("limitation", "Limitation/delay position stated"),
            ("nature_of_suit", "Nature of suit stated"),
            ("valuation", "Valuation for jurisdiction/court fee (required for many civil filings)"),
            ("court_fee", "Court fee (often required)"),
        ]
    if doc == "legal_notice":
        return [
            ("from_address", "Sender address present"),
            ("to_address", "Recipient address present"),
            ("subject", "Subject line present"),
            ("notice_deadline_days", "Time to comply stated"),
            ("timeline", "Material facts present"),
            ("reliefs", "Demand/relief stated"),
            ("documents", "Enclosures listed (or 'none')"),
        ]
    if doc == "writ_petition":
        return [
            ("timeline", "List of dates/events present"),
            ("questions_of_law", "Questions of law identified"),
            ("declarations", "Required averments/declarations included"),
            ("reliefs", "Prayer/reliefs stated"),
            ("jurisdiction_facts", "Jurisdiction/maintainability facts present"),
        ]
    if doc == "slp":
        return [
            ("timeline", "List of dates/events present"),
            ("questions_of_law", "Questions of law identified"),
            ("declarations", "Declarations included"),
            ("reliefs", "Prayer/reliefs stated"),
        ]
    return [
        ("timeline", "Facts present"),
        ("reliefs", "Prayer/reliefs stated"),
        ("jurisdiction_facts", "Forum/jurisdiction facts present (if applicable)"),
    ]


# --------------------------------------------
# 10) LangGraph nodes (Stages A → I, with gates)
# --------------------------------------------

def node_a_classify(state: DraftState) -> DraftState:
    if is_filled(state.get("document_type")) and is_filled(state.get("forum")) and is_filled(state.get("stage")):
        return {"log": ["Stage A: already classified"], "intake_batch": state.get("intake_batch", 1)}

    prompt = {
        "stage": "A",
        "title": "Classify the request (document + forum + stage)",
        "instructions": wrap(
            """
            Choose:
            1) document type
            2) forum
            3) stage

            Reply in key:value lines, OR you can reply with numbers.

            Example (key:value):
              document_type: writ_petition
              forum: High Court
              stage: Filing

            Example (numbers):
              document_type: 4
              forum: 2
              stage: 2
            """
        ),
        "document_type_options": [f"{i+1}) {label}" for i, (_, label) in enumerate(DOC_TYPE_OPTIONS)],
        "forum_options": [f"{i+1}) {label}" for i, label in enumerate(FORUM_OPTIONS)],
        "stage_options": [f"{i+1}) {label}" for i, label in enumerate(STAGE_OPTIONS)],
    }

    answer = interrupt(prompt)
    data = parse_kv_or_raw(answer)

    doc_raw = str(data.get("document_type", data.get("_raw", ""))).strip()
    forum_raw = str(data.get("forum", "")).strip()
    stage_raw = str(data.get("stage", "")).strip()

    doc_pick = pick_option(doc_raw, DOC_TYPE_OPTIONS) if doc_raw else ""
    forum_pick = forum_raw
    stage_pick = stage_raw

    if forum_pick:
        if forum_pick.isdigit():
            idx = int(forum_pick) - 1
            if 0 <= idx < len(FORUM_OPTIONS):
                forum_pick = FORUM_OPTIONS[idx]
    if stage_pick:
        if stage_pick.isdigit():
            idx = int(stage_pick) - 1
            if 0 <= idx < len(STAGE_OPTIONS):
                stage_pick = STAGE_OPTIONS[idx]

    doc_norm = normalize_doc_type(doc_pick)

    return {
        "document_type": doc_norm if doc_norm else doc_pick,
        "forum": forum_pick,
        "stage": stage_pick,
        "intake_batch": 1,
        "log": [f"Stage A: document_type={doc_norm}, forum={forum_pick}, stage={stage_pick}"],
    }


def node_b_intake(state: DraftState) -> DraftState:
    batch = int(state.get("intake_batch", 1))
    if batch > 8:
        return {"log": ["Stage B: intake complete"], "last_missing": [], "last_understood": ""}

    spec = INTAKE_BATCHES[batch]
    prompt = {
        "stage": "B",
        "batch": batch,
        "title": f"Intake batch {batch}/8 — {spec['title']}",
        "instructions": spec["instructions"],
        "required_fields": spec["required"],
    }

    answer = interrupt(prompt)

    updates: DraftState = {}
    missing: list[str] = []

    # Freeform batches store the entire answer in one key.
    if "freeform_key" in spec:
        key = spec["freeform_key"]
        text = "" if answer is None else str(answer).strip()
        updates[key] = text
        if key in spec["required"] and not is_filled(text):
            missing.append(key)
        preview = text[:120].replace("\n", " ")
        understood = f"Captured {key}: {preview}"
        updates["last_understood"] = understood
        updates["last_missing"] = missing
    else:
        data = parse_kv_or_raw(answer)
        for field in spec["fields"]:
            if field in data:
                updates[field] = str(data[field]).strip()
        # If user didn't follow key:value, store raw in special_status so nothing is lost.
        if not updates and "_raw" in data:
            updates["special_status"] = str(data["_raw"]).strip()

        for field in spec["required"]:
            v = updates.get(field, state.get(field))
            if not is_filled(v):
                missing.append(field)

        understood = []
        for field in spec["fields"]:
            v = updates.get(field, state.get(field))
            if is_filled(v):
                understood.append(f"{field}={str(v)[:60]}")
        updates["last_understood"] = ", ".join(understood) if understood else "[no structured fields captured]"
        updates["last_missing"] = missing

    if missing:
        updates["log"] = [f"Stage B batch {batch}: missing {missing} (ask again)"]
        updates["intake_batch"] = batch
        return updates

    updates["log"] = [f"Stage B batch {batch}: ok"]
    updates["intake_batch"] = batch + 1
    return updates


def route_after_intake(state: DraftState) -> str:
    return "intake" if int(state.get("intake_batch", 1)) <= 8 else "minimum_gate"


def node_c_minimum_gate(state: DraftState) -> DraftState:
    missing: list[str] = []
    next_batch = 99

    for key, label, batch in MINIMUM_REQUIRED:
        if not is_filled(state.get(key)):
            missing.append(f"{key} — {label}")
            if batch != 0:
                next_batch = min(next_batch, batch)

    ok = len(missing) == 0
    updates: DraftState = {
        "minimum_gate_ok": ok,
        "minimum_missing": missing,
        "log": [f"Stage C minimum gate ok={ok}"],
    }
    if not ok:
        # If A is missing, go back to classify; else go to the relevant intake batch.
        if any(m.startswith("document_type") or m.startswith("forum") or m.startswith("stage") for m in missing):
            updates["log"] = [f"Stage C missing classification fields: {missing}"]
        else:
            if next_batch == 99:
                next_batch = 1
            updates["intake_batch"] = next_batch
            updates["log"] = [f"Stage C missing fields -> returning to intake batch {next_batch}"]
    return updates


def route_after_minimum_gate(state: DraftState) -> str:
    if not state.get("minimum_gate_ok"):
        missing = state.get("minimum_missing", [])
        if any(m.startswith("document_type") or m.startswith("forum") or m.startswith("stage") for m in missing):
            return "classify"
        return "intake"
    return "confirm_case_file"


def node_c_confirm_case_file(state: DraftState) -> DraftState:
    summary = wrap(
        f"""
        What I understood (minimum viable case file):

        - document_type: {state.get('document_type')}
        - forum: {state.get('forum')}
        - stage: {state.get('stage')}
        - client: {state.get('client_name')}
        - opposite: {state.get('opposite_party_name')}

        Timeline (first lines):
        {chr(10).join(lines_from_text(state.get('timeline', ''))[:5])}

        Reliefs (first lines):
        {chr(10).join(lines_from_text(state.get('reliefs', ''))[:5])}

        Reply:
          yes
        OR give corrections in key:value lines (example):
          client_name: ...
          reliefs: ...
        """
    )

    answer = interrupt({"stage": "C", "title": "Confirm understanding before planning", "summary": summary})
    text = "" if answer is None else str(answer).strip()
    if text.lower() in {"y", "yes", "ok", "okay"}:
        return {"case_file_confirmed": True, "log": ["Stage C: case file confirmed by user"]}

    data = parse_kv_or_raw(answer)
    updates: DraftState = {"case_file_confirmed": False, "log": ["Stage C: user provided corrections -> re-check gate"]}
    # Apply only known keys (keep it simple)
    for k in [
        "document_type",
        "forum",
        "stage",
        "client_name",
        "client_description",
        "opposite_party_name",
        "opposite_party_description",
        "timeline",
        "grievance",
        "jurisdiction_facts",
        "reliefs",
        "documents",
        "prior_proceedings",
        "limitation",
    ]:
        if k in data:
            updates[k] = str(data[k]).strip()
    return updates


def route_after_confirm_case_file(state: DraftState) -> str:
    return "plan" if state.get("case_file_confirmed") else "minimum_gate"


def node_d_plan(state: DraftState) -> DraftState:
    # Very simple issues list; user can extend.
    issues = [
        "Maintainability / correct forum / correct remedy",
        "Jurisdiction",
        "Limitation / delay",
        "Merits (based on grievance)",
        "Reliefs (main + interim, if any)",
    ]
    outline = outline_for(state.get("document_type", ""))

    prompt = {
        "stage": "D",
        "title": "Plan the draft (issues + outline)",
        "outline": outline,
        "issues": issues,
        "instructions": wrap(
            """
            Reply:
              yes
            OR add extra issues as lines (we will append them).
            """
        ),
    }

    answer = interrupt(prompt)
    text = "" if answer is None else str(answer).strip()
    if text.lower() in {"y", "yes", "ok", "okay"}:
        return {"issues": issues, "outline": outline, "plan_confirmed": True, "log": ["Stage D: plan confirmed"]}

    extra = lines_from_text(text)
    issues2 = issues + [e for e in extra if e]
    return {"issues": issues2, "outline": outline, "plan_confirmed": True, "log": ["Stage D: plan adjusted by user"]}


def node_d_particulars(state: DraftState) -> DraftState:
    """
    Stage D (continued): collect document-type-specific mandatory particulars
    BEFORE we draft, so we don't "assume" them later.
    """
    doc = normalize_doc_type(str(state.get("document_type", "")))

    required: list[tuple[str, str]] = []
    if doc == "legal_notice":
        required = [
            ("from_address", "Sender address (client address)"),
            ("to_address", "Recipient address (opposite party address)"),
            ("subject", "Subject line"),
            ("notice_deadline_days", "Time to comply (days)"),
        ]
    elif doc == "civil_plaint":
        required = [
            ("nature_of_suit", "Nature of suit (e.g., recovery / injunction / declaration)"),
            ("valuation", "Valuation for jurisdiction"),
            ("court_fee", "Court fee (as applicable)"),
        ]
    elif doc == "writ_petition":
        required = [
            ("questions_of_law", "Questions of law"),
            ("declarations", "Required averments/declarations (e.g., no other petition)"),
        ]
    elif doc == "slp":
        required = [
            ("questions_of_law", "Questions of law"),
            ("declarations", "Declarations (as per format)"),
        ]

    missing = [f"{k} — {desc}" for (k, desc) in required if not is_filled(state.get(k))]
    if not missing:
        return {"log": ["Stage D: particulars already present"]}

    prompt = {
        "stage": "D",
        "title": "Mandatory particulars for this document type",
        "missing": missing,
        "instructions": wrap(
            """
            Reply with key:value lines for the missing items.
            If you don't know, write [BLANK] (we will keep it as a blank and show it at the end).
            """
        ),
    }
    answer = interrupt(prompt)
    data = parse_kv_or_raw(answer)

    updates: DraftState = {"log": ["Stage D: captured mandatory particulars"]}
    for k, _ in required:
        if k in data:
            updates[k] = str(data[k]).strip()
    return updates


def node_e_research(state: DraftState, runtime: Runtime[Ctx]) -> DraftState:
    issues = state.get("issues", [])
    i = int(state.get("research_i", 0))
    if i >= len(issues):
        return {"log": ["Stage E: research complete"]}

    issue = issues[i]
    suggestion = research_tool(issue)

    prompt = {
        "stage": "E",
        "title": f"Research ({i+1}/{len(issues)}): {issue}",
        "instructions": wrap(
            """
            Paste statute/case-law/procedure notes for this issue.
            If you don't have them now, reply: SKIP
            """
        ),
        "suggestion": suggestion,
    }

    answer = interrupt(prompt)
    text = "" if answer is None else str(answer).strip()
    note = "" if text.upper() == "SKIP" else text

    notes = dict(state.get("research_notes", {}))
    notes[issue] = note

    # Persist research notes as we go (durable)
    runtime.store.put(("cases", runtime.context.case_id), f"research_note_{i}", {"issue": issue, "note": note})  # type: ignore[union-attr]

    return {
        "research_i": i + 1,
        "research_notes": notes,
        "log": [f"Stage E: stored research note for issue {i+1}/{len(issues)}"],
    }


def route_after_research(state: DraftState) -> str:
    issues = state.get("issues", [])
    i = int(state.get("research_i", 0))
    return "research" if i < len(issues) else "compile"


def node_f_compile(state: DraftState, runtime: Runtime[Ctx]) -> DraftState:
    # Build a simple "case file" dict (this is what seniors keep internally).
    case_file = {
        "classification": {
            "document_type": state.get("document_type"),
            "forum": state.get("forum"),
            "stage": state.get("stage"),
        },
        "parties": {
            "client_name": state.get("client_name"),
            "client_description": state.get("client_description"),
            "opposite_party_name": state.get("opposite_party_name"),
            "opposite_party_description": state.get("opposite_party_description"),
            "special_status": state.get("special_status"),
        },
        "timeline": lines_from_text(state.get("timeline", "")),
        "grievance": state.get("grievance"),
        "jurisdiction_facts": state.get("jurisdiction_facts"),
        "reliefs": state.get("reliefs"),
        "documents": lines_from_text(state.get("documents", "")),
        "prior_proceedings": state.get("prior_proceedings"),
        "limitation": state.get("limitation"),
        "issues": state.get("issues", []),
        "research_notes": state.get("research_notes", {}),
    }

    blanks: list[str] = []
    for key, label, _ in MINIMUM_REQUIRED:
        if not is_filled(state.get(key)):
            blanks.append(label)

    runtime.store.put(("cases", runtime.context.case_id), "case_file", case_file)  # type: ignore[union-attr]

    return {"case_file": case_file, "assumptions_or_blanks": blanks, "log": ["Stage F: compiled case file"]}


def node_g_draft(state: DraftState, runtime: Runtime[Ctx]) -> DraftState:
    draft_text, blanks, annexures = build_draft_text(state)
    brief = build_one_page_brief(state)

    runtime.store.put(("cases", runtime.context.case_id), "draft", {"text": draft_text})  # type: ignore[union-attr]
    runtime.store.put(("cases", runtime.context.case_id), "brief", {"text": brief})  # type: ignore[union-attr]

    return {
        "draft": draft_text,
        "brief": brief,
        "annexures": annexures,
        "assumptions_or_blanks": blanks,
        "log": ["Stage G: drafted document"],
    }


def node_h_compliance(state: DraftState) -> DraftState:
    rules = compliance_rules_for(state.get("document_type", ""))
    missing: list[str] = []
    for key, desc in rules:
        if not is_filled(state.get(key)):
            missing.append(f"{key} — {desc}")

    needs_fix = len(missing) > 0
    return {
        "compliance_missing": missing,
        "needs_fix": needs_fix,
        "log": [f"Stage H: needs_fix={needs_fix} missing={len(missing)}"],
    }


def route_after_compliance(state: DraftState) -> str:
    return "fix_missing" if state.get("needs_fix") else "deliver"


def node_h_fix_missing(state: DraftState) -> DraftState:
    missing = state.get("compliance_missing", [])
    prompt = {
        "stage": "H",
        "title": "Fill missing mandatory particulars (compliance gate)",
        "missing": missing,
        "instructions": wrap(
            """
            Reply with key:value lines for the missing items.

            Example:
              valuation: INR 5,00,000
              court_fee: [as per schedule]

            If you truly don't know, write [BLANK].
            """
        ),
    }
    answer = interrupt(prompt)
    data = parse_kv_or_raw(answer)

    updates: DraftState = {"log": ["Stage H: applied compliance fixes"]}
    for key in [m.split(" — ", 1)[0] for m in missing]:
        if key in data:
            updates[key] = str(data[key]).strip()
    return updates


def node_i_deliver(state: DraftState, runtime: Runtime[Ctx]) -> DraftState:
    # Write a "filing support pack" folder (multiple files, not one blob).
    case_dir = DATA_DIR / f"case_{runtime.context.case_id}"
    case_dir.mkdir(exist_ok=True)

    draft_path = case_dir / "01_draft.txt"
    brief_path = case_dir / "02_one_page_brief.txt"
    blanks_path = case_dir / "03_blanks_and_assumptions.txt"
    annexures_path = case_dir / "04_annexures.txt"
    checklist_path = case_dir / "05_compliance_checklist.txt"
    next_steps_path = case_dir / "06_next_steps.txt"

    draft_path.write_text(state.get("draft", ""), encoding="utf-8")
    brief_path.write_text(state.get("brief", ""), encoding="utf-8")

    blanks = state.get("assumptions_or_blanks", []) or []
    blanks_text = "\n".join([f"- {x}" for x in blanks]) + ("\n" if blanks else "[]\n")
    blanks_path.write_text(blanks_text, encoding="utf-8")

    annex = state.get("annexures", []) or []
    annex_text = "\n".join([f"Annexure-{i}: {x}" for i, x in enumerate(annex, start=1)]) + ("\n" if annex else "[]\n")
    annexures_path.write_text(annex_text, encoding="utf-8")

    next_steps = [
        "Review: ensure only material facts are pleaded (remove evidence/arguments from facts).",
        "Confirm: forum + remedy + provision (especially for writ/SLP formats).",
        "Prepare: verification / affidavit / vakalatnama / memo of appearance (as applicable).",
        "Prepare annexures: index + page numbering + legible copies.",
        "Check limitation and add condonation application if needed.",
        "Have a qualified advocate review before filing/serving.",
    ]

    missing_keys = {m.split(" — ", 1)[0] for m in (state.get("compliance_missing", []) or [])}
    rules = compliance_rules_for(state.get("document_type", ""))
    checklist_lines: list[str] = []
    checklist_lines.append("COMPLIANCE CHECKLIST (educational)")
    checklist_lines.append(f"Document type: {state.get('document_type')}")
    checklist_lines.append("")
    for key, desc in rules:
        ok = "OK" if key not in missing_keys else "MISSING"
        checklist_lines.append(f"- {ok}: {key} — {desc}")
    checklist_path.write_text("\n".join(checklist_lines).strip() + "\n", encoding="utf-8")

    next_steps_path.write_text("\n".join([f"- {x}" for x in next_steps]).strip() + "\n", encoding="utf-8")

    runtime.store.put(  # type: ignore[union-attr]
        ("cases", runtime.context.case_id),
        "delivery",
        {
            "case_dir": str(case_dir),
            "files": {
                "draft": str(draft_path),
                "brief": str(brief_path),
                "blanks": str(blanks_path),
                "annexures": str(annexures_path),
                "checklist": str(checklist_path),
                "next_steps": str(next_steps_path),
            },
        },
    )

    return {
        "next_steps": next_steps,
        "output_path": str(case_dir),
        "log": ["Stage I: delivered output package"],
    }


# -----------------------------
# 11) Build the LangGraph graph
# -----------------------------

builder = StateGraph(state_schema=DraftState, context_schema=Ctx)
builder.add_node("classify", node_a_classify)
builder.add_node("intake", node_b_intake)
builder.add_node("minimum_gate", node_c_minimum_gate)
builder.add_node("confirm_case_file", node_c_confirm_case_file)
builder.add_node("plan", node_d_plan)
builder.add_node("particulars", node_d_particulars)
builder.add_node("research", node_e_research)
builder.add_node("compile", node_f_compile)
builder.add_node("draft", node_g_draft)
builder.add_node("compliance", node_h_compliance)
builder.add_node("fix_missing", node_h_fix_missing)
builder.add_node("deliver", node_i_deliver)

builder.add_edge(START, "classify")
builder.add_edge("classify", "intake")
builder.add_conditional_edges("intake", route_after_intake, {"intake": "intake", "minimum_gate": "minimum_gate"})
builder.add_conditional_edges(
    "minimum_gate",
    route_after_minimum_gate,
    {"classify": "classify", "intake": "intake", "confirm_case_file": "confirm_case_file"},
)
builder.add_conditional_edges(
    "confirm_case_file",
    route_after_confirm_case_file,
    {"plan": "plan", "minimum_gate": "minimum_gate"},
)
builder.add_edge("plan", "particulars")
builder.add_edge("particulars", "research")
builder.add_conditional_edges("research", route_after_research, {"research": "research", "compile": "compile"})
builder.add_edge("compile", "draft")
builder.add_edge("draft", "compliance")
builder.add_conditional_edges("compliance", route_after_compliance, {"fix_missing": "fix_missing", "deliver": "deliver"})
builder.add_edge("fix_missing", "draft")
builder.add_edge("deliver", END)


# -----------------------------
# 12) Interactive runner (human in loop)
# -----------------------------

def read_multiline_from_stdin() -> str:
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


def print_interrupt_prompt(prompt: dict) -> None:
    title(f"INTERRUPT — Stage {prompt.get('stage')} — {prompt.get('title')}")

    if "instructions" in prompt:
        print("\n" + str(prompt["instructions"]).strip())

    if "document_type_options" in prompt:
        step("Document type options")
        for x in prompt["document_type_options"]:
            print("  " + x)
    if "forum_options" in prompt:
        step("Forum options")
        for x in prompt["forum_options"]:
            print("  " + x)
    if "stage_options" in prompt:
        step("Stage options")
        for x in prompt["stage_options"]:
            print("  " + x)

    if "summary" in prompt:
        step("Summary")
        print(str(prompt["summary"]))

    if "outline" in prompt:
        step("Outline")
        for i, x in enumerate(prompt["outline"], start=1):
            print(f"  {i}. {x}")
    if "issues" in prompt:
        step("Issues")
        for i, x in enumerate(prompt["issues"], start=1):
            print(f"  {i}. {x}")

    if "suggestion" in prompt:
        step("Research suggestion (cached tool output)")
        print(str(prompt["suggestion"]))

    if "missing" in prompt:
        step("Missing items")
        for x in prompt["missing"]:
            print("  - " + x)


DEMO_ANSWERS: list[str] = [
    # Stage A
    "document_type: legal_notice\nforum: District Court / Civil Court\nstage: Pre-litigation",
    # Batch 1
    "\n".join(
        [
            "client_name: Mr. A",
            "client_description: Adult Indian citizen, resident of Bengaluru, Karnataka.",
            "opposite_party_name: M/s B Pvt Ltd",
            "opposite_party_description: Company incorporated under Companies Act, having office at Bengaluru.",
            "special_status: none",
        ]
    ),
    # Batch 2 timeline
    "\n".join(
        [
            "2024-01-10: Service contract executed between the parties.",
            "2024-02-05: Invoice raised for INR 5,00,000 payable within 15 days.",
            "2024-03-01: Reminder email sent; no payment received.",
        ]
    ),
    # Batch 3 grievance
    "Non-payment of invoice amount despite contractual obligation and repeated reminders.",
    # Batch 4 jurisdiction
    "Cause of action arose in Bengaluru where the contract was executed and performed; opposite party carries on business here.",
    # Batch 5 reliefs
    "\n".join(
        [
            "Demand payment of INR 5,00,000 with interest.",
            "Demand written confirmation of payment timeline within 7 days.",
        ]
    ),
    # Batch 6 documents
    "\n".join(["Service contract dated 2024-01-10", "Invoice dated 2024-02-05", "Reminder email dated 2024-03-01"]),
    # Batch 7 prior proceedings
    "none",
    # Batch 8 limitation
    "Within limitation as the invoice default is in 2024.",
    # Confirm case file
    "yes",
    # Plan confirm
    "yes",
    # Mandatory particulars (legal notice)
    "\n".join(
        [
            "from_address: No. 10, MG Road, Bengaluru, Karnataka, India.",
            "to_address: No. 20, Residency Road, Bengaluru, Karnataka, India.",
            "subject: Demand for payment of outstanding invoice amount",
            "notice_deadline_days: 7",
        ]
    ),
    # Research for each issue (5 issues)
    "SKIP",
    "SKIP",
    "SKIP",
    "SKIP",
    "SKIP",
    # Compliance fixes fallback (if any)
    "valuation: [BLANK]\ncourt_fee: [BLANK]\nquestions_of_law: [BLANK]\ndeclarations: [BLANK]",
]


def run_graph(*, demo: bool, thread_id: str | None, case_id: str | None, resume_answer: str | None, pause_on_interrupt: bool) -> None:
    global CACHE

    if case_id is None:
        case_id = str(uuid.uuid4())[:8]
    if thread_id is None:
        thread_id = f"draft-{case_id}"

    config = {"configurable": {"thread_id": thread_id}}
    context = Ctx(user_id="u1", case_id=case_id)

    title("Drafting Deep Research Agent (Gated Drafting) — Learning Run")
    print("Not legal advice. Educational workflow only.\n")
    show("SQLite data dir", str(DATA_DIR))
    show("thread_id (checkpoints key)", thread_id)
    show("case_id (store namespace)", case_id)

    CACHE = SqliteCache(path=str(CACHE_DB))

    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
        with SqliteStore.from_conn_string(str(STORE_DB)) as store:
            graph = builder.compile(checkpointer=checkpointer, store=store)

            demo_answers = list(DEMO_ANSWERS)
            if resume_answer is not None:
                current_input: object = Command(resume=resume_answer)
            else:
                current_input = {"log": [], "intake_batch": 1, "research_i": 0, "research_notes": {}}

            while True:
                interrupted = False
                for chunk in graph.stream(current_input, config, context=context, stream_mode="updates"):
                    if "__interrupt__" in chunk:
                        interrupted = True
                        interrupt_obj = chunk["__interrupt__"][0]
                        prompt = interrupt_obj.value
                        if not isinstance(prompt, dict):
                            prompt = {"stage": "?", "title": "Unknown", "instructions": str(prompt)}

                        print_interrupt_prompt(prompt)

                        if pause_on_interrupt:
                            print("\nPaused on interrupt (pause mode). Resume with:")
                            print(
                                "./.venv/bin/python drafting_deepreearch.py "
                                f"--thread \"{thread_id}\" --case \"{case_id}\" "
                                "--resume \"<YOUR ANSWER HERE>\""
                            )
                            return

                        if demo:
                            if not demo_answers:
                                raise RuntimeError("Demo mode ran out of answers.")
                            answer = demo_answers.pop(0)
                            step("Demo answer used")
                            print(answer)
                        else:
                            answer = read_multiline_from_stdin()

                        current_input = Command(resume=answer)
                        break

                    # Normal node update chunk
                    if isinstance(chunk, dict) and len(chunk) == 1:
                        node_name = next(iter(chunk.keys()))
                        payload = chunk[node_name]
                        step(f"UPDATE from node: {node_name}")
                        if isinstance(payload, dict) and "last_understood" in payload:
                            show("what_i_understood", payload.get("last_understood"))
                            if payload.get("last_missing"):
                                show("what_is_missing", payload.get("last_missing"))
                        elif node_name == "minimum_gate" and isinstance(payload, dict) and payload.get("minimum_missing"):
                            show("minimum_missing", payload.get("minimum_missing"))
                        elif node_name == "compliance" and isinstance(payload, dict) and payload.get("compliance_missing"):
                            show("compliance_missing", payload.get("compliance_missing"))
                        else:
                            show("update", payload)
                    else:
                        show("update", chunk)

                if not interrupted:
                    break

            step("DONE. Final outputs")
            snap = graph.get_state(config)
            show("output_path", snap.values.get("output_path"))
            show("blanks/assumptions", snap.values.get("assumptions_or_blanks"))
            show("next_steps", snap.values.get("next_steps"))

            print("\n--- DRAFT (first 1200 chars) ---")
            draft_text = snap.values.get("draft", "")
            print(str(draft_text)[:1200] + ("\n...\n" if len(str(draft_text)) > 1200 else ""))


# -----------------------------
# 13) CLI entrypoint (simple)
# -----------------------------

if __name__ == "__main__":
    demo = False
    thread_id: str | None = None
    case_id: str | None = None
    resume_answer: str | None = None
    pause_on_interrupt = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--demo":
            demo = True
            i += 1
            continue
        if args[i] == "--pause":
            pause_on_interrupt = True
            i += 1
            continue
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

    run_graph(demo=demo, thread_id=thread_id, case_id=case_id, resume_answer=resume_answer, pause_on_interrupt=pause_on_interrupt)
