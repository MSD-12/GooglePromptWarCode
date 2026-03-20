"""
Poison Guard — MCP Server for Google Cloud Run

Transport: SSE (Server-Sent Events) over HTTP — required for Cloud Run.
Clients connect via:  https://<your-cloud-run-url>/sse
"""

import os
import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from google import genai
from google.genai import types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import uvicorn

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poison-guard-mcp")

# ── Gemini Config ─────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")
client = genai.Client(api_key=GEMINI_API_KEY)

# ── System Prompt (same as Streamlit app) ─────────────────────────────────────
SYSTEM_PROMPT = """You are 'Poison Guard', a highly advanced AI system with two distinct personas:
1. Emergency Mode (Poison Control Specialist): When the user input describes a potential poisoning, immediate threat, or panic, act authoritatively and clearly. Identify the threat and prioritize first aid.
2. Educational Mode (Health Educator): When the user is asking general questions, exploring potential household hazards, or inquiring about toxicity profiles, provide detailed, informative, and preventative advice.

Analyze the given text carefully.

You MUST respond strictly in the following JSON schema:
{
  "mode": "EMERGENCY" or "EDUCATION",
  "identified_threat": "Name of the substance, plant, pest, or product",
  "toxicity_level": "None", "Mild", "Moderate", "Severe", or "Lethal",
  "first_aid_steps": ["Step 1", "Step 2", ...],
  "urgency": "Low", "Medium", "High", or "Critical",
  "call_911": true or false,
  "educational_info": {
     "common_names": "Common names",
     "toxicity_to_groups": "Information regarding pets, children, adults",
     "preventative_measures": "How to prevent exposure",
     "symptoms_to_watch": ["Symptom 1", "Symptom 2", ...]
  }
}
If a field is not applicable based on the mode, provide an empty string or empty list, but DO NOT OMIT the key. Do not provide any markdown formatting around the JSON, just output the raw JSON string.
"""

# ── MCP Server Setup ──────────────────────────────────────────────────────────
mcp_server = Server("poison-guard")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Declare the tools exposed by this MCP server."""
    return [
        Tool(
            name="analyze_poison",
            description=(
                "Analyzes a text description of a potentially poisonous substance, "
                "plant, chemical, or exposure scenario. Returns structured JSON with "
                "the identified threat, toxicity level, urgency, first-aid steps, "
                "and educational information. Automatically switches between "
                "EMERGENCY and EDUCATION modes based on the severity of input."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": (
                            "Text description of the substance, exposure, or question. "
                            "Examples: 'my dog ate a mushroom from the garden', "
                            "'what is the toxicity of bleach', "
                            "'child swallowed cleaning product — help!'"
                        ),
                    }
                },
                "required": ["description"],
            },
        ),
        Tool(
            name="get_first_aid",
            description=(
                "Quick first-aid lookup for a named poisonous substance or chemical. "
                "Returns only the immediate first-aid steps and whether to call 911."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "substance": {
                        "type": "string",
                        "description": "Name of the substance e.g. 'bleach', 'acetaminophen', 'oleander'",
                    }
                },
                "required": ["substance"],
            },
        ),
        Tool(
            name="toxicity_profile",
            description=(
                "Returns a comprehensive toxicity profile for a given substance, "
                "including effects on different population groups (children, adults, pets), "
                "common names, symptoms, and preventative measures."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "substance": {
                        "type": "string",
                        "description": "Name of the substance to profile",
                    }
                },
                "required": ["substance"],
            },
        ),
    ]


async def _call_gemini(prompt: str) -> dict:
    """Call Gemini and parse its JSON response."""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route and execute tool calls."""
    logger.info("Tool called: %s with args: %s", name, arguments)

    try:
        if name == "analyze_poison":
            description = arguments.get("description", "")
            if not description:
                raise ValueError("'description' argument is required.")
            result = await _call_gemini(description)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_first_aid":
            substance = arguments.get("substance", "")
            if not substance:
                raise ValueError("'substance' argument is required.")
            prompt = (
                f"Provide EMERGENCY first-aid steps for exposure to: {substance}. "
                "Focus ONLY on immediate actions and whether to call 911."
            )
            result = await _call_gemini(prompt)
            summary = {
                "substance": result.get("identified_threat", substance),
                "call_911": result.get("call_911", False),
                "urgency": result.get("urgency", "Unknown"),
                "first_aid_steps": result.get("first_aid_steps", []),
            }
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        elif name == "toxicity_profile":
            substance = arguments.get("substance", "")
            if not substance:
                raise ValueError("'substance' argument is required.")
            prompt = (
                f"Provide a detailed EDUCATIONAL toxicity profile for: {substance}. "
                "Include effects on all population groups, common names, symptoms, and prevention."
            )
            result = await _call_gemini(prompt)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as exc:
        logger.error("Error in tool %s: %s", name, exc, exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


# ── Starlette App with SSE Transport ─────────────────────────────────────────
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    """Handle incoming SSE connections from MCP clients."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options(),
        )


async def health(request: Request):
    """Health check endpoint required by Cloud Run."""
    return JSONResponse({"status": "ok", "service": "poison-guard-mcp"})


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/sse", handle_sse),
        Mount("/messages/", app=sse_transport.handle_post_message),
    ]
)

# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting Poison Guard MCP server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
