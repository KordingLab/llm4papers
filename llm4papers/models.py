"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
import logging
from pydantic import BaseModel

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EditTrigger(BaseModel):
    line_range: tuple[int, int]
    request_text: str
    doc_id: str
