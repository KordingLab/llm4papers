"""
Overleaf conveniently exposes a git remote for each project. This file handles
reading and writing to Overleaf documents using gitpython.

"""

import pathlib
import shutil
import datetime
from git import Repo  # type: ignore

from llm4papers.models import DocumentID, EditTrigger
from llm4papers.logger import logger
from llm4papers.paper_remote.MultiDocumentPaperRemote import MultiDocumentPaperRemote


def _too_close_to_human_edits(
    repo: Repo, filename: str, line_number: int, last_n: int = 2
) -> bool:
    """
    Determine if the line `line_number` of the file `filename` was changed in
    the last `last_n` commits.

    This function is most useful for determining if the user has "gotten out
    of the way" of the AI so that linewise changes to the document can be
    made without stomping on the user's edits.

    """
    # Get the date of the nth-back commit:
    last_commit_date = repo.head.commit.committed_datetime
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    print(f"Last commit date: {last_commit_date}")
    print(f"Now: {now}")

    sec_since_last_commit = (now - last_commit_date).total_seconds()

    # If the last commit was more than 10 seconds ago, any edit is fine:
    if sec_since_last_commit > 10:
        logger.info(f"Last commit was {sec_since_last_commit}s ago, approving edit.")
        return False

    # Get the diff for HEAD~n:
    total_diff = repo.git.diff(f"HEAD~{last_n}", filename, unified=0)

    # Get the current repo state of that line:
    current_line = repo.git.show(f"HEAD:{filename}").split("\n")[line_number]

    logger.debug("Diff: " + total_diff)
    logger.debug("Current line: " + current_line)

    # Match the line in the diff:
    if current_line in total_diff:
        logger.info(
            f"Found current line ({current_line[:10]}...) in diff, rejecting edit."
        )
        return True

    return False


class OverleafGitPaperRemote(MultiDocumentPaperRemote):
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
        self._git_repository_uri = git_repo
        self._cached_repo: Repo | None = None
        self._refresh_changes()

    @property
    def _repo(self) -> Repo:
        if self._cached_repo is None:
            self._refresh_changes()
        return self._cached_repo  # type: ignore

    def _doc_id_to_path(self, doc_id: DocumentID) -> pathlib.Path:
        git_root = self._repo.working_tree_dir
        if git_root is None:
            raise ValueError(
                f"Repository failed to initialize in filesystem for {self._repo}"
            )
        # We assert in this PaperRemote that doc_ids are 1:1 with filenames,
        # so we can cast to a string on this next line:
        return pathlib.Path(git_root) / str(doc_id)

    def _refresh_changes(self):
        """
        This is a fallback method (that likely needs some love) to ensure that
        the repo is up to date with the latest upstream changes.

        In case of unresolvable errors, this method will recursively delete the
        repo and start over.
        """
        # If the repo doesn't exist, clone it.
        if not pathlib.Path(f"/tmp/{self._reposlug}").exists():
            self._cached_repo = Repo.clone_from(
                self._git_repository_uri, f"/tmp/{self._reposlug}"
            )

        self._cached_repo = Repo(f"/tmp/{self._reposlug}")

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
            self._cached_repo = None
            # recursively delete the repo
            shutil.rmtree(f"/tmp/{self._reposlug}")
            self._refresh_changes()

    def list_doc_ids(self) -> list[str]:
        """
        List the document ids available in this paper

        """
        git_root = self._repo.working_tree_dir
        if git_root is None:
            raise ValueError(
                f"Repository failed to initialize in filesystem for {self._repo}"
            )
        root = pathlib.Path(git_root)
        return [str(file.relative_to(root)) for file in root.glob("**/*.tex")]

    def get_lines(self, doc_id: DocumentID) -> list[str]:
        path = self._doc_id_to_path(doc_id)
        if not path.exists():
            raise FileNotFoundError(f"Document {doc_id} not found.")

        with open(path) as f:
            return f.readlines()

    def is_edit_ok(self, edit: EditTrigger) -> bool:
        """
        Pull the latest from git and then check if any of the lines in the edit recently
        changed. If so, veto it.
        """
        # TODO - do we really want to refresh here and risk making the Trigger outdated?
        self._refresh_changes()

        # Check to see if this line was in the last commit. If it is, ignore, since we
        # want to wait for the user to move on to the next line.
        repo_scoped_file = str(self._doc_id_to_path(edit.doc_id))
        for i in range(edit.line_range[0], edit.line_range[1]):
            if _too_close_to_human_edits(self._repo, repo_scoped_file, i):
                logger.info(
                    f"Temporarily skipping edit request in {edit.doc_id}"
                    " at line {i} because it was still in progress"
                    " in the last commit."
                )
                return False
        return True

    def dict(self) -> dict:
        """
        Return a dictionary representation of this remote.

        """
        return {
            "git_repo": self._repo.remotes.origin.url,
            "repo_slug": self._reposlug,
            "type": "OverleafGitPaperRemote",
        }

    def perform_edit(self, edit: EditTrigger, edit_result: str):
        """
        Perform an edit on the remote.

        Arguments:
            edit: The original edit trigger
            edit_result: The result of the edit

        Returns:
            None

        """
        logger.info(
            f"Performing edit {edit} with content {edit_result} on remote "
            f"{self._reposlug}"
        )
        # For now, just remove the AI comment and replace it with "@human: done"

        # Remove old lines and replace with new lines.
        # We replace instead of just setting
        # `lines[edit.line_range[0]:edit.line_range[1]] = new_lines`
        # because the number of lines may be different.
        lines = self.get_lines(edit.doc_id)
        lines = (
            lines[: edit.line_range[0]] + [edit_result] + lines[edit.line_range[1] :]
        )

        file = self._doc_id_to_path(edit.doc_id)
        with open(file, "w") as f:
            f.writelines(lines)
        self._repo.index.add([file])
        self._repo.index.commit("AI edit completed.")
        # self._repo.remotes.origin.push()
        # Instead of just pushing, we need to rebase and then push.
        # This is because we want to make sure that the AI edits are always
        # on top of the stack.
        self._repo.git.pull()
        # TODO: We could do a better job catching WARNs here.
        self._repo.git.push()
