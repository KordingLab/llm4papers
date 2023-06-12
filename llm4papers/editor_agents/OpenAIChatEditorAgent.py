import guidance
from llm4papers.config import Settings
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import EditTrigger, EditResult, EditType, DocumentRange
from llm4papers.paper_remote import PaperRemote
from llm4papers.editor_agents.prompts import ChatPrompts
from llm4papers.logger import logger

from typing import Iterable


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

    def get_available_edits(self, paper: PaperRemote) -> Iterable[EditTrigger]:
        """
        Return all the edits that are possible in this paper by this Agent.
        """
        for doc_id in paper.list_doc_ids():
            for i, line in enumerate(paper.get_lines(doc_id)):
                if "@ai:" in line:
                    yield EditTrigger(
                        input_ranges=[
                            DocumentRange(
                                doc_id=doc_id,
                                revision_id=paper.current_revision_id,
                                selection=(i, i + 1),
                            )
                        ],
                        output_ranges=[
                            DocumentRange(
                                doc_id=doc_id,
                                revision_id=paper.current_revision_id,
                                selection=(i, i + 1),
                            )
                        ],
                        request_text=line.split("@ai:")[-1].strip(),
                    )

    def edit(self, paper: PaperRemote, edit: EditTrigger) -> Iterable[EditResult]:
        """
        Perform an edit on a file, using a chat model.
        """
        guidance.llm = guidance.llms.OpenAI(
            "gpt-3.5-turbo",
            **self._openai_kwargs,
        )

        assert (
            len(edit.input_ranges) == 1
            and len(edit.output_ranges) == 1
            and edit.input_ranges[0] == edit.output_ranges[0]
        ), "Expected single-line edits only."

        doc_range = edit.input_ranges[0]

        # We scope the context to the edit line range, plus a little bit of
        # context on either side. This avoids the model getting more text than
        # it can chew on. This is configurable in the settings (config.py) and
        # in the future, TODO this will be a great place to add full-project-
        # level context.
        lines = paper.get_lines(doc_range.doc_id)
        context_start = max(0, doc_range.selection[0] - Settings().context_radius)
        context_end = min(
            len(lines), doc_range.selection[1] + Settings().context_radius
        )
        document_context = lines[context_start:context_end]
        # TODO: Should support parametrized prompts.
        editor = guidance.Program(ChatPrompts.BASIC_v1)
        editable_text = "\n".join(
            lines[doc_range.selection[0] : doc_range.selection[1]]
        )
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
            original_lines = lines[doc_range.selection[0] : doc_range.selection[1]]
            prefix_lines = [
                f"% {line.split('@ai')[0]}\n" if "@ai" in line else f"% {line}"
                for line in original_lines
            ]
            edited = "".join(prefix_lines) + edited

        # Guarantee that we don't accidentally step on our own toes by adding
        # another @ai: request.
        edited = edited.replace("@ai:", "-ai-:")
        return [
            EditResult(
                type=EditType.replace,
                range=doc_range,
                content=edited,
            )
        ]
