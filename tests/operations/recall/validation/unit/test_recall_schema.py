"""Schema contract for worker recall requests."""

import pytest
from pydantic import ValidationError

from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest


def test_recall_rejects_blank_query() -> None:
    """recall should require a concrete query."""

    with pytest.raises(ValidationError) as exc_info:
        MemoryRecallRequest.model_validate({"repo_id": "repo-a", "query": "   "})

    assert any(error["loc"] == ("query",) for error in exc_info.value.errors())
