from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class ParagraphRecord(TypedDict):
    paragraph_index: int
    section_index: int
    section_para_index: int
    text: str
    text_preview: str
    char_count: int


class OperationRecord(TypedDict, total=False):
    type: str
    section_index: int
    para_index: int
    new_text: str
    row_count: int
    col_count: int
    start_char: int
    end_char: int


class DocumentRecord(TypedDict):
    document_id: str
    path: str
    format: str
    readonly: bool
    working_text: str
    dirty: bool
    operations: list[OperationRecord]
    working_paragraphs: list[ParagraphRecord]


class DocumentStoreError(Exception):
    """Raised when a document session is missing or invalid."""


class DocumentStore:
    def __init__(self) -> None:
        self._counter: int = 0
        self._documents: dict[str, DocumentRecord] = {}

    def reset(self) -> None:
        self._documents.clear()
        self._counter = 0

    def open_document(self, path: Path, *, readonly: bool) -> DocumentRecord:
        self._counter += 1
        document_id = f"doc_{self._counter:04d}"
        record: DocumentRecord = {
            "document_id": document_id,
            "path": str(path),
            "format": path.suffix.lower().lstrip("."),
            "readonly": readonly,
            "working_text": "",
            "dirty": False,
            "operations": [],
            "working_paragraphs": [],
        }
        self._documents[document_id] = record
        return record

    def get(self, document_id: str) -> DocumentRecord:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise DocumentStoreError(f"Unknown document_id: {document_id}") from exc

    def set_working_text(self, document_id: str, text: str) -> DocumentRecord:
        record = self.get(document_id)
        record["working_text"] = text
        record["dirty"] = True
        return record

    def get_working_text(self, document_id: str) -> str | None:
        record = self.get(document_id)
        return record["working_text"] or None

    def set_working_paragraphs(
        self, document_id: str, paragraphs: list[ParagraphRecord]
    ) -> DocumentRecord:
        record = self.get(document_id)
        record["working_paragraphs"] = paragraphs
        return record

    def get_working_paragraphs(self, document_id: str) -> list[ParagraphRecord]:
        record = self.get(document_id)
        return record["working_paragraphs"]

    def append_operation(self, document_id: str, operation: OperationRecord) -> DocumentRecord:
        record = self.get(document_id)
        record["operations"].append(operation)
        record["dirty"] = True
        return record

    def get_operations(self, document_id: str) -> list[OperationRecord]:
        record = self.get(document_id)
        return record["operations"]


DOCUMENT_STORE = DocumentStore()
