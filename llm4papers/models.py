"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
import abc
import logging
from typing import Hashable, Protocol
from pydantic import BaseModel, Field

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# class EditRequest(BaseModel):
#     line_range: tuple[int, int]
#     request_text: str
#     file_path: str = Field(default="main.tex")


class Document(Protocol):
    """
    A document that can be edited.

    """

    def lines(self) -> list[str]:
        """
        Returns the lines of the document.

        """
        ...

    def as_string(self) -> str:
        """
        Returns the document as a string.

        """
        ...


class DocumentLocation(Protocol):
    """
    A location in a document.

    Could be implemented by something very simple, like LinesDocumentLocation.
    But could also annoyingly be implemented by something more annoying, like
    DiffDocumentLocation, which will require actual business logic to convert
    a diff blob into indices.

    """

    def as_char_range(self) -> tuple[int, int]:
        """
        Returns the location as a char range.

        """
        ...

    def as_line_range(self) -> tuple[int, int]:
        """
        Returns the location as a line range. The same as as_line_char_range()
        where start_char is 0 and end_char is the length of the line.

        """
        ...

    def as_line_char_range(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """
        Returns the location as a line char range.

        Takes the form ((start_line, start_char), (end_line, end_char))

        """
        ...


class Subdocument(Document):
    """
    A subdocument is an excerpt of a document that knows its own start and end
    locations.

    This is a useful abstraction because it allows us to edit a subdocument
    without having to know the entire document.

    """

    def __init__(
        self, document: Document, start: DocumentLocation, end: DocumentLocation
    ):
        self.document = document
        self._start = start
        self._end = end

    @property
    def start(self) -> DocumentLocation:
        return self._start

    @property
    def end(self) -> DocumentLocation:
        return self._end

    def lines(self) -> list[str]:
        """
        Returns the lines of the document.

        """
        return self.document.lines()[
            self.start.as_line_range()[0] : self.end.as_line_range()[1]
        ]

    def as_string(self) -> str:
        """
        Returns the document as a string.

        """
        return self.document.as_string()[
            self.start.as_char_range()[0] : self.end.as_char_range()[1]
        ]


class InMemoryDocument(Document):
    """
    A document that is stored in memory.

    Uses a list of lines as a data-structure.

    """

    _lines: list[str]

    def __init__(self, lines: list[str]):
        """
        Creates a new InMemoryDocument.

        Arguments:
            lines: The lines of the document.

        """
        self._lines = [(line.removesuffix("\n") + "\n") for line in lines]

    @classmethod
    def from_string(cls, string: str):
        """
        Creates a new InMemoryDocument from a string.

        """
        return cls(string.split("\n"))

    def lines(self) -> list[str]:
        """
        Returns the lines of the document.

        """
        return self._lines

    def as_string(self) -> str:
        """
        Returns the document as a string.

        """
        return "\n".join(self._lines)


class LinesDocumentLocation(DocumentLocation):
    """
    A location in a document, specified by line number and character number.

    """

    start_line: int
    start_char: int | None
    end_line: int
    end_char: int | None

    def __init__(
        self,
        document: Document,
        start_line: int,
        start_char: int | None = None,
        end_line: int | None = None,
        end_char: int | None = None,
    ):
        """
        Creates a new LinesDocumentLocation.

        Requires a document because we need to compute the line lengths.

        Arguments:
            document: The document that this location is in.
            start_line: The line number of the start of the location.
            start_char: The character number of the start of the location. If
                None, then the start of the line is used.
            end_line: The line number of the end of the location. If None, then
                start_line+1 is used.
            end_char: The character number of the end of the location. If None,
                then the end of the line is used.

        """
        self.start_line = start_line
        self.start_char = start_char
        self.end_line = end_line or start_line + 1
        self.end_char = end_char
        self.document = document

    def as_char_range(self) -> tuple[int, int]:
        """
        Returns the location as a char range.

        """
        # Get the total number of characters in the document up to the start
        # of the start_line.
        start_char = sum(
            [len(line) for line in self.document.lines()[: self.start_line]]
        )
        if self.start_char is not None:
            start_char += self.start_char

        # Get the total number of characters in the document up to the end of
        # the end_line.
        end_char = start_char + sum(
            [
                len(line)
                for line in self.document.lines()[self.start_line : self.end_line]
            ]
        )
        if self.end_char is not None:
            end_char += self.end_char

        return (start_char, end_char)

    def as_line_range(self) -> tuple[int, int]:
        """
        Returns the location as a line range. The same as as_line_char_range()
        where start_char is 0 and end_char is the length of the line.

        """
        return (self.start_line, self.end_line)

    def as_line_char_range(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """
        Returns the location as a line char range.

        Takes the form ((start_line, start_char), (end_line, end_char))

        """
        return (
            (self.start_line, self.start_char or 0),
            (self.end_line, self.end_char or len(self.document.lines()[self.end_line])),
        )


DocumentID = Hashable


class EditRequest(BaseModel):
    """
    An action that can be taken to edit a document.

    """

    request_text: str


class SingleDocumentEditRequest(EditRequest):
    """
    An action that can be taken to edit a document.

    """

    editable_region: Subdocument
    context: list[Subdocument]


class MultiDocumentEditRequest(EditRequest):
    """
    A request to an LLM to edit multiple documents (scoped).

    """

    editable_regions: dict[DocumentID, Subdocument]
    context: dict[DocumentID, list[Subdocument]]


class Workspace(abc.ABC):
    """
    A general representation of a writing project.

    """

    name: str


class SingleDocumentWorkspace(Workspace):
    """
    A workspace that contains only one document.

    """

    document: Document

    def can_perform_edit(self, edit_request: SingleDocumentEditRequest) -> None:
        """
        Performs an edit on the document.

        """

    def perform_edit(self, edit_request: SingleDocumentEditRequest) -> None:
        """
        Performs an edit on the document.

        """


class MultiDocumentWorkspace(Workspace):
    """
    A workspace that contains multiple documents.

    """

    documents: dict[DocumentID, Document]

    def can_perform_edit(self, edit_request: MultiDocumentEditRequest) -> None:
        """
        Performs an edit on the document.

        """

    def perform_edit(self, edit_request: MultiDocumentEditRequest) -> None:
        """
        Performs an edit on the document.

        """


class MultiDocumentWorkspaceWithEntrypoint(MultiDocumentWorkspace):
    """
    A workspace that contains multiple documents, and has a main document.

    """

    entrypoint: DocumentID
