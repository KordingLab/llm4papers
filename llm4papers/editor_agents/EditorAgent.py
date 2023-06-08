from llm4papers.models import EditTrigger
from llm4papers.paper_remote.PaperRemote import PaperRemote

from typing import Protocol, Generator


class EditorAgent(Protocol):
    """
    An EditorAgent is a generic interface for requesting edits to a document.

    An EditorAgent is responsible for determining whether it can perform a
    requested edit, and for performing the edit itself.

    EditorAgent implementors will almost certainly be LLM API calls, but it is
    also possible to implement an EditorAgent that uses a human editor, in an
    async "take a look at this when you get a chance" kind of way.

    """

    def get_available_edits(
        self, paper: PaperRemote
    ) -> Generator[EditTrigger, None, None]:
        """
        Return all the edits that are possible in this paper by this Agent.
        """
        ...

    def edit(self, paper: PaperRemote, edit: EditTrigger) -> str:
        """
        Edit a file, returning the new text that will replace the lines specified
        in the Trigger.

        TODO - refactor so that edits can be more than just strings and can happen at
            other parts of the document.

        """
        ...
