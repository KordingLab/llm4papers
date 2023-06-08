import logging
from typing import Protocol
from llm4papers.models import EditTrigger

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PaperRemote(Protocol):
    def dict(self):
        ...

    def refresh_changes(self) -> None:
        """
        Check for any changes and update

        """
        ...

    def get_lines(self, path=None) -> list[str]:
        """
        Get the lines of the paper at path 'path' or the default document if path is
        None

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
