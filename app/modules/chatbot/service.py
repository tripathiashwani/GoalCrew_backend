from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db.models.goal_progress_events import GoalProgressEvent
from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_members import PodMember
from app.db.models.pod_goals import PodGoal
from app.db.models.pods import Pod
from app.db.models.reflection_goals import ReflectionGoal
from app.db.models.reflections import Reflection
from app.db.models.user import User
from app.modules.chatbot.prompt import (
    ANSWER_FORMATTING_PROMPT,
    SCHEMA_DESCRIPTION,
    SQL_GENERATION_PROMPT,
)
from app.modules.chatbot.schemas import ChatResponse
from app.utils.logger import get_logger

logger = get_logger("Chatbot")

ACCESSIBLE_PODS_CTE = "WITH accessible_pods(pod_id) AS (VALUES {values})"
MAX_QUERY_ROWS = 50
QUERY_TIMEOUT = "5s"
SQL_DANGEROUS_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|CALL|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.lower()).strip()


def _pick_target_pod(accessible_pods: list[dict[str, str]], pod_id: UUID | None) -> dict[str, str]:
    if pod_id:
        for pod in accessible_pods:
            if pod["id"] == str(pod_id):
                return pod
    return accessible_pods[0]


def _load_genai_client():
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - depends on deployment env
        raise RuntimeError("google-genai is not installed") from exc

    return genai.Client(api_key=config.GEMINI_API_KEY)


def _clean_sql(sql: str) -> str:
    cleaned = sql.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("sql\n", "", 1).replace("SQL\n", "", 1)
    return cleaned.strip().rstrip(";")


def validate_sql_query(sql: str) -> str:
    cleaned = _clean_sql(sql)

    if not cleaned:
        raise ValueError("SQL query is empty")

    if SQL_DANGEROUS_PATTERN.search(cleaned):
        raise ValueError("Only read-only SELECT queries are allowed")

    if ";" in cleaned:
        raise ValueError("Multiple SQL statements are not allowed")

    upper = cleaned.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError("Only SELECT or WITH queries are allowed")

    if "ACCESSIBLE_PODS" not in upper:
        raise ValueError("Query must scope data through accessible_pods")

    return cleaned


def build_accessible_pods_cte(pod_ids: list[UUID]) -> str:
    if not pod_ids:
        raise ValueError("At least one accessible pod is required")

    values = ", ".join(f"('{pod_id}'::uuid)" for pod_id in pod_ids)
    return ACCESSIBLE_PODS_CTE.format(values=values)


def build_sql_prompt(user_id: str, user_name: str, question: str, accessible_pods_cte: str, accessible_pods: list[dict[str, str]]) -> str:
    logger.info(f"Accessible pods: {accessible_pods}")
    pod_context = json.dumps(accessible_pods, default=str, ensure_ascii=True)
    return "\n\n".join(
        [
            SQL_GENERATION_PROMPT,
            f"Schema:\n{SCHEMA_DESCRIPTION}",
            f"Current user id: {user_id}",
            f"Current user name: {user_name}",
            f"Accessible pods: {pod_context}",
            f"Use this exact scope CTE at the top of the query:\n{accessible_pods_cte}",
            f"User question: {question}",
        ]
    )


def build_answer_prompt(question: str, sql_query: str, rows: list[dict[str, object]]) -> str:
    rows_json = json.dumps(rows, default=str, ensure_ascii=True)
    return "\n\n".join(
        [
            ANSWER_FORMATTING_PROMPT,
            f"Question: {question}",
            f"SQL used: {sql_query}",
            f"Rows returned: {rows_json}",
        ]
    )


def _extract_text(response) -> str:
    text_value = getattr(response, "text", None)
    if text_value:
        return str(text_value).strip()
    return str(response).strip()


async def _generate_sql(client, prompt: str) -> str:
    logger.info(f"generate sql called with prompt:{prompt}")
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return _extract_text(response)


async def _format_answer(client, prompt: str) -> str:
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return _extract_text(response)


