import logging
from typing import Protocol
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import EditRequest

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PaperRemote(Protocol):
    def dict(self):
        ...

    def get_next_edit_request(self) -> EditRequest:
        """
        Get the next edit request from the remote.

        """
        ...

    def perform_edit(self, edit: EditRequest, agent_cascade: list[EditorAgent]):
        """
        Perform an edit on the remote.

        Arguments:
            edit: The edit location requested by the AI.
            agent_cascade: A list of EditorAgents to try in order, until one
                can perform the edit. The first agent that can perform the edit
                will be used. This is generally provided by a PapersManager.

        Returns:
            None

        """
        ...
