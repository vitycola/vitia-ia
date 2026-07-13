import httpx

from src.domain.food import MacrosPer100g

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


class OFFFallbackClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, name: str) -> MacrosPer100g | None:
        """Query OFF v1 CGI search; return MacrosPer100g for first usable product, or None."""
        params = {
            "search_terms": name,
            "search_simple": "1",
            "action": "process",
            "json": "1",
            "page_size": "5",
        }
        response = await self._client.get(OFF_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        for product in data.get("products", []):
            macros = self._extract_macros(product)
            if macros is not None:
                return macros
        return None

    @staticmethod
    def _extract_macros(product: dict) -> MacrosPer100g | None:
        protein = product.get("proteins_100g")
        carbs = product.get("carbohydrates_100g")
        fat = product.get("fat_100g")

        if protein is None or carbs is None or fat is None:
            return None

        # Energy resolution: prefer kcal, fallback kJ / 4.184, else 0.0
        kcal = product.get("energy-kcal_100g")
        if kcal is not None:
            calories = float(kcal)
        else:
            kj = product.get("energy_100g")
            calories = float(kj) / 4.184 if kj is not None else 0.0

        return MacrosPer100g(
            calories=calories,
            protein=float(protein),
            carbs=float(carbs),
            fat=float(fat),
        )
