"""
FastAPI backend for the UK Parliament AI Analyst.

Provides:
    GET  /
    GET  /health
    POST /ask
    POST /ask/demo

The production /ask endpoint uses the evidence-grounded RAG engine.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import Config
from app.real_rag_engine import RealRAGEngine


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Parliamentary AI Analyst API",
    description=(
        "Evidence-grounded AI research assistant for "
        "UK Parliament data."
    ),
    version="3.0.0",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

default_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

cors_env = os.getenv("CORS_ORIGINS", "").strip()

if cors_env:
    allowed_origins = [
        origin.strip()
        for origin in cors_env.split(",")
        if origin.strip()
    ]
else:
    allowed_origins = default_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# RAG engine
# ---------------------------------------------------------------------------

logger.info("Starting Parliamentary AI Analyst RAG engine...")

# use_openai=False to avoid API rate limits/credit issues
rag_engine = RealRAGEngine(
    use_openai=False,
    collect_fresh_data=True,
)

logger.info(
    "RAG engine startup complete. initialized=%s data_source=%s",
    getattr(rag_engine, "initialized", False),
    rag_engine.get_data_source() if hasattr(rag_engine, "get_data_source") else "unknown",
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QuestionRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=2,
        max_length=getattr(
            Config,
            "MAX_QUERY_LENGTH",
            1000,
        ),
        description="Question to ask the parliamentary RAG system.",
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of evidence documents to retrieve.",
    )


class SourceResponse(BaseModel):
    title: str = ""
    source: str = ""
    type: str = ""
    date: str = ""
    url: str = ""
    record_id: str = ""
    snippet: str = ""
    is_sample: bool = False


class DataStatusResponse(BaseModel):
    live_documents: int = 0
    sample_documents: int = 0
    total_documents: int = 0
    data_source: str = "none"
    engine_data_source: str = "none"


class AnswerResponse(BaseModel):
    answer: str
    sources: List[SourceResponse] = Field(
        default_factory=list
    )
    evidence_count: int = 0
    is_sample_data: bool = False
    data_status: DataStatusResponse
    generation_status: str = "unknown"
    retrieval_status: str = "unknown"
    timestamp: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value: Any) -> str:
    """Convert a value safely into clean display text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return " ".join(value.split())

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):

        preferred_keys = (
            "_value",
            "value",
            "label",
            "name",
            "title",
            "text",
            "description",
            "displayAs",
        )

        for key in preferred_keys:

            if key in value:

                result = clean_text(
                    value[key]
                )

                if result:
                    return result

        parts = []

        for nested_value in value.values():

            result = clean_text(
                nested_value
            )

            if result:
                parts.append(result)

        return " ".join(parts)

    if isinstance(value, (list, tuple, set)):

        return "; ".join(
            clean_text(item)
            for item in value
            if clean_text(item)
        )

    return str(value).strip()


def source_snippet(
    document: Any,
    max_length: int = 350,
) -> str:
    """Create a useful evidence snippet for the frontend."""

    metadata = getattr(
        document,
        "metadata",
        {},
    ) or {}

    candidates = (
        metadata.get("answer"),
        metadata.get("content"),
        metadata.get("question"),
        metadata.get("text"),
        metadata.get("body"),
        getattr(
            document,
            "page_content",
            "",
        ),
    )

    for candidate in candidates:

        text = clean_text(candidate)

        if text:

            if len(text) > max_length:

                truncated = text[:max_length].rstrip()

                last_sentence = max(
                    truncated.rfind(". "),
                    truncated.rfind("."),
                )

                if last_sentence > 100:

                    return truncated[
                        :last_sentence + 1
                    ]

                return truncated + "..."

            return text

    return ""


def format_sources(
    documents: List[Any],
) -> List[SourceResponse]:
    """Convert retrieved LangChain documents into API sources."""

    sources: List[SourceResponse] = []

    seen = set()

    for document in documents:

        metadata = getattr(
            document,
            "metadata",
            {},
        ) or {}

        title = clean_text(
            metadata.get("title")
        )

        source = clean_text(
            metadata.get("source")
        )

        record_type = clean_text(
            metadata.get("type")
        )

        date = clean_text(
            metadata.get("date")
        )

        url = clean_text(
            metadata.get("url")
        )

        record_id = clean_text(
            metadata.get("record_id")
            or metadata.get("id")
        )

        is_sample = (
            metadata.get("is_sample") is True
        )

        identity = (
            source,
            record_id or title,
            date,
        )

        if identity in seen:
            continue

        seen.add(identity)

        sources.append(
            SourceResponse(
                title=title,
                source=source,
                type=record_type,
                date=date,
                url=url,
                record_id=record_id,
                snippet=source_snippet(
                    document
                ),
                is_sample=is_sample,
            )
        )

    return sources


