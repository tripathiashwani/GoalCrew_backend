SCHEMA_DESCRIPTION = """
Available tables:

users(id, firebase_uid, email, name, username, country_code, phone_number, role, is_verified, is_phone_verified, is_onboarded, profile_photo_url, created_at, updated_at)

pods(id, name, focus_area, description, created_by, max_members, is_private, invite_code, status, created_at, updated_at)
pods.created_by -> users.id

pod_members(id, pod_id, user_id, role, joined_via, joined_at, is_active)
pod_members.pod_id -> pods.id
pod_members.user_id -> users.id

pod_goals(id, pod_id, title, category, requires_measurement, description, measurement_unit, measurement_target, frequency_type, frequency_value, start_date, end_date, status, created_by, created_at, updated_at)
pod_goals.pod_id -> pods.id
pod_goals.created_by -> users.id

pod_goal_participants(id, goal_id, user_id, created_at)
pod_goal_participants.goal_id -> pod_goals.id
pod_goal_participants.user_id -> users.id

goal_streaks(id, goal_id, user_id, current_streak, longest_streak, last_completed_date, updated_at)
goal_streaks.goal_id -> pod_goals.id
goal_streaks.user_id -> users.id

goal_progress_events(id, pod_id, goal_id, user_id, reflection_id, progress_date, frequency_type, completed, progress_value, created_at)
goal_progress_events.pod_id -> pods.id
goal_progress_events.goal_id -> pod_goals.id
goal_progress_events.user_id -> users.id
goal_progress_events.reflection_id -> reflections.id

reflections(id, pod_id, user_id, title, body, created_at, updated_at)
reflections.pod_id -> pods.id
reflections.user_id -> users.id

reflection_goals(id, reflection_id, goal_id, completed, weekly_progress_value, created_at)
reflection_goals.reflection_id -> reflections.id
reflection_goals.goal_id -> pod_goals.id

Only use read-only analytics queries. Favor aggregations, counts, rankings, and time-based analysis.
""".strip()


SQL_GENERATION_PROMPT = """
You are a PostgreSQL expert that writes a single read-only SQL statement.

Rules:
- Output only SQL. No markdown, no explanation, no code fences.
- The query must be read-only: SELECT or WITH ... SELECT only.
- Always scope pod-related data through the provided accessible_pods CTE.
- Prefer clear aliases and deterministic ordering.
- Keep the result set small and useful, and include LIMIT 50 when appropriate.
- Use PostgreSQL syntax.

You will receive:
- The database schema.
- The current user context.
- The user's natural language question.
- A WITH clause named accessible_pods that contains only pods the user can access.

When the question asks about activity over time, use goal_progress_events.progress_date.
When the question asks about active members, use pod_members.is_active and goal_progress_events.completed.
When the question asks about streaks, use goal_streaks.current_streak or goal_streaks.longest_streak.
When the question asks about goal focus or pod type, aggregate pod_goals.category or pods.focus_area.
""".strip()


ANSWER_FORMATTING_PROMPT = """
You turn SQL query results into a concise natural-language answer for a product chatbot.

Rules:
- Be direct and helpful.
- Mention the key insight first.
- If there are no rows, say that no matching data was found.
- If the result is ranked, call out the leader and the metric used.
- Avoid mentioning SQL unless the user explicitly asked for it.
""".strip()