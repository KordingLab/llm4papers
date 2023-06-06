import json
import logging
import pathlib
import time
from typing import Protocol


from llm4papers.editor_agents.OpenAIChatEditorAgent import OpenAIChatEditorAgent
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.paper_remote import OverleafGitPaperRemote, PaperRemote

from llm4papers.config import OpenAIConfig


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


class JSONFilePaperManager(PaperManager):
    def __init__(
        self,
        json_path: pathlib.Path | str = "papers_manifest.json",
        agents: list[EditorAgent] | None = None,
    ):
        self._agents = agents or [OpenAIChatEditorAgent(OpenAIConfig().dict())]
        self._json_path = pathlib.Path(json_path)
        self._load_json()

    def _load_json(self):
        if not self._json_path.exists():
            self._json = {"papers": []}
            with open(self._json_path, "w") as f:
                json.dump(self._json, f)
        else:
            with open(self._json_path) as f:
                self._json = json.load(f)

    def add_paper_remote(self, remote: PaperRemote):
        # Make sure it doesn't already exist.
        for paper in self.papers():
            if paper.dict() == remote.dict():
                logger.info("Paper already exists, not adding.")
                return
        self._json["papers"].append(remote.dict())
        with open(self._json_path, "w") as f:
            json.dump(self._json, f)

    def papers(self) -> list[PaperRemote]:
        papers_json = self._json["papers"]
        return [OverleafGitPaperRemote(paper["git_repo"]) for paper in papers_json]

    def poll_once(self):
        self._load_json()
        logger.info(f"Polling {len(self.papers())} papers for edits.")
        for paper in self.papers():
            logger.info(f"Polling paper {paper.dict()}")
            try:
                edit = paper.get_next_edit_request()
            except ValueError as e:
                logger.info(e)
                continue
            paper.perform_edit(edit, self._agents)
            return True
        return False

    def poll(self, interval: int = 5):
        while True:
            if self.poll_once():
                logger.info("Performed an edit.")
            else:
                logger.info("No edits to perform.")
            time.sleep(interval)
