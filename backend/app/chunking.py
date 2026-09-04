"""
Parliamentary document chunking.

Converts collected parliamentary records into LangChain Documents
while preserving substantive evidence and important metadata.

Designed for:
    UK Parliament WebSearch results
    Hansard pages
    Commons Library material
    Members data
    Parliamentary questions
    Bills and debates

Important:
    Nested API values such as {"_value": "..."} are preserved.
    Stable chunk IDs are generated for retrieval and deduplication.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, Iterable, List, Optional

try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document


logger = logging.getLogger(__name__)


# ================================================================
# Configuration
# ================================================================

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 180
MIN_CHUNK_SIZE = 300

SEARCHABLE_FIELDS = (
    "title",
    "label",
    "question",
    "answer",
    "content",
    "text",
    "body",
    "full_text",
    "proceedings",
    "summary",
    "abstract",
    "description",
    "details",
    "speaker",
    "member",
    "asking_member",
    "answering_member",
    "tabling_member",
    "answering_minister",
    "answering_body",
    "department",
    "committee",
    "house",
    "type",
    "subtype",
    "section",
    "topics",
    "location",
    "bill_stage",
    "clause",
    "decision",
    "majority",
    "turnout",
    "electorate",
    "paper_number",
    "identifier",
    "uin",
)


# ================================================================
# Generic value handling
# ================================================================

def _clean_text(value: Any) -> str:
    """
    Convert arbitrary nested API values into readable text.

    Handles Parliament API structures such as:

        {"_value": "Prime Minister"}
        {"value": "Prime Minister"}
        {"label": "Prime Minister"}

    as well as lists and nested dictionaries.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):

        preferred_keys = (
            "_value",
            "value",
            "text",
            "label",
            "name",
            "title",
            "description",
            "displayName",
        )

        for key in preferred_keys:
            if key in value:

                result = _clean_text(
                    value[key]
                )

                if result:
                    return result

        parts: List[str] = []

        for key, item in value.items():

            if str(key).startswith("@"):
                continue

            result = _clean_text(item)

            if result:
                parts.append(result)

        return " ".join(parts).strip()

    if isinstance(value, (list, tuple, set)):

        parts = [
            _clean_text(item)
            for item in value
            if item is not None
        ]

        return " ".join(
            part
            for part in parts
            if part
        ).strip()

    return str(value).strip()


def _normalise_whitespace(
    text: str,
) -> str:
    """Normalise excessive whitespace."""

    if not text:
        return ""

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    # Preserve paragraph boundaries while removing
    # excessive spaces.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _dedupe_lines(
    text: str,
) -> str:
    """
    Remove repeated adjacent lines.

    Parliamentary HTML pages sometimes expose the same heading or
    navigation text more than once.
    """

    if not text:
        return ""

    lines = text.splitlines()

    output: List[str] = []

    previous = None

    for line in lines:

        cleaned = line.strip()

        if not cleaned:
            if output and output[-1] != "":
                output.append("")

            continue

        if cleaned == previous:
            continue

        output.append(cleaned)
        previous = cleaned

    return "\n".join(output).strip()


