"""
UK Parliament data collector.

Production collector for the current UK Parliament public APIs.

Design goals:
- Use currently available UK Parliament API services.
- Never manufacture "live" parliamentary records.
- Keep sample data strictly opt-in.
- Normalise heterogeneous API responses into one RAG-friendly schema.
- Preserve raw API records for traceability.
- Provide deterministic IDs.
- Save processed JSON for the RAG pipeline.
- Fetch underlying parliamentary pages when WebSearch only returns metadata.
- Reject title-only records from the RAG evidence corpus.

Current API services used:
- Parliamentary WebSearch API
- Members API
- Parliamentary WebSearch result pages
- Written Questions API when a usable public endpoint is available
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class ParliamentaryDataCollector:
    """Collect and normalise data from current UK Parliament APIs."""

    # ------------------------------------------------------------------
    # Current UK Parliament APIs
    # ------------------------------------------------------------------

    WEBSEARCH_BASE_URL = "https://websearch-api.parliament.uk"
    MEMBERS_BASE_URL = "https://members-api.parliament.uk"
    WRITTEN_QUESTIONS_BASE_URL = "https://api.wqa.parliament.uk"

    USER_AGENT = (
        "Parliamentary-AI-Analyst/5.0 "
        "(UK Parliament Hackathon; educational project)"
    )

    # ------------------------------------------------------------------
    # Search configuration
    # ------------------------------------------------------------------

    SEARCH_QUERIES = {
        "parliamentary_search_general": (
            "Parliament UK government legislation debate"
        ),
        "parliamentary_search_prime_minister": (
            "Prime Minister government"
        ),
        "parliamentary_search_legislation": (
            "legislation bill law Parliament"
        ),
        "parliamentary_search_debates": (
            "debate House of Commons House of Lords"
        ),
        "parliamentary_search_questions": (
            "parliamentary question government"
        ),
        "parliamentary_search_economy": (
            "economy taxation spending"
        ),
        "parliamentary_search_health": (
            "NHS health healthcare"
        ),
        "parliamentary_search_immigration": (
            "immigration asylum borders"
        ),
        "parliamentary_search_climate": (
            "climate change environment net zero"
        ),
        "parliamentary_search_foreign_affairs": (
            "foreign affairs international relations"
        ),
    }

    # ------------------------------------------------------------------
    # Page extraction configuration
    # ------------------------------------------------------------------

    MIN_EVIDENCE_CHARS = max(
        80,
        int(os.getenv("PARLIAMENT_MIN_EVIDENCE_CHARS", "180")),
    )

    MAX_PAGE_TEXT_CHARS = max(
        5000,
        int(os.getenv("PARLIAMENT_MAX_PAGE_TEXT_CHARS", "30000")),
    )

    FETCH_DETAIL_PAGES = (
        os.getenv(
            "PARLIAMENT_FETCH_DETAIL_PAGES",
            "true",
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self.data_dir = Path(
            os.getenv(
                "DATA_DIR",
                "data/processed",
            )
        )
        self.data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.timeout = max(
            5,
            int(
                os.getenv(
                    "PARLIAMENT_API_TIMEOUT",
                    "30",
                )
            ),
        )

        self.page_size = max(
            10,
            min(
                int(
                    os.getenv(
                        "PARLIAMENT_PAGE_SIZE",
                        "50",
                    )
                ),
                100,
            ),
        )

        self.max_pages = max(
            1,
            int(
                os.getenv(
                    "PARLIAMENT_MAX_PAGES",
                    "10",
                )
            ),
        )

        self.search_result_limit = max(
            1,
            int(
                os.getenv(
                    "PARLIAMENT_SEARCH_LIMIT",
                    "25",
                )
            ),
        )

        self.member_result_limit = max(
            1,
            int(
                os.getenv(
                    "PARLIAMENT_MEMBER_LIMIT",
                    "100",
                )
            ),
        )

        self.written_question_limit = max(
            1,
            int(
                os.getenv(
                    "PARLIAMENT_WRITTEN_QUESTION_LIMIT",
                    "100",
                )
            ),
        )

        self.use_sample_fallback = (
            os.getenv(
                "USE_SAMPLE_FALLBACK",
                "false",
            )
            .strip()
            .lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        self.session = self._build_session()

        self.stats: Dict[str, Any] = {
            "started_at": None,
            "finished_at": None,
            "datasets_attempted": 0,
            "datasets_successful": 0,
            "datasets_failed": 0,
            "records_collected": 0,
            "records_unique": 0,
            "records_sample": 0,
            "records_live": 0,
            "records_with_evidence": 0,
            "records_without_evidence": 0,
            "pages_fetched": 0,
            "pages_fetch_failed": 0,
            "by_source": {},
            "errors": [],
        }

        logger.info(
            "ParliamentaryDataCollector configured: "
            "page_size=%s max_pages=%s search_limit=%s "
            "fetch_detail_pages=%s min_evidence=%s "
            "sample_fallback=%s",
            self.page_size,
            self.max_pages,
            self.search_result_limit,
            self.FETCH_DETAIL_PAGES,
            self.MIN_EVIDENCE_CHARS,
            self.use_sample_fallback,
        )

    # ==================================================================
    # HTTP
    # ==================================================================

    def _build_session(self) -> requests.Session:
        """Create a requests session with safe retry behaviour."""

        session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1,
            status_forcelist=(
                429,
                500,
                502,
                503,
                504,
            ),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )

        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=10,
        )

        session.mount(
            "https://",
            adapter,
        )
        session.mount(
            "http://",
            adapter,
        )

        session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": (
                    "application/json, "
                    "application/xml;q=0.9, "
                    "text/html;q=0.8, "
                    "text/plain;q=0.7, "
                    "*/*;q=0.5"
                ),
            }
        )

        return session

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Any]:
        """Perform a GET request and decode JSON where possible."""

        try:
            response = self.session.get(
                url,
                params=params or {},
                headers=headers or {},
                timeout=self.timeout,
            )

            if response.status_code != 200:
                logger.warning(
                    "Parliament API returned HTTP %s: %s",
                    response.status_code,
                    response.url,
                )
                return None

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                )
                .lower()
            )

            if (
                "json" in content_type
                or response.text.strip().startswith(("{", "["))
            ):
                try:
                    return response.json()
                except ValueError:
                    pass

            text = response.text.strip()

            if text:
                return {
                    "_raw_text_response": text,
                    "_content_type": content_type,
                    "_url": response.url,
                }

            return None

        except requests.RequestException as exc:
            logger.warning(
                "Parliament API request failed: %s | %s",
                url,
                exc,
            )
            return None

    def _fetch_html_page(
        self,
        url: str,
    ) -> Optional[str]:
        """
        Fetch an underlying Parliament page.

        This is intentionally separate from _make_request because
        WebSearch result pages are normally HTML rather than JSON.
        """

        if not url:
            return None

        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return None

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={
                    "Accept": (
                        "text/html,application/xhtml+xml;"
                        "q=0.9,*/*;q=0.5"
                    )
                },
            )

            if response.status_code != 200:
                logger.debug(
                    "Detail page returned HTTP %s: %s",
                    response.status_code,
                    url,
                )
                self.stats["pages_fetch_failed"] += 1
                return None

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                )
                .lower()
            )

            if (
                "html" not in content_type
                and "xhtml" not in content_type
            ):
                logger.debug(
                    "Detail page is not HTML: %s [%s]",
                    url,
                    content_type,
                )
                self.stats["pages_fetch_failed"] += 1
                return None

            self.stats["pages_fetched"] += 1

            return response.text

        except requests.RequestException as exc:
            self.stats["pages_fetch_failed"] += 1
            logger.debug(
                "Could not fetch detail page %s: %s",
                url,
                exc,
            )
            return None

    # ==================================================================
    # Generic value helpers
    # ==================================================================

    @staticmethod
    def _string(value: Any) -> str:
        """Convert nested API values to readable text."""

        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(
            value,
            (int, float, bool),
        ):
            return str(value)

        if isinstance(value, dict):
            preferred_keys = (
                "_value",
                "value",
                "label",
                "prefLabel",
                "displayAs",
                "display",
                "name",
                "title",
                "text",
                "description",
                "uri",
                "url",
                "id",
            )

            for key in preferred_keys:
                if key in value:
                    result = ParliamentaryDataCollector._string(
                        value[key]
                    )
                    if result:
                        return result

            parts: List[str] = []

            for key, item in value.items():
                if str(key).startswith("@"):
                    continue

                converted = ParliamentaryDataCollector._string(
                    item
                )

                if converted:
                    parts.append(converted)

            return " ".join(parts).strip()

        if isinstance(
            value,
            (list, tuple, set),
        ):
            parts = []

            for item in value:
                converted = ParliamentaryDataCollector._string(
                    item
                )

                if converted:
                    parts.append(converted)

            return "; ".join(parts)

        return str(value).strip()

    @classmethod
    def _first_value(
        cls,
        record: Dict[str, Any],
        keys: Iterable[str],
    ) -> str:
        """Return the first non-empty value."""

        for key in keys:
            if key not in record:
                continue

            value = cls._string(
                record.get(key)
            )

            if value:
                return value

        return ""

    @classmethod
    def _nested_value(
        cls,
        record: Dict[str, Any],
        paths: Iterable[Tuple[str, ...]],
    ) -> str:
        """Read a value from nested dictionaries."""

        for path in paths:
            current: Any = record

            for key in path:
                if not isinstance(current, dict):
                    current = None
                    break

                current = current.get(key)

            value = cls._string(current)

            if value:
                return value

        return ""

    @staticmethod
    def _clean_text(
        value: str,
    ) -> str:
        """Normalise whitespace while preserving paragraphs."""

        if not value:
            return ""

        value = html.unescape(value)

        value = value.replace(
            "\r\n",
            "\n",
        )
        value = value.replace(
            "\r",
            "\n",
        )

        paragraphs: List[str] = []

        for paragraph in value.split("\n"):
            paragraph = re.sub(
                r"[ \t\f\v]+",
                " ",
                paragraph,
            ).strip()

            if paragraph:
                paragraphs.append(paragraph)

        return "\n".join(paragraphs)

    @staticmethod
    def _normalise_url(
        url: str,
        base_url: Optional[str] = None,
    ) -> str:
        """Normalise and validate HTTP(S) URLs."""

        if not url:
            return ""

        url = html.unescape(
            str(url).strip()
        )

        if base_url:
            url = urljoin(
                base_url,
                url,
            )

        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return ""

        if not parsed.netloc:
            return ""

        return url

    # ==================================================================
    # URL / ID helpers
    # ==================================================================

    @classmethod
    def _item_url(
        cls,
        record: Dict[str, Any],
    ) -> str:
        """Extract a public URL from a record."""

        keys = (
            "url",
            "uri",
            "webUrl",
            "web_url",
            "link",
            "href",
            "_about",
            "about",
            "@id",
            "id",
        )

        for key in keys:
            value = cls._string(
                record.get(key)
            )

            value = cls._normalise_url(
                value
            )

            if value:
                return value

        for key in (
            "links",
            "link",
            "navigation",
            "metadata",
        ):
            value = record.get(key)

            if isinstance(
                value,
                dict,
            ):
                for nested_key in (
                    "url",
                    "href",
                    "uri",
                    "webUrl",
                ):
                    candidate = cls._string(
                        value.get(nested_key)
                    )

                    candidate = cls._normalise_url(
                        candidate
                    )

                    if candidate:
                        return candidate

            if isinstance(
                value,
                list,
            ):
                for item in value:
                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    for nested_key in (
                        "url",
                        "href",
                        "uri",
                        "webUrl",
                    ):
                        candidate = cls._string(
                            item.get(nested_key)
                        )

                        candidate = cls._normalise_url(
                            candidate
                        )

                        if candidate:
                            return candidate

        return ""

    @classmethod
    def _record_key(
        cls,
        record: Dict[str, Any],
        source: str,
    ) -> str:
        """Generate a deterministic ID."""

        for key in (
            "id",
            "_id",
            "Id",
            "ID",
            "identifier",
            "uin",
            "UIN",
            "uid",
            "memberId",
            "member_id",
            "questionId",
            "question_id",
            "billId",
            "bill_id",
            "resultId",
            "result_id",
        ):
            value = cls._string(
                record.get(key)
            )

            if value:
                safe_value = re.sub(
                    r"[^A-Za-z0-9_.-]+",
                    "_",
                    value,
                )

                return (
                    f"{source}_{safe_value}"
                )

        url = cls._item_url(
            record
        )

        if url:
            digest = hashlib.sha1(
                url.encode("utf-8")
            ).hexdigest()[:20]

            return (
                f"{source}_{digest}"
            )

        identity_fields = (
            "title",
            "name",
            "question",
            "questionText",
            "text",
            "description",
            "date",
            "dateTime",
            "member",
            "memberName",
            "speaker",
            "content",
        )

        identity = "|".join(
            cls._string(
                record.get(field)
            )
            for field in identity_fields
        )

        if not identity.strip():
            identity = json.dumps(
                record,
                sort_keys=True,
                default=str,
            )

        digest = hashlib.sha1(
            f"{source}|{identity}".encode(
                "utf-8"
            )
        ).hexdigest()[:20]

        return (
            f"{source}_{digest}"
        )

    # ==================================================================
    # HTML evidence extraction
    # ==================================================================

    @classmethod
    def _extract_page_text(
        cls,
        html_text: str,
        title_hint: str = "",
    ) -> str:
        """
        Extract useful visible text from a Parliament HTML page.

        Removes navigation, scripts, styles and boilerplate.
        Prefers Parliament/Hansard content containers where possible.
        """

        if not html_text:
            return ""

        try:
            soup = BeautifulSoup(
                html_text,
                "html.parser",
            )
        except Exception:
            return ""

        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "template",
                "iframe",
            ]
        ):
            element.decompose()

        # Remove obvious navigation and page furniture.
        for selector in (
            "header",
            "footer",
            "nav",
            ".cookie-banner",
            ".cookies",
            ".cookie",
            ".site-header",
            ".site-footer",
            ".navigation",
            ".breadcrumb",
            ".breadcrumbs",
            ".govuk-header",
            ".govuk-footer",
        ):
            try:
                for element in soup.select(
                    selector
                ):
                    element.decompose()
            except Exception:
                continue

        preferred_selectors = (
            "#content",
            ".content",
            "main",
            "[role='main']",
            ".hansard-content",
            ".debate-content",
            ".question-content",
            ".written-question",
            ".oral-question",
            ".article",
            "article",
        )

        selected = None

        for selector in preferred_selectors:
            try:
                candidate = soup.select_one(
                    selector
                )
            except Exception:
                candidate = None

            if candidate is None:
                continue

            candidate_text = cls._clean_text(
                candidate.get_text(
                    "\n",
                    strip=True,
                )
            )

            if len(candidate_text) >= cls.MIN_EVIDENCE_CHARS:
                selected = candidate
                break

        target = (
            selected
            if selected is not None
            else soup.body or soup
        )

        text = cls._clean_text(
            target.get_text(
                "\n",
                strip=True,
            )
        )

        # Remove repeated empty lines.
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        # Remove very common navigation-only lines.
        blocked_exact = {
            "Menu",
            "Search",
            "Home",
            "Skip to main content",
            "Cookies",
            "Accept cookies",
            "Reject cookies",
            "Close",
        }

        lines: List[str] = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if line in blocked_exact:
                continue

            lines.append(line)

        text = "\n".join(lines)

        # Avoid storing a page where the only useful text is the title.
        if title_hint:
            normalised_text = re.sub(
                r"\s+",
                " ",
                text.lower(),
            ).strip()

            normalised_title = re.sub(
                r"\s+",
                " ",
                title_hint.lower(),
            ).strip()

            if (
                normalised_text
                and normalised_text == normalised_title
            ):
                return ""

        if len(text) > cls.MAX_PAGE_TEXT_CHARS:
            text = (
                text[: cls.MAX_PAGE_TEXT_CHARS]
                + "\n[Page text truncated]"
            )

        return text

    @classmethod
    def _extract_links_from_html(
        cls,
        html_text: str,
        base_url: str,
    ) -> List[str]:
        """Extract useful Parliament links from a page."""

        if not html_text:
            return []

        try:
            soup = BeautifulSoup(
                html_text,
                "html.parser",
            )
        except Exception:
            return []

        urls: List[str] = []

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = cls._normalise_url(
                anchor.get("href", ""),
                base_url=base_url,
            )

            if not href:
                continue

            parsed = urlparse(href)

            if "parliament.uk" not in parsed.netloc.lower():
                continue

            if href not in urls:
                urls.append(href)

        return urls

    # ==================================================================
    # Record normalisation
    # ==================================================================

    @classmethod
    def _normalise_record(
        cls,
        record: Dict[str, Any],
        source: str,
        record_type: str,
        is_sample: bool = False,
    ) -> Dict[str, Any]:
        """Convert an API record into the RAG common schema."""

        if not isinstance(
            record,
            dict,
        ):
            record = {
                "value": record
            }

        record = dict(record)

        record_id = cls._record_key(
            record,
            source,
        )

        title = cls._nested_value(
            record,
            (
                ("title",),
                ("name",),
                ("displayAs",),
                ("label",),
                ("subject",),
                ("question",),
                ("questionText",),
                ("QuestionText",),
                ("eventTitle",),
                ("debateTitle",),
                ("description",),
            ),
        )

        date = cls._nested_value(
            record,
            (
                ("date",),
                ("Date",),
                ("dateTime",),
                ("DateTime",),
                ("published",),
                ("publicationDate",),
                ("sittingDate",),
                ("SittingDate",),
                ("eventDate",),
                ("answerDate",),
                ("AnswerDate",),
                ("AnsweredWhen",),
                ("TabledWhen",),
                ("DueForAnswer",),
            ),
        )

        url = cls._item_url(
            record
        )

        question = cls._nested_value(
            record,
            (
                ("question",),
                ("questionText",),
                ("QuestionText",),
                ("questionTextValue",),
                ("text",),
                ("Question",),
                ("body",),
            ),
        )

        answer = cls._nested_value(
            record,
            (
                ("answer",),
                ("answerText",),
                ("AnswerText",),
                ("answeringText",),
                ("Answer",),
                ("response",),
                ("responseText",),
                ("answerBody",),
            ),
        )

        content = cls._nested_value(
            record,
            (
                ("content",),
                ("body",),
                ("fullText",),
                ("full_text",),
                ("proceedings",),
                ("summary",),
                ("abstract",),
                ("description",),
                ("details",),
                ("snippet",),
                ("text",),
            ),
        )

        speaker = cls._nested_value(
            record,
            (
                ("speaker",),
                ("speakerName",),
                ("member",),
                ("memberName",),
                ("MemberName",),
                ("person",),
                ("personName",),
                ("askedBy",),
                ("askingMember",),
                ("AskingMember",),
            ),
        )

        member = cls._nested_value(
            record,
            (
                ("member",),
                ("memberName",),
                ("MemberName",),
                ("person",),
                ("personName",),
                ("AskingMember",),
            ),
        )

        constituency = cls._nested_value(
            record,
            (
                ("constituency",),
                ("Constituency",),
                ("memberConstituency",),
            ),
        )

        house = cls._nested_value(
            record,
            (
                ("house",),
                ("House",),
                ("houseName",),
                ("HouseName",),
            ),
        )

        party = cls._nested_value(
            record,
            (
                ("party",),
                ("partyName",),
                ("PartyName",),
            ),
        )

        department = cls._nested_value(
            record,
            (
                ("department",),
                ("Department",),
                ("governmentDepartment",),
                ("answeringDepartment",),
            ),
        )

        answering_body = cls._nested_value(
            record,
            (
                ("answeringBody",),
                ("AnsweringBody",),
                ("answeringDepartment",),
                ("department",),
            ),
        )

        committee = cls._nested_value(
            record,
            (
                ("committee",),
                ("Committee",),
                ("committeeName",),
            ),
        )

        question_type = cls._nested_value(
            record,
            (
                ("questionType",),
                ("QuestionType",),
                ("type",),
            ),
        )

        bill = cls._nested_value(
            record,
            (
                ("bill",),
                ("billTitle",),
                ("billName",),
            ),
        )

        stage = cls._nested_value(
            record,
            (
                ("stage",),
                ("billStage",),
                ("stageName",),
            ),
        )

        decision = cls._nested_value(
            record,
            (
                ("decision",),
                ("result",),
            ),
        )

        topics = cls._nested_value(
            record,
            (
                ("topics",),
                ("topic",),
                ("subject",),
            ),
        )

        labels = [
            ("Title", title),
            ("Type", record_type),
            ("Date", date),
            ("Question", question),
            ("Answer", answer),
            ("Content", content),
            ("Speaker", speaker),
            ("Member", member),
            ("Constituency", constituency),
            ("House", house),
            ("Party", party),
            ("Department", department),
            ("Answering body", answering_body),
            ("Committee", committee),
            ("Question type", question_type),
            ("Bill", bill),
            ("Stage", stage),
            ("Decision", decision),
            ("Topics", topics),
        ]

        text_parts: List[str] = []

        for label, value in labels:
            value = cls._clean_text(
                value
            )

            if value:
                text_parts.append(
                    f"{label}: {value}"
                )

        additional_fields = (
            "summary",
            "abstract",
            "description",
            "body",
            "fullText",
            "full_text",
            "snippet",
            "proceedings",
            "details",
            "location",
            "majority",
            "turnout",
            "electorate",
            "paperNumber",
            "paper_number",
            "identifier",
            "uin",
            "UIN",
            "reference",
            "AnsweredWhen",
            "TabledWhen",
            "DueForAnswer",
        )

        known_values = {
            value
            for _, value in labels
            if value
        }

        for field in additional_fields:
            value = cls._string(
                record.get(field)
            )

            value = cls._clean_text(
                value
            )

            if (
                value
                and value not in known_values
            ):
                text_parts.append(
                    f"{field}: {value}"
                )

        text = "\n".join(
            part
            for part in text_parts
            if part.strip()
        )

        if not text:
            fallback_parts: List[str] = []

            for key, value in record.items():
                if str(key).startswith("@"):
                    continue

                if key in {
                    "raw_result",
                    "raw_page_html",
                    "page_links",
                }:
                    continue

                converted = cls._clean_text(
                    cls._string(value)
                )

                if converted:
                    fallback_parts.append(
                        f"{key}: {converted}"
                    )

            text = "\n".join(
                fallback_parts
            )

        normalized: Dict[str, Any] = {
            "id": record_id,
            "source": source,
            "type": record_type,
            "title": title or record_type,
            "date": date,
            "url": url,
            "question": question,
            "answer": answer,
            "content": content,
            "text": text,
            "speaker": speaker,
            "member": member,
            "constituency": constituency,
            "house": house,
            "party": party,
            "department": department,
            "answering_body": answering_body,
            "committee": committee,
            "question_type": question_type,
            "bill": bill,
            "stage": stage,
            "decision": decision,
            "topics": topics,
            "is_sample": bool(is_sample),
            "raw_data": record,
        }

        return normalized

    # ==================================================================
    # WebSearch response handling
    # ==================================================================

    @classmethod
    def _extract_search_items(
        cls,
        payload: Any,
    ) -> List[Dict[str, Any]]:
        """
        Extract search records from JSON responses.

        Supports common JSON/OpenSearch representations.
        """

        if payload is None:
            return []

        if isinstance(
            payload,
            list,
        ):
            return [
                item
                for item in payload
                if isinstance(
                    item,
                    dict,
                )
            ]

        if not isinstance(
            payload,
            dict,
        ):
            return []

        for key in (
            "results",
            "items",
            "records",
            "data",
            "documents",
            "searchResults",
            "SearchResults",
        ):
            value = payload.get(key)

            if isinstance(
                value,
                list,
            ):
                return [
                    item
                    for item in value
                    if isinstance(
                        item,
                        dict,
                    )
                ]

        for outer_key in (
            "result",
            "Result",
            "searchResult",
            "SearchResult",
        ):
            result = payload.get(
                outer_key
            )

            if isinstance(
                result,
                dict,
            ):
                for key in (
                    "items",
                    "results",
                    "records",
                    "data",
                    "documents",
                ):
                    value = result.get(
                        key
                    )

                    if isinstance(
                        value,
                        list,
                    ):
                        return [
                            item
                            for item in value
                            if isinstance(
                                item,
                                dict,
                            )
                        ]

        title = payload.get(
            "title"
        )
        links = payload.get(
            "link"
        )
        descriptions = payload.get(
            "description"
        )

        if (
            isinstance(title, list)
            or isinstance(links, list)
            or isinstance(descriptions, list)
        ):
            titles = (
                title
                if isinstance(title, list)
                else []
            )

            urls = (
                links
                if isinstance(links, list)
                else []
            )

            descriptions_list = (
                descriptions
                if isinstance(
                    descriptions,
                    list,
                )
                else []
            )

            count = max(
                len(titles),
                len(urls),
                len(descriptions_list),
            )

            items = []

            for index in range(count):
                items.append(
                    {
                        "title": (
                            titles[index]
                            if index < len(titles)
                            else ""
                        ),
                        "url": (
                            urls[index]
                            if index < len(urls)
                            else ""
                        ),
                        "description": (
                            descriptions_list[index]
                            if index < len(descriptions_list)
                            else ""
                        ),
                    }
                )

            return items

        return []

    @classmethod
    def _normalise_search_result(
        cls,
        item: Dict[str, Any],
        query: str,
    ) -> Dict[str, Any]:
        """Convert one WebSearch result into a common record."""

        title = cls._first_value(
            item,
            (
                "title",
                "Title",
                "name",
                "Name",
            ),
        )

        description = cls._first_value(
            item,
            (
                "description",
                "Description",
                "snippet",
                "Snippet",
                "summary",
                "Summary",
                "text",
            ),
        )

        url = cls._item_url(
            item
        )

        published = cls._first_value(
            item,
            (
                "published",
                "publicationDate",
                "date",
                "Date",
                "lastModified",
            ),
        )

        result_type = cls._first_value(
            item,
            (
                "type",
                "contentType",
                "category",
                "resultType",
            ),
        )

        return {
            "title": title,
            "description": description,
            "url": url,
            "date": published,
            "type": result_type,
            "search_query": query,
            "raw_result": item,
        }

    def _enrich_search_result(
        self,
        search_record: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and attach actual page evidence to a WebSearch result.

        Search metadata by itself is deliberately not accepted as the
        final RAG evidence when it is only a title.
        """

        title = self._string(
            search_record.get("title")
        )

        description = self._clean_text(
            self._string(
                search_record.get(
                    "description"
                )
            )
        )

        url = self._normalise_url(
            self._string(
                search_record.get("url")
            )
        )

        page_text = ""

        if (
            self.FETCH_DETAIL_PAGES
            and url
        ):
            page_html = self._fetch_html_page(
                url
            )

            if page_html:
                page_text = self._extract_page_text(
                    page_html,
                    title_hint=title,
                )

        # Build actual evidence from the fetched page.
        evidence_parts: List[str] = []

        if page_text:
            evidence_parts.append(
                page_text
            )

        # Search description can contain useful actual text.
        # It is accepted only if it contains substantive information.
        if (
            description
            and len(description) >= self.MIN_EVIDENCE_CHARS
        ):
            if description not in evidence_parts:
                evidence_parts.append(
                    f"Search description: {description}"
                )

        if not evidence_parts:
            logger.debug(
                "Discarding title-only search result: %s",
                title,
            )
            return None

        evidence = "\n\n".join(
            evidence_parts
        )

        record = {
            "title": title,
            "description": description,
            "content": page_text,
            "text": evidence,
            "url": url,
            "date": self._string(
                search_record.get("date")
            ),
            "type": self._string(
                search_record.get("type")
            ),
            "search_query": self._string(
                search_record.get("search_query")
            ),
            "raw_result": search_record.get(
                "raw_result",
                {},
            ),
            "page_fetched": bool(
                page_text
            ),
        }

        normalized = self._normalise_record(
            record,
            source="parliament_websearch",
            record_type=(
                self._string(
                    search_record.get(
                        "type"
                    )
                )
                or "Parliamentary Web Search Result"
            ),
            is_sample=False,
        )

        # Make sure fetched evidence survives normalisation.
        normalized["content"] = page_text
        normalized["text"] = evidence

        return normalized

    def _fetch_websearch(
        self,
        source: str,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Search the current Parliamentary WebSearch API and enrich
        each result with underlying page content.
        """

        url = (
            f"{self.WEBSEARCH_BASE_URL}"
            "/query"
        )

        params = {
            "q": query,
        }

        payload = self._make_request(
            url,
            params=params,
            headers={
                "Accept": "application/json",
            },
        )

        if payload is None:
            logger.warning(
                "WebSearch returned no response for query: %s",
                query,
            )
            return []

        items = self._extract_search_items(
            payload
        )

        if not items:
            logger.warning(
                "WebSearch returned no structured results "
                "for query: %s",
                query,
            )
            return []

        records: List[Dict[str, Any]] = []

        raw_limit = min(
            len(items),
            self.search_result_limit,
        )

        enriched_count = 0

        for item in items[:raw_limit]:
            search_record = self._normalise_search_result(
                item,
                query,
            )

            enriched = self._enrich_search_result(
                search_record
            )

            if enriched is None:
                continue

            records.append(
                enriched
            )
            enriched_count += 1

        logger.info(
            "WebSearch query '%s': %s usable records "
            "from %s search results",
            query,
            enriched_count,
            raw_limit,
        )

        return records

    # ==================================================================
    # Members API
    # ==================================================================

    @classmethod
    def _extract_items_from_payload(
        cls,
        payload: Any,
    ) -> List[Dict[str, Any]]:
        """Generic extraction for current REST APIs."""

        if payload is None:
            return []

        if isinstance(
            payload,
            list,
        ):
            return [
                item
                for item in payload
                if isinstance(
                    item,
                    dict,
                )
            ]

        if not isinstance(
            payload,
            dict,
        ):
            return []

        for key in (
            "items",
            "results",
            "records",
            "data",
            "members",
            "value",
        ):
            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return [
                    item
                    for item in value
                    if isinstance(
                        item,
                        dict,
                    )
                ]

        for key in (
            "result",
            "Result",
        ):
            result = payload.get(
                key
            )

            if isinstance(
                result,
                dict,
            ):
                for nested_key in (
                    "items",
                    "results",
                    "records",
                    "data",
                ):
                    value = result.get(
                        nested_key
                    )

                    if isinstance(
                        value,
                        list,
                    ):
                        return [
                            item
                            for item in value
                            if isinstance(
                                item,
                                dict,
                            )
                        ]

        return []

    def _fetch_members(
        self,
    ) -> List[Dict[str, Any]]:
        """Fetch current Members API records."""

        url = (
            f"{self.MEMBERS_BASE_URL}"
            "/api/Members/Search"
        )

        params = {
            "House": "All",
            "IsCurrent": "true",
            "Skip": 0,
            "Take": min(
                self.member_result_limit,
                100,
            ),
        }

        payload = self._make_request(
            url,
            params=params,
        )

        if payload is None:
            logger.warning(
                "Members API returned no usable response."
            )
            return []

        items = self._extract_items_from_payload(
            payload
        )

        if not items:
            logger.warning(
                "Members API returned no member records."
            )
            return []

        records: List[Dict[str, Any]] = []

        for item in items[
            : self.member_result_limit
        ]:
            if isinstance(
                item.get("value"),
                dict,
            ):
                combined = dict(item)
                combined.update(
                    item["value"]
                )
                item = combined

            normalized = self._normalise_record(
                item,
                source="members",
                record_type="Parliamentary Member",
                is_sample=False,
            )

            records.append(
                normalized
            )

        logger.info(
            "Members API: %s records",
            len(records),
        )

        return records

    # ==================================================================
    # Written Questions API
    # ==================================================================

    def _fetch_written_questions(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Attempt to fetch written questions.

        The public WQA service has a documented REST API, but its root
        does not expose question records directly. We therefore do not
        guess undocumented routes. If a known endpoint responds with
        usable records, they are accepted; otherwise this source is
        simply skipped.
        """

        candidate_urls = [
            (
                f"{self.WRITTEN_QUESTIONS_BASE_URL}"
                "/api/Questions"
            ),
            (
                f"{self.WRITTEN_QUESTIONS_BASE_URL}"
                "/api/PublishedWrittenQuestions"
            ),
            (
                f"{self.WRITTEN_QUESTIONS_BASE_URL}"
                "/api/Questions/Published"
            ),
        ]

        for url in candidate_urls:
            payload = self._make_request(
                url
            )

            if payload is None:
                continue

            items = self._extract_items_from_payload(
                payload
            )

            if not items:
                continue

            records: List[Dict[str, Any]] = []

            for item in items[
                : self.written_question_limit
            ]:
                normalized = self._normalise_record(
                    item,
                    source="written_questions",
                    record_type=(
                        "Written Parliamentary Question"
                    ),
                    is_sample=False,
                )

                records.append(
                    normalized
                )

            if records:
                logger.info(
                    "Written Questions API: %s records from %s",
                    len(records),
                    url,
                )
                return records

        logger.info(
            "Written Questions API did not expose a usable "
            "enumerable public records endpoint. "
            "No fabricated written-question data was added."
        )

        return []

    # ==================================================================
    # Sample fallback
    # ==================================================================

    @staticmethod
    def _sample_records() -> List[Dict[str, Any]]:
        """Explicit demo records, never used unless enabled."""

        samples = [
            {
                "id": "sample_pm_role",
                "title": "Prime Minister and Government",
                "question": (
                    "What is the role of the Prime Minister?"
                ),
                "content": (
                    "The Prime Minister is the head of "
                    "the UK Government and leads the work "
                    "of the government."
                ),
                "date": "2026-01-01",
                "url": "https://www.parliament.uk/",
            },
            {
                "id": "sample_parliament",
                "title": "Parliamentary Government",
                "content": (
                    "Parliament scrutinises the work "
                    "of government, debates legislation "
                    "and considers matters of public policy."
                ),
                "date": "2026-01-01",
                "url": "https://www.parliament.uk/",
            },
        ]

        return [
            ParliamentaryDataCollector._normalise_record(
                record,
                source="sample_data",
                record_type="Sample Parliamentary Data",
                is_sample=True,
            )
            for record in samples
        ]

    # ==================================================================
    # Evidence validation
    # ==================================================================

    @classmethod
    def _has_substantive_evidence(
        cls,
        record: Dict[str, Any],
    ) -> bool:
        """
        Determine whether a record contains enough actual evidence
        to be indexed by the RAG system.
        """

        question = cls._clean_text(
            cls._string(
                record.get("question")
            )
        )

        answer = cls._clean_text(
            cls._string(
                record.get("answer")
            )
        )

        content = cls._clean_text(
            cls._string(
                record.get("content")
            )
        )

        text = cls._clean_text(
            cls._string(
                record.get("text")
            )
        )

        substantive_parts = [
            value
            for value in (
                question,
                answer,
                content,
                text,
            )
            if value
        ]

        if not substantive_parts:
            return False

        total_length = sum(
            len(value)
            for value in substantive_parts
        )

        if total_length < cls.MIN_EVIDENCE_CHARS:
            return False

        title = cls._clean_text(
            cls._string(
                record.get("title")
            )
        )

        if (
            title
            and text
            and text.strip().lower()
            == f"title: {title}".strip().lower()
        ):
            return False

        return True

    # ==================================================================
    # Deduplication
    # ==================================================================

    @classmethod
    def _deduplicate(
        cls,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicates while preserving the most useful version.

        If the same URL appears more than once, prefer the record with
        the longest substantive evidence.
        """

        by_id: Dict[str, Dict[str, Any]] = {}
        by_url: Dict[str, Dict[str, Any]] = {}
        unique: List[Dict[str, Any]] = []

        def evidence_length(
            record: Dict[str, Any],
        ) -> int:
            values = [
                cls._string(
                    record.get("question")
                ),
                cls._string(
                    record.get("answer")
                ),
                cls._string(
                    record.get("content")
                ),
                cls._string(
                    record.get("text")
                ),
            ]

            return sum(
                len(value)
                for value in values
            )

        for record in records:
            record_id = cls._string(
                record.get("id")
            )

            url = cls._string(
                record.get("url")
            )

            if (
                record_id
                and record_id in by_id
            ):
                existing = by_id[
                    record_id
                ]

                if (
                    evidence_length(record)
                    > evidence_length(existing)
                ):
                    index = unique.index(
                        existing
                    )
                    unique[index] = record
                    by_id[record_id] = record

                continue

            if (
                url
                and url in by_url
            ):
                existing = by_url[
                    url
                ]

                if (
                    evidence_length(record)
                    > evidence_length(existing)
                ):
                    index = unique.index(
                        existing
                    )
                    unique[index] = record
                    by_url[url] = record

                    if existing.get("id"):
                        by_id[
                            existing["id"]
                        ] = record

                continue

            text = cls._clean_text(
                cls._string(
                    record.get("text")
                )
            )

            content_hash = ""

            if len(text) >= 300:
                content_hash = hashlib.sha1(
                    text.lower().encode(
                        "utf-8"
                    )
                ).hexdigest()

            duplicate_by_content = False

            if content_hash:
                for existing in unique:
                    existing_text = cls._clean_text(
                        cls._string(
                            existing.get("text")
                        )
                    )

                    if len(existing_text) < 300:
                        continue

                    existing_hash = hashlib.sha1(
                        existing_text.lower().encode(
                            "utf-8"
                        )
                    ).hexdigest()

                    if existing_hash == content_hash:
                        duplicate_by_content = True
                        break

            if duplicate_by_content:
                continue

            unique.append(
                record
            )

            if record_id:
                by_id[
                    record_id
                ] = record

            if url:
                by_url[
                    url
                ] = record

        return unique

    # ==================================================================
    # Save
    # ==================================================================

    def save_data(
        self,
        records: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> str:
        """Save normalised records to JSON."""

        if filename is None:
            timestamp = datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d_%H%M%S"
            )

            filename = (
                "parliamentary_data_"
                f"{timestamp}.json"
            )

        output_path = (
            self.data_dir / filename
        )

        payload = {
            "metadata": {
                "created_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "record_count": len(
                    records
                ),
                "data_source": (
                    self._determine_data_source(
                        records
                    )
                ),
                "collector": (
                    "ParliamentaryDataCollector"
                ),
                "version": "5.0",
                "collection_stats": self.stats,
            },
            "records": records,
        }

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        logger.info(
            "Saved %s records to %s",
            len(records),
            output_path,
        )

        return str(output_path)

    # ==================================================================
    # Main collection method
    # ==================================================================

    def fetch_all_advanced_data(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Collect current UK Parliament data.

        WebSearch discovers relevant parliamentary pages and this
        collector fetches the underlying pages so the RAG pipeline
        receives actual evidence rather than titles only.
        """

        self.stats = {
            "started_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "finished_at": None,
            "datasets_attempted": 0,
            "datasets_successful": 0,
            "datasets_failed": 0,
            "records_collected": 0,
            "records_unique": 0,
            "records_sample": 0,
            "records_live": 0,
            "records_with_evidence": 0,
            "records_without_evidence": 0,
            "pages_fetched": 0,
            "pages_fetch_failed": 0,
            "by_source": {},
            "errors": [],
        }

        all_records: List[
            Dict[str, Any]
        ] = []

        # --------------------------------------------------------------
        # Parliamentary WebSearch
        # --------------------------------------------------------------

        for source, query in (
            self.SEARCH_QUERIES.items()
        ):
            self.stats[
                "datasets_attempted"
            ] += 1

            try:
                records = self._fetch_websearch(
                    source,
                    query,
                )

                if records:
                    self.stats[
                        "datasets_successful"
                    ] += 1

                    all_records.extend(
                        records
                    )

                    self.stats[
                        "by_source"
                    ][source] = {
                        "status": "success",
                        "records": len(
                            records
                        ),
                        "api": (
                            "Parliamentary WebSearch"
                        ),
                        "query": query,
                        "detail_pages_fetched": sum(
                            1
                            for record in records
                            if record.get(
                                "raw_data",
                                {}
                            ).get(
                                "page_fetched",
                                False,
                            )
                        ),
                    }

                else:
                    self.stats[
                        "datasets_failed"
                    ] += 1

                    self.stats[
                        "by_source"
                    ][source] = {
                        "status": (
                            "unavailable_or_empty"
                        ),
                        "records": 0,
                        "api": (
                            "Parliamentary WebSearch"
                        ),
                        "query": query,
                    }

            except Exception as exc:
                self.stats[
                    "datasets_failed"
                ] += 1

                error = (
                    f"{source}: {exc}"
                )

                self.stats[
                    "errors"
                ].append(
                    error
                )

                self.stats[
                    "by_source"
                ][source] = {
                    "status": "failed",
                    "records": 0,
                    "api": (
                        "Parliamentary WebSearch"
                    ),
                    "error": str(exc),
                }

                logger.exception(
                    "WebSearch collection failed: %s",
                    source,
                )

        # --------------------------------------------------------------
        # Members
        # --------------------------------------------------------------

        self.stats[
            "datasets_attempted"
        ] += 1

        try:
            member_records = (
                self._fetch_members()
            )

            if member_records:
                self.stats[
                    "datasets_successful"
                ] += 1

                all_records.extend(
                    member_records
                )

                self.stats[
                    "by_source"
                ]["members"] = {
                    "status": "success",
                    "records": len(
                        member_records
                    ),
                    "api": "Members API",
                }

            else:
                self.stats[
                    "datasets_failed"
                ] += 1

                self.stats[
                    "by_source"
                ]["members"] = {
                    "status": (
                        "unavailable_or_empty"
                    ),
                    "records": 0,
                    "api": "Members API",
                }

        except Exception as exc:
            self.stats[
                "datasets_failed"
            ] += 1

            self.stats[
                "errors"
            ].append(
                f"members: {exc}"
            )

            self.stats[
                "by_source"
            ]["members"] = {
                "status": "failed",
                "records": 0,
                "api": "Members API",
                "error": str(exc),
            }

            logger.exception(
                "Members API collection failed."
            )

        # --------------------------------------------------------------
        # Written Questions
        # --------------------------------------------------------------

        self.stats[
            "datasets_attempted"
        ] += 1

        try:
            question_records = (
                self._fetch_written_questions()
            )

            if question_records:
                self.stats[
                    "datasets_successful"
                ] += 1

                all_records.extend(
                    question_records
                )

                self.stats[
                    "by_source"
                ]["written_questions"] = {
                    "status": "success",
                    "records": len(
                        question_records
                    ),
                    "api": (
                        "Written Questions API"
                    ),
                }

            else:
                # This is not treated as a hard API failure.
                # The current public service may expose documentation
                # without an enumerable root collection.
                self.stats[
                    "by_source"
                ]["written_questions"] = {
                    "status": (
                        "unavailable_or_no_public_collection"
                    ),
                    "records": 0,
                    "api": (
                        "Written Questions API"
                    ),
                }

        except Exception as exc:
            self.stats[
                "datasets_failed"
            ] += 1

            self.stats[
                "errors"
            ].append(
                f"written_questions: {exc}"
            )

            self.stats[
                "by_source"
            ]["written_questions"] = {
                "status": "failed",
                "records": 0,
                "api": (
                    "Written Questions API"
                ),
                "error": str(exc),
            }

            logger.exception(
                "Written Questions API collection failed."
            )

        # --------------------------------------------------------------
        # Optional sample fallback
        # --------------------------------------------------------------

        if (
            not all_records
            and self.use_sample_fallback
        ):
            logger.warning(
                "No live parliamentary records were collected. "
                "USE_SAMPLE_FALLBACK=true, loading explicit demo data."
            )

            all_records.extend(
                self._sample_records()
            )

        # --------------------------------------------------------------
        # Remove records with no substantive evidence.
        # --------------------------------------------------------------

        evidence_records: List[
            Dict[str, Any]
        ] = []

        for record in all_records:
            if self._has_substantive_evidence(
                record
            ):
                evidence_records.append(
                    record
                )

        self.stats[
            "records_without_evidence"
        ] = (
            len(all_records)
            - len(evidence_records)
        )

        self.stats[
            "records_with_evidence"
        ] = len(
            evidence_records
        )

        # --------------------------------------------------------------
        # Deduplicate
        # --------------------------------------------------------------

        self.stats[
            "records_collected"
        ] = len(
            evidence_records
        )

        unique_records = self._deduplicate(
            evidence_records
        )

        self.stats[
            "records_unique"
        ] = len(
            unique_records
        )

        self.stats[
            "records_sample"
        ] = sum(
            1
            for record in unique_records
            if record.get(
                "is_sample",
                False,
            )
        )

        self.stats[
            "records_live"
        ] = (
            len(unique_records)
            - self.stats[
                "records_sample"
            ]
        )

        self.stats[
            "finished_at"
        ] = datetime.now(
            timezone.utc
        ).isoformat()

        logger.info(
            "Parliament collection completed: "
            "%s unique records, %s live, %s sample",
            self.stats[
                "records_unique"
            ],
            self.stats[
                "records_live"
            ],
            self.stats[
                "records_sample"
            ],
        )

        logger.info(
            "Evidence quality: %s records with evidence, "
            "%s rejected as insufficient evidence",
            self.stats[
                "records_with_evidence"
            ],
            self.stats[
                "records_without_evidence"
            ],
        )

        logger.info(
            "Detail pages fetched: %s, failed: %s",
            self.stats[
                "pages_fetched"
            ],
            self.stats[
                "pages_fetch_failed"
            ],
        )

        logger.info(
            "Dataset coverage: %s/%s successful",
            self.stats[
                "datasets_successful"
            ],
            self.stats[
                "datasets_attempted"
            ],
        )

        for source, source_stats in (
            self.stats[
                "by_source"
            ].items()
        ):
            logger.info(
                "Source %-40s %s records [%s]",
                source,
                source_stats.get(
                    "records",
                    0,
                ),
                source_stats.get(
                    "status"
                ),
            )

        return unique_records

    # ==================================================================
    # Compatibility aliases
    # ==================================================================

    def fetch_all_data(
        self,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible alias."""

        return self.fetch_all_advanced_data()

    def collect_all_data(
        self,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible alias."""

        return self.fetch_all_advanced_data()

    # ==================================================================
    # Data source
    # ==================================================================

    @staticmethod
    def _determine_data_source(
        records: List[Dict[str, Any]],
    ) -> str:
        """Determine whether records are live, sample, mixed, or empty."""

        if not records:
            return "none"

        has_live = any(
            not record.get(
                "is_sample",
                False,
            )
            for record in records
        )

        has_sample = any(
            record.get(
                "is_sample",
                False,
            )
            for record in records
        )

        if has_live and has_sample:
            return "mixed"

        if has_live:
            return "live_api"

        if has_sample:
            return "sample_data"

        return "none"

    # ==================================================================
    # Statistics
    # ==================================================================

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Return collection statistics."""

        return dict(
            self.stats
        )

    # ==================================================================
    # Processed file helpers
    # ==================================================================

    def get_latest_processed_file(
        self,
    ) -> Optional[Path]:
        """Return newest processed parliamentary JSON."""

        files = sorted(
            self.data_dir.glob(
                "parliamentary_data_*.json"
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        return (
            files[0]
            if files
            else None
        )

    def load_latest_processed_data(
        self,
    ) -> List[Dict[str, Any]]:
        """Load the newest processed JSON file."""

        latest = (
            self.get_latest_processed_file()
        )

        if latest is None:
            logger.warning(
                "No processed parliamentary data found."
            )
            return []

        try:
            with latest.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(
                    file
                )

            if isinstance(
                payload,
                dict,
            ):
                records = payload.get(
                    "records",
                    [],
                )

                if isinstance(
                    records,
                    list,
                ):
                    logger.info(
                        "Loaded %s records from %s",
                        len(records),
                        latest,
                    )
                    return records

            if isinstance(
                payload,
                list,
            ):
                return payload

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            logger.error(
                "Could not load processed data %s: %s",
                latest,
                exc,
            )

        return []


# ======================================================================
# Standalone test
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    collector = ParliamentaryDataCollector()

    records = (
        collector.fetch_all_advanced_data()
    )

    print()
    print("=" * 75)
    print("UK PARLIAMENT DATA COLLECTION COMPLETE")
    print("=" * 75)

    print(
        f"Unique records: {len(records)}"
    )

    live_count = sum(
        not record.get(
            "is_sample",
            False,
        )
        for record in records
    )

    sample_count = sum(
        record.get(
            "is_sample",
            False,
        )
        for record in records
    )

    evidence_count = sum(
        collector._has_substantive_evidence(
            record
        )
        for record in records
    )

    print(
        f"Live records: {live_count}"
    )

    print(
        f"Sample records: {sample_count}"
    )

    print(
        f"Records with substantive evidence: "
        f"{evidence_count}"
    )

    print(
        "Data source: "
        f"{collector._determine_data_source(records)}"
    )

    print()

    print("Collection statistics:")

    stats = collector.get_stats()

    print(
        f"  Pages fetched: "
        f"{stats.get('pages_fetched', 0)}"
    )

    print(
        f"  Page fetch failures: "
        f"{stats.get('pages_fetch_failed', 0)}"
    )

    print(
        f"  Records rejected without evidence: "
        f"{stats.get('records_without_evidence', 0)}"
    )

    print()

    print("Dataset coverage:")

    for source, source_stats in (
        stats["by_source"].items()
    ):
        print(
            f"  {source}: "
            f"{source_stats.get('records', 0)} "
            f"[{source_stats.get('status')}]"
        )

    # Show evidence previews so we can verify that the collector
    # is no longer indexing title-only search results.
    print()

    print("Evidence preview:")

    for index, record in enumerate(
        records[:5],
        start=1,
    ):
        print()
        print(
            f"[{index}] "
            f"{record.get('title', '')}"
        )

        print(
            f"URL: "
            f"{record.get('url', '')}"
        )

        preview = (
            ParliamentaryDataCollector._clean_text(
                ParliamentaryDataCollector._string(
                    record.get("text")
                )
            )
        )

        if len(preview) > 500:
            preview = (
                preview[:500]
                + "..."
            )

        print(
            preview
        )

    if records:
        output = collector.save_data(
            records
        )

        print()
        print(
            f"Saved to: {output}"
        )