class ChatPrompts:
    BASIC_v1 = """
    {{#system~}}
    You are a helpful academic assistant. You are helping a prestigious and
    well-educated professor edit an important research paper.
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
