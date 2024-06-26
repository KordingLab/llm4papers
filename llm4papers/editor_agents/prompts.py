"""
This file holds a library of prompts that can be used to generate text from an
LLM. The prompts are written in the microsoft/guidance templating language. If
you are about to edit one of these prompts, consider creating a new one instead
in order to enable us to A/B test different prompts in the future.

All prompts should accept the following variables:

- edit_window: The text that the AI will edit.
- edit_request: The text of the edit request (e.g., "formalize this text")

All prompts should return the following variables:

- new_window: The text to replace `edit_window` in the document

"""


class ChatPrompts:
    """
    Prompts that are compatible with OpenAI Chat-based LLMs like GPT-3.5-turbo.

    These are just strings, but by scoping them to a ChatPrompts class, we can
    do some early checks to make sure model-prompt combinations are compatible.

    """

    BASIC_v1 = """
    {{#system~}}
    You are a helpful academic assistant. You are helping a well-educated
    professor at a prestigous university edit an important research paper to be
    submitted to nature neuroscience with an audience of math inclined PhD
    students of neuroscience in mind.
    As an assistant your focus is on brevity (you like text to feel snappy and
    to the point) and precision (you want to make sure that the text is clear).
    When a text segment contains multiple sentences, you are particularly
    mindful of narrative structure (ideas need to be motivated before they are
    introduced, they need to be clearly summarized, and the reader needs to
    find a take-away message at the end).
    Also keep in mind that your edit should not remove any creative aspects
    introduced by the writer, such as personal notes.
    {{~/system}}

    {{#user~}}
    The document contains the following text:
    {{context}}

    The professor has requested that you make an edit to the following line:

    ---
    LINE:
    {{edit_window}}
    ---

    The desired change is:

    {{edit_request}}

    What would be a good replacement to make for that line? Remember to change
    the "% @ai: [command]" comment to "% @user: [comments]" when you are done.
    Only respond with the changed text; do not include comments or suggestions.

    ---
    REPLACEMENT:
    {{~/user}}

    {{#assistant~}}
    {{gen 'new_window' stop='---'}}
    {{~/assistant}}
    """
