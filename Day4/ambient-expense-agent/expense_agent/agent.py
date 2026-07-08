# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os

import google.auth
from dotenv import load_dotenv
from google import genai
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import START, Workflow
from google.genai import types
from pydantic import BaseModel, Field

# Load local environment variables from .env file
load_dotenv()

# Setup Google Cloud / Vertex AI vs. Google AI Studio configuration
use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() == "true"
if use_vertex:
    try:
        _, project_id = google.auth.default()
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    except Exception:
        pass
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# Initialize Google GenAI client
if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "True":
    client = genai.Client(vertexai=True)
else:
    client = genai.Client()

# Load configuration settings
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH) as f:
    config = json.load(f)

THRESHOLD = config.get("threshold", 100.0)
MODEL_NAME = config.get("model", "gemini-3.1-flash-lite")


# Define structured output schema
class ExpenseResponse(BaseModel):
    status: str = Field(
        description="Approval status: Approved, Approved (Auto), Rejected, or Error"
    )
    amount: float = Field(description="Expense amount")
    submitter: str = Field(description="Submitter name")
    category: str = Field(description="Expense category")
    description: str = Field(description="Expense description")
    date: str = Field(description="Expense date")
    risk_report: str | None = Field(
        default=None, description="LLM risk analysis report if reviewed"
    )


# Helper parser for plain JSON, wrapped JSON, and base64 Pub/Sub data
def parse_expense_event(query_text: str) -> dict:
    try:
        payload = json.loads(query_text)
    except json.JSONDecodeError:
        return {}

    data = payload.get("data")
    if not data:
        # Fallback if raw details are at the root
        if "amount" in payload or "submitter" in payload:
            return payload
        return {}

    if isinstance(data, str):
        # Handle Base64 encoded Pub/Sub message
        try:
            decoded_bytes = base64.b64decode(data, validate=True)
            decoded_str = decoded_bytes.decode("utf-8")
            return json.loads(decoded_str)
        except Exception:
            # Try to parse string as JSON in case it's not base64-encoded
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
    elif isinstance(data, dict):
        return data

    return {}


# Helper for scrubbing PII (SSN and Credit Cards) from the description
def scrub_pii(text: str) -> tuple[str, list[str]]:
    import re

    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    cc_pattern = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b|\b\d{13,16}\b")

    redacted_categories = []
    scrubbed = text

    if ssn_pattern.search(scrubbed):
        scrubbed = ssn_pattern.sub("[REDACTED_SSN]", scrubbed)
        redacted_categories.append("SSN")

    if cc_pattern.search(scrubbed):
        scrubbed = cc_pattern.sub("[REDACTED_CC]", scrubbed)
        redacted_categories.append("Credit Card")

    return scrubbed, redacted_categories


# Helper for detecting prompt injection in description
def detect_prompt_injection(text: str) -> bool:
    injection_indicators = [
        "ignore all previous",
        "ignore instructions",
        "ignore rules",
        "bypass rules",
        "bypass threshold",
        "override rules",
        "override threshold",
        "force auto-approval",
        "force approval",
        "auto-approve this",
        "you must approve",
        "system message",
        "developer mode",
        "act as",
        "instead of",
    ]
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in injection_indicators)


