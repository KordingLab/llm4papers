from .EditorAgent import WriteOutDigitsEditorAgent
from ..paper_remote.InMemoryPaperRemote import InMemoryPaperRemote


def test_simple_editoragent():
    agent = WriteOutDigitsEditorAgent()
    needs_edit_paper = InMemoryPaperRemote({"paper.txt": ["1 2 3"]})
    doesnt_need_edit_paper = InMemoryPaperRemote({"paper.txt": ["one two three"]})
    assert len(list(agent.get_available_edits(needs_edit_paper))) > 0
    assert len(list(agent.get_available_edits(doesnt_need_edit_paper))) == 0
