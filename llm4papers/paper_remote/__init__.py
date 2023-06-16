from .PaperRemote import PaperRemote, DocumentID
from .MultiDocumentPaperRemote import MultiDocumentPaperRemote
from .OverleafGitPaperRemote import OverleafGitPaperRemote


# To support PaperRemote.from_dict(cls, d), this function lets us lookup a class from
# its name. New subclasses of PaperRemote should be added here.
def lookup_paper_remote_class(name: str):
    if name == "OverleafGitPaperRemote":
        return OverleafGitPaperRemote
    else:
        raise ValueError(f"Unknown PaperRemote class {name}")


__all__ = [
    "lookup_paper_remote_class",
    "PaperRemote",
    "DocumentID",
    "MultiDocumentPaperRemote",
    "OverleafGitPaperRemote",
]
