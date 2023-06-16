from llm4papers.models import DocumentID, EditTrigger, EditResult
from llm4papers.paper_remote import MultiDocumentPaperRemote


class InMemoryPaperRemote(MultiDocumentPaperRemote):
    """
    This PaperRemote implementation stores the paper in memory, and uses a dict
    to keep track of the lines of each document.

    It is intended for primary use in testing and debugging.

    """

    current_revision_id: int

    def __init__(self, documents: dict[DocumentID, list[str]]):
        """
        Create a new InMemoryPaperRemote.

        Arguments:
            documents: A dict mapping document IDs to lists of lines.

        """
        self._documents = documents
        self.current_revision_id = 0

    def list_doc_ids(self) -> list[DocumentID]:
        """
        List the document IDs available in this paper.

        Arguments:
            None

        Returns:
            list[DocumentID]: A list of document IDs for this project, each of
                which is a Hashable that uniquely identifies the document.

        """
        return list(self._documents.keys())

    def get_lines(self, doc_id: DocumentID) -> list[str]:
        """
        Get the lines of the specified document.

        """
        return self._documents[doc_id]

    def is_edit_ok(self, edit: EditTrigger) -> bool:
        """
        Confirm that the edit can be run now.

        This implementation always returns True because there are no other
        processes that could be editing the paper, as long as the document
        that the edit requests actually exists.

        Arguments:
            edit: The edit trigger to run, which can be vetoed if the remote
                decides it is no longer valid.

        Returns:
            bool: True if the edit can still be performed.

        """

        for doc_range in edit.input_ranges + edit.output_ranges:
            return doc_range.doc_id in self.list_doc_ids()

    def to_dict(self):
        d = super().to_dict()
        d["kwargs"]["documents"] = self._documents
        return d

    def perform_edit(self, edit: EditResult) -> bool:
        """
        Perform an edit on the remote.

        Arguments:
            edit: The result of the edit

        Returns:
            True if edit successful, False otherwise

        """
        new_lines = [
            line.removesuffix("\n") + "\n" for line in edit.content.split("\n")
        ]
        old_lines = self.get_lines(edit.range.doc_id)
        edit_start, edit_end = edit.range.selection
        new_lines = old_lines[:edit_start] + new_lines + old_lines[edit_end:]
        self._documents[edit.range.doc_id] = new_lines
        self.current_revision_id += 1
        return True
