from .OverleafGitPaperRemote import OverleafGitPaperRemote
from ..models import EditTrigger, EditResult, EditType, DocumentRange
import pytest
import git
from pathlib import Path
import shutil
import time


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

    # Create initial commit with (mostly empty) main.tex file, then add content to it by
    # copying main-1.tex, main-2.tex, etc to main.tex. The purpose of this is to ensure
    # that the git history has a few commits.
    repo = git.Repo.init(src, mkdir=False)
    i = 0
    while (file := src / f"main-{i}.tex").exists():
        shutil.copyfile(file, src / "main.tex")
        repo.git.add("main.tex")
        repo.index.commit(f"Commit {i}")
        i += 1

    # If /tmp/dummy_overleaf_git_project exists, delete it, since this is where
    # OverleafGitPaperRemote will clone the repo to.
    dst = Path("/tmp/dummy_overleaf_git_project")
    if dst.exists():
        _recursive_delete(dst)

    # Set it so that the 'origin' repo (in test_data) does not have any branches
    # checked out, allowing 'push' from the /tmp/ clone to work. Do this by checking
    # out the current commit directly (detached HEAD state)
    repo.git.checkout(repo.head.commit.hexsha)

    # Use the file:// protocol explicitly so that the repo is "cloned" from the local
    # filesystem, and adding file://username:password@src works
    yield "file://" + str(src.resolve())

    # Run this after the test is done (after yield)
    (src / "main.tex").unlink()
    repo.close()
    _recursive_delete(src / ".git")


def test_merge_resolution_from_revision_id(temporary_git_paper_repo):
    remote = OverleafGitPaperRemote(temporary_git_paper_repo)
    # Test that we can make *two* edits to different parts of the file by rebasing
    # the second edit onto the first one.

    # First, add a line early in the paper (after \section{} before text)
    lines = remote.get_lines("main.tex")
    i_section = next(i for i, line in enumerate(lines) if r"\section" in line)
    i_end_doc = next(i for i, line in enumerate(lines) if r"\end{document}" in line)

    edit1 = EditResult(
        type=EditType.replace,
        range=DocumentRange(
            doc_id="main.tex",
            revision_id=remote.current_revision_id,
            selection=(i_section + 2, i_section + 2),
        ),
        content="% This is a comment\n% that spans\n% multiple lines\n",
    )

    # Second, add some stuff at the end of the paper *after* the \end{document}, using
    # the same revision ID as the first edit. Since the first edit spans multiple lines,
    # this fails unless we rebase the second edit onto the first one.
    edit2 = EditResult(
        type=EditType.replace,
        range=DocumentRange(
            doc_id="main.tex",
            revision_id=remote.current_revision_id,
            selection=(i_end_doc + 1, i_end_doc + 1),
        ),
        content="\n% This is a comment that should appear AFTER the end-document\n",
    )

    # Perform the two edits in succession
    remote.perform_edit(edit1)
    remote.perform_edit(edit2)

    # Confirm that both edits happened
    lines = remote.get_lines("main.tex")
    assert any("multiple lines" in line for line in lines)
    assert any("appear AFTER" in line for line in lines)

    # Confirm that the second edit was rebased onto the first one by checking that the
    # comment did indeed appear after the \end{document}
    i_end_doc_2 = next(i for i, line in enumerate(lines) if r"\end{document}" in line)
    i_second_edit = next(i for i, line in enumerate(lines) if "appear AFTER" in line)
    assert i_second_edit > i_end_doc_2


def test_can_always_make_edits_to_overleaf_git_paper_remote(temporary_git_paper_repo):
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = OverleafGitPaperRemote(temporary_git_paper_repo)
    assert remote.is_edit_ok(
        EditTrigger(
            input_ranges=[
                DocumentRange(
                    doc_id="main.tex",
                    revision_id=remote.current_revision_id,
                    selection=(0, 1),
                )
            ],
            output_ranges=[
                DocumentRange(
                    doc_id="main.tex",
                    revision_id=remote.current_revision_id,
                    selection=(0, 1),
                )
            ],
            request_text="Nothin'!",
        )
    )


def test_edit_ok_if_different_part_of_doc(temporary_git_paper_repo):
    # Add a comment at the end. This doesn't overlap with anything in the document, so
    # it should be immediately accepted.
    remote = OverleafGitPaperRemote(temporary_git_paper_repo)
    num_lines = len(remote.get_lines("main.tex"))
    new_last_line = "\n% --- end of document ---\n"
    end_of_doc_comment_edit = EditTrigger(
        input_ranges=[
            DocumentRange(
                doc_id="main.tex",
                revision_id=remote.current_revision_id,
                selection=(num_lines, num_lines + 1),
            )
        ],
        output_ranges=[
            DocumentRange(
                doc_id="main.tex",
                revision_id=remote.current_revision_id,
                selection=(num_lines, num_lines + 1),
            )
        ],
        request_text=new_last_line,
    )
    assert remote.is_edit_ok(end_of_doc_comment_edit)
    remote.perform_edit(
        EditResult(
            type=EditType.replace,
            range=end_of_doc_comment_edit.output_ranges[0],
            content=new_last_line,
        )
    )
    assert remote.get_lines("main.tex")[-1].strip() == new_last_line.strip()


def test_edit_reject_or_accept_given_delay(temporary_git_paper_repo):
    """
    Confirm that edits are rejected if "human edits" happened within the last 10s, but
    accepted if they happened more than 10s ago.
    """
    remote = OverleafGitPaperRemote(temporary_git_paper_repo)
    # Find the line where the "\title{}" is, and make an edit to it.
    lines = remote.get_lines("main.tex")
    i_title = next(i for i, line in enumerate(lines) if r"\title" in line)

    title_edit = EditTrigger(
        input_ranges=[
            DocumentRange(
                doc_id="main.tex",
                revision_id=remote.current_revision_id,
                selection=(i_title, i_title + 1),
            )
        ],
        output_ranges=[
            DocumentRange(
                doc_id="main.tex",
                revision_id=remote.current_revision_id,
                selection=(i_title, i_title + 1),
            )
        ],
        request_text=r"\title{A much snazzier title}\n",
    )
    assert not remote.is_edit_ok(title_edit)
    time.sleep(10)
    assert remote.is_edit_ok(title_edit)
