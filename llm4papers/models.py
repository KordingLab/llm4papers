"""
This file includes the PaperManager, types, as well as other systems to edit an
academic paper using a large language model AI.
"""
import json
import shutil
import pathlib
import time
from pydantic import BaseModel, Field
from typing import Protocol
from git import Repo
import guidance
import logging

from llm4papers.config import OpenAIConfig, Settings
from llm4papers.prompts import ChatPrompts

# Logging info:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EditRequest(BaseModel):
    line_range: tuple[int, int]
    request_text: str
    file_path: str = Field(default="main.tex")


class Document(BaseModel):
    """
    A document that can be edited.

    """

    lines: list[str]
    name: str


class EditorAgent(Protocol):
    def can_edit(self, edit: EditRequest) -> bool:
        """
        Can this agent perform the desired edit here?

        """
        ...

    def edit(self, document: Document, edit: EditRequest) -> str:
        """
        Edit a file.

        """
        ...


class OpenAIChatEditorAgent(EditorAgent):
    def __init__(self, openai_config: dict):
        self._openai_kwargs = openai_config

    def can_edit(self, edit: EditRequest) -> bool:
        return True

    def edit(self, document: Document, edit: EditRequest) -> str:
        guidance.llm = guidance.llms.OpenAI(
            "gpt-3.5-turbo",
            **self._openai_kwargs,
        )
        document_context = document.lines[
            max(
                edit.line_range[0] - Settings().context_radius,
                0,
            ) : min(
                edit.line_range[1] + Settings().context_radius,
                len(document.lines),
            )
        ]
        editor = guidance.Program(ChatPrompts.BASIC_v1)
        editable_text = "\n".join(
            document.lines[edit.line_range[0] : edit.line_range[1]]
        )
        response = editor(
            context="\n".join(document_context),
            edit_window=editable_text,
            edit_request=edit.request_text,
        )

        edited = response["new_window"]
        logger.info(f"Edited text for document {document.name}:")
        logger.info(f"- {editable_text}")
        logger.info(f"+ {edited}")

        # Guarantee that we don't accidentally step on our own toes:
        return edited.replace("@ai:", "-ai-:")


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

        """
        ...


class OverleafGitPaperRemote(PaperRemote):
    def __init__(self, git_repo: str):
        """
        Saves the git repo to a local temporary directory using gitpython.

        """
        self._reposlug = git_repo.split("/")[-1].split(".")[0]
        self._gitrepo = git_repo
        self._repo: Repo = None
        self._refresh_repo()

    def _refresh_repo(self):
        # If the repo doesn't exist, clone it.
        if not pathlib.Path(f"/tmp/{self._reposlug}").exists():
            self._repo = Repo.clone_from(self._gitrepo, f"/tmp/{self._reposlug}")

        self._repo = Repo(f"/tmp/{self._reposlug}")

        logger.info(f"Pulling latest from repo {self._reposlug}")
        try:
            self._repo.git.stash()
            self._repo.remotes.origin.pull(force=True)
            try:
                self._repo.git.stash("pop")
            except Exception as e:
                # TODO: this just means there was nothing to pop, but
                # we should handle this more gracefully.
                logger.debug(f"Nothing to pop: {e}")
                pass
        except Exception as e:
            logger.error(
                f"Error pulling from repo {self._reposlug}: {e}. "
                "Falling back on DESTRUCTION!!!"
            )
            # Recursively delete the repo and try again.
            self._repo.close()
            self._repo = None
            # recursively delete the repo
            shutil.rmtree(f"/tmp/{self._reposlug}")
            self._refresh_repo()

    def get_next_edit_request(self) -> EditRequest:
        """
        Pull the latest and then review all .tex files.

        Requests will be comments that look like this:

        blah blah blah % @ai: rewrite this formally
        """
        self._refresh_repo()

        for file in pathlib.Path(self._repo.working_tree_dir).glob("*.tex"):
            with open(file) as f:
                for i, line in enumerate(f.readlines()):
                    if (
                        "@ai:" in line
                        and "%" in line
                        and line.index("%") < line.index("@ai:")
                    ):
                        # TODO: Check to see if this line was in the last commit.
                        # If it is, ignore, since we want to wait for the user
                        # to move on to the next line.
                        logging.info(f"Found edit request in {file} at line {i}")
                        return EditRequest(
                            line_range=(i, i + 1),
                            request_text=line.split("@ai:")[1],
                            file_path=str(file),
                        )
        raise ValueError("No edit requests found.")

    def dict(self):
        return {
            "git_repo": self._repo.remotes.origin.url,
            "repo_slug": self._reposlug,
        }

    def perform_edit(self, edit: EditRequest, agent_cascade: list[EditorAgent]):
        """
        Perform an edit on the remote.

        """
        logger.info(f"Performing edit {edit} on remote {self._reposlug}")
        # For now, just remove the AI comment and replace it with "@human: done"
        with open(edit.file_path) as f:
            lines = f.readlines()

        doc = Document(lines=lines, name=edit.file_path)
        for agent in agent_cascade:
            if agent.can_edit(edit):
                break
        else:
            raise ValueError("No agents can edit this request.")
        new_lines = agent.edit(doc, edit)
        # Remove old lines and replace with new lines.
        # We replace instead of just setting
        # `lines[edit.line_range[0]:edit.line_range[1]] = new_lines`
        # because the number of lines may be different.
        lines = lines[: edit.line_range[0]] + [new_lines] + lines[edit.line_range[1] :]

        with open(edit.file_path, "w") as f:
            f.writelines(lines)
        self._repo.index.add([edit.file_path])
        self._repo.index.commit("AI edit completed.")
        self._repo.remotes.origin.push()


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
        if self._json_path.exists():
            with open(self._json_path) as f:
                self._json = json.load(f)
        else:
            self._json = {"papers": []}

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
        for paper in self.papers():
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