def _stable_hash(
    value: str,
) -> str:
    """Generate a deterministic short SHA1 identifier."""

    return hashlib.sha1(
        value.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()[:20]


def _get_value(
    record: Dict[str, Any],
    *keys: str,
) -> Any:
    """Return the first non-empty value from a record."""

    for key in keys:

        if key not in record:
            continue

        value = record.get(key)

        if value is None:
            continue

        cleaned = _clean_text(value)

        if cleaned:
            return value

    return ""


# ================================================================
# Record text construction
# ================================================================

def _record_to_text(
    record: Dict[str, Any],
) -> str:
    """
    Build the searchable text for one parliamentary record.

    The evidence fields are deliberately placed before secondary
    metadata so the actual parliamentary content receives priority.
    """

    sections: List[str] = []

    # ------------------------------------------------------------
    # Title
    # ------------------------------------------------------------

    title = _clean_text(
        _get_value(
            record,
            "title",
            "label",
            "name",
        )
    )

    if title:
        sections.append(
            f"Title: {title}"
        )

    # ------------------------------------------------------------
    # Core parliamentary evidence
    # ------------------------------------------------------------

    evidence_fields = (
        "question",
        "answer",
        "content",
        "text",
        "body",
        "full_text",
        "proceedings",
        "summary",
        "abstract",
        "description",
        "details",
    )

    used_evidence = set()

    for field in evidence_fields:

        value = _clean_text(
            record.get(field)
        )

        if not value:
            continue

        # Avoid copying identical text from multiple aliases.
        fingerprint = _normalise_whitespace(
            value
        ).lower()

        if not fingerprint:
            continue

        if fingerprint in used_evidence:
            continue

        used_evidence.add(
            fingerprint
        )

        label = field.replace(
            "_",
            " ",
        ).title()

        sections.append(
            f"{label}: {value}"
        )

    # ------------------------------------------------------------
    # Important contextual metadata
    # ------------------------------------------------------------

    context_fields = (
        "speaker",
        "member",
        "asking_member",
        "answering_member",
        "tabling_member",
        "answering_minister",
        "answering_body",
        "department",
        "committee",
        "house",
        "type",
        "subtype",
        "section",
        "topics",
        "location",
        "bill_stage",
        "clause",
        "decision",
        "paper_number",
        "uin",
    )

    for field in context_fields:

        value = _clean_text(
            record.get(field)
        )

        if not value:
            continue

        label = field.replace(
            "_",
            " ",
        ).title()

        sections.append(
            f"{label}: {value}"
        )

    text = "\n".join(
        sections
    )

    text = _normalise_whitespace(
        text
    )

    text = _dedupe_lines(
        text
    )

    return text


# ================================================================
# Metadata
# ================================================================

def _build_metadata(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """Build safe, retrieval-friendly metadata."""

    metadata: Dict[str, Any] = {}

    record_id = _clean_text(
        _get_value(
            record,
            "record_id",
            "id",
            "identifier",
            "uid",
        )
    )

    if not record_id:

        seed = "|".join(
            [
                _clean_text(
                    record.get("source")
                ),
                _clean_text(
                    record.get("url")
                ),
                _clean_text(
                    record.get("title")
                ),
                _clean_text(
                    record.get("text")
                ),
            ]
        )

        record_id = (
            "record_"
            + _stable_hash(seed)
        )

    metadata["id"] = record_id
    metadata["record_id"] = record_id

    # ------------------------------------------------------------
    # Core metadata
    # ------------------------------------------------------------

    metadata["title"] = _clean_text(
        _get_value(
            record,
            "title",
            "label",
            "name",
        )
    )

    metadata["source"] = _clean_text(
        record.get("source")
    )

    metadata["type"] = _clean_text(
        record.get("type")
    )

    metadata["date"] = _clean_text(
        _get_value(
            record,
            "date",
            "published",
            "publication_date",
            "tabled",
            "tabled_date",
        )
    )

    metadata["url"] = _clean_text(
        _get_value(
            record,
            "url",
            "uri",
            "link",
            "web_url",
            "detail_url",
        )
    )

    metadata["is_sample"] = bool(
        record.get(
            "is_sample",
            False,
        )
    )

    # ------------------------------------------------------------
    # Preserve important searchable fields
    # ------------------------------------------------------------

    for field in SEARCHABLE_FIELDS:

        if field in metadata:
            continue

        if field not in record:
            continue

        value = _clean_text(
            record.get(field)
        )

        if value:
            metadata[field] = value

    # ------------------------------------------------------------
    # Evidence status
    # ------------------------------------------------------------

    metadata["has_evidence"] = bool(
        _clean_text(
            record.get("content")
        )
        or _clean_text(
            record.get("text")
        )
        or _clean_text(
            record.get("body")
        )
        or _clean_text(
            record.get("full_text")
        )
        or _clean_text(
            record.get("question")
        )
        or _clean_text(
            record.get("answer")
        )
    )

    evidence_length = 0

    for field in (
        "content",
        "text",
        "body",
        "full_text",
        "question",
        "answer",
        "summary",
        "description",
    ):

        value = _clean_text(
            record.get(field)
        )

        evidence_length += len(value)

    metadata["evidence_length"] = evidence_length

    # ------------------------------------------------------------
    # Detail fetch information
    # ------------------------------------------------------------

    for field in (
        "detail_url",
        "detail_fetch_status",
        "detail_text_length",
        "evidence_source",
    ):

        if field not in record:
            continue

        value = _clean_text(
            record.get(field)
        )

        if value:
            metadata[field] = value

    return metadata


# ================================================================
# Chunk splitting
# ================================================================

def _split_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[str]:
    """
    Split text into approximately chunk_size character chunks.

    Attempts to preserve:
        paragraphs
        sentences
        words

    before using a hard character boundary.
    """

    text = _normalise_whitespace(
        text
    )

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []

    start = 0
    text_length = len(text)

    while start < text_length:

        target_end = min(
            start + chunk_size,
            text_length,
        )

        if target_end >= text_length:

            chunk = text[start:].strip()

            if chunk:
                chunks.append(chunk)

            break

        boundary = target_end

        # --------------------------------------------------------
        # Prefer paragraph boundary.
        # --------------------------------------------------------

        paragraph_boundary = text.rfind(
            "\n\n",
            start,
            target_end,
        )

        if (
            paragraph_boundary > start
            + int(chunk_size * 0.55)
        ):
            boundary = (
                paragraph_boundary
                + 2
            )

        else:

            # ----------------------------------------------------
            # Prefer sentence boundary.
            # ----------------------------------------------------

            sentence_matches = list(
                re.finditer(
                    r"[.!?](?:\s+|$)",
                    text[start:target_end],
                )
            )

            if sentence_matches:

                last_match = (
                    sentence_matches[-1]
                )

                candidate = (
                    start
                    + last_match.end()
                )

                if candidate > (
                    start
                    + int(
                        chunk_size
                        * 0.55
                    )
                ):
                    boundary = candidate

            else:

                # ------------------------------------------------
                # Prefer word boundary.
                # ------------------------------------------------

                whitespace_boundary = text.rfind(
                    " ",
                    start,
                    target_end,
                )

                if (
                    whitespace_boundary
                    > start
                    + int(
                        chunk_size
                        * 0.55
                    )
                ):
                    boundary = (
                        whitespace_boundary
                    )

        chunk = text[
            start:boundary
        ].strip()

        if chunk:
            chunks.append(chunk)

        if boundary >= text_length:
            break

        next_start = (
            boundary
            - chunk_overlap
        )

        if next_start <= start:
            next_start = boundary

        start = next_start

    return chunks


# ================================================================
# Record chunking
# ================================================================

def chunk_record(
    record: Dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    Convert one parliamentary record into LangChain Documents.
    """

    if not isinstance(record, dict):
        return []

    chunk_size = max(
        MIN_CHUNK_SIZE,
        int(chunk_size),
    )

    chunk_overlap = max(
        0,
        int(chunk_overlap),
    )

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(
            0,
            chunk_size // 5,
        )

    text = _record_to_text(
        record
    )

    if not text:
        return []

    metadata = _build_metadata(
        record
    )

    record_id = metadata[
        "record_id"
    ]

    chunks = _split_text(
        text,
        chunk_size,
        chunk_overlap,
    )

    if not chunks:
        return []

    documents: List[Document] = []

    chunk_count = len(chunks)

    for index, chunk in enumerate(
        chunks
    ):

        chunk_metadata = metadata.copy()

        chunk_number = index + 1

        chunk_id = (
            f"{record_id}:"
            f"{chunk_number}"
        )

        chunk_metadata[
            "chunk_id"
        ] = chunk_id

        chunk_metadata[
            "chunk_number"
        ] = chunk_number

        chunk_metadata[
            "chunk_count"
        ] = chunk_count

        chunk_metadata[
            "is_chunk"
        ] = True

        chunk_metadata[
            "chunk_characters"
        ] = len(chunk)

        documents.append(
            Document(
                page_content=chunk,
                metadata=chunk_metadata,
            )
        )

    return documents


# ================================================================
# Public API
# ================================================================

def create_chunks(
    records: Iterable[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    Convert an iterable of parliamentary records into Documents.
    """

    if records is None:
        return []

    documents: List[Document] = []

    record_count = 0
    skipped_count = 0

    for record in records:

        record_count += 1

        chunks = chunk_record(
            record,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not chunks:
            skipped_count += 1
            continue

        documents.extend(
            chunks
        )

    logger.info(
        "Created %s searchable chunks from %s parliamentary records "
        "(skipped=%s)",
        len(documents),
        record_count,
        skipped_count,
    )

    return documents


# ================================================================
# Compatibility aliases
# ================================================================

def chunk_documents(
    records: Iterable[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """Compatibility alias."""

    return create_chunks(
        records,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def create_document_chunks(
    records: Iterable[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """Compatibility alias."""

    return create_chunks(
        records,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


# ================================================================
# Standalone validation
# ================================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    test_record = {
        "id": "test_001",
        "source": "hansard",
        "type": "Hansard Debate",
        "title": "Role of the Prime Minister",
        "date": "2026-09-04",
        "url": "https://example.org/test",
        "content": (
            "The Prime Minister is the head of the UK Government. "
            "The Prime Minister leads the Government and appoints "
            "ministers. The Prime Minister also provides overall "
            "political direction and represents the Government "
            "in Parliament and internationally."
        ),
        "speaker": "Example Speaker",
        "house": "House of Commons",
    }

    docs = create_chunks(
        [test_record],
        chunk_size=500,
        chunk_overlap=80,
    )

    print(
        "\n"
        "============================================================\n"
        "CHUNKING TEST\n"
        "============================================================"
    )

    print(
        f"Documents created: {len(docs)}"
    )

    for document in docs:

        print(
            "\nChunk ID:",
            document.metadata.get(
                "chunk_id"
            ),
        )

        print(
            "Title:",
            document.metadata.get(
                "title"
            ),
        )

        print(
            "Source:",
            document.metadata.get(
                "source"
            ),
        )

        print(
            "Evidence:",
            document.metadata.get(
                "has_evidence"
            ),
        )

        print(
            "Characters:",
            len(
                document.page_content
            ),
        )

        print(
            "\n",
            document.page_content[:500],
        )