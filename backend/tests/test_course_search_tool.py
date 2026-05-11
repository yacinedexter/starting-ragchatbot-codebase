"""
Tests for CourseSearchTool.execute() in search_tools.py.

Covers: results found, empty results, error results, course/lesson
filtering, source population, and output formatting.
"""
import pytest
from unittest.mock import MagicMock

from search_tools import CourseSearchTool
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_lesson_link.return_value = None
    return store


@pytest.fixture
def tool(mock_store):
    return CourseSearchTool(mock_store)


def _results(docs, metas):
    """Build a SearchResults with parallel doc/meta lists."""
    return SearchResults(
        documents=docs,
        metadata=metas,
        distances=[0.1] * len(docs),
    )


# ---------------------------------------------------------------------------
# execute(): happy path
# ---------------------------------------------------------------------------

class TestExecuteReturnsContent:
    def test_contains_document_text(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["Python is dynamically typed"],
            [{"course_title": "Python 101", "lesson_number": 1}],
        )
        result = tool.execute(query="typing")
        assert "Python is dynamically typed" in result

    def test_contains_course_title_header(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content"],
            [{"course_title": "Python 101", "lesson_number": 1}],
        )
        result = tool.execute(query="anything")
        assert "Python 101" in result

    def test_contains_lesson_number_in_header(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content"],
            [{"course_title": "Python 101", "lesson_number": 3}],
        )
        result = tool.execute(query="anything")
        assert "Lesson 3" in result

    def test_multiple_results_are_all_included(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["First chunk", "Second chunk"],
            [
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course A", "lesson_number": 2},
            ],
        )
        result = tool.execute(query="topic")
        assert "First chunk" in result
        assert "Second chunk" in result

    def test_lesson_number_absent_in_metadata_skips_lesson_header(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content without lesson"],
            [{"course_title": "Course A"}],  # no lesson_number key
        )
        result = tool.execute(query="something")
        assert "Lesson" not in result
        assert "Course A" in result


# ---------------------------------------------------------------------------
# execute(): empty results
# ---------------------------------------------------------------------------

class TestExecuteEmptyResults:
    def test_returns_no_content_message(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = tool.execute(query="obscure topic")
        assert "No relevant content found" in result

    def test_includes_course_filter_in_no_content_message(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = tool.execute(query="topic", course_name="Python 101")
        assert "Python 101" in result

    def test_includes_lesson_filter_in_no_content_message(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[]
        )
        result = tool.execute(query="topic", lesson_number=5)
        assert "lesson 5" in result.lower()


# ---------------------------------------------------------------------------
# execute(): error path
# ---------------------------------------------------------------------------

class TestExecuteErrorHandling:
    def test_returns_error_string_on_search_error(self, tool, mock_store):
        mock_store.search.return_value = SearchResults.empty(
            "Search error: DB unavailable"
        )
        result = tool.execute(query="anything")
        assert "Search error" in result

    def test_does_not_raise_on_search_error(self, tool, mock_store):
        mock_store.search.return_value = SearchResults.empty("boom")
        # Should return the error string, not raise
        result = tool.execute(query="query")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# execute(): filtering — verifies args passed to store.search
# ---------------------------------------------------------------------------

class TestExecutePassesFiltersToStore:
    def test_passes_query_only(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
        tool.execute(query="python basics")
        mock_store.search.assert_called_once_with(
            query="python basics", course_name=None, lesson_number=None
        )

    def test_passes_course_name(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
        tool.execute(query="basics", course_name="Python 101")
        mock_store.search.assert_called_once_with(
            query="basics", course_name="Python 101", lesson_number=None
        )

    def test_passes_lesson_number(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
        tool.execute(query="topic", lesson_number=2)
        mock_store.search.assert_called_once_with(
            query="topic", course_name=None, lesson_number=2
        )

    def test_passes_both_filters(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
        tool.execute(query="topic", course_name="ML", lesson_number=4)
        mock_store.search.assert_called_once_with(
            query="topic", course_name="ML", lesson_number=4
        )


# ---------------------------------------------------------------------------
# Source tracking (last_sources)
# ---------------------------------------------------------------------------

class TestSourceTracking:
    def test_last_sources_populated_after_results(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content"],
            [{"course_title": "Course A", "lesson_number": 1}],
        )
        mock_store.get_lesson_link.return_value = "https://example.com/lesson/1"
        tool.execute(query="topic")
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["label"] == "Course A - Lesson 1"
        assert tool.last_sources[0]["url"] == "https://example.com/lesson/1"

    def test_last_sources_empty_when_no_results(self, tool, mock_store):
        mock_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
        tool.execute(query="nothing")
        # last_sources should remain [] since _format_results was never called
        assert tool.last_sources == []

    def test_last_sources_url_is_none_when_no_lesson_link(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content"],
            [{"course_title": "Course B", "lesson_number": 2}],
        )
        mock_store.get_lesson_link.return_value = None
        tool.execute(query="topic")
        assert tool.last_sources[0]["url"] is None

    def test_last_sources_label_has_no_lesson_when_lesson_number_absent(self, tool, mock_store):
        mock_store.search.return_value = _results(
            ["content"],
            [{"course_title": "Course C"}],  # no lesson_number
        )
        tool.execute(query="topic")
        assert tool.last_sources[0]["label"] == "Course C"
