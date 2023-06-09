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


class WriteOutDigitsEditorAgent(EditorAgent):
    """
    A simple editor agent that converts single-digit numerals to words.

    Intended for testing and simple debugging.

    """

    def get_available_edits(
        self, paper: PaperRemote
    ) -> Generator[EditTrigger, None, None]:
        """
        Find all standalone digits in the paper.

        """
        for doc_id in paper.list_doc_ids():
            for line_num, line in enumerate(paper.get_lines(doc_id)):
                for word_num, word in enumerate(line.split()):
                    if word.isdigit():
                        yield EditTrigger(
                            line_range=(line_num, line_num + 1),
                            request_text=line,
                            doc_id=doc_id,
                        )

    def edit(self, paper: PaperRemote, edit: EditTrigger) -> str:
        """
        Convert a single-digit numeral to a word.

        """
        text = "".join(
            paper.get_lines(edit.doc_id)[edit.line_range[0] : edit.line_range[1]]
        )
        numerals = {
            "0": "zero",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
        }
        for numeral, word in numerals.items():
            text = text.replace(numeral, word)
        return text
