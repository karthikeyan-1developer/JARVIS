import os
import asyncio
import contextlib
import logging
from typing import Any, Optional, List

from dotenv import load_dotenv
from livekit.agents import AgentSession, Agent
from livekit.plugins import google
from prompt import AGENT_INSTRUCTION, AGENT_RESPONSE

# Text fallback SDK
import google.generativeai as genai

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


GOOGLE_API_KEY = _require_env("GOOGLE_API_KEY")

# Configure Google text SDK (non-realtime fallback)
genai.configure(api_key=GOOGLE_API_KEY)
_TEXT_MODEL_NAME = "gemini-1.5-flash"  # fast, reliable text generation


def _message_text_from_item(item: Any) -> Optional[str]:
    """
    Extract plain text from a chat item object.
    Prefers item.content as a list of strings (observed shape), with fallbacks.
    """
    # 1) content: list[str]
    content = getattr(item, "content", None)
    if isinstance(content, list):
        chunks = [c for c in content if isinstance(c, str) and c.strip()]
        if chunks:
            return "".join(chunks).strip().rstrip("\n")

    # 2) direct string fields
    for attr in ("text", "content"):
        v = getattr(item, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 3) parts: list[str|dict{text|content}]
    parts = getattr(item, "parts", None)
    if isinstance(parts, list):
        texts: List[str] = []
        for p in parts:
            if isinstance(p, str) and p.strip():
                texts.append(p.strip())
            elif isinstance(p, dict):
                t = p.get("text") or p.get("content")
                if isinstance(t, str) and t.strip():
                    texts.append(t.strip())
        if texts:
            return " ".join(texts).strip().rstrip("\n")

    # 4) readable string fallback
    try:
        s = str(item)
        if s and s != object.__repr__(item):
            return s
    except Exception:
        pass

    return None


def _extract_from_chat_items_list(items: List[Any]) -> Optional[str]:
    """
    From a list of chat items, prefer the last assistant-like message,
    else use the last item.
    """
    if not items:
        return None

    last_assistant = None
    for it in items:
        role = getattr(it, "role", None) or getattr(it, "speaker", None)
        if isinstance(role, str) and role.lower() in ("assistant", "ai", "agent", "jarvis"):
            last_assistant = it

    target = last_assistant or items[-1]
    return _message_text_from_item(target)


async def _finalize_and_extract(speech_handle: Any) -> Optional[str]:
    """
    Wait for generation to finalize (when possible), then extract plain text
    from chat_items (property or callable depending on build).
    """
    # Try completion signals if present
    for wait_call, timeout in (("done", 10), ("wait_for_playout", 8)):
        if hasattr(speech_handle, wait_call):
            with contextlib.suppress(Exception):
                await asyncio.wait_for(getattr(speech_handle, wait_call)(), timeout=timeout)

    # Access chat_items as property (list) first, then callable fallback
    items = None
    try:
        ci = getattr(speech_handle, "chat_items", None)
        if isinstance(ci, list):
            items = ci
        elif callable(ci):
            items = ci()
    except Exception as e:
        logger.debug("accessing chat_items failed: %s", e)

    if isinstance(items, list) and items:
        text = _extract_from_chat_items_list(items)
        if text and isinstance(text, str) and text.strip():
            return text.strip().rstrip("\n")

    # One more attempt if callable exists
    try:
        ci_callable = getattr(speech_handle, "chat_items", None)
        if callable(ci_callable):
            items2 = ci_callable()
            if isinstance(items2, list) and items2:
                text = _extract_from_chat_items_list(items2)
                if text and text.strip():
                    return text.strip().rstrip("\n")
    except Exception:
        pass

    return None


async def _generate_text_direct(prompt: str, system_instruction: str) -> str:
    """
    Generate plain text using a stable text-first Gemini model.
    Runs in a thread to avoid blocking the event loop.
    """
    def _run():
        model = genai.GenerativeModel(
            model_name=_TEXT_MODEL_NAME,
            system_instruction=system_instruction,
        )
        resp = model.generate_content(prompt)
        return (getattr(resp, "text", "") or "").strip()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run)


