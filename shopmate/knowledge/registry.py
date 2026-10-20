from shopmate.knowledge.providers import KnowledgeProvider


class KnowledgeProviderRegistry:
    """Provider ID -> KnowledgeProvider 对象。"""

    def __init__(self, providers: list[KnowledgeProvider]) -> None:
        self._providers_by_id = {
            provider.provider_id: provider for provider in providers
        }

    def get(self, provider_id: str) -> KnowledgeProvider:
        return self._providers_by_id[provider_id]

    @property
    def provider_ids(self) -> list[str]:
        return sorted(self._providers_by_id)
