import guidance
from llm4papers.config import Settings
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import EditTrigger, logger
from llm4papers.paper_remote import PaperRemote
from llm4papers.editor_agents.prompts import ChatPrompts

from typing import Generator


class OpenAIChatEditorAgent(EditorAgent):
    """
    An EditorAgent that uses OpenAI's chat API to perform edits.

    """

    def __init__(self, openai_config: dict):
        """
        Arguments:
            openai_config: A dictionary of OpenAI API parameters. Must include
                keys 'organization' and 'token'.

        """
        self._openai_kwargs = openai_config

    def get_available_edits(
        self, paper: PaperRemote
    ) -> Generator[EditTrigger, None, None]:
        """
        Return all the edits that are possible in this paper by this Agent.
        """
        for doc_id in paper.list_doc_ids():
            for i, line in enumerate(paper.get_lines(doc_id)):
                if "@ai:" in line:
                    yield EditTrigger(
                        line_range=(i, i + 1),
                        request_text=line.split("@ai:")[-1].strip(),
                        doc_id=doc_id,
                    )

    def edit(self, paper: PaperRemote, edit: EditTrigger) -> str:
        """
        Perform an edit on a file, using a chat model.
        """
        guidance.llm = guidance.llms.OpenAI(
            "gpt-3.5-turbo",
            **self._openai_kwargs,
        )
        # We scope the context to the edit line range, plus a little bit of
        # context on either side. This avoids the model getting more text than
        # it can chew on. This is configurable in the settings (config.py) and
        # in the future, TODO this will be a great place to add full-project-
        # level context.
        lines = paper.get_lines(edit.doc_id)
        context_start = max(0, edit.line_range[0] - Settings().context_radius)
        context_end = min(len(lines), edit.line_range[0] + Settings().context_radius)
        document_context = lines[context_start:context_end]
        # TODO: Should support parametrized prompts.
        editor = guidance.Program(ChatPrompts.BASIC_v1)
        editable_text = "\n".join(lines[edit.line_range[0] : edit.line_range[1]])
        response = editor(
            context="\n".join(document_context),
            edit_window=editable_text,
            edit_request=edit.request_text,
        )

        edited = response["new_window"] + "\n"
        logger.info(f"Edited text for document {paper.dict()}:")
        logger.info(f"- {editable_text}")
        logger.info(f"+ {edited}")

        # If configured in settings, keep the old lines but comment them out
        if Settings().retain_originals_as_comments:
            prefix_lines = [f"% {line.split('@ai')[0]}\n" for line in document_context]
            edited = "".join(prefix_lines) + edited

        # Guarantee that we don't accidentally step on our own toes by adding
        # another @ai: request.
        return edited.replace("@ai:", "-ai-:")
