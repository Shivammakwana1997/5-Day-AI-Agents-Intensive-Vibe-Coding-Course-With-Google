# ruff: noqa
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

import os
import google.auth
from google.auth.exceptions import DefaultCredentialsError

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
except DefaultCredentialsError:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

from google.adk.workflow import Workflow, START
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.agents.context import Context
from google.genai import types
from pydantic import BaseModel, Field


# 1. Define Pydantic schema for classification output
class Classification(BaseModel):
    is_shipping_related: bool = Field(
        description="True if the user query is related to shipping (such as rates, tracking, delivery, or returns). False otherwise."
    )


# 2. Node to save original query to state so we can access it downstream
def save_query(ctx: Context, node_input: types.Content) -> Event:
    text = ""
    if node_input.parts:
        text = node_input.parts[0].text
    return Event(output=text, actions=EventActions(state_delta={"user_query": text}))


# 3. Classifier LLM Agent Node
classifier_agent = LlmAgent(
    name="classifier_agent",
    model=Gemini(
        model="gemini-3.1-flash-lite",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an expert customer support router. Classify if the user query is related "
        "to shipping (rates, tracking, delivery, returns) or unrelated. "
        "Provide structured output matching the Classification schema."
    ),
    output_schema=Classification,
)


# 4. Router Node to direct flow based on classification result
def route_query(ctx: Context, node_input: dict) -> Event:
    is_shipping = node_input.get("is_shipping_related", False)
    route = "shipping" if is_shipping else "unrelated"
    original_query = ctx.state.get("user_query", "")
    return Event(output=original_query, actions=EventActions(route=route))


# 5. Shipping FAQ Agent (when query is related to shipping)
shipping_faq_agent = LlmAgent(
    name="shipping_faq_agent",
    model=Gemini(
        model="gemini-3.1-flash-lite",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an enthusiastic and playful customer support representative for a shipping company! 🚚✨ "
        "Answer the user's inquiry regarding shipping rates, tracking, delivery, or returns with high energy, "
        "playful tone, and lots of emojis! 🎉 Crucially, always highlight that we offer FREE shipping on orders "
        "over $50! 🤩💸"
    ),
)


# 6. Decline Node (when query is unrelated to shipping)
def decline_answer(node_input: str):
    response = (
        "I apologize, but I am only able to assist with shipping-related inquiries "
        "such as rates, tracking, delivery, and returns. How else can I help you with your shipping needs?"
    )
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=response)])
    )
    yield Event(output=response)


# 7. Define the overall workflow graph using RoutingMap (dict) for conditional edges
root_agent = Workflow(
    name="customer_support_workflow",
    edges=[
        (START, save_query),
        (save_query, classifier_agent),
        (classifier_agent, route_query),
        (route_query, {"shipping": shipping_faq_agent, "unrelated": decline_answer}),
    ],
    description="A customer support routing workflow for a shipping company.",
)

# 8. Create the App
app = App(
    root_agent=root_agent,
    name="app",
)