def _is_quota_or_connection_error(msg: str) -> bool:
    m = msg.lower()
    return (
        "quota" in m
        or "billing" in m
        or "failed to connect" in m
        or "connection" in m
        or "realtime" in m and "error" in m
    )


async def get_jarvis_response(message: str) -> str:
    """
    Try realtime first (for low latency/voice-enabled setups), but ALWAYS
    provide a reliable text response: fall back to text-only generation
    when realtime fails (quota/billing/connection).
    Returns: plain text (no prefix).
    """
    combined_instructions = f"{AGENT_INSTRUCTION.strip()}\n\nResponse style:\n{AGENT_RESPONSE.strip()}"

    # Text-oriented realtime model: omit voice so chat_items populate more reliably.
    # If you need server-side voice, uncomment voice="Puck", but text may be less reliable.
    rt_model = google.beta.realtime.RealtimeModel(
        model="gemini-2.0-flash-exp",
        api_key=GOOGLE_API_KEY,
        # voice="Puck",  # optional; keep commented to favor text transcripts
        temperature=0.8,
        instructions=combined_instructions,
    )

    session = AgentSession(llm=rt_model)
    agent = Agent(instructions=combined_instructions)

    try:
        await session.start(agent=agent)

        # Launch both in parallel: realtime and text fallback
        rt_task = asyncio.create_task(
            asyncio.wait_for(session.generate_reply(instructions=message), timeout=30)
        )
        text_task = asyncio.create_task(
            asyncio.wait_for(_generate_text_direct(message, combined_instructions), timeout=20)
        )

        # Wait for first result
        done, pending = await asyncio.wait({rt_task, text_task}, return_when=asyncio.FIRST_COMPLETED)

        # Prefer direct text if it’s ready
        text_reply = ""
        if text_task in done:
            try:
                text_reply = text_task.result() or ""
            except Exception:
                text_reply = ""
        else:
            # Give text a brief grace period
            try:
                text_reply = await asyncio.wait_for(text_task, timeout=2)
            except Exception:
                text_reply = ""

        # Try realtime extraction
        realtime_text = ""
        if rt_task in done:
            try:
                speech_handle = rt_task.result()
                realtime_text = await _finalize_and_extract(speech_handle) or ""
            except Exception as e:
                # If quota/connection error on realtime, ignore here (text fallback likely succeeded)
                logger.debug("Realtime extraction error: %s", e)
        else:
            # Give realtime a brief grace period
            try:
                speech_handle = await asyncio.wait_for(rt_task, timeout=2)
                realtime_text = await _finalize_and_extract(speech_handle) or ""
            except Exception:
                realtime_text = ""

        # Decision: return the most reliable available text
        if text_reply:
            return text_reply
        if realtime_text:
            return realtime_text

        # If neither produced text, return a clear message
        return "(No assistant text found)"

    except Exception as e:
        msg = str(e)
        logger.error("Realtime error: %s", msg)

        # If realtime failed due to quota/connection, try a direct text call as a fallback
        if _is_quota_or_connection_error(msg):
            try:
                fallback_text = await asyncio.wait_for(
                    _generate_text_direct(message, combined_instructions), timeout=20
                )
                if fallback_text:
                    return fallback_text
            except Exception as e2:
                logger.error("Text fallback also failed: %s", e2)
            # Final clear messages
            if "quota" in msg.lower() or "billing" in msg.lower():
                return "(Temporarily unavailable: model quota exceeded. Check plan/billing.)"
            return "(Service connection issue to Gemini Live. Please retry shortly.)"

        # Generic failure
        return f"(Error: {e})"

    finally:
        with contextlib.suppress(Exception):
            await session.stop()
