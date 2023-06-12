from .EditorAgent import WriteOutDigitsEditorAgent
from ..paper_remote.InMemoryPaperRemote import InMemoryPaperRemote


def test_WriteOutDigitsEditorAgent():
    agent = WriteOutDigitsEditorAgent()
    needs_edit_paper = InMemoryPaperRemote({"paper.txt": ["1 2 3"]})
    assert len(list(agent.get_available_edits(needs_edit_paper))) > 0

    # Perform the edits:
    for edit in agent.get_available_edits(needs_edit_paper):
        for result in agent.edit(needs_edit_paper, edit):
            needs_edit_paper.perform_edit(result)

    # Check that the edits worked:
    assert needs_edit_paper.get_lines("paper.txt") == ["one two three\n"]
