# llm4papers

Read our blog post announcement on the project [here](https://kordinglab.com/2024/06/03/llm4papers).

This is a simple plugin for Overleaf (and, maybe, other editors in the future) that allows you to edit a document with LLMs (Large Language Models) in an intuitive and unintrusive way.

https://github.com/KordingLab/llm4papers/assets/693511/a642c534-50d7-4feb-aa16-d53ab8825279

## How to use

> **Warning**: I absolutely cannot overstate how un-production-ready this tool is. **Do not use this on important documents!** Don't use this on documents you care about. And if you want to use this on something important, don't. Okay. Now I'm de-risked and un-liable. Do whatever you want.

-   Clone and install dependencies (`poetry install`)
-   Populate a `config.py` file with your credentials (see `config.example.py`)
-   Add a new `paper` to the paper manifest (right now, can be done at startup or manually by editing the papers manifest JSON)
-   Run the server from this repository (`poetry run python3 llm4papers/service.py`)
-   Open the paper in Overleaf and edit as you usually would. When you want to invoke the AI assistant, add a comment with the following format: `@ai: <command>`. For example, `the brain is weird. % @ai: formalize this`
-   The AI assistant will replace lines on which this comment is found with the output of the command.
-   

## Technical Overview

This plugin works by cloning the Overleaf git repository and editing files locally in `/tmp` and then pushing them back to the remote. This is done using the `git` Python library.

Other document APIs can be added by implementing the `PaperRemote` protocol in [the `paper_remote` module](llm4papers/paper_remote/__init__.py). For an example, see the `OverleafGitPaperRemote` class.

<hr /><p align='center'><small>Made with 💚 at <a href='https://kordinglab.com/'> the Kording Lab <img alt='KordingLab.com' align='center' src='https://github.com/KordingLab/chatify-server/assets/693511/39f519fe-b05d-43fb-a5d4-f6792de1dbb6' height='32px'></a></small></p>
