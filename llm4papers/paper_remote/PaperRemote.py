from llm4papers.models import DocumentID, RevisionID, EditTrigger, EditResult

from typing import Protocol


class PaperRemote(Protocol):
    """
    A PaperRemote is a manager class for a single 'paper' project, which can be
    any number of documents, each of which is text (i.e., a .tex file or a
    .markdown file) or could be binary blobs (i.e., a .png file or a pdf).

    Each unique piece of the paper (i.e., a file, or blob) is identified by a
    DocumentID, which can be any hashable object. It would make sense for a
    filesystem-based PaperRemote to use the filename as the DocumentID, e.g.
    By specification, any method call to a single-document paper remote that
    takes a document ID as an argument will ignore the document ID and use the
    single document.

    """

    current_revision_id: RevisionID

    def dict(self):
        ...

    def refresh(self):
        """
        Ensure that the paper remote is up-to-date with the remote.

        For example, if changes have occurred in a git repo, or files have
        changed since we last cached...

        """
        ...

    def get_lines(self, doc_id: DocumentID) -> list[str]:
        """
        Get the lines of the specified document.

        For single-document paper remotes, this function call will ignore the
        doc_id and return the lines of the single document.

        """
        ...

    def list_doc_ids(self) -> list[DocumentID]:
        """
        List the document IDs of the paper.

        For single-document paper remotes, this function call will return a
        list with a single element, the document ID of the single document. The
        implementer may choose what this ID is. By specification, any method
        call to a single-document paper remote that takes a document ID as an
        argument will ignore the document ID and use the single document.

        """
        ...

    def is_edit_ok(self, edit: EditTrigger) -> bool:
        """
        Return True if the edit is ok to run now, False otherwise. Gives the
        PaperRemote an opportunity to veto the edit before it starts.
        """
        ...

    def perform_edit(self, edit: EditResult) -> bool:
        """
        Perform an edit on the remote.

        Arguments:
            edit: An EditResult object

        Returns:
            True if the edit was successful, False otherwise
        """
        ...
