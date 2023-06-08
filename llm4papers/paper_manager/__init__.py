import logging
from typing import Protocol

from llm4papers.paper_remote import PaperRemote

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PaperManager(Protocol):
    """
    A class that manages all of the papers that this assistant is responsible
    for editing.

    """

    def add_paper_remote(self, remote: PaperRemote):
        """
        Add a paper to the manager.

        """
        ...

    def papers(self) -> list[PaperRemote]:
        """
        Get all of the papers that this manager is responsible for.

        """
        ...


