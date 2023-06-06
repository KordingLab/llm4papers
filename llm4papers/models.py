"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
import logging
from pydantic import BaseModel, Field

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EditRequest(BaseModel):
    line_range: tuple[int, int]
    request_text: str
    file_path: str = Field(default="main.tex")


class Document(BaseModel):
    """
    A document that can be edited.

    """

    lines: list[str]
    name: str
