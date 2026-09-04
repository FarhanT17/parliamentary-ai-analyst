"""
Hybrid parliamentary retriever.

Combines:
1. Semantic FAISS retrieval
2. TF-IDF keyword retrieval
3. Reciprocal Rank Fusion (RRF)
4. Query-aware source weighting
5. Evidence quality scoring
6. Exact keyword and phrase matching
7. Parent-record and source diversity
8. Parliamentary evidence prioritisation

Designed for substantive UK Parliament / Hansard records.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from sklearn.feature_extraction.text import TfidfVectorizer


logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid semantic and lexical retriever for parliamentary evidence."""

    # ================================================================
    # Source groups
    # ================================================================

    STRONG_SOURCES = {
        "hansard",
        "hansard_commons",
        "hansard_lords",
        "hansard_written_questions",
        "commons_oral_questions",
        "commons_written_questions",
        "commons_oral_question_times",
        "lords_written_questions",
        "answered_questions",
        "lords_bill_amendments",
        "research_briefings",
        "commons_divisions",
        "lords_divisions",
        "debates",
        "bills",
        "parliament_websearch",
    }

    MEDIUM_SOURCES = {
        "members",
        "election_results",
        "elections",
        "lords_members",
        "eld_commons_members",
    }

    LOW_PRIORITY_SOURCES = {
        "tv_programmes",
        "publication_logs",
        "terms",
    }

    # ================================================================
    # Query intent
    # ================================================================

    SOURCE_HINTS = {
        "debate": {
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
            "debates",
        },
        "debates": {
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
            "debates",
        },
        "speech": {
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
        },
        "speeches": {
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
        },
        "question": {
            "commons_oral_questions",
            "commons_written_questions",
            "answered_questions",
            "lords_written_questions",
            "hansard_written_questions",
            "parliament_websearch",
        },
        "questions": {
            "commons_oral_questions",
            "commons_written_questions",
            "answered_questions",
            "lords_written_questions",
            "hansard_written_questions",
            "parliament_websearch",
        },
        "law": {
            "bills",
            "lords_bill_amendments",
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
        },
        "bill": {
            "bills",
            "lords_bill_amendments",
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
        },
        "legislation": {
            "bills",
            "lords_bill_amendments",
            "hansard",
            "hansard_commons",
            "hansard_lords",
            "parliament_websearch",
        },
        "election": {
            "elections",
            "election_results",
            "parliament_websearch",
        },
        "elections": {
            "elections",
            "election_results",
            "parliament_websearch",
        },
        "member": {
            "members",
            "lords_members",
            "eld_commons_members",
            "parliament_websearch",
        },
        "members": {
            "members",
            "lords_members",
            "eld_commons_members",
            "parliament_websearch",
        },
        "mp": {
            "members",
            "hansard_commons",
            "commons_oral_questions",
            "commons_written_questions",
            "parliament_websearch",
        },
        "mps": {
            "members",
            "hansard_commons",
            "commons_oral_questions",
            "commons_written_questions",
            "parliament_websearch",
        },
        "lord": {
            "lords_members",
            "hansard_lords",
            "lords_written_questions",
            "parliament_websearch",
        },
        "lords": {
            "lords_members",
            "hansard_lords",
            "lords_written_questions",
            "parliament_websearch",
        },
    }

    # ================================================================
    # Stop words
    # ================================================================

    STOP_WORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "what",
        "who",
        "where",
        "when",
        "why",
        "how",
        "does",
        "do",
        "did",
        "is",
        "are",
        "was",
        "were",
        "be",
        "being",
        "been",
        "of",
        "to",
        "in",
        "on",
        "for",
        "from",
        "by",
        "with",
        "about",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "their",
        "they",
        "he",
        "she",
        "we",
        "you",
        "i",
        "uk",
        "united",
        "kingdom",
    }

    # ================================================================
    # Initialisation
    # ================================================================

    def __init__(
        self,
        vectorstore: Optional[FAISS] = None,
        documents: Optional[List[Document]] = None,
        semantic_weight: float = 0.70,
        keyword_weight: float = 0.30,
    ) -> None:

        self.vectorstore = vectorstore

        self.documents: List[Document] = (
            documents.copy()
            if documents
            else []
        )

        self.semantic_weight = float(
            semantic_weight
        )

        self.keyword_weight = float(
            keyword_weight
        )

        total_weight = (
            self.semantic_weight
            + self.keyword_weight
        )

        if total_weight <= 0:
            self.semantic_weight = 0.70
            self.keyword_weight = 0.30
        else:
            self.semantic_weight /= total_weight
            self.keyword_weight /= total_weight

        self.vectorizer: Optional[
            TfidfVectorizer
        ] = None

        self.tfidf_matrix = None

        self.tfidf_document_indices: List[int] = []

        if self.documents:
            self._build_tfidf_index()

        logger.info(
            "HybridRetriever initialized: %s documents, "
            "semantic_weight=%.2f, keyword_weight=%.2f",
            len(self.documents),
            self.semantic_weight,
            self.keyword_weight,
        )

    # ================================================================
    # Text extraction
    # ================================================================

    @staticmethod
    def _safe_string(value: Any) -> str:
        """Convert nested Parliament API values to searchable text."""

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
                    result = HybridRetriever._safe_string(
                        value[key]
                    )

                    if result:
                        return result

            parts = []

            for key, item in value.items():
                if key.startswith("@"):
                    continue

                result = HybridRetriever._safe_string(item)

                if result:
                    parts.append(result)

            return " ".join(parts)

        if isinstance(value, (list, tuple, set)):
            return " ".join(
                HybridRetriever._safe_string(item)
                for item in value
                if item is not None
            ).strip()

        return str(value).strip()

    @classmethod
    def _metadata_text(
        cls,
        document: Document,
    ) -> str:
        """Build rich searchable text from document metadata."""

        metadata = document.metadata or {}

        fields = (
            "title",
            "label",
            "question",
            "answer",
            "content",
            "text",
            "body",
            "full_text",
            "summary",
            "description",
            "details",
            "abstract",
            "speaker",
            "member",
            "asking_member",
            "answering_member",
            "answering_body",
            "department",
            "committee",
            "house",
            "type",
            "subtype",
            "section",
            "topics",
            "bill_stage",
            "clause",
            "decision",
        )

        parts = []

        for field in fields:
            value = cls._safe_string(
                metadata.get(field)
            )

            if value:
                parts.append(value)

        return " ".join(parts)

    @classmethod
    def _document_text(
        cls,
        document: Document,
    ) -> str:
        """Return the strongest searchable representation."""

        page_content = cls._safe_string(
            document.page_content
        )

        metadata_text = cls._metadata_text(
            document
        )

        combined = " ".join(
            part
            for part in (
                metadata_text,
                page_content,
            )
            if part
        )

        return re.sub(
            r"\s+",
            " ",
            combined,
        ).strip()

    # ================================================================
    # TF-IDF
    # ================================================================

    def _build_tfidf_index(self) -> None:

        if not self.documents:
            self.vectorizer = None
            self.tfidf_matrix = None
            self.tfidf_document_indices = []
            return

        texts = []
        indices = []

        for index, document in enumerate(
            self.documents
        ):
            text = self._document_text(
                document
            )

            if text:
                texts.append(text)
                indices.append(index)

        if not texts:
            logger.warning(
                "No usable text available for TF-IDF index."
            )

            self.vectorizer = None
            self.tfidf_matrix = None
            self.tfidf_document_indices = []

            return

        try:
            self.vectorizer = TfidfVectorizer(
                max_features=50000,
                ngram_range=(1, 2),
                sublinear_tf=True,
                min_df=1,
                max_df=0.98,
                strip_accents="unicode",
                lowercase=True,
            )

            self.tfidf_matrix = (
                self.vectorizer.fit_transform(
                    texts
                )
            )

            self.tfidf_document_indices = indices

            logger.info(
                "TF-IDF index built: %s documents, %s features",
                len(indices),
                len(
                    self.vectorizer.get_feature_names_out()
                ),
            )

        except Exception:
            logger.exception(
                "Failed to build TF-IDF index."
            )

            self.vectorizer = None
            self.tfidf_matrix = None
            self.tfidf_document_indices = []

    # ================================================================
    # Identity
    # ================================================================

    @staticmethod
    def _document_key(
        document: Document,
    ) -> str:

        metadata = document.metadata or {}

        chunk_id = metadata.get("chunk_id")

        if chunk_id:
            return f"chunk:{chunk_id}"

        record_id = (
            metadata.get("record_id")
            or metadata.get("id")
        )

        chunk_number = metadata.get(
            "chunk_number"
        )

        if record_id:
            if chunk_number is not None:
                return (
                    f"record:{record_id}:"
                    f"chunk:{chunk_number}"
                )

            return f"record:{record_id}"

        url = metadata.get("url")

        if url:
            return f"url:{url}"

        return f"object:{id(document)}"

    @staticmethod
    def _record_key(
        document: Document,
    ) -> str:

        metadata = document.metadata or {}

        record_id = (
            metadata.get("record_id")
            or metadata.get("id")
        )

        if record_id:
            return str(record_id)

        url = metadata.get("url")

        if url:
            return str(url)

        source = str(
            metadata.get(
                "source",
                "",
            )
        )

        title = str(
            metadata.get(
                "title",
                "",
            )
        )

        return f"{source}|{title}"

    # ================================================================
    # Tokenisation
    # ================================================================

    @classmethod
    def _tokenize(
        cls,
        text: str,
    ) -> List[str]:

        if not text:
            return []

        tokens = re.findall(
            r"[a-zA-Z0-9][a-zA-Z0-9'_-]*",
            text.lower(),
        )

        return [
            token
            for token in tokens
            if token not in cls.STOP_WORDS
            and len(token) > 1
        ]

    @classmethod
    def _query_tokens(
        cls,
        query: str,
    ) -> List[str]:

        return cls._tokenize(query)

    # ================================================================
    # Query intent
    # ================================================================

    @classmethod
    def _query_source_preferences(
        cls,
        query: str,
    ) -> set:

        tokens = set(
            cls._query_tokens(query)
        )

        preferred = set()

        for token in tokens:
            preferred.update(
                cls.SOURCE_HINTS.get(
                    token,
                    set(),
                )
            )

        return preferred

    @classmethod
    def _is_general_knowledge_query(
        cls,
        query: str,
    ) -> bool:

        tokens = set(
            cls._query_tokens(query)
        )

        explicit_record_terms = {
            "debate",
            "debates",
            "speech",
            "speeches",
            "question",
            "questions",
            "bill",
            "bills",
            "law",
            "legislation",
            "election",
            "elections",
        }

        return not (
            tokens
            & explicit_record_terms
        )

    # ================================================================
    # Source quality
    # ================================================================

    @classmethod
    def _source_quality(
        cls,
        document: Document,
        query: str,
    ) -> float:

        source = str(
            (document.metadata or {}).get(
                "source",
                "",
            )
        ).strip().lower()

        preferred = (
            cls._query_source_preferences(
                query
            )
        )

        # For broad factual questions, substantive parliamentary
        # evidence should outrank member metadata.
        if (
            cls._is_general_knowledge_query(
                query
            )
            and source == "members"
        ):
            return 0.72

        if source in preferred:
            return 1.22

        if source in cls.STRONG_SOURCES:
            return 1.12

        if source in cls.MEDIUM_SOURCES:
            return 0.90

        if source in cls.LOW_PRIORITY_SOURCES:
            return 0.65

        return 0.92

    # ================================================================
    # Evidence quality
    # ================================================================

    @classmethod
    def _content_quality(
        cls,
        document: Document,
    ) -> float:

        metadata = document.metadata or {}

        page_content = cls._safe_string(
            document.page_content
        )

        substantive_fields = []

        for field in (
            "content",
            "text",
            "body",
            "full_text",
            "question",
            "answer",
            "summary",
            "description",
            "details",
        ):
            value = cls._safe_string(
                metadata.get(field)
            )

            if value:
                substantive_fields.append(
                    value
                )

        evidence = " ".join(
            [page_content]
            + substantive_fields
        ).strip()

        length = len(evidence)

        if length < 80:
            score = 0.45
        elif length < 180:
            score = 0.70
        elif length < 350:
            score = 0.90
        elif length < 700:
            score = 1.05
        else:
            score = 1.12

        title = cls._safe_string(
            metadata.get("title")
        )

        if (
            title
            and evidence.lower()
            == title.lower()
        ):
            score *= 0.45

        if metadata.get("answer"):
            score *= 1.08

        if metadata.get("question"):
            score *= 1.05

        if (
            metadata.get("content")
            or metadata.get("text")
            or metadata.get("body")
            or metadata.get("full_text")
        ):
            score *= 1.05

        return min(
            max(score, 0.35),
            1.30,
        )

    # ================================================================
    # Lexical matching
    # ================================================================

    @classmethod
    def _keyword_overlap(
        cls,
        query: str,
        document: Document,
    ) -> float:

        query_tokens = set(
            cls._query_tokens(query)
        )

        if not query_tokens:
            return 0.0

        metadata = document.metadata or {}

        title = cls._safe_string(
            metadata.get("title")
        )

        text = cls._document_text(
            document
        )

        text_tokens = set(
            cls._tokenize(text)
        )

        if not text_tokens:
            return 0.0

        overlap = (
            len(
                query_tokens
                & text_tokens
            )
            / len(query_tokens)
        )

        title_tokens = set(
            cls._tokenize(title)
        )

        title_overlap = 0.0

        if title_tokens:
            title_overlap = (
                len(
                    query_tokens
                    & title_tokens
                )
                / len(query_tokens)
            )

        return min(
            1.0,
            overlap * 0.70
            + title_overlap * 0.30,
        )

    @classmethod
    def _phrase_match(
        cls,
        query: str,
        document: Document,
    ) -> float:

        normalized_query = re.sub(
            r"\s+",
            " ",
            query.lower().strip(),
        )

        if len(normalized_query) < 4:
            return 0.0

        metadata = document.metadata or {}

        title = cls._safe_string(
            metadata.get("title")
        ).lower()

        text = cls._document_text(
            document
        ).lower()

        if normalized_query in title:
            return 1.0

        if normalized_query in text:
            return 0.90

        tokens = cls._query_tokens(query)

        if len(tokens) >= 2:
            for size in (
                min(4, len(tokens)),
                min(3, len(tokens)),
                2,
            ):
                phrase = " ".join(
                    tokens[:size]
                )

                if phrase in text:
                    return 0.55

        return 0.0

    # ================================================================
    # Semantic search
    # ================================================================

    def _semantic_search(
        self,
        query: str,
        candidate_k: int,
    ) -> List[Tuple[Document, int]]:

        if (
            self.vectorstore is None
            or not self.documents
        ):
            return []

        try:
            results = (
                self.vectorstore
                .similarity_search_with_score(
                    query,
                    k=min(
                        candidate_k,
                        len(self.documents),
                    ),
                )
            )

            ranked = []

            for rank, item in enumerate(
                results,
                start=1,
            ):
                if not item:
                    continue

                document = item[0]

                ranked.append(
                    (
                        document,
                        rank,
                    )
                )

            return ranked

        except Exception:
            logger.exception(
                "Semantic retrieval failed."
            )

            return []

    # ================================================================
    # TF-IDF search
    # ================================================================

    def _keyword_search(
        self,
        query: str,
        candidate_k: int,
    ) -> List[Tuple[Document, int]]:

        if (
            self.vectorizer is None
            or self.tfidf_matrix is None
            or not self.tfidf_document_indices
        ):
            return []

        try:
            query_vector = (
                self.vectorizer.transform(
                    [query]
                )
            )

            scores = (
                self.tfidf_matrix
                .dot(query_vector.T)
                .toarray()
                .ravel()
            )

            ranked_positions = sorted(
                range(len(scores)),
                key=lambda index: scores[index],
                reverse=True,
            )

            results = []

            for position in ranked_positions:

                if scores[position] <= 0:
                    continue

                document_index = (
                    self.tfidf_document_indices[
                        position
                    ]
                )

                results.append(
                    (
                        self.documents[
                            document_index
                        ],
                        len(results) + 1,
                    )
                )

                if len(results) >= candidate_k:
                    break

            return results

        except Exception:
            logger.exception(
                "Keyword retrieval failed."
            )

            return []

    # ================================================================
    # RRF
    # ================================================================

    def _rrf_combine(
        self,
        semantic_results: List[
            Tuple[Document, int]
        ],
        keyword_results: List[
            Tuple[Document, int]
        ],
    ) -> Dict[str, Dict[str, Any]]:

        combined: Dict[
            str,
            Dict[str, Any]
        ] = {}

        rank_constant = 60.0

        def add_results(
            results: List[
                Tuple[Document, int]
            ],
            weight: float,
            retrieval_type: str,
        ) -> None:

            for document, rank in results:

                key = self._document_key(
                    document
                )

                if key not in combined:
                    combined[key] = {
                        "document": document,
                        "rrf_score": 0.0,
                        "semantic_rank": None,
                        "keyword_rank": None,
                    }

                combined[key][
                    "rrf_score"
                ] += (
                    weight
                    / (
                        rank_constant
                        + float(rank)
                    )
                )

                combined[key][
                    f"{retrieval_type}_rank"
                ] = rank

        add_results(
            semantic_results,
            self.semantic_weight,
            "semantic",
        )

        add_results(
            keyword_results,
            self.keyword_weight,
            "keyword",
        )

        return combined

    # ================================================================
    # Final scoring
    # ================================================================

    def _final_score(
        self,
        query: str,
        document: Document,
        rrf_score: float,
    ) -> float:

        source_quality = (
            self._source_quality(
                document,
                query,
            )
        )

        content_quality = (
            self._content_quality(
                document
            )
        )

        keyword_overlap = (
            self._keyword_overlap(
                query,
                document,
            )
        )

        phrase_match = (
            self._phrase_match(
                query,
                document,
            )
        )

        score = rrf_score

        # Lexical evidence is useful, but RRF remains dominant.
        score += (
            keyword_overlap * 0.025
        )

        score += (
            phrase_match * 0.045
        )

        score *= content_quality
        score *= source_quality

        return score

    # ================================================================
    # Diversity
    # ================================================================

    def _select_diverse(
        self,
        ranked_documents: List[
            Tuple[Document, float]
        ],
        k: int,
    ) -> List[Document]:

        if not ranked_documents:
            return []

        selected = []

        selected_document_keys = set()
        selected_record_keys = set()
        selected_sources = set()

        # Pass 1:
        # Different record and different source.
        for document, _score in ranked_documents:

            if len(selected) >= k:
                break

            document_key = (
                self._document_key(
                    document
                )
            )

            if document_key in selected_document_keys:
                continue

            record_key = (
                self._record_key(
                    document
                )
            )

            if record_key in selected_record_keys:
                continue

            source = self._source_name(
                document
            )

            if (
                source
                and source in selected_sources
            ):
                continue

            selected.append(document)

            selected_document_keys.add(
                document_key
            )

            selected_record_keys.add(
                record_key
            )

            if source:
                selected_sources.add(
                    source
                )

        # Pass 2:
        # Different parent records, source repetition allowed.
        if len(selected) < k:

            for document, _score in ranked_documents:

                if len(selected) >= k:
                    break

                document_key = (
                    self._document_key(
                        document
                    )
                )

                if document_key in selected_document_keys:
                    continue

                record_key = (
                    self._record_key(
                        document
                    )
                )

                if record_key in selected_record_keys:
                    continue

                selected.append(document)

                selected_document_keys.add(
                    document_key
                )

                selected_record_keys.add(
                    record_key
                )

        # Pass 3:
        # Allow multiple chunks from the same record only if necessary.
        if len(selected) < k:

            for document, _score in ranked_documents:

                if len(selected) >= k:
                    break

                document_key = (
                    self._document_key(
                        document
                    )
                )

                if document_key in selected_document_keys:
                    continue

                selected.append(document)

                selected_document_keys.add(
                    document_key
                )

        return selected

    # ================================================================
    # Public retrieval
    # ================================================================

    def retrieve(
        self,
        query: str,
        k: int = 5,
    ) -> List[Document]:

        if not query or not query.strip():
            return []

        if not self.documents:
            logger.warning(
                "Hybrid retrieval requested with no documents."
            )
            return []

        k = max(
            1,
            min(
                int(k),
                len(self.documents),
            ),
        )

        candidate_k = min(
            len(self.documents),
            max(
                k * 10,
                40,
            ),
        )

        semantic_results = (
            self._semantic_search(
                query,
                candidate_k,
            )
        )

        keyword_results = (
            self._keyword_search(
                query,
                candidate_k,
            )
        )

        combined = self._rrf_combine(
            semantic_results,
            keyword_results,
        )

        if not combined:
            logger.warning(
                "Hybrid retrieval produced no candidates for: %s",
                query,
            )
            return []

        ranked = []

        for item in combined.values():

            document = item["document"]

            score = self._final_score(
                query,
                document,
                item["rrf_score"],
            )

            ranked.append(
                (
                    document,
                    score,
                )
            )

        ranked.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        selected = self._select_diverse(
            ranked,
            k,
        )

        logger.info(
            "Hybrid retrieval returned %s results for query: %s",
            len(selected),
            query,
        )

        source_counts = defaultdict(int)

        for document in selected:

            source = self._source_name(
                document
            )

            source_counts[
                source or "unknown"
            ] += 1

        logger.info(
            "Retrieved source distribution: %s",
            dict(source_counts),
        )

        return selected

    # ================================================================
    # Compatibility aliases
    # ================================================================

    def similarity_search(
        self,
        query: str,
        k: int = 5,
    ) -> List[Document]:

        return self.retrieve(
            query,
            k,
        )

    def get_relevant_documents(
        self,
        query: str,
        k: int = 5,
    ) -> List[Document]:

        return self.retrieve(
            query,
            k,
        )

    # ================================================================
    # Index management
    # ================================================================

    def add_documents(
        self,
        documents: List[Document],
    ) -> None:

        if not documents:
            logger.warning(
                "add_documents called with empty list."
            )
            return

        self.documents = documents.copy()

        self._build_tfidf_index()

        logger.info(
            "HybridRetriever document index rebuilt: %s documents",
            len(self.documents),
        )

    def set_vectorstore(
        self,
        vectorstore: FAISS,
    ) -> None:

        self.vectorstore = vectorstore

        logger.info(
            "HybridRetriever vector store updated."
        )

    def clear(self) -> None:

        self.documents = []
        self.vectorstore = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.tfidf_document_indices = []

        logger.info(
            "HybridRetriever cleared."
        )

    # ================================================================
    # Diagnostics
    # ================================================================

    def describe_results(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:

        if not self.documents:
            return []

        candidate_k = min(
            len(self.documents),
            max(k * 10, 40),
        )

        semantic_results = (
            self._semantic_search(
                query,
                candidate_k,
            )
        )

        keyword_results = (
            self._keyword_search(
                query,
                candidate_k,
            )
        )

        combined = self._rrf_combine(
            semantic_results,
            keyword_results,
        )

        rows = []

        for item in combined.values():

            document = item["document"]

            score = self._final_score(
                query,
                document,
                item["rrf_score"],
            )

            rows.append(
                (
                    document,
                    score,
                    item,
                )
            )

        rows.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        output = []

        for document, score, ranking in rows[:k]:

            metadata = (
                document.metadata or {}
            )

            output.append(
                {
                    "score": round(
                        float(score),
                        8,
                    ),
                    "rrf_score": round(
                        float(
                            ranking[
                                "rrf_score"
                            ]
                        ),
                        8,
                    ),
                    "semantic_rank": ranking.get(
                        "semantic_rank"
                    ),
                    "keyword_rank": ranking.get(
                        "keyword_rank"
                    ),
                    "source": metadata.get(
                        "source",
                        "",
                    ),
                    "title": metadata.get(
                        "title",
                        "",
                    ),
                    "id": metadata.get(
                        "id",
                        "",
                    ),
                    "record_id": metadata.get(
                        "record_id",
                        metadata.get(
                            "id",
                            "",
                        ),
                    ),
                    "chunk_id": metadata.get(
                        "chunk_id",
                        "",
                    ),
                    "content_length": len(
                        document.page_content
                        or ""
                    ),
                    "url": metadata.get(
                        "url",
                        "",
                    ),
                }
            )

        return output

    # ================================================================
    # Source helper
    # ================================================================

    @staticmethod
    def _source_name(
        document: Document,
    ) -> str:

        metadata = document.metadata or {}

        return str(
            metadata.get(
                "source",
                "",
            )
        ).strip().lower()