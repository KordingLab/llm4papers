"""
Overleaf conveniently exposes a git remote for each project. This file handles
reading and writing to Overleaf documents using gitpython.

"""

import pathlib
import shutil
import datetime
from git import Repo  # type: ignore

from llm4papers.models import EditTrigger, EditResult, EditType, DocumentID, RevisionID
from llm4papers.paper_remote.MultiDocumentPaperRemote import MultiDocumentPaperRemote
from llm4papers.logger import logger


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

    current_revision_id: RevisionID

    def __init__(self, git_cached_repo: str):
        """
        Saves the git repo to a local temporary directory using gitpython.

        Arguments:
            git_cached_repo: The git repo to clone.

        """
        self._reposlug = git_cached_repo.split("/")[-1].split(".")[0]
        self._git_cached_repository_uri = git_cached_repo
        self._cached_repo: Repo | None = None
        self.refresh()

    def _get_repo(self) -> Repo:
        if self._cached_repo is None:
            # TODO - this makes me anxious about race conditions. every time we refresh,
            #  we change the "timestamp" of the underlying doc(s). If this happens in
            #  between triggering and doing edits, e.g., then we *might* get subtle
            #  conflicts.
            self.refresh()
        return self._cached_repo  # type: ignore

    def _doc_id_to_path(self, doc_id: DocumentID) -> pathlib.Path:
        git_root = self._get_repo().working_tree_dir
        if git_root is None:
            raise ValueError(
                f"Repository failed to initialize in filesystem for {self._get_repo()}"
            )
        # We assert in this PaperRemote that doc_ids are 1:1 with filenames,
        # so we can cast to a string on this next line:
        return pathlib.Path(git_root) / str(doc_id)

    def refresh(self):
        """
        This is a fallback method (that likely needs some love) to ensure that
        the repo is up to date with the latest upstream changes.

        In case of unresolvable errors, this method will recursively delete the
        repo and start over.
        """
        # If the repo doesn't exist, clone it.
        if not pathlib.Path(f"/tmp/{self._reposlug}").exists():
            self._cached_repo = Repo.clone_from(
                self._git_cached_repository_uri, f"/tmp/{self._reposlug}"
            )

        self._cached_repo = Repo(f"/tmp/{self._reposlug}")

        logger.info(f"Pulling latest from repo {self._reposlug}.")
        try:
            self._get_repo().git.stash()
            self._get_repo().remotes.origin.pull(force=True)
            logger.info(
                f"Latest change at {self._get_repo().head.commit.committed_datetime}"
            )
            logger.info(f"Repo dirty: {self._get_repo().is_dirty()}")
            self.current_revision_id = self._get_repo().head.commit.hexsha
            try:
                self._get_repo().git.stash("pop")
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
            self._get_repo().close()
            self._cached_repo = None
            # recursively delete the repo
            shutil.rmtree(f"/tmp/{self._reposlug}")
            self.refresh()

    def list_doc_ids(self) -> list[DocumentID]:
        """
        List the document ids available in this paper

        """
        git_root = self._get_repo().working_tree_dir
        if git_root is None:
            raise ValueError(
                f"Repository failed to initialize in filesystem for {self._get_repo()}"
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
        self.refresh()

        # Check to see if this line was in the last commit. If it is, ignore, since we
        # want to wait for the user to move on to the next line.
        for doc_range in edit.input_ranges + edit.output_ranges:
            repo_scoped_file = str(self._doc_id_to_path(doc_range.doc_id))
            for i in range(doc_range.selection[0], doc_range.selection[1]):
                if _too_close_to_human_edits(self._get_repo(), repo_scoped_file, i):
                    logger.info(
                        f"Temporarily skipping edit request in {doc_range.doc_id}"
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
            "git_cached_repo": self._get_repo().remotes.origin.url,
            "repo_slug": self._reposlug,
            "type": "OverleafGitPaperRemote",
        }

    def perform_edit(self, edit: EditResult) -> bool:
        """
        Perform an edit on the remote.

        Arguments:
            edit: An EditResult object

        Returns:
            True if the edit was successful, False otherwise
        """
        logger.info(f"Performing edit {edit} on remote {self._reposlug}")

        if edit.type == EditType.replace:
            success = self._perform_replace(edit)
        elif edit.type == EditType.comment:
            success = self._perform_comment(edit)
        else:
            raise ValueError(f"Unknown edit type {edit.type}")

        if success:
            # TODO - apply edit relative to the edit.range.revision_id commit and then
            #  rebase onto HEAD for poor-man's operational transforms
            self._get_repo().index.add([self._doc_id_to_path(str(edit.range.doc_id))])
            self._get_repo().index.commit("AI edit completed.")
            # Instead of just pushing, we need to rebase and then push.
            # This is because we want to make sure that the AI edits are always
            # on top of the stack.
            self._get_repo().git.pull()
            # TODO: We could do a better job catching WARNs here and then maybe setting
            #  success = False
            self._get_repo().git.push()

        return success

    def _perform_replace(self, edit: EditResult) -> bool:
        """
        Perform a replacement edit on the remote.

        Arguments:
            edit: An EditResult object

        Returns:
            True if the edit was successful, False otherwise
        """
        doc_range, text = edit.range, edit.content
        try:
            lines = self.get_lines(doc_range.doc_id)
            lines = (
                lines[: doc_range.selection[0]]
                + [text]
                + lines[doc_range.selection[1] :]
            )
            file = self._doc_id_to_path(str(doc_range.doc_id))
            with open(file, "w") as f:
                f.writelines(lines)
            return True
        except (FileNotFoundError, IndexError):
            logger.error(f"Error performing edit {edit}")
            return False

    def _perform_comment(self, edit: EditResult) -> bool:
        """
        Perform a comment edit on the remote.

        Arguments:
            edit: An EditResult object

        Returns:
            True if the edit was successful, False otherwise
        """
        # TODO - implement this for real
        logger.info(f"Performing comment edit {edit} on remote {self._reposlug}")
        return True
