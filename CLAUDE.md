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

**Environment setup** — create a `.env` file in the repo root (loaded by `python-dotenv`):
```
ANTHROPIC_API_KEY=your_key_here
```

## Architecture

The app is a single-server FastAPI backend that serves both the REST API and the static frontend. There is no separate frontend build step.

**Request flow:**
1. `frontend/` (HTML/CSS/JS) → `POST /api/query` → `app.py`
2. `app.py` → `RAGSystem.query()` in `rag_system.py` (the central orchestrator)
3. `RAGSystem` calls `AIGenerator.generate_response()` with the Claude API and a `CourseSearchTool`
4. Claude decides via tool use whether to call `search_course_content`; if so, `ToolManager` executes `CourseSearchTool.execute()` → `VectorStore.search()`
5. ChromaDB returns semantically matched chunks; Claude synthesizes the final answer

**Key components:**
- `backend/rag_system.py` — orchestrates all components; entry point for queries
- `backend/ai_generator.py` — wraps the Anthropic SDK; handles the two-step tool-use loop (initial call → execute tools → follow-up call)
- `backend/vector_store.py` — two ChromaDB collections: `course_catalog` (course titles for semantic course-name resolution) and `course_content` (chunked lesson text)
- `backend/search_tools.py` — `Tool` ABC, `CourseSearchTool`, `ToolManager`; register new tools via `ToolManager.register_tool()`
- `backend/document_processor.py` — parses `.txt` course files with a rigid header format (Course Title / Course Link / Course Instructor) and `Lesson N: Title` markers into `Course` + `CourseChunk` models
- `backend/session_manager.py` — in-memory only; history is lost on server restart; stores last `MAX_HISTORY=2` exchanges

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

**Model:** `claude-sonnet-4-20250514` with `temperature=0`, `max_tokens=800`. The system prompt enforces one search per query maximum.
