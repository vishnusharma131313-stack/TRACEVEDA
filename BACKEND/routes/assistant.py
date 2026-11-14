"""Public TraceVeda website assistant. It cannot perform privileged actions."""

from datetime import datetime, timedelta, timezone
import secrets
import logging

from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import settings
from database import db

router = APIRouter(prefix="/api/assistant", tags=["Public Assistant"])
logger = logging.getLogger(__name__)

WELCOME = (
    "Welcome to TraceVeda! I can explain the website, its supply-chain modules, "
    "and help you request an organisation account. Ask me anything, or choose "
    "‘Request an account’ below. / TraceVeda mein aapka swagat hai!"
)

SYSTEM_PROMPT = """You are TraceVeda Assistant, the public website guide for TraceVeda.

TRUSTED WEBSITE KNOWLEDGE:
- TraceVeda is an Ayurvedic supply-chain traceability platform. Its intended
  journey covers farm/raw-material collection, processing, laboratory quality
  testing, medicine manufacturing, storage, transportation and consumer QR
  verification.
- The current website includes role-based workspaces for Farmer, Processor,
  Laboratory, Manufacturer, Transporter/Logistics, Auditor/Regulator, Consumer
  and Administrator. Public account requests are available for Farmer,
  Processor, Laboratory, Manufacturer, Transporter and Auditor. Admin access
  is never self-requested and is provisioned internally.
- Existing platform areas include batch records, laboratory testing, medicine
  batch/QR verification, IoT readings, truck/transport events, storage events,
  forward/reverse traceability, blockchain event verification, consumer reports
  and investigations, plus admin user and access-request management.
- IoT and blockchain views show records supplied to the platform; do not claim
  that a sensor is currently online or that a batch is safe unless the system
  explicitly provides that fact to the visitor. This public assistant has no
  access to private account data, live telemetry, private batch records, or
  admin actions.

BEHAVIOUR AND SAFETY:
- Answer questions about the website using only the trusted knowledge above.
  Do not invent features, routes, regulatory certifications, uptime, or data.
- Explain unknown or role-restricted features honestly and direct the visitor
  to sign in or request the relevant role when appropriate.
- If asked to register, explain that the visitor can use the Request an account
  action in this chat. The visitor provides email and phone details for manual
  administrator contact only; neither is verified and no email/SMS is sent.
  The applicant receives a one-time recovery code to track the application and
  activate the approved account. Administrator approval is mandatory and not
  guaranteed.
- Match the user's language and style: English, Hindi or Hinglish. Keep answers
  clear, friendly and concise.
- Never ask for passwords, OTPs, API keys, payment details or identity secrets.
  The separate secure application workflow collects only the information it
  needs; never process its details as a general chat message.
- You cannot create accounts, approve requests, change roles, alter records,
  access user data or bypass authentication. Never claim that you have done so.
- Do not give medical advice or certify that a medicine is safe for consumption.
"""


class AssistantChatRequest(BaseModel):
    session_id: str = Field(min_length=24, max_length=128)
    message: str = Field(min_length=1, max_length=1200)


def _fallback_answer(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ("blockchain", "hash", "ledger", "ब्लॉकचेन")):
        return ("TraceVeda records selected supply-chain events in a SHA-256 hash-chain ledger. "
                "The blockchain area lets authorised users review events and verify chain integrity. "
                "/ TraceVeda selected events ko hash-chain mein record karta hai.")
    if any(word in text for word in ("iot", "sensor", "temperature", "humidity", "truck", "storage", "gps")):
        return ("TraceVeda has IoT monitoring areas for sensor readings, transport and storage events. "
                "Authorised users can review the records available to their workspace. I cannot see live device status in this public chat.")
    if any(word in text for word in ("lab", "laboratory", "quality", "test", "लैब")):
        return ("The Laboratory workspace is intended for quality testing and verification records associated with batches. "
                "A laboratory organisation can request access through this assistant.")
    if any(word in text for word in ("manufacturer", "manufacturing", "medicine batch")):
        return ("The Manufacturer workspace supports medicine and batch-related workflow areas. "
                "A manufacturer can request access through this assistant; an administrator reviews every application.")
    if any(word in text for word in ("transport", "transporter", "logistics", "truck")):
        return ("The Transporter/Logistics workspace covers transport events and available truck telemetry. "
                "Transport organisations can request access using the Request an account action.")
    if any(word in text for word in ("auditor", "audit", "regulator", "investigation")):
        return ("The Auditor/Regulator workspace supports compliance review, traceability checks and investigation workflows. "
                "Auditor access requires an administrator-approved request.")
    if any(word in text for word in ("qr", "consumer", "verify medicine", "authenticity")):
        return ("Consumers can use the public medicine QR verification experience to view the traceability information made available for a product. "
                "A QR result is a platform record, not medical advice or a safety guarantee.")
    return ("I can explain TraceVeda's batch traceability, laboratory, manufacturing, transport, storage, IoT, "
            "blockchain-verification and consumer QR areas. You can also request a Farmer, Processor, Laboratory, "
            "Manufacturer, Transporter or Auditor account here. Applicants provide email and phone for administrator contact; no OTP or email is sent. If the AI service is not configured yet, some answers may be limited.")