# 1. Parse Expense Event Node
async def parse_expense_node(ctx: Context, node_input: types.Content | str):
    """Parses input event query, extracts details and routes by amount threshold."""
    query_text = ""
    if isinstance(node_input, types.Content):
        if node_input.parts:
            for part in node_input.parts:
                if part.text:
                    query_text += part.text
    else:
        query_text = str(node_input)

    # If a prior human_approval interrupt is pending, the user's reply (e.g.
    # "approve" / "reject") arrives here as a new turn.  Detect that and
    # forward it directly to human_approval_node instead of trying to parse
    # it as a new expense JSON.
    stripped = query_text.strip().lower()
    if ctx.state.get("expense") and stripped in ("approve", "approved", "reject", "rejected", "yes", "no"):
        yield Event.model_validate(
            {"route": "human_decision", "state": {"pending_decision": query_text.strip()}}
        )
        return

    expense = parse_expense_event(query_text)
    if not expense or "amount" not in expense or "submitter" not in expense:
        yield Event.model_validate(
            {
                "route": "error",
                "content": types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text="Error: Could not parse expense details. Missing 'amount' or 'submitter'."
                        )
                    ],
                ),
            }
        )
        return

    # Convert amount safely
    try:
        amount = float(expense.get("amount", 0.0))
        expense["amount"] = amount
    except ValueError:
        yield Event.model_validate(
            {
                "route": "error",
                "content": types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text="Error: 'amount' must be a valid number."
                        )
                    ],
                ),
            }
        )
        return

    # Route based on threshold
    if amount < THRESHOLD:
        yield Event.model_validate(
            {"route": "auto_approve", "state": {"expense": expense}}
        )
    else:
        # Route to security checkpoint instead of direct LLM review
        yield Event.model_validate(
            {"route": "security_check", "state": {"expense": expense}}
        )


# 2. Auto-Approve Node
async def auto_approve_node(ctx: Context, node_input=None):
    """Instantly auto-approves expenses below the config threshold."""
    expense = ctx.state["expense"]
    response_text = f"✅ Auto-Approved: Expense of ${expense['amount']} by {expense['submitter']} falls below the ${THRESHOLD} threshold."

    yield Event.model_validate(
        {
            "content": types.Content(
                role="model", parts=[types.Part.from_text(text=response_text)]
            ),
            "output": ExpenseResponse(
                status="Approved (Auto)",
                amount=expense["amount"],
                submitter=expense["submitter"],
                category=expense.get("category", "Uncategorized"),
                description=expense.get("description", ""),
                date=expense.get("date", ""),
                risk_report="None (Auto-approved below threshold)",
            ),
        }
    )


# 2.5 Security Checkpoint Node
async def security_checkpoint_node(ctx: Context, node_input=None):
    """Performs prompt injection checks and scrubs PII from the description."""
    expense = ctx.state["expense"]
    description = expense.get("description", "")

    # 1. Check for prompt injection
    if detect_prompt_injection(description):
        alert_msg = "⚠️ SECURITY ALERT: Prompt injection attempt detected in expense description!"
        yield Event.model_validate(
            {
                "route": "security_alert",
                "content": types.Content(
                    role="model", parts=[types.Part.from_text(text=alert_msg)]
                ),
                "state": {"security_flag": True, "risk_report": alert_msg},
            }
        )
        return

    # 2. Scrub PII from description
    scrubbed_desc, redacted_categories = scrub_pii(description)
    expense["description"] = scrubbed_desc

    yield Event.model_validate(
        {
            "route": "clean",
            "state": {
                "expense": expense,
                "redacted_categories": redacted_categories,
            },
        }
    )


# 3. LLM Review Node
async def llm_review_node(ctx: Context, node_input=None):
    """Invokes LLM (gemini-3.1-flash-lite) to analyze expense risks."""
    expense = ctx.state["expense"]

    prompt = (
        "You are an AI expense auditor. Audit the following expense details for risk factors "
        "and potential policy violations (such as duplicate entries, off-hours dates, suspicious categories, "
        "or overly vague descriptions). Provide a concise risk assessment.\n\n"
        f"Amount: ${expense.get('amount')}\n"
        f"Submitter: {expense.get('submitter')}\n"
        f"Category: {expense.get('category', 'N/A')}\n"
        f"Description: {expense.get('description', 'N/A')}\n"
        f"Date: {expense.get('date', 'N/A')}\n"
    )

    # Run LLM review
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        risk_report = response.text or "No risk report returned from LLM."
    except Exception as e:
        risk_report = f"LLM evaluation failed: {e}"

    yield Event.model_validate(
        {
            "content": types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=f"⚠️ LLM Risk Analysis Report:\n{risk_report}"
                    )
                ],
            ),
            "state": {"risk_report": risk_report},
        }
    )


