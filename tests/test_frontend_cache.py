from starlette.responses import Response

from treasury_rag.api import apply_frontend_cache_policy


def test_frontend_assets_are_not_cached() -> None:
    for path in ("/", "/static/app.js", "/static/styles.css"):
        response = apply_frontend_cache_policy(path, Response())
        assert response.headers["cache-control"] == "no-store, max-age=0"
        assert response.headers["pragma"] == "no-cache"


def test_api_responses_keep_their_normal_cache_policy() -> None:
    response = apply_frontend_cache_policy("/api/memories", Response())
    assert "cache-control" not in response.headers
