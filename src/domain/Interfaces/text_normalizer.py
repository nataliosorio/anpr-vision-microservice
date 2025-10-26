from typing import Protocol

class ITextNormalizer(Protocol):
    def normalize(self, text: str) -> str: ...