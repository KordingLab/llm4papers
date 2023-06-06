from llm4papers.models import JSONFilePaperManager, OverleafGitPaperRemote
from llm4papers.config import Settings

if __name__ == "__main__":
    manager = JSONFilePaperManager()
    manager.add_paper_remote(
        OverleafGitPaperRemote("https://git.overleaf.com/6478b2143a88519e36cb44dc")
    )
    manager.poll(interval=Settings().polling_interval_sec)
