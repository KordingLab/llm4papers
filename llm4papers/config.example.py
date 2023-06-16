from pydantic import BaseSettings


class OpenAIConfig(BaseSettings):
    token: str = "sk-###"
    organization: str = "org-###"


class OverleafConfig(BaseSettings):
    username: str = "###"
    password: str = "###"


class Settings(BaseSettings):
    # How many lines of context to include in the edit request. A value of 10
    # means that the edit request will include 10 lines before and 10 lines
    # after the edit centroid, for a total of (minimum) 21 lines.
    context_radius = 10

    # How often to poll for new edits.
    polling_interval_sec = 10

    # The name of the JSON manifest file to use, if using the JSONPapersManager
    json_manifest_file = "papers_manifest.json"

    # When performing edits, should the original lines be retained as comments?
    retain_originals_as_comments = True
