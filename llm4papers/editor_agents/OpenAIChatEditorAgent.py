import guidance
from llm4papers.config import Settings
from llm4papers.editor_agents.EditorAgent import EditorAgent
from llm4papers.models import Document, EditRequest, logger
from llm4papers.prompts import ChatPrompts


class OpenAIChatEditorAgent(EditorAgent):
    def __init__(self, openai_config: dict):
        self._openai_kwargs = openai_config

    def can_edit(self, edit: EditRequest) -> bool:
        return True

    def edit(self, document: Document, edit: EditRequest) -> str:
        guidance.llm = guidance.llms.OpenAI(
            "gpt-3.5-turbo",
            **self._openai_kwargs,
        )
        document_context = document.lines[
            max(
                edit.line_range[0] - Settings().context_radius,
                0,
            ) : min(
                edit.line_range[1] + Settings().context_radius,
                len(document.lines),
            )
        ]
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

        # Guarantee that we don't accidentally step on our own toes:
        return edited.replace("@ai:", "-ai-:")
