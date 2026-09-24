import json
import httpx
from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

KB_SYSTEM_PROMPT = """أنت وكيل دعم فني يرد بالعربية على مشاكل العملاء اعتمادًا فقط على المقاطع
المرجعية المرفقة من قاعدة المعرفة. أرجع النتيجة بصيغة JSON فقط بهذا الشكل:
{"answer": "...", "confidence": 0.0-1.0, "kb_article_id": "..."}
لو المقاطع لا تكفي لحل المشكلة، ضع confidence أقل من 0.5."""

WEB_SYSTEM_PROMPT = """أنت وكيل دعم فني يرد بالعربية بناءً فقط على نتائج البحث المرفقة.
لخّص حلاً عمليًا وواضحًا للعميل. لو النتائج غير كافية، قل ذلك صراحة."""


async def generate_kb_answer(question_ar: str, retrieved: list[dict]) -> dict:
    context = "\n\n".join(
        f"[{c['kb_article_id']}] {c['text']}\nالحل: {c['solution_text']}" for c in retrieved
    )
    user_prompt = f"مشكلة العميل: {question_ar}\n\nمقاطع مرجعية:\n{context}"
    raw = await _call_llm(KB_SYSTEM_PROMPT, user_prompt, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"answer": raw, "confidence": 0.3, "kb_article_id": None}


async def generate_web_answer(question_ar: str, web_results: list[dict]) -> str:
    context = "\n\n".join(f"[{r['url']}]\n{r['content']}" for r in web_results)
    user_prompt = f"مشكلة العميل: {question_ar}\n\nنتائج البحث:\n{context}"
    return await _call_llm(WEB_SYSTEM_PROMPT, user_prompt, json_mode=False)


async def classify_call_response(customer_text_ar: str) -> str:
    """Returns 'resolved' or 'unresolved' based on what the customer said on the confirmation call."""
    system = """صنّف رد العميل إلى resolved أو unresolved فقط، بدون أي شرح إضافي."""
    raw = await _call_llm(system, customer_text_ar, json_mode=False)
    return "resolved" if "resolved" in raw.lower() else "unresolved"


async def _call_llm(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    models = [settings.LLM_MODEL_PRIMARY, *settings.LLM_MODEL_FALLBACKS]
    last_error = None
    for model in models:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - deliberate fallback chain
            last_error = e
            continue
    raise RuntimeError(f"All LLM fallbacks failed: {last_error}")
