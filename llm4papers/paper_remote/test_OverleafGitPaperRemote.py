from .OverleafGitPaperRemote import OverleafGitPaperRemote
from ..models import EditTrigger, DocumentRange
import pytest
import git
from pathlib import Path


def _recursive_delete(path: Path):
    """Delete a file or directory, recursively."""
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        for child in path.iterdir():
            _recursive_delete(child)
        path.rmdir()


# Create a local git repo to test with. Upon the start of each test, copy the contents
# of
@pytest.fixture
def temporary_git_paper_repo():
    src = Path("test_data/dummy_overleaf_git_project/")
    # Remove the .git directory from the dummy project to make a fresh start.
    git_root = src / ".git"
    if git_root.exists():
        _recursive_delete(git_root)
    repo = git.Repo.init(src, mkdir=False)
    repo.git.add(".")
    repo.index.commit("Initial commit.")
    # If /tmp/dummy_overleaf_git_project exists, delete it, since this is where
    # OverleafGitPaperRemote will clone the repo to.
    dst = Path("/tmp/dummy_overleaf_git_project")
    if dst.exists():
        _recursive_delete(dst)
    # Use the file:// protocol explicitly so that the repo is "cloned" from the local
    # filesystem, and adding file://username:password@src works
    return "file://" + str(src.resolve())


def test_can_always_make_edits_to_overleaf_git_paper_remote(temporary_git_paper_repo):
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = OverleafGitPaperRemote(temporary_git_paper_repo)
    assert remote.is_edit_ok(
        EditTrigger(
            input_ranges=[
                DocumentRange(doc_id="main.tex", revision_id=0, selection=(0, 1))
            ],
            output_ranges=[
                DocumentRange(doc_id="main.tex", revision_id=0, selection=(0, 1))
            ],
            request_text="Nothin'!",
        )
    )
