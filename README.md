# llm4papers

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

## License

This code is NOT licensed for re-use or publication, and is only for use by Kording Lab affiliates.

## Technical Overview

This plugin works by cloning the Overleaf git repository and editing files locally in `/tmp` and then pushing them back to the remote. This is done using the `git` Python library.

Other document APIs can be added by implementing the `PaperRemote` protocol in [`models.py`](llm4papers/models.py). For an example, see the `OverleafGitPaperRemote` class.