async def _run_sql(db: AsyncSession, sql_query: str) -> list[dict[str, object]]:
    async with db.begin():
        await db.execute(text(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT}'"))
        await db.execute(text("SET TRANSACTION READ ONLY"))
        result = await db.execute(text(sql_query))
        return [_normalize_row(row) for row in result.mappings().all()[:MAX_QUERY_ROWS]]


def _normalize_row(row) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def _append_limit(sql_query: str) -> str:
    if re.search(r"\bLIMIT\b", sql_query, re.IGNORECASE):
        return sql_query
    return f"{sql_query}\nLIMIT {MAX_QUERY_ROWS}"


def _ensure_scope_wrapper(sql_query: str, accessible_pods_cte: str) -> str:
    cleaned = validate_sql_query(sql_query)
    if cleaned.upper().startswith("WITH"):
        return _append_limit(cleaned)
    return _append_limit(f"{accessible_pods_cte}\n{cleaned}")


async def ask_question(db: AsyncSession, user: User, question: str, pod_id: UUID | None = None) -> ChatResponse:
    accessible_stmt = (
        select(Pod.id, Pod.name, Pod.focus_area)
        .join(PodMember, PodMember.pod_id == Pod.id)
        .where(PodMember.user_id == user.id, PodMember.is_active.is_(True))
        .order_by(Pod.name.asc())
    )

    if pod_id:
        accessible_stmt = accessible_stmt.where(Pod.id == pod_id)

    rows = (await db.execute(accessible_stmt)).all()
    if not rows:
        raise ValueError("You do not have access to any pods for this request")

    accessible_pods = [
        {"id": str(pod_id), "name": pod_name, "focus_area": pod_focus}
        for pod_id, pod_name, pod_focus in rows
    ]
    accessible_pods_cte = build_accessible_pods_cte([UUID(pod["id"]) for pod in accessible_pods])
    user_id = str(user.id)
    user_name = user.name or ""
    await db.rollback()

    normalized_question = _normalize_question(question)
    target_pod = _pick_target_pod(accessible_pods, pod_id)

    fallback_mode = not config.GEMINI_API_KEY
    if fallback_mode:
        if any(keyword in normalized_question for keyword in ["best streak", "longest streak", "streak"]):
            sql_query = _ensure_scope_wrapper(
                f"""
                SELECT u.name AS user_name,
                       pg.title AS goal_title,
                       gs.current_streak,
                       gs.longest_streak
                FROM goal_streaks gs
                JOIN users u ON u.id = gs.user_id
                JOIN pod_goals pg ON pg.id = gs.goal_id
                JOIN accessible_pods ap ON ap.pod_id = pg.pod_id
                WHERE pg.pod_id = '{target_pod['id']}'::uuid
                ORDER BY gs.longest_streak DESC, gs.current_streak DESC, u.name ASC
                LIMIT 5
                """,
                accessible_pods_cte,
            )
            result_rows = await _run_sql(db, sql_query)
            if not result_rows:
                return ChatResponse(answer="I couldn’t find streak data for that pod yet.", query_used=sql_query)
            top = result_rows[0]
            answer = (
                f"{top.get('user_name', 'Someone')} is leading in {target_pod['name']} with a longest streak of "
                f"{top.get('longest_streak', 0)} on {top.get('goal_title', 'a goal')}."
            )
            return ChatResponse(answer=answer, query_used=sql_query)

        if any(keyword in normalized_question for keyword in ["most active month", "which month", "active month", "months of the year"]):
            sql_query = _ensure_scope_wrapper(
                f"""
                SELECT EXTRACT(MONTH FROM gpe.progress_date)::int AS month_number,
                       COUNT(*) AS activity_count
                FROM goal_progress_events gpe
                JOIN accessible_pods ap ON ap.pod_id = gpe.pod_id
                WHERE gpe.pod_id = '{target_pod['id']}'::uuid
                  AND COALESCE(gpe.completed, false) = true
                GROUP BY 1
                ORDER BY activity_count DESC, month_number ASC
                LIMIT 12
                """,
                accessible_pods_cte,
            )
            result_rows = await _run_sql(db, sql_query)
            if not result_rows:
                return ChatResponse(answer="I couldn’t find monthly activity data for that pod yet.", query_used=sql_query)
            top = result_rows[0]
            answer = (
                f"{target_pod['name']} is most active in month {top.get('month_number')} with "
                f"{top.get('activity_count', 0)} completed activity events."
            )
            return ChatResponse(answer=answer, query_used=sql_query)

        if any(keyword in normalized_question for keyword in ["most active member", "most active user", "achieving more goals", "who is most active"]):
            sql_query = _ensure_scope_wrapper(
                f"""
                SELECT u.name AS user_name,
                       COUNT(*) AS completed_actions,
                       COUNT(DISTINCT gpe.goal_id) AS goal_count
                FROM goal_progress_events gpe
                JOIN users u ON u.id = gpe.user_id
                JOIN accessible_pods ap ON ap.pod_id = gpe.pod_id
                WHERE gpe.pod_id = '{target_pod['id']}'::uuid
                  AND COALESCE(gpe.completed, false) = true
                GROUP BY u.name
                ORDER BY completed_actions DESC, goal_count DESC, user_name ASC
                LIMIT 5
                """,
                accessible_pods_cte,
            )
            result_rows = await _run_sql(db, sql_query)
            if not result_rows:
                return ChatResponse(answer="I couldn’t find activity data for that pod yet.", query_used=sql_query)
            top = result_rows[0]
            answer = (
                f"{top.get('user_name', 'A member')} is the most active in {target_pod['name']} "
                f"with {top.get('completed_actions', 0)} completed actions across {top.get('goal_count', 0)} goals."
            )
            return ChatResponse(answer=answer, query_used=sql_query)

        if any(keyword in normalized_question for keyword in ["pod focus", "what is my pod focused on", "study oriented", "fitness oriented", "focus area"]):
            sql_query = _ensure_scope_wrapper(
                f"""
                SELECT pg.category,
                       COUNT(*) AS goal_count
                FROM pod_goals pg
                JOIN accessible_pods ap ON ap.pod_id = pg.pod_id
                WHERE pg.pod_id = '{target_pod['id']}'::uuid
                GROUP BY pg.category
                ORDER BY goal_count DESC, pg.category ASC
                LIMIT 10
                """,
                accessible_pods_cte,
            )
            result_rows = await _run_sql(db, sql_query)
            if not result_rows:
                return ChatResponse(answer=f"I couldn’t find goal categories for {target_pod['name']} yet.", query_used=sql_query)
            top = result_rows[0]
            answer = (
                f"{target_pod['name']} appears to be centered on {top.get('category') or 'mixed'} goals, "
                f"with {top.get('goal_count', 0)} goals in that category."
            )
            return ChatResponse(answer=answer, query_used=sql_query)

        if any(keyword in normalized_question for keyword in ["which pod has the most active members", "most active pods", "active members"]):
            sql_query = _ensure_scope_wrapper(
                """
                SELECT p.id AS pod_id,
                       p.name AS pod_name,
                       COUNT(DISTINCT pm.user_id) AS active_member_count,
                       COUNT(*) FILTER (WHERE COALESCE(gpe.completed, false) = true) AS completed_events
                FROM pods p
                JOIN pod_members pm ON pm.pod_id = p.id
                JOIN accessible_pods ap ON ap.pod_id = p.id
                LEFT JOIN goal_progress_events gpe ON gpe.pod_id = p.id
                WHERE pm.is_active = true
                GROUP BY p.id, p.name
                ORDER BY active_member_count DESC, completed_events DESC, pod_name ASC
                LIMIT 10
                """,
                accessible_pods_cte,
            )
            result_rows = await _run_sql(db, sql_query)
            if not result_rows:
                return ChatResponse(answer="I couldn’t compare pod activity yet.", query_used=sql_query)
            top = result_rows[0]
            answer = (
                f"{top.get('pod_name', 'A pod')} has the most active members in your accessible pods, "
                f"with {top.get('active_member_count', 0)} active members."
            )
            return ChatResponse(answer=answer, query_used=sql_query)

        return ChatResponse(
            answer=(
                "I can answer pod analytics questions like best streak, most active member, "
                "most active month, pod focus, or which pod has the most active members."
            ),
            query_used=None,
        )

    client = _load_genai_client()
    sql_prompt = build_sql_prompt(user_id, user_name, question, accessible_pods_cte, accessible_pods)
    generated_sql = await _generate_sql(client, sql_prompt)
    sql_query = _ensure_scope_wrapper(generated_sql, accessible_pods_cte)

    result_rows = await _run_sql(db, sql_query)

    if not result_rows:
        return ChatResponse(
            answer="I could not find matching data in the pods you can access.",
            query_used=sql_query,
        )

    answer_prompt = build_answer_prompt(question, sql_query, result_rows)
    answer = await _format_answer(client, answer_prompt)

    return ChatResponse(answer=answer, query_used=sql_query)