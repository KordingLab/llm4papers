import logging
from typing import Protocol
from llm4papers.models import EditTrigger

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PaperRemote(Protocol):
    def dict(self):
        ...

    def _refresh_changes(self) -> None:
        """
        Check for any changes and update

        """
        ...

    def list_doc_ids(self) -> list[str]:
        """
        List the document ids available in this paper

        """
        ...

    def get_lines(self, doc_id: str) -> list[str]:
        """
        Get the lines of the specified document

        """
        ...

    def is_edit_ok(self, edit: EditTrigger) -> bool:
        """
        Return True if the edit is ok to run now, False otherwise. Gives the
        PaperRemote an opportunity to veto the edit before it starts.
        """
        ...

    def perform_edit(self, edit: EditTrigger, edit_result: str):
        """
        Perform an edit on the remote.

        Arguments:
            edit: The original edit trigger
            edit_result: The result of the edit

        Returns:
            None

        """
        ...
