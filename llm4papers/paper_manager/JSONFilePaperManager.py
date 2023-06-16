import json
import pathlib
import time

from llm4papers.config import OpenAIConfig
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.editor_agents.OpenAIChatEditorAgent import OpenAIChatEditorAgent
from llm4papers.paper_manager import PaperManager
from llm4papers.logger import logger
from llm4papers.paper_remote import PaperRemote


class JSONFilePaperManager(PaperManager):
    def __init__(
        self,
        json_path: pathlib.Path | str = "papers_manifest.json",
        agents: list[EditorAgent] | None = None,
    ):
        self._agents = agents or [OpenAIChatEditorAgent(OpenAIConfig().dict())]
        self._json_path = pathlib.Path(json_path)
        self._load_json()
        self._paper_remote_class_lookup = {}

    def _load_json(self):
        if not self._json_path.exists():
            self._json = {"papers": []}
            with open(self._json_path, "w") as f:
                json.dump(self._json, f)
        else:
            with open(self._json_path) as f:
                self._json = json.load(f)

    def register_paper_remote_class(self, cls):
        self._paper_remote_class_lookup[cls.__name__] = cls

    def add_paper_remote(self, remote: PaperRemote):
        # Make sure it doesn't already exist.
        for paper in self.papers():
            if paper.to_dict() == remote.to_dict():
                logger.info("Paper already exists, not adding.")
                return
        self._json["papers"].append(remote.to_dict())
        with open(self._json_path, "w") as f:
            json.dump(self._json, f)

    def papers(self) -> list[PaperRemote]:
        papers_json = self._json["papers"]
        papers = []
        for paper_dict in papers_json:
            if "type" not in paper_dict:
                logger.error(f"Paper dict {paper_dict} has no 'type' key.")
                continue

            if paper_dict["type"] in self._paper_remote_class_lookup:
                cls = self._paper_remote_class_lookup[paper_dict["type"]]
            else:
                logger.error(
                    f"PaperRemote type {paper_dict['type']} is unknown (did "
                    f"you call manager.register_paper_remote_class?)."
                )
                continue

            try:
                paper = cls.from_dict(paper_dict)
            except Exception as e:
                logger.error(f"Error creating paper from dict {paper_dict}: {e}")
                continue

            papers.append(paper)
        return papers

    def poll_once(self):
        self._load_json()
        logger.info(f"Polling {len(self.papers())} papers for edits.")
        is_triggered = False
        for paper in self.papers():
            logger.info(f"Polling paper {paper.to_dict()}")
            paper.refresh()
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
                # TODO - be more specific about errors. Maybe create error subtypes
                #  for both Agent errors and Paper errors
                try:
                    for result in agent.edit(paper, edit):
                        success = paper.perform_edit(result)
                        did_edit |= success
                except Exception as e:
                    logger.error(f"Exception {e} while editing paper {paper}")
        return did_edit
