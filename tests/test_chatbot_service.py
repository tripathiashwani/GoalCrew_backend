from uuid import UUID

import pytest

from app.modules.chatbot.service import build_accessible_pods_cte, validate_sql_query


def test_validate_sql_query_rejects_mutation():
    with pytest.raises(ValueError):
        validate_sql_query("UPDATE users SET name = 'x'")


def test_validate_sql_query_requires_accessible_pods():
    with pytest.raises(ValueError):
        validate_sql_query("SELECT * FROM pods LIMIT 5")


def test_build_accessible_pods_cte_contains_pod_ids():
    pod_id = UUID("12345678-1234-5678-1234-567812345678")
    cte = build_accessible_pods_cte([pod_id])

    assert "accessible_pods" in cte
    assert str(pod_id) in cte