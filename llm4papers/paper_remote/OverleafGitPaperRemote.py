"""
Overleaf conveniently exposes a git remote for each project. This file handles
reading and writing to Overleaf documents using gitpython.

"""

import logging
import pathlib
import shutil

from git import Repo, Commit

from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import Document, EditRequest
from llm4papers.paper_remote import PaperRemote, logger


def _line_was_in_last_n_commit(
    repo: Repo, filename: str, line_number: int, last_n: int = 2
) -> bool:
    """
    Determine if the line `line_number` of the file `filename` was changed in
    the last `last_n` commits.

    This function is most useful for determining if the user has "gotten out
    of the way" of the AI so that linewise changes to the document can be
    made without stomping on the user's edits.

    """
    # Get the diff for HEAD~n:
    total_diff = repo.git.diff(f"HEAD~{last_n}", filename, unified=0)

    # Get the current repo state of that line:
    current_line = repo.git.show(f"HEAD:{filename}").split("\n")[line_number]

    logger.debug("Diff: " + total_diff)
    logger.debug("Current line: " + current_line)

    # Match the line in the diff:
    if current_line in total_diff:
        return True

    # Get the n latest commits, in reverse chronological order
    # commits: list[Commit] = repo.iter_commits(max_count=last_n)
    # for commit in commits:
    #     # Get the diffs for this commit
    #     # https://gitpython.readthedocs.io/en/stable/reference.html?highlight=iter_commits#git.diff.Diffable
    #     diffs = commit.diff()

    #     # Check if the line was changed in any of the diffs
    #     for diff in diffs:
    #         print("Path eq", diff.b_blob.path, filename)
    #         if diff.b_blob is None or diff.b_blob.path != filename:
    #             continue

    #         # TODO: Get the line number of the diff... Not clear to me this is
    #         # even doable in a dependable way with "regular" git.

    return False


class OverleafGitPaperRemote(PaperRemote):
    """
    Overleaf exposes a git remote for each project. This class handles reading
    and writing to Overleaf documents using gitpython, and implements the
    PaperRemote protocol for use by the AI editor.

    """

    def __init__(self, git_repo: str):
        """
        Saves the git repo to a local temporary directory using gitpython.

        Arguments:
            git_repo: The git repo to clone.

        """
        self._reposlug = git_repo.split("/")[-1].split(".")[0]
        self._gitrepo = git_repo
        self._repo: Repo = None
        self._refresh_repo()

    def _refresh_repo(self):
        """
        This is a fallback method (that likely needs some love) to ensure that
        the repo is up to date with the latest upstream changes.

        In case of unresolvable errors, this method will recursively delete the
        repo and start over.
        """
        # If the repo doesn't exist, clone it.
        if not pathlib.Path(f"/tmp/{self._reposlug}").exists():
            self._repo = Repo.clone_from(self._gitrepo, f"/tmp/{self._reposlug}")

        self._repo = Repo(f"/tmp/{self._reposlug}")

        logger.info(f"Pulling latest from repo {self._reposlug}.")
        try:
            self._repo.git.stash()
            self._repo.remotes.origin.pull(force=True)
            logger.info(f"Latest change at {self._repo.head.commit.committed_datetime}")
            logger.info(f"Repo dirty: {self._repo.is_dirty()}")
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
        Pull the latest from git and then review all .tex files for the trigger

        Requests will be comments that look like this:

        > blah blah blah % @ai: rewrite this formally

        Arguments:
            None

        Returns:
            An EditRequest object scoped to this repo.

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
                        # Check to see if this line was in the last commit.
                        # If it is, ignore, since we want to wait for the user
                        # to move on to the next line.
                        repo_scoped_file = pathlib.Path(file).relative_to(
                            self._repo.working_tree_dir
                        )
                        if _line_was_in_last_n_commit(
                            self._repo, str(repo_scoped_file), i
                        ):
                            logging.info(
                                f"Temporarily skipping edit request in {file}"
                                " at line {i} because it was still in progress"
                                " in the last commit."
                            )
                            continue
                        logging.info(f"Found edit request in {file} at line {i}")
                        return EditRequest(
                            line_range=(i, i + 1),
                            request_text=line.split("@ai:")[1],
                            file_path=str(file),
                        )
        raise ValueError("No edit requests found.")

    def dict(self) -> dict:
        """
        Return a dictionary representation of this remote.

        """
        return {
            "git_repo": self._repo.remotes.origin.url,
            "repo_slug": self._reposlug,
            "type": "OverleafGitPaperRemote",
        }

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
        # self._repo.remotes.origin.push()
        # Instead of just pushing, we need to rebase and then push.
        # This is because we want to make sure that the AI edits are always
        # on top of the stack.
        self._repo.git.pull()
        # TODO: We could do a better job catching WARNs here.
        self._repo.git.push()
