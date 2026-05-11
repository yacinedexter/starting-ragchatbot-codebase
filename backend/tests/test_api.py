"""
Tests for the FastAPI endpoints: POST /api/query and GET /api/courses.

Uses the `client` fixture from conftest.py, which spins up a minimal
test app with the same route handlers but without the static-file mount.
"""
import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_returns_200_on_valid_request(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200

    def test_response_contains_answer_string(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_response_contains_sources_list(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_response_contains_session_id_string(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        data = resp.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)

    def test_answer_matches_rag_output(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Specific answer text.", [])
        resp = client.post("/api/query", json={"query": "question"})
        assert resp.json()["answer"] == "Specific answer text."

    def test_sources_shape_in_response(self, client, mock_rag_system):
        mock_rag_system.query.return_value = (
            "Answer",
            [{"label": "Course A - Lesson 1", "url": "https://example.com"}],
        )
        resp = client.post("/api/query", json={"query": "question"})
        sources = resp.json()["sources"]
        assert sources[0]["label"] == "Course A - Lesson 1"
        assert sources[0]["url"] == "https://example.com"

    def test_creates_session_when_none_provided(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "Hello"})
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_uses_provided_session_id(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "Hello", "session_id": "my-session"})
        mock_rag_system.session_manager.create_session.assert_not_called()
        assert mock_rag_system.query.call_args.args[1] == "my-session"

    def test_query_text_forwarded_to_rag(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "Explain decorators"})
        assert mock_rag_system.query.call_args.args[0] == "Explain decorators"

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_empty_query_string_is_accepted(self, client):
        resp = client.post("/api/query", json={"query": ""})
        assert resp.status_code == 200

    def test_rag_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("RAG failure")
        resp = client.post("/api/query", json={"query": "Boom"})
        assert resp.status_code == 500

    def test_500_detail_contains_error_message(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("db offline")
        resp = client.post("/api/query", json={"query": "Boom"})
        assert "db offline" in resp.json()["detail"]

    def test_generated_session_id_appears_in_response(self, client, mock_rag_system):
        mock_rag_system.session_manager.create_session.return_value = "generated-id"
        resp = client.post("/api/query", json={"query": "Hello"})
        assert resp.json()["session_id"] == "generated-id"

    def test_provided_session_id_echoed_in_response(self, client):
        resp = client.post("/api/query", json={"query": "Hi", "session_id": "echo-me"})
        assert resp.json()["session_id"] == "echo-me"


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200

    def test_response_contains_total_courses_int(self, client):
        resp = client.get("/api/courses")
        data = resp.json()
        assert "total_courses" in data
        assert isinstance(data["total_courses"], int)

    def test_response_contains_course_titles_list(self, client):
        resp = client.get("/api/courses")
        data = resp.json()
        assert "course_titles" in data
        assert isinstance(data["course_titles"], list)

    def test_total_courses_matches_analytics(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 5,
            "course_titles": ["A", "B", "C", "D", "E"],
        }
        resp = client.get("/api/courses")
        assert resp.json()["total_courses"] == 5

    def test_course_titles_match_analytics(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Python 101", "Data Science"],
        }
        resp = client.get("/api/courses")
        assert resp.json()["course_titles"] == ["Python 101", "Data Science"]

    def test_empty_catalog_returns_zero_total(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        resp = client.get("/api/courses")
        assert resp.json()["total_courses"] == 0
        assert resp.json()["course_titles"] == []

    def test_rag_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("analytics error")
        resp = client.get("/api/courses")
        assert resp.status_code == 500

    def test_500_detail_contains_error_message(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("analytics down")
        resp = client.get("/api/courses")
        assert "analytics down" in resp.json()["detail"]
