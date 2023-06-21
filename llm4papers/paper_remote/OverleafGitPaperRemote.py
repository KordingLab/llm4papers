"""
Overleaf conveniently exposes a git remote for each project. This file handles
reading and writing to Overleaf documents using gitpython.

"""

import pathlib
import shutil
import datetime
from urllib.parse import quote
from git import Repo, GitCommandError  # type: ignore
from typing import Iterable
import re

from llm4papers.models import (
    EditTrigger,
    EditResult,
    EditType,
    DocumentID,
    RevisionID,
    LineRange,
)
from llm4papers.paper_remote.MultiDocumentPaperRemote import MultiDocumentPaperRemote
from llm4papers.logger import logger


diff_line_edit_re = re.compile(
    r"@{2,}\s*-(?P<old_line>\d+),(?P<old_count>\d+)\s*\+(?P<new_line>\d+),(?P<new_count>\d+)\s*@{2,}"
)


def _diff_to_ranges(diff: str) -> Iterable[LineRange]:
    """Given a git diff, return LineRange object(s) indicating which lines in the
    original document were changed.
    """
    for match in diff_line_edit_re.finditer(diff):
        git_line_number = int(match.group("new_line"))
        git_line_count = int(match.group("new_count"))
        # Git counts from 1 and gives (start, length), inclusive. LineRange counts from
        # 0 and gives start:end indices (exclusive).
        zero_index_start = git_line_number - 1
        yield zero_index_start, zero_index_start + git_line_count


def _ranges_overlap(a: LineRange, b: LineRange) -> bool:
    """Given two LineRanges, return True if they overlap, False otherwise."""
    return not (a[1] < b[0] or b[1] < a[0])


