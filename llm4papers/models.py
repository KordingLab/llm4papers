"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
import logging
from pydantic import BaseModel, Field

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EditTrigger(BaseModel):
    line_range: tuple[int, int]
    request_text: str
    # TODO switch from file/path semantics to document_id semantics
    file_path: str = Field(default="main.tex")
