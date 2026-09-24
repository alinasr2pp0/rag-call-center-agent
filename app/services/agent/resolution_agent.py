"""
Central resolution logic, used both for the first text reply and for every
retry during the confirmation call. Attempt number decides the strategy:
  1 -> narrow KB retrieval (high confidence only)
  2 -> broad KB retrieval (wider net, lower threshold)
  3 -> web search (Tavily) synthesis
  >3 -> caller should escalate to a human agent instead of calling this again
"""
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import Ticket, Resolution, WebSearchLog
from app.services.rag.embeddings import embed_texts
from app.services.rag.vectorstore import query_kb
from app.services.rag import llm, web_search


@dataclass
class ResolutionResult:
    answer_text: str
    source: str  # 'kb' | 'web_search'
    confidence: float
    should_escalate: bool
    resolution_id: str | None = None
    kb_article_id: str | None = None
    web_search_log_id: str | None = None
    category: str | None = None


async def attempt_resolution(db: AsyncSession, ticket: Ticket, problem_text: str) -> ResolutionResult:
    """
    Tries strategies in order (narrow KB -> broad KB -> web search) within
    this single call, advancing automatically past any strategy that comes
    back with nothing to say (e.g. zero KB matches) instead of surfacing an
    empty answer to the caller. Without this loop, a single empty KB result
    would look identical to "should escalate" to the caller and skip
    straight past the remaining strategies (including web search) — this
    was a real bug in the first version of this function.

    Only returns should_escalate=True once every strategy up to
    MAX_RESOLUTION_ATTEMPTS has actually been tried and none produced an
    answer, or the final attempt's answer came back low-confidence.
    """
    result: ResolutionResult | None = None

    while ticket.resolution_attempts < settings.MAX_RESOLUTION_ATTEMPTS:
        attempt_number = ticket.resolution_attempts + 1

        if attempt_number == 1:
            result = await _try_kb(problem_text, k=5, min_score=0.75)
        elif attempt_number == 2:
            result = await _try_kb(problem_text, k=10, min_score=0.55)
        else:  # attempt 3
            result = await _try_web_search(db, ticket, problem_text)

        ticket.resolution_attempts = attempt_number
        if result.category and not ticket.category:
            ticket.category = result.category

        resolution = Resolution(
            ticket_id=ticket.id,
            source=result.source,
            kb_article_id=result.kb_article_id,
            web_search_log_id=result.web_search_log_id,
            answer_text=result.answer_text,
            confidence_score=result.confidence,
        )
        db.add(resolution)
        await db.flush()
        result.resolution_id = resolution.id

        if result.answer_text:
            break  # got something to say — stop here even if attempts remain

    if result is None:
        # Degenerate config (MAX_RESOLUTION_ATTEMPTS <= 0) — nothing to try at all.
        return ResolutionResult(answer_text="", source="none", confidence=0.0, should_escalate=True)

    # Escalate if we ran out of strategies with nothing to say, or the final
    # allowed attempt's answer came back low-confidence.
    if not result.answer_text or (
        ticket.resolution_attempts >= settings.MAX_RESOLUTION_ATTEMPTS and result.confidence < 0.5
    ):
        result.should_escalate = True

    return result


async def _try_kb(problem_text: str, k: int, min_score: float) -> ResolutionResult:
    [embedding] = await embed_texts([problem_text], input_type="query")
    matches = query_kb(embedding, k=k, min_score=min_score)

    if not matches:
        return ResolutionResult(answer_text="", source="kb", confidence=0.0, should_escalate=False)

    parsed = await llm.generate_kb_answer(problem_text, matches)
    matched_id = parsed.get("kb_article_id")
    # Trust the LLM's cited article only if it's actually among what we retrieved;
    # otherwise fall back to the top match so traceability never points at a
    # hallucinated id.
    valid_ids = {m["kb_article_id"] for m in matches}
    if matched_id not in valid_ids:
        matched_id = matches[0]["kb_article_id"]
    category = next((m.get("category") for m in matches if m["kb_article_id"] == matched_id), None)

    return ResolutionResult(
        answer_text=parsed.get("answer", ""),
        source="kb",
        confidence=float(parsed.get("confidence", 0.0) or 0.0),
        should_escalate=False,
        kb_article_id=matched_id,
        category=category,
    )


async def _try_web_search(db: AsyncSession, ticket: Ticket, problem_text: str) -> ResolutionResult:
    web_results = await web_search.search_web(problem_text)

    log = WebSearchLog(ticket_id=ticket.id, query=problem_text)
    if web_results:
        log.source_url = web_results[0]["url"]
        log.snippet = web_results[0]["content"][:500]
        log.used_in_resolution = True
    db.add(log)
    await db.flush()

    if not web_results:
        return ResolutionResult(answer_text="", source="web_search", confidence=0.0, should_escalate=True,
                                 web_search_log_id=log.id)

    answer = await llm.generate_web_answer(problem_text, web_results)
    # Web search is the last resort — treat as lower default confidence unless clearly conclusive.
    return ResolutionResult(answer_text=answer, source="web_search", confidence=0.6, should_escalate=False,
                             web_search_log_id=log.id)