def _too_close_to_human_edits(
    repo: Repo, filename: str, line_range: LineRange, last_n: int = 2
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

    # Get the diff for HEAD~n. Note that the gitpython DiffIndex and Diff objects drop the line number info (!) so we
    # can't use the gitpython object-oriented API to do this. Calling repo.git.diff is pretty much a direct pass-through
    # to running "git diff HEAD~n -- <filename>" on the command line.
    total_diff = repo.git.diff(f"HEAD~{last_n}", filename, unified=0)

    for git_line_range in _diff_to_ranges(total_diff):
        if _ranges_overlap(git_line_range, line_range):
            logger.info(
                f"Line range {line_range} overlaps with git-edited {git_line_range}, "
                f"rejecting edit."
            )
            return True
    return False


def _add_auth(uri: str):
    if "@" not in uri:
        try:
            from llm4papers.config import OverleafConfig
        except ImportError:
            logger.debug("No config file found, assuming public repo.")
            return uri

        config = OverleafConfig()
        un, pw = quote(config.username), quote(config.password)
        protocol = (uri.split("://")[0] + "://") if "://" in uri else ""
        address = uri.split("://")[-1]
        return f"{protocol}{un}:{pw}@{address}"
    else:
        return uri


class OverleafGitPaperRemote(MultiDocumentPaperRemote):
    """
    Overleaf exposes a git remote for each project. This class handles reading
    and writing to Overleaf documents using gitpython, and implements the
    PaperRemote protocol for use by the AI editor.
    """

    def __init__(self, git_cached_repo: str):
        """
        Saves the git repo to a local temporary directory using gitpython.

        Arguments:
            git_cached_repo: The git repo to clone.

        """
        self._reposlug = git_cached_repo.split("/")[-1].split(".")[0]
        self._git_cached_repository_uri = _add_auth(git_cached_repo)
        self._git_cached_repo_arg = git_cached_repo
        self._cached_repo: Repo | None = None
        self.refresh()

    @property
    def current_revision_id(self) -> RevisionID:
        return self._get_repo().head.commit.hexsha

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

    def refresh(self, retry: bool = True):
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
            try:
                self._get_repo().git.stash("pop")
            except GitCommandError as e:
                # TODO: this just means there was nothing to pop, but
                # we should handle this more gracefully.
                logger.debug(f"Nothing to pop: {e}")
                pass
        except GitCommandError as e:
            logger.error(
                f"Error pulling from repo {self._reposlug}: {e}. "
                "Falling back on DESTRUCTION!!!"
            )
            # Recursively delete the repo and try again.
            self._get_repo().close()
            self._cached_repo = None
            # recursively delete the repo
            shutil.rmtree(f"/tmp/{self._reposlug}")
            if retry:
                self.refresh(retry=False)
            else:
                raise e

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
            if _too_close_to_human_edits(
                self._get_repo(), repo_scoped_file, doc_range.selection
            ):
                logger.info(
                    f"Temporarily skipping edit request in {doc_range.doc_id}"
                    " at line {i} because it was still in progress"
                    " in the last commit."
                )
                return False
        return True

    def to_dict(self):
        d = super().to_dict()
        d["kwargs"]["git_cached_repo"] = self._git_cached_repo_arg
        return d

    def perform_edit(self, edit: EditResult) -> bool:
        """
        Perform an edit on the remote.

        Arguments:
            edit: An EditResult object

        Returns:
            True if the edit was successful, False otherwise
        """
        if not self._doc_id_to_path(edit.range.doc_id).exists():
            logger.error(f"Document {edit.range.doc_id} does not exist.")
            return False

        logger.info(f"Performing edit {edit} on remote {self._reposlug}")

        try:
            with self.rewind(edit.range.revision_id, message="AI edit") as paper:
                if edit.type == EditType.replace:
                    success = paper._perform_replace(edit)
                elif edit.type == EditType.comment:
                    success = paper._perform_comment(edit)
                else:
                    raise ValueError(f"Unknown edit type {edit.type}")
        except GitCommandError as e:
            logger.error(
                f"Git error performing edit {edit} on remote {self._reposlug}: {e}"
            )
            success = False

        if success:
            self._get_repo().git.push()
        else:
            self.refresh()

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
            num_lines = len(self.get_lines(doc_range.doc_id))
            if (
                any(i < 0 for i in doc_range.selection)
                or doc_range.selection[1] < doc_range.selection[0]
                or any(
                    i > len(self.get_lines(doc_range.doc_id))
                    for i in doc_range.selection
                )
            ):
                raise IndexError(
                    f"Invalid selection {doc_range.selection} for document "
                    f"{doc_range.doc_id} with {num_lines} lines."
                )
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

    def rewind(self, commit: str, message: str):
        return self.RewindContext(self, commit, message)

    # Create an inner class for "with" semantics so that we can do
    # `with remote.rewind(commit)` to rewind to a particular commit and play some edits
    # onto it, then merge when the 'with' context exits.
    class RewindContext:
        # TODO - there are tricks in gitpython where an IndexFile can be used to handle changes to files in-memory
        #  without having to call checkout() and (briefly) modify the state of things on disk. This would be an
        #  improvement, but would require using the gitpython API more directly inside of perform_edit,
        #  such as calling git.IndexFile.write() instead of python's open() and write()

        def __init__(self, remote: "OverleafGitPaperRemote", commit: str, message: str):
            self._remote = remote
            self._message = message
            self._rewind_commit = commit

        def __enter__(self):
            repo = self._remote._get_repo()
            self._restore_ref = repo.head.ref
            self._new_branch = repo.create_head("tmp-edit-branch", commit=self._rewind_commit)
            self._new_branch.checkout()
            return self._remote

        def __exit__(self, exc_type, exc_val, exc_tb):
            repo = self._remote._get_repo()
            assert repo.active_branch == self._new_branch, "Branch changed unexpectedly mid-`with`"
            # Add files that changed
            repo.index.add([_file for (_file, _), _ in repo.index.entries.items()])
            repo.index.commit(self._message)
            self._restore_ref.checkout()
            try:
                repo.git.merge("tmp-edit-branch")
            except GitCommandError as e:
                # Hard reset on failure
                repo.git.reset("--hard", self._restore_ref.commit.hexsha)
                raise e
            finally:
                repo.delete_head(self._new_branch, force=True)
