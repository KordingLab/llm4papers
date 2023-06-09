from .InMemoryPaperRemote import InMemoryPaperRemote
from ..models import EditTrigger, DocumentRange


def test_can_always_make_edits_to_in_memory_paper_remote():
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = InMemoryPaperRemote({"paper.txt": ["Hello, world!"]})
    assert remote.is_edit_ok(
        EditTrigger(
            input_ranges=[
                DocumentRange(doc_id="paper.txt", revision_id=0, selection=(0, 1))
            ],
            output_ranges=[
                DocumentRange(doc_id="paper.txt", revision_id=0, selection=(0, 1))
            ],
            request_text="Nothin'!",
        )
    )


def test_cant_edit_DNE_file_in_memory_paper_remote():
    """
    Confirm that edits can always be made to an in-memory paper remote.

    """
    remote = InMemoryPaperRemote({"exists.txt": ["Hello, world!"]})
    assert not remote.is_edit_ok(
        EditTrigger(
            input_ranges=[
                DocumentRange(
                    doc_id="this_paper_dne.txt", revision_id=0, selection=(0, 1)
                )
            ],
            output_ranges=[
                DocumentRange(
                    doc_id="this_paper_dne.txt", revision_id=0, selection=(0, 1)
                )
            ],
            request_text="Nothin'!",
        )
    )
