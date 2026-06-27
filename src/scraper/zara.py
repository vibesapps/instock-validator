from ..proxy.manager import ProxyManager
from ..storage.models import Product, ScrapeResult
from .http_scraper import HttpScraper


class ZaraScraper:
    def __init__(self, proxy: ProxyManager) -> None:
        self._http = HttpScraper(proxy, brand="zara")

    async def scrape(self, product: Product) -> ScrapeResult:
        return await self._http.scrape(product)
