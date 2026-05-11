"""
Tests for RAGSystem.query() content-question handling in rag_system.py.

Verifies the orchestration layer: that tools are wired up correctly,
sources are retrieved and reset, session history is tracked, and
no exception leaks out of query() for nominal failure cases.
"""
import pytest
from unittest.mock import MagicMock, patch

from rag_system import RAGSystem
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    cfg.CHROMA_PATH = ":memory:"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.MAX_RESULTS = 5
    cfg.ANTHROPIC_API_KEY = "test-key"
    cfg.ANTHROPIC_MODEL = "test-model"
    cfg.MAX_HISTORY = 2
    return cfg


@pytest.fixture
def rag(mock_config):
    """RAGSystem with VectorStore, AIGenerator, and DocumentProcessor mocked out."""
    with patch("rag_system.VectorStore") as MockVS, \
         patch("rag_system.AIGenerator") as MockAI, \
         patch("rag_system.DocumentProcessor"):

        mock_vs = MagicMock()
        mock_vs.search.return_value = SearchResults(
            documents=["Python is great"],
            metadata=[{"course_title": "Python 101", "lesson_number": 1}],
            distances=[0.1],
        )
        mock_vs.get_lesson_link.return_value = None
        mock_vs.get_course_outline.return_value = None
        MockVS.return_value = mock_vs

        mock_ai = MagicMock()
        mock_ai.generate_response.return_value = "Python is a high-level language."
        MockAI.return_value = mock_ai

        system = RAGSystem(mock_config)
        yield system, mock_vs, mock_ai


# ---------------------------------------------------------------------------
# Basic query contract
# ---------------------------------------------------------------------------

class TestQueryReturnShape:
    def test_query_returns_two_element_tuple(self, rag):
        system, _, _ = rag
        result = system.query("What is Python?")
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_a_string(self, rag):
        system, _, _ = rag
        response, _ = system.query("What is Python?")
        assert isinstance(response, str)

    def test_second_element_is_a_list(self, rag):
        system, _, _ = rag
        _, sources = system.query("What is Python?")
        assert isinstance(sources, list)

    def test_response_text_matches_ai_generator_output(self, rag):
        system, _, mock_ai = rag
        mock_ai.generate_response.return_value = "Specific answer."
        response, _ = system.query("A question")
        assert response == "Specific answer."


# ---------------------------------------------------------------------------
# Tools are wired up and passed to the AI generator
# ---------------------------------------------------------------------------

class TestToolsPassedToAIGenerator:
    def test_generate_response_receives_tools_list(self, rag):
        system, _, mock_ai = rag
        system.query("What is Python?")
        call_kwargs = mock_ai.generate_response.call_args.kwargs
        assert "tools" in call_kwargs
        assert isinstance(call_kwargs["tools"], list)
        assert len(call_kwargs["tools"]) > 0

    def test_search_course_content_tool_is_registered(self, rag):
        system, _, mock_ai = rag
        system.query("Explain decorators")
        tool_names = [
            t["name"]
            for t in mock_ai.generate_response.call_args.kwargs["tools"]
        ]
        assert "search_course_content" in tool_names

    def test_get_course_outline_tool_is_registered(self, rag):
        system, _, mock_ai = rag
        system.query("Show me the outline")
        tool_names = [
            t["name"]
            for t in mock_ai.generate_response.call_args.kwargs["tools"]
        ]
        assert "get_course_outline" in tool_names

    def test_tool_manager_passed_to_generate_response(self, rag):
        system, _, mock_ai = rag
        system.query("question")
        call_kwargs = mock_ai.generate_response.call_args.kwargs
        assert "tool_manager" in call_kwargs
        assert call_kwargs["tool_manager"] is system.tool_manager


# ---------------------------------------------------------------------------
# Source retrieval and reset
# ---------------------------------------------------------------------------

