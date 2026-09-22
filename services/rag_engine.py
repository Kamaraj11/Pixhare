"""
services/rag_engine.py — Retrieval-Augmented Generation chat engine.

Builds a rich context from:
  - Event metadata (name, date, venue, photo count)
  - Guest info (name, matched photo count)
  - Recent matched photo filenames

Then calls Groq LLM (llama-3.3-70b-versatile by default) with the
context + user question to produce a helpful, photo-aware answer.

Falls back gracefully when:
  - LLM_API_KEY is not set (returns context-only summary)
  - Groq API call fails (returns error message)

Public API:
    build_context(event_name, guest_name)  → str
    ask(event_name, guest_name, question)  → str
"""

from utils.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────

def build_context(event_name: str, guest_name: str) -> str:
    """
    Build a text context block from the database for the given event and guest.

    Args:
        event_name: Name of the event.
        guest_name: Name of the guest (used to find their gallery).

    Returns:
        Multi-line string describing the event, guest, and their photos.
    """
    from models.event import Event          # noqa: PLC0415
    from models.photo import EventPhoto     # noqa: PLC0415
    from models.user import Guest           # noqa: PLC0415

    lines = ["=== Pixhare Context ==="]

    # Event info
    event = Event.query.filter_by(name=event_name).first()
    if event:
        lines.append(f"Event: {event.name}")
        lines.append(f"Date: {event.date}")
        if event.venue:
            lines.append(f"Venue: {event.venue}")
        if event.event_time:
            lines.append(f"Time: {event.event_time}")
        if event.description:
            lines.append(f"Description: {event.description}")
        lines.append(f"Total photos uploaded: {event.photo_count}")
    else:
        lines.append(f"Event: {event_name} (details not found)")

    lines.append("")

    # Guest info + matched photos
    guest = Guest.query.filter_by(
        event_name=event_name, name=guest_name
    ).order_by(Guest.registered_at.desc()).first()

    if guest:
        lines.append(f"Guest: {guest.name} ({guest.email})")
        lines.append(f"Registered at: {guest.registered_at.isoformat() if guest.registered_at else 'unknown'}")
        lines.append(f"Photos emailed: {guest.last_emailed_photo_count}")
        lines.append(f"Gallery link: {_gallery_url(guest.gallery_token)}")
    else:
        lines.append(f"Guest '{guest_name}' not found for this event.")

    lines.append("")

    # Recent matched photos
    photos = EventPhoto.query.filter_by(
        event_name=event_name, matched=True
    ).order_by(EventPhoto.uploaded_at.desc()).limit(20).all()

    if photos:
        lines.append(f"Recent processed photos ({len(photos)}):")
        for p in photos[:10]:
            lines.append(f"  - {p.filename} (status: {p.upload_status})")
    else:
        lines.append("No processed photos found for this event yet.")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# LLM call
# ─────────────────────────────────────────────────────────────

def ask(event_name: str, guest_name: str, question: str) -> str:
    """
    Answer a guest's question about their event photos using Groq LLM.

    Args:
        event_name: Event the guest attended.
        guest_name: Guest's name.
        question:   The guest's question in natural language.

    Returns:
        Answer string from the LLM, or a fallback message.
    """
    from config import Config  # noqa: PLC0415

    context = build_context(event_name, guest_name)

    if not Config.LLM_API_KEY or Config.LLM_PROVIDER == "none":
        log.info("LLM_API_KEY not set — returning context summary.")
        return (
            f"I can see the following about your event:\n\n{context}\n\n"
            "(AI answers are disabled. Set LLM_API_KEY in your .env to enable them.)"
        )

    system_prompt = (
        "You are Pixhare AI, a friendly assistant for event photography. "
        "You help guests find their photos and answer questions about events. "
        "Be concise, warm, and helpful. Use the context provided.\n\n"
        f"Context:\n{context}"
    )

    try:
        if Config.LLM_PROVIDER == "groq":
            return _call_groq(system_prompt, question)
        elif Config.LLM_PROVIDER == "openai":
            return _call_openai(system_prompt, question)
        else:
            return f"Unknown LLM provider: {Config.LLM_PROVIDER}"
    except Exception as exc:
        log.error("LLM call failed: %s", exc)
        return "Sorry, I'm having trouble connecting to the AI service right now. Please try again later."


def _call_groq(system_prompt: str, user_message: str) -> str:
    from config import Config  # noqa: PLC0415
    from groq import Groq      # noqa: PLC0415

    client = Groq(api_key=Config.LLM_API_KEY)
    response = client.chat.completions.create(
        model       = Config.LLM_MODEL,
        messages    = [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_message},
        ],
        max_tokens  = Config.LLM_MAX_TOKENS,
        temperature = Config.LLM_TEMPERATURE,
    )
    answer = response.choices[0].message.content.strip()
    log.debug("Groq answer (%d chars)", len(answer))
    return answer


def _call_openai(system_prompt: str, user_message: str) -> str:
    from config import Config   # noqa: PLC0415
    import openai               # noqa: PLC0415

    openai.api_key = Config.LLM_API_KEY
    response = openai.chat.completions.create(
        model    = Config.LLM_MODEL,
        messages = [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_message},
        ],
        max_tokens  = Config.LLM_MAX_TOKENS,
        temperature = Config.LLM_TEMPERATURE,
    )
    return response.choices[0].message.content.strip()


def _gallery_url(token: str) -> str:
    from config import Config  # noqa: PLC0415
    return f"{Config.BASE_URL}/gallery/{token}" if token else "N/A"
