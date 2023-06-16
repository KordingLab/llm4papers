from typing import Hashable
from pydantic import BaseModel
from enum import Enum


DocumentID = Hashable
RevisionID = Hashable
# TODO move from line to character ranges
LineRange = tuple[int, int]


class DocumentRange(BaseModel):
    doc_id: DocumentID
    revision_id: RevisionID
    selection: LineRange


class EditTrigger(BaseModel):
    input_ranges: list[DocumentRange]
    output_ranges: list[DocumentRange]
    request_text: str


class EditType(str, Enum):
    replace = "replace"
    comment = "comment"


class EditResult(BaseModel):
    type: EditType
    range: DocumentRange
    content: str
