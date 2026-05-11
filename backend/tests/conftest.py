import sys
import os
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional

# Make the backend directory importable from all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Shared RAGSystem mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """Fully mocked RAGSystem for use in API-level and unit tests."""
    mock = MagicMock()
    mock.query.return_value = (
        "Python is a high-level programming language.",
        [{"label": "Python 101 - Lesson 1", "url": "https://example.com/lesson/1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python 101", "Machine Learning Basics"],
    }
    mock.session_manager.create_session.return_value = "test-session-id"
    return mock


# ---------------------------------------------------------------------------
# Pydantic models (mirrors app.py — kept here so tests don't import app.py,
# which mounts StaticFiles against a frontend directory that won't exist in CI)
# ---------------------------------------------------------------------------

class _QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class _Source(BaseModel):
    label: str
    url: Optional[str] = None

class _QueryResponse(BaseModel):
    answer: str
    sources: List[_Source]
    session_id: str

class _CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Test application — same routes as app.py, no static-file mount
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(mock_rag_system):
    """
    Minimal FastAPI app that mirrors /api/query and /api/courses.

    Defined inline to avoid importing app.py, which mounts StaticFiles at
    module level and calls RAGSystem.__init__() (initialises ChromaDB and the
    embedding model) before any fixture patches can be applied.
    """
    rag = mock_rag_system
    app = FastAPI()

    @app.post("/api/query", response_model=_QueryResponse)
    async def query_documents(request: _QueryRequest):
        try:
            session_id = request.session_id or rag.session_manager.create_session()
            answer, sources = rag.query(request.query, session_id)
            return _QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=_CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return _CourseStats(**analytics)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """HTTP test client bound to the test application."""
    return TestClient(test_app)
