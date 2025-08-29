"""Base connector class."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from bs4 import BeautifulSoup

from workers.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class BaseConnector(ABC):
    """Base class for all data connectors."""
    
    def __init__(self, name: str):
        self.name = name
        self.client: Optional[httpx.AsyncClient] = None
        self.last_request_time = 0.0
        self.robots_cache: Dict[str, RobotFileParser] = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout),
            headers={
                "User-Agent": settings.user_agent,
            },
            follow_redirects=True,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    async def _respect_rate_limit(self):
        """Respect rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < settings.request_delay:
            await asyncio.sleep(settings.request_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        try:
            from urllib.parse import urljoin, urlparse
            
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")
            
            if base_url not in self.robots_cache:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                
                try:
                    if self.client:
                        response = await self.client.get(robots_url)
                        if response.status_code == 200:
                            rp.set_url(robots_url)
                            rp.read()
                except Exception:
                    # If robots.txt is not accessible, assume allowed
                    pass
                
                self.robots_cache[base_url] = rp
            
            return self.robots_cache[base_url].can_fetch(settings.user_agent, url)
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True  # Default to allowed if check fails
    
    async def _make_request(self, url: str, **kwargs) -> Optional[httpx.Response]:
        """Make an HTTP request with rate limiting and robots.txt compliance."""
        if not await self._check_robots_txt(url):
            logger.warning(f"URL blocked by robots.txt: {url}")
            return None
        
        await self._respect_rate_limit()
        
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        for attempt in range(settings.max_retries):
            try:
                response = await self.client.get(url, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff, max 60s
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                elif e.response.status_code >= 500:  # Server error
                    if attempt < settings.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                raise
                
            except (httpx.RequestError, httpx.TimeoutException) as e:
                if attempt < settings.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                raise
        
        return None
    
    def _extract_text(self, html: str) -> str:
        """Extract clean text from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    @abstractmethod
    async def fetch_data(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch data from the connector source.
        
        Yields:
            Dictionary containing signal data
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get the source name for this connector."""
        pass
