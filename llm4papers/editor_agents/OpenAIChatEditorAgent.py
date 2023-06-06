import guidance
from llm4papers.config import Settings
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import Document, EditRequest, logger
from llm4papers.editor_agents.prompts import ChatPrompts


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

    def can_edit(self, edit: EditRequest) -> bool:
        """
        Can this agent perform the desired edit here? Yes.

        We always return True here; the OpenAI chat API is very general and
        should be able to perform any edit requested in plain language.

        Arguments:
            edit: The edit to be performed.

        Returns:
            True

        """
        return True

    def edit(self, document: Document, edit: EditRequest) -> str:
        """
        Perform an edit on a file, using a chat model.

        Arguments:
            document: The document to be edited.
            edit: The edit to be performed.

        Returns:
            The edited text.

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
        document_context = document.lines[
            max(
                edit.line_range[0] - Settings().context_radius,
                0,
            ) : min(
                edit.line_range[1] + Settings().context_radius,
                len(document.lines),
            )
        ]
        # TODO: Should support parametrized prompts.
        editor = guidance.Program(ChatPrompts.BASIC_v1)
        editable_text = "\n".join(
            document.lines[edit.line_range[0] : edit.line_range[1]]
        )
        response = editor(
            context="\n".join(document_context),
            edit_window=editable_text,
            edit_request=edit.request_text,
        )

        edited = response["new_window"]
        logger.info(f"Edited text for document {document.name}:")
        logger.info(f"- {editable_text}")
        logger.info(f"+ {edited}")

        # Guarantee that we don't accidentally step on our own toes by adding
        # another @ai: request.
        return edited.replace("@ai:", "-ai-:")
