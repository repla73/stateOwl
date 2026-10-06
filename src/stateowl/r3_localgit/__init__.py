from .base import LocalGitBase
from .admit import LocalGitAdmitMixin

class LocalGitPublicationStorage(LocalGitAdmitMixin, LocalGitBase):
    pass

__all__ = ["LocalGitPublicationStorage"]