class TestSourceLifecycle:
    def test_sources_returned_from_search_tool(self, rag):
        system, _, _ = rag
        system.search_tool.last_sources = [
            {"label": "Python 101 - Lesson 1", "url": "https://example.com"}
        ]
        _, sources = system.query("What is Python?")
        assert sources == [{"label": "Python 101 - Lesson 1", "url": "https://example.com"}]

    def test_sources_are_reset_after_query(self, rag):
        system, _, _ = rag
        system.search_tool.last_sources = [{"label": "some source", "url": None}]
        system.query("What is Python?")
        assert system.search_tool.last_sources == []

    def test_empty_sources_when_no_tool_called(self, rag):
        system, _, _ = rag
        # last_sources starts empty (no tool was triggered)
        _, sources = system.query("What is 2+2?")
        assert sources == []


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

class TestSessionHistory:
    def test_history_passed_to_generate_response_on_second_query(self, rag):
        system, _, mock_ai = rag
        session_id = "sess_1"
        system.session_manager.create_session()
        system.session_manager.sessions[session_id] = []

        system.query("First question", session_id=session_id)
        system.query("Second question", session_id=session_id)

        second_call_kwargs = mock_ai.generate_response.call_args.kwargs
        assert second_call_kwargs.get("conversation_history") is not None

    def test_no_history_on_first_query(self, rag):
        system, _, mock_ai = rag
        session_id = "fresh_session"
        system.session_manager.sessions[session_id] = []

        system.query("First question", session_id=session_id)
        first_call_kwargs = mock_ai.generate_response.call_args.kwargs
        # No prior exchanges → history should be None
        assert first_call_kwargs.get("conversation_history") is None


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_ai_exception_propagates_out_of_query(self, rag):
        """
        If AIGenerator raises, the exception must propagate to app.py so it
        can return a 500. query() must not swallow it.
        """
        system, _, mock_ai = rag
        mock_ai.generate_response.side_effect = Exception("Anthropic API error")
        with pytest.raises(Exception, match="Anthropic API error"):
            system.query("A question")

    def test_query_with_empty_ai_response_returns_empty_string(self, rag):
        system, _, mock_ai = rag
        mock_ai.generate_response.return_value = ""
        response, _ = system.query("A question")
        assert response == ""


# ---------------------------------------------------------------------------
# None lesson_number in metadata — add_course_content guard
# ---------------------------------------------------------------------------

class TestAddCourseContentNoneLessonNumber:
    """
    ChromaDB 1.0 raises TypeError when metadata contains None values.
    add_course_content() must omit lesson_number from the metadata dict
    when it is None, otherwise ingestion fails silently and the content
    collection stays empty.
    """

    def test_none_lesson_number_is_not_passed_to_chromadb(self):
        """
        Regression: CourseChunk.lesson_number=None must not appear in the
        metadata dict handed to ChromaDB.  We verify this by calling the
        real add_course_content() with a mocked collection and inspecting
        the metadata that was actually passed.
        """
        from models import CourseChunk
        from vector_store import VectorStore

        chunks = [
            CourseChunk(
                content="Content without a lesson",
                course_title="Test Course",
                lesson_number=None,
                chunk_index=0,
            )
        ]

        mock_collection = MagicMock()
        mock_vs = MagicMock(spec=VectorStore)
        mock_vs.course_content = mock_collection

        # Call the real method body, not the mock
        VectorStore.add_course_content(mock_vs, chunks)

        call_kwargs = mock_collection.add.call_args.kwargs
        for meta in call_kwargs["metadatas"]:
            assert "lesson_number" not in meta, (
                "lesson_number=None must be omitted from ChromaDB metadata; "
                "ChromaDB 1.0 raises TypeError on any None metadata value."
            )

    def test_valid_lesson_number_still_included_in_metadata(self):
        """lesson_number is kept when it is an integer."""
        from models import CourseChunk
        from vector_store import VectorStore

        chunks = [
            CourseChunk(
                content="Lesson content",
                course_title="Course",
                lesson_number=3,
                chunk_index=0,
            )
        ]

        mock_collection = MagicMock()
        mock_vs = MagicMock(spec=VectorStore)
        mock_vs.course_content = mock_collection

        VectorStore.add_course_content(mock_vs, chunks)

        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["metadatas"][0]["lesson_number"] == 3