def _gemini_answer(messages: list[dict]) -> str:
    """Generate a public-assistant reply with the Gemini Developer API."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    # Gemini uses "model" for assistant turns. Keep the last 16 transcript
    # entries and pass the trusted website prompt separately as system input.
    contents = []
    for item in messages[-16:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        contents.append({
            "role": "user" if role == "user" else "model",
            "parts": [{"text": content}],
        })

    if not contents:
        raise RuntimeError("No valid conversation messages were provided")

    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=25_000),
    )
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=600,
        ),
    )

    answer = (response.text or "").strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty response")
    return answer[:5000]


@router.post("/session", status_code=201)
def create_assistant_session():
    now = datetime.now(timezone.utc)
    session_id = secrets.token_urlsafe(36)
    expires_at = now + timedelta(days=settings.assistant_session_days)
    db.assistant_conversations.insert_one({
        "session_id": session_id,
        "messages": [],
        "message_count": 0,
        "rate_window_started_at": now,
        "rate_window_count": 0,
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
    })
    return {"session_id": session_id, "expires_at": expires_at, "retention_days": settings.assistant_session_days}


@router.get("/session/{session_id}")
def get_assistant_session(session_id: str):
    session = db.assistant_conversations.find_one({"session_id": session_id}, {"_id": 0})
    if not session or session.get("expires_at") <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Assistant session expired. Start a new conversation.")
    return {
        "session_id": session_id,
        "messages": session.get("messages", []),
        "expires_at": session.get("expires_at"),
    }


@router.delete("/session/{session_id}", status_code=204)
def delete_assistant_session(session_id: str):
    """Delete the anonymous conversation when the visitor starts a new chat."""
    db.assistant_conversations.delete_one({"session_id": session_id})
    return None


@router.post("/chat")
def chat(data: AssistantChatRequest):
    text = data.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Please enter a message.")
    now = datetime.now(timezone.utc)
    session = db.assistant_conversations.find_one({"session_id": data.session_id})
    if not session or session.get("expires_at") <= now:
        raise HTTPException(status_code=404, detail="Assistant session expired. Start a new conversation.")

    window_started = session.get("rate_window_started_at") or now
    window_count = int(session.get("rate_window_count", 0))
    if now - window_started >= timedelta(hours=1):
        window_started, window_count = now, 0
    if window_count >= 40:
        raise HTTPException(status_code=429, detail="This chat has reached its hourly message limit. Please try again later.")

    history = session.get("messages", [])
    conversation_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in history[-16:]
        if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)
    ]
    conversation_messages.append({"role": "user", "content": text})
    provider = "gemini"
    try:
        reply = _gemini_answer(conversation_messages)
    except Exception as error:
        # The website guide remains useful during initial setup or a temporary
        # provider outage. Do not expose provider errors or secrets to visitors.
        logger.warning("Assistant provider unavailable (%s); using FAQ fallback", type(error).__name__)
        provider = "fallback"
        reply = _fallback_answer(text)

    new_messages = [
        {"role": "user", "content": text, "created_at": now},
        {"role": "assistant", "content": reply, "created_at": now},
    ]
    db.assistant_conversations.update_one(
        {"session_id": data.session_id},
        {
            "$push": {"messages": {"$each": new_messages, "$slice": -40}},
            "$set": {
                "updated_at": now,
                "expires_at": now + timedelta(days=settings.assistant_session_days),
                "rate_window_started_at": window_started,
                "rate_window_count": window_count + 1,
            },
            "$inc": {"message_count": 1},
        },
    )
    return {"reply": reply, "provider": provider}
