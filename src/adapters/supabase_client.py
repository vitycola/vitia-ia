import httpx


class GenericFoodRepository:
    def __init__(self, client: httpx.AsyncClient, base_url: str, anon_key: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._anon_key = anon_key

    async def search(self, normalized: str) -> list[dict]:
        """Search generic_foods by ilike on name_normalized. Returns up to 10 rows."""
        url = f"{self._base_url}/rest/v1/generic_foods"
        params = {
            "name_normalized": f"ilike.*{normalized}*",
            "select": "id,name,calories_per_100g,protein_per_100g,carbs_per_100g,fat_per_100g",
            "limit": "10",
        }
        headers = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {self._anon_key}",
        }
        response = await self._client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