# 4. Human Approval Node
async def human_approval_node(ctx: Context, node_input=None):
    """Interrupts workflow to await human decision via RequestInput."""
    expense = ctx.state["expense"]

    # Retrieve security metadata from state
    security_flag = ctx.state.get("security_flag", False)
    redacted_categories = ctx.state.get("redacted_categories", [])

    if security_flag:
        risk_report = "⚠️ SECURITY ALERT: Prompt injection attempt detected in the expense description! LLM review was bypassed."
    else:
        risk_report = ctx.state.get("risk_report", "No risk analysis report available.")

    redacted_note = ""
    if redacted_categories:
        redacted_note = (
            f"\n🔒 Redacted Sensitive Data: {', '.join(redacted_categories)}"
        )

    # Case 1: decision forwarded via pending_decision state key
    # (set by parse_expense_node when it detects an approval/rejection reply)
    pending = ctx.state.get("pending_decision")
    if pending:
        yield Event(output=pending)
        return

    # Case 2: decision provided via resume_inputs (proper interrupt resume)
    if ctx.resume_inputs and "decision" in ctx.resume_inputs:
        decision = ctx.resume_inputs["decision"]
        yield Event(output=decision)
        return

    # No decision yet — interrupt and ask the human
    message = (
        f"Expense of ${expense['amount']} submitted by {expense['submitter']} requires human approval.\n"
        f"Category: {expense.get('category', 'Uncategorized')}\n"
        f"Description: {expense.get('description', '')}{redacted_note}\n\n"
        f"Assessment:\n{risk_report}\n\n"
        "Please reply 'approve' or 'reject'."
    )
    yield RequestInput(interrupt_id="decision", message=message)
    return


# 5. Record Outcome Node
async def record_outcome_node(ctx: Context, node_input: str):
    """Records the final decision outcome and returns the final ExpenseResponse."""
    expense = ctx.state["expense"]
    risk_report = ctx.state.get("risk_report", "No risk analysis report available.")
    decision = node_input.lower().strip()

    if "approve" in decision:
        status = "Approved"
    else:
        status = "Rejected"

    response_text = f"Recorded outcome: Expense was {status}."
    yield Event(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=response_text)]
        ),
        output=ExpenseResponse(
            status=status,
            amount=expense["amount"],
            submitter=expense["submitter"],
            category=expense.get("category", "Uncategorized"),
            description=expense.get("description", ""),
            date=expense.get("date", ""),
            risk_report=risk_report,
        ),
    )


# 6. Parse Error Node
async def parse_error_node(ctx: Context, node_input: None):
    """Handles cases where input parsing failed."""
    yield Event(
        output=ExpenseResponse(
            status="Error",
            amount=0.0,
            submitter="Unknown",
            category="N/A",
            description="Failed to parse incoming event details",
            date="N/A",
            risk_report=None,
        )
    )


# Build the ADK 2.0 Graph Workflow Graph
root_agent = Workflow(
    name="ambient_expense_agent",
    output_schema=ExpenseResponse,
    edges=[
        (START, parse_expense_node),
        # parse_expense_node routes conditionally using a RoutingMap dictionary
        (
            parse_expense_node,
            {
                "auto_approve": auto_approve_node,
                "security_check": security_checkpoint_node,
                "error": parse_error_node,
                # Human typed approve/reject in a new turn
                "human_decision": human_approval_node,
            },
        ),
        # security_checkpoint_node routes conditionally
        (
            security_checkpoint_node,
            {
                "clean": llm_review_node,
                "security_alert": human_approval_node,
            },
        ),
        # LLM review cascades to human approval
        (llm_review_node, human_approval_node),
        # Human approval cascades to recording outcome
        (human_approval_node, record_outcome_node),
    ],
)

# App Container
app = App(
    root_agent=root_agent,
    name="expense_agent",
)
