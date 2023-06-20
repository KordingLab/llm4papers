import sys
from llm4papers.config import Settings
from llm4papers.paper_manager.JSONFilePaperManager import JSONFilePaperManager
from llm4papers.paper_remote import OverleafGitPaperRemote

if __name__ == "__main__":
    manifest_file = (
        sys.argv[-1]
        if sys.argv[-1].endswith(".json")
        else Settings().json_manifest_file
    )
    manager = JSONFilePaperManager(manifest_file)
    manager.register_paper_remote_class(OverleafGitPaperRemote)
    manager.poll(interval=Settings().polling_interval_sec)
