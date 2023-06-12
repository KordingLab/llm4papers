"""
Some papers (such as LaTeX projects) are composed of multiple text files.
This class handles reading and writing to such projects.

"""

from llm4papers.models import EditTrigger
from llm4papers.paper_remote.PaperRemote import PaperRemote, DocumentID


class MultiDocumentPaperRemote(PaperRemote):
    """
    Some papers (such as LaTeX projects) are composed of multiple text files.
    This class handles reading and writing to such projects.

    In this setup, each document gets its own "DocumentID", which is a Hashable
    that represents the document uniquely. For filesystem-based projects, this
    is the path to the file relative to the root of the project; for in-memory
    projects, this could just be the unique name of the string.

    """

    def list_doc_ids(self) -> list[DocumentID]:
        """
        List the document IDs available in this paper.

        Arguments:
            None

        Returns:
            list[DocumentID]: A list of document IDs for this project, each of
                which is a Hashable that uniquely identifies the document.

        """
        raise NotImplementedError()

    def refresh(self):
        """
        Ensure that the paper remote is up-to-date with the remote.

        For example, if changes have occurred in a git repo, or files have
        changed since we last cached...

        """

    def get_lines(self, doc_id: DocumentID) -> list[str]:
        """
        Get the lines of the specified document.

        """
        raise NotImplementedError()

    def is_edit_ok(self, edit: EditTrigger) -> bool:
        """
        Confirm that the edit can be run now.

        Arguments:
            edit: The edit trigger to run, which can be vetoed if the remote
                decides it is no longer valid.

        Returns:
            bool: True if the edit can still be performed.

        """
        raise NotImplementedError()

    def dict(self) -> dict:
        """
        Return a dictionary representation of this remote.

        """
        raise NotImplementedError()

    def perform_edit(self, edit: EditTrigger, edit_result: str):
        """
        Perform an edit on the remote.

        Arguments:
            edit: The original edit trigger
            edit_result: The result of the edit

        Returns:
            None

        """
        raise NotImplementedError()
