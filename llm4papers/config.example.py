from pydantic import BaseSettings


class OpenAIConfig(BaseSettings):
    token: str = "sk-###"
    organization: str = "org-###"


class Settings(BaseSettings):
    # How many lines of context to include in the edit request. A value of 10
    # means that the edit request will include 10 lines before and 10 lines
    # after the edit centroid, for a total of (minimum) 21 lines.
    context_radius = 10

    # How often to poll for new edits.
    polling_interval_sec = 10
