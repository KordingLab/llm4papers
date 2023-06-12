"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
from typing import Hashable
from pydantic import BaseModel


DocumentID = Hashable


class EditTrigger(BaseModel):
    line_range: tuple[int, int]
    request_text: str
    doc_id: DocumentID
