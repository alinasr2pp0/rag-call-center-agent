"""
Customer identity via Vonage Verify (OTP over SMS) — lets a customer log in
with just their phone number to see their own ticket history, no password.
Uses the same Vonage Application (VONAGE_APPLICATION_ID/PRIVATE_KEY) as
telephony.py; make sure "Verify" is enabled as a capability on that
Application in the Vonage dashboard, not just "Voice".
"""
from vonage import Auth, Vonage
from vonage_verify.requests import VerifyRequest
from vonage_verify import SmsChannel
from app.config import settings

_client: Vonage | None = None


def _get_client() -> Vonage:
    global _client
    if _client is None:
        _client = Vonage(Auth(application_id=settings.VONAGE_APPLICATION_ID, private_key=settings.VONAGE_PRIVATE_KEY))
    return _client


def _normalize_number(number: str) -> str:
    return number.lstrip("+").replace(" ", "").replace("-", "")


def start_verification(phone: str) -> str:
    """Sends an SMS OTP, returns the request_id needed to check the code."""
    request = VerifyRequest(
        brand="RAG Call Center",
        workflow=[SmsChannel(to=_normalize_number(phone))],
    )
    response = _get_client().verify.start_verification(request)
    return response.request_id


def check_verification(request_id: str, code: str) -> bool:
    """Returns True if the code is correct. Vonage raises on an invalid/expired code."""
    try:
        response = _get_client().verify.check_code(request_id, code)
        return response.status == "completed"
    except Exception:
        return False
