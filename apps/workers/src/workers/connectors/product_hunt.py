"""Product Hunt connector."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import structlog

from workers.connectors.base import BaseConnector

logger = structlog.get_logger()


class ProductHuntConnector(BaseConnector):
    """Connector for Product Hunt data."""
    
    def __init__(self):
        super().__init__("product_hunt")
        self.base_url = "https://www.producthunt.com"
    
    def get_source_name(self) -> str:
        """Get the source name."""
        return "product_hunt"
    
    async def fetch_data(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch Product Hunt data."""
        # Get today's products
        url = f"{self.base_url}/posts"
        
        response = await self._make_request(url)
        if not response:
            return
        
        # Parse the HTML to extract product data
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find product cards (this is a simplified extraction)
        products = soup.find_all('div', {'data-test': 'post-item'})
        
        for product in products:
            try:
                # Extract product information
                title_elem = product.find('h3')
                title = title_elem.get_text().strip() if title_elem else "Unknown"
                
                description_elem = product.find('p')
                description = description_elem.get_text().strip() if description_elem else ""
                
                link_elem = product.find('a')
                product_url = ""
                if link_elem and link_elem.get('href'):
                    product_url = f"{self.base_url}{link_elem['href']}"
                
                # Extract vote count
                vote_elem = product.find('div', class_='vote-count')
                votes = 0
                if vote_elem:
                    try:
                        votes = int(vote_elem.get_text().strip())
                    except ValueError:
                        pass
                
                yield {
                    "title": title,
                    "content": f"{title}. {description}",
                    "url": product_url,
                    "metadata": {
                        "votes": votes,
                        "description": description,
                        "platform": "product_hunt",
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    "published_at": datetime.utcnow().isoformat(),
                }
                
            except Exception as e:
                logger.warning(f"Error parsing product: {e}")
                continue
    
    async def fetch_trending(self, period: str = "today") -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch trending products."""
        url = f"{self.base_url}/posts?period={period}"
        
        response = await self._make_request(url)
        if not response:
            return
        
        async for item in self._parse_products(response.text):
            yield item
    
    async def _parse_products(self, html: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Parse products from HTML."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # This is a simplified parser - in production, you'd need to handle
        # Product Hunt's dynamic loading and API endpoints
        products = soup.find_all('div', {'data-test': 'post-item'})
        
        for product in products:
            try:
                title_elem = product.find('h3')
                if not title_elem:
                    continue
                
                title = title_elem.get_text().strip()
                
                # Extract other data...
                yield {
                    "title": title,
                    "content": title,
                    "url": f"{self.base_url}/posts/{title.lower().replace(' ', '-')}",
                    "metadata": {
                        "platform": "product_hunt",
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    "published_at": datetime.utcnow().isoformat(),
                }
                
            except Exception as e:
                logger.warning(f"Error parsing product: {e}")
                continue