def build_data_status() -> DataStatusResponse:
    """Build current index/data status."""

    try:
        status = rag_engine.get_status()

        live_documents = int(
            status.get(
                "live_documents",
                0,
            )
        )

        sample_documents = int(
            status.get(
                "sample_documents",
                0,
            )
        )

        total_documents = int(
            status.get(
                "documents_indexed",
                0,
            )
        )

        return DataStatusResponse(
            live_documents=live_documents,
            sample_documents=sample_documents,
            total_documents=total_documents,
            data_source=(
                "mixed"
                if live_documents and sample_documents
                else (
                    "live_api"
                    if live_documents
                    else (
                        "sample_data"
                        if sample_documents
                        else "none"
                    )
                )
            ),
            engine_data_source=clean_text(
                status.get(
                    "data_source",
                    "none",
                )
            ) or "none",
        )

    except Exception:

        logger.exception(
            "Could not build RAG data status."
        )

        return DataStatusResponse()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> Dict[str, Any]:
    """API information."""

    status = rag_engine.get_status()

    return {
        "name": "Parliamentary AI Analyst API",
        "version": "3.0.0",
        "status": (
            "healthy"
            if status.get("ready")
            else "initializing"
        ),
        "description": (
            "Evidence-grounded UK Parliament "
            "research assistant."
        ),
        "endpoints": {
            "health": "/health",
            "ask": "/ask",
            "demo": "/ask/demo",
            "docs": "/docs",
        },
        "data_source": status.get(
            "data_source",
            "none",
        ),
        "documents_indexed": status.get(
            "documents_indexed",
            0,
        ),
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Return detailed backend health information."""

    try:
        status = rag_engine.get_status()

        return {
            "status": (
                "healthy"
                if status.get("ready")
                else "degraded"
            ),
            "service": "parliamentary-ai-analyst",
            "version": "3.0.0",
            "timestamp": utc_timestamp(),
            "engine": status,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "service": "parliamentary-ai-analyst",
            "version": "3.0.0",
            "timestamp": utc_timestamp(),
            "error": str(e),
        }


@app.post(
    "/ask",
    response_model=AnswerResponse,
)
async def ask_question(
    request: QuestionRequest,
) -> AnswerResponse:
    """Answer a question using the production RAG pipeline."""

    query = clean_text(
        request.query
    )

    if len(query) < 2:

        raise HTTPException(
            status_code=422,
            detail=(
                "Please provide a question "
                "containing at least 2 characters."
            ),
        )

    try:

        status = rag_engine.get_status()

        if not status.get("ready"):

            logger.error(
                "RAG engine is not ready. Status: %s",
                status,
            )

            raise HTTPException(
                status_code=503,
                detail=(
                    "The parliamentary RAG engine is "
                    "not currently ready. Please try again."
                ),
            )

        result = rag_engine.query(
            query,
            top_k=request.top_k,
        )

        answer = clean_text(
            result.get(
                "result",
                "",
            )
        )

        documents = result.get(
            "source_documents",
            [],
        )

        if not isinstance(
            documents,
            list,
        ):
            documents = []

        sources = format_sources(
            documents
        )

        data_status = build_data_status()

        is_sample_data = (
            data_status.sample_documents > 0
            and data_status.live_documents == 0
        )

        logger.info(
            "Question answered: query=%r evidence=%s "
            "generation=%s retrieval=%s",
            query,
            len(documents),
            result.get(
                "generation_status",
                "unknown",
            ),
            result.get(
                "retrieval_status",
                "unknown",
            ),
        )

        return AnswerResponse(
            answer=(
                answer
                or "No answer could be generated "
                   "from the available evidence."
            ),
            sources=sources,
            evidence_count=len(documents),
            is_sample_data=is_sample_data,
            data_status=data_status,
            generation_status=clean_text(
                result.get(
                    "generation_status",
                    "unknown",
                )
            ) or "unknown",
            retrieval_status=clean_text(
                result.get(
                    "retrieval_status",
                    "unknown",
                )
            ) or "unknown",
            timestamp=utc_timestamp(),
        )

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "Unexpected error while answering question."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The server could not process the question. "
                f"Error: {exc}"
            ),
        ) from exc


@app.post(
    "/ask/demo",
)
async def ask_demo() -> Dict[str, Any]:
    """
    Explicit demo endpoint.

    This endpoint is intentionally separate from /ask so that
    production answers are never silently replaced by fake data.
    """

    return {
        "answer": (
            "Demo mode is available separately. "
            "The production /ask endpoint uses the "
            "evidence-grounded parliamentary RAG pipeline."
        ),
        "sources": [],
        "evidence_count": 0,
        "is_sample_data": True,
        "data_status": {
            "live_documents": 0,
            "sample_documents": 0,
            "total_documents": 0,
            "data_source": "demo",
            "engine_data_source": "demo",
        },
        "generation_status": "demo",
        "retrieval_status": "demo",
        "timestamp": utc_timestamp(),
    }


# ---------------------------------------------------------------------------
# Local execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv(
            "HOST",
            "0.0.0.0",
        ),
        port=int(
            os.getenv(
                "PORT",
                "8000",
            )
        ),
        reload=False,
    )