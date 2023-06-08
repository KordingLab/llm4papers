from llm4papers.models import  EditTrigger
from llm4papers.paper_remote import PaperRemote

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

    def get_available_edits(self, paper: PaperRemote) -> Generator[EditTrigger, None, None]:
        """
        Can this agent perform the desired edit here? If so, return all that it can do by yielding them
        """
        ...

    def edit(self, paper: PaperRemote, edit: EditTrigger):
        """
        Edit a file.

        The nature of the edit is entirely up to the implementer and can expand
        beyond the scope of the requested edit. For example, if the requested
        edit is to change a single line, the implementer may choose to change
        the entire paragraph, or even the entire document.

        """
        ...
