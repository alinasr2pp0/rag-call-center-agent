"""
Vonage Voice API adapter. Call flow uses NCCO (JSON) instead of Twilio's
TwiML (XML): Vonage fetches an NCCO array from our /webhooks/answer/{id}
when the call connects, and posts speech results to whatever eventUrl the
"input" action names (our /webhooks/gather/{id}).

Unlike Twilio's trial, which flatly blocks <Stream> and <Dial><Number>,
Vonage's trial restriction is destination-based (calls only reach your
registered number + up to 4 verified test numbers) — the "connect" action
used for live transfer below is not itself blocked, so a real transfer works
in trial as long as HUMAN_AGENT_TRANSFER_NUMBER is also a verified number.
"""
from vonage import Auth, Vonage
from vonage_voice.models.requests import CreateCallRequest, ToPhone
from vonage_voice.models.common import Phone
from vonage_voice.models.ncco import Talk, Input, Speech, Connect, PhoneEndpoint
from app.config import settings

_client: Vonage | None = None  # lazy-initialized — see _get_client()

SAY_LANGUAGE = "ar"         # Vonage <Talk> locale for Arabic TTS
GATHER_LANGUAGE = "ar-EG"   # Vonage ASR language for Egyptian Arabic


def _get_client() -> Vonage:
    """
    Built on first use rather than at import time: constructing Vonage(Auth(...))
    validates the private key immediately and raises if it's missing/malformed,
    which would otherwise crash the whole app at startup (this module is
    imported transitively by app.main) even for someone only testing the
    text-only KB flow before they've filled in Vonage credentials.
    """
    global _client
    if _client is None:
        _client = Vonage(Auth(application_id=settings.VONAGE_APPLICATION_ID, private_key=settings.VONAGE_PRIVATE_KEY))
    return _client


def _normalize_number(number: str) -> str:
    """Vonage wants digits only (no leading '+'), unlike Twilio's E.164-with-plus."""
    return number.lstrip("+").replace(" ", "").replace("-", "")


def place_outbound_call(to_number: str, call_id: str) -> str:
    request = CreateCallRequest(
        to=[ToPhone(number=_normalize_number(to_number))],
        from_=Phone(number=_normalize_number(settings.VONAGE_FROM_NUMBER)),
        answer_url=[f"{settings.PUBLIC_BASE_URL}/webhooks/answer/{call_id}"],
        answer_method="GET",
        event_url=[f"{settings.PUBLIC_BASE_URL}/webhooks/event/{call_id}"],
        event_method="POST",
    )
    response = _get_client().voice.create_call(request)
    return response.uuid


def build_gather_ncco(call_id: str, message_ar: str) -> list[dict]:
    """Speaks message_ar, then listens via Vonage's own ASR and POSTs the
    transcript to /webhooks/gather/{call_id}."""
    action_url = f"{settings.PUBLIC_BASE_URL}/webhooks/gather/{call_id}"
    actions = [
        Talk(text=message_ar, language=SAY_LANGUAGE),
        Input(
            type=["speech"],
            eventUrl=[action_url],
            eventMethod="POST",
            speech=Speech(language=GATHER_LANGUAGE, endOnSilence=1.5),
        ),
    ]
    return [a.model_dump(mode="json", exclude_none=True, by_alias=True) for a in actions]


def build_say_hangup_ncco(message_ar: str) -> list[dict]:
    """Speaks a final message; Vonage ends the call once the NCCO runs out
    of actions (no explicit hangup action needed)."""
    return [Talk(text=message_ar, language=SAY_LANGUAGE).model_dump(mode="json", exclude_none=True, by_alias=True)]


def build_transfer_ncco(message_ar: str) -> list[dict]:
    """Speaks a short message, then live-connects the call to the human
    agent line via a 'connect' action — a real transfer, not just a message
    (see the trial-restriction note in the module docstring)."""
    actions = [
        Talk(text=message_ar, language=SAY_LANGUAGE),
        Connect(
            endpoint=[PhoneEndpoint(number=_normalize_number(settings.HUMAN_AGENT_TRANSFER_NUMBER))],
            from_=_normalize_number(settings.VONAGE_FROM_NUMBER),
        ),
    ]
    return [a.model_dump(mode="json", exclude_none=True, by_alias=True) for a in actions]
