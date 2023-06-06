from llm4papers.models import Document, EditRequest

from typing import Protocol


class EditorAgent(Protocol):
    def can_edit(self, edit: EditRequest) -> bool:
        """
        Can this agent perform the desired edit here?
        """
        ...

    def edit(self, document: Document, edit: EditRequest) -> str:
        """
        Edit a file.
        """
        ...
