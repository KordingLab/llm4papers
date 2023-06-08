import json
import pathlib
import time

from llm4papers.config import OpenAIConfig
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.editor_agents.OpenAIChatEditorAgent import OpenAIChatEditorAgent
from llm4papers.paper_manager import PaperManager, logger
from llm4papers.paper_remote import PaperRemote
from llm4papers.paper_remote.OverleafGitPaperRemote import OverleafGitPaperRemote


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
        is_triggered = False
        for paper in self.papers():
            logger.info(f"Polling paper {paper.dict()}")
            paper.refresh_changes()
            is_triggered |= self._do_edits_helper(paper)
        return is_triggered

    def poll(self, interval: int = 5, falloff: str = "linear_threshold"):
        """
        Repeatedly poll for new changes to the papers.


        """
        current_interval = interval
        strat_lambdas = {
            "constant": lambda x: interval,
            "linear": lambda x: x + interval,
            "linear_threshold": (
                lambda x: x + interval if x < 21600 else 21600
            ),  # 6 hours
        }
        if falloff not in strat_lambdas:
            raise ValueError(f"Invalid falloff strategy {falloff}")
        strat_lambda = strat_lambdas[falloff]

        while True:
            if self.poll_once():
                logger.info("Performed an edit.")
                current_interval = interval
            else:
                logger.info("No edits to perform.")
                current_interval = strat_lambda(current_interval)

            # print every second with a countdown and overwrite last line:
            for i in range(current_interval):
                print(
                    f"Sleeping for {current_interval - i} seconds before next poll.",
                    end="\r",
                )
                time.sleep(1)

    def _do_edits_helper(self, paper: PaperRemote) -> bool:
        # TODO - threading with some job management so the same edit isn't spawned
        #  multiple times
        did_edit = False
        for agent in self._agents:
            for edit in agent.get_available_edits(paper):
                logger.info(f"Agent {agent} can edit paper {paper}: {edit}")
                new_text = agent.edit(paper, edit)
                paper.perform_edit(edit, new_text)
                did_edit = True
        return did_edit
