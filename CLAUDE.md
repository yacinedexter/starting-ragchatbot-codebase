# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the app:**
```bash
cd backend && uv run uvicorn app:app --reload --port 8000
```
Or use the convenience script from the repo root:
```bash
chmod +x run.sh && ./run.sh
```
The UI and API are both served from `http://localhost:8000`. API docs at `/docs`.

**Install dependencies** (always use `uv`, never `pip` directly):
```bash
uv sync
```

**Run tests:**
```bash
cd backend && uv run pytest tests/
```
Run a single test file: `uv run pytest tests/test_ai_generator.py`

**Environment setup** — create a `.env` file in the repo root (loaded by `python-dotenv` via parent-directory search):
```
ANTHROPIC_API_KEY=your_key_here
```

## Architecture

The app is a single-server FastAPI backend that serves both the REST API and the static frontend. There is no separate frontend build step.

**Request flow:**
1. `frontend/` (HTML/CSS/JS) → `POST /api/query` → `app.py`
2. `app.py` → `RAGSystem.query()` in `rag_system.py` (the central orchestrator)
3. `RAGSystem` calls `AIGenerator.generate_response()` with the Claude API and both registered tools
4. `AIGenerator._run_agentic_loop()` runs up to `MAX_ROUNDS=2` sequential tool-call rounds; each round appends assistant + tool-result messages before the next API call
5. Claude calls `search_course_content` or `get_course_outline` as needed; `ToolManager` dispatches to the correct `Tool.execute()`
6. After the loop, `ToolManager.get_last_sources()` extracts UI source links, then `reset_sources()` clears them for the next query

**Key components:**
- `backend/rag_system.py` — orchestrates all components; entry point for queries
- `backend/ai_generator.py` — wraps the Anthropic SDK; `_run_agentic_loop()` handles up to `MAX_ROUNDS` tool-call rounds then makes a final synthesis call (without `tool_choice`) so Claude returns text
- `backend/vector_store.py` — two ChromaDB collections: `course_catalog` (course titles/lesson metadata for semantic name resolution) and `course_content` (chunked lesson text); lesson metadata is JSON-serialized into `lessons_json` because ChromaDB metadata values must be scalars
- `backend/search_tools.py` — `Tool` ABC, `CourseSearchTool` (`search_course_content`), `CourseOutlineTool` (`get_course_outline`), `ToolManager`; register new tools via `ToolManager.register_tool()`
- `backend/document_processor.py` — parses `.txt` course files into `Course` + `CourseChunk` models
- `backend/session_manager.py` — in-memory only; history is lost on server restart; stores last `MAX_HISTORY=2` exchanges
- `backend/config.py` — single `Config` dataclass; tune `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_RESULTS`, `MAX_HISTORY`, `EMBEDDING_MODEL`, and `CHROMA_PATH` here

**Course document format** (files go in `docs/`):
```
Course Title: My Course
Course Link: https://...
Course Instructor: Jane Doe

Lesson 1: Intro
Lesson Link: https://...
<lesson content>

Lesson 2: ...
```
Only `.pdf`, `.docx`, and `.txt` are scanned on startup — but `DocumentProcessor.read_file()` currently only handles plain text. PDFs/DOCX will fail unless a parser is added.

**ChromaDB deduplication:** on startup `add_course_folder()` fetches existing course titles by ID and skips any already-indexed course. To force a full re-index, call `VectorStore.clear_all_data()` or pass `clear_existing=True` to `add_course_folder()`.

**Model:** `claude-sonnet-4-20250514` with `temperature=0`, `max_tokens=800`. The system prompt allows up to 2 sequential tool calls per query.
