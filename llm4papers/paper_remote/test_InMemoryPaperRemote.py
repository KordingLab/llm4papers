from .InMemoryPaperRemote import InMemoryPaperRemote
from ..models import EditTrigger


def test_can_always_make_edits_to_in_memory_paper_remote():
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = InMemoryPaperRemote({"paper.txt": ["Hello, world!"]})
    assert remote.is_edit_ok(
        EditTrigger(
            line_range=(0, 1),
            request_text="Nothin'!",
            doc_id="paper.txt",
        )
    )


def test_cant_edit_DNE_file_in_memory_paper_remote():
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = InMemoryPaperRemote({"exists.txt": ["Hello, world!"]})
    assert not remote.is_edit_ok(
        EditTrigger(
            line_range=(0, 1),
            request_text="Nothin'!",
            # This is the line of interest:
            doc_id="does_not_exist.txt",
        )
    )
