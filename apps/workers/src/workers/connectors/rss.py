"""RSS/News feed connector."""

import feedparser
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List

import structlog

from workers.connectors.base import BaseConnector

logger = structlog.get_logger()


class RSSConnector(BaseConnector):
    """Connector for RSS/Atom feeds."""
    
    def __init__(self):
        super().__init__("rss")
        self.default_feeds = [
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.feedburner.com/venturebeat/SZYF",
            "https://www.wired.com/feed/rss",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/technologyNews",
            "https://www.reddit.com/r/startups/.rss",
            "https://www.reddit.com/r/entrepreneur/.rss",
            "https://news.ycombinator.com/rss",
        ]
    
    def get_source_name(self) -> str:
        """Get the source name."""
        return "rss"
    
    async def fetch_data(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch RSS feed data."""
        feeds = kwargs.get("feeds", self.default_feeds)
        max_items_per_feed = kwargs.get("max_items", 50)
        
        for feed_url in feeds:
            try:
                async for item in self.fetch_feed(feed_url, max_items_per_feed):
                    yield item
            except Exception as e:
                logger.error(f"Error fetching feed {feed_url}: {e}")
                continue
    
    async def fetch_feed(self, feed_url: str, max_items: int = 50) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch items from a single RSS feed."""
        try:
            response = await self._make_request(feed_url)
            if not response:
                return
            
            # Parse the feed
            feed = feedparser.parse(response.text)
            
            if feed.bozo:
                logger.warning(f"Feed parsing issues for {feed_url}: {feed.bozo_exception}")
            
            # Extract feed metadata
            feed_title = getattr(feed.feed, 'title', 'Unknown Feed')
            feed_description = getattr(feed.feed, 'description', '')
            
            # Process entries
            for i, entry in enumerate(feed.entries[:max_items]):
                try:
                    # Extract entry data
                    title = getattr(entry, 'title', 'No Title')
                    summary = getattr(entry, 'summary', getattr(entry, 'description', ''))
                    link = getattr(entry, 'link', '')
                    
                    # Parse published date
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = datetime(*entry.published_parsed[:6]).isoformat()
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        published_at = datetime(*entry.updated_parsed[:6]).isoformat()
                    else:
                        published_at = datetime.utcnow().isoformat()
                    
                    # Extract tags/categories
                    tags = []
                    if hasattr(entry, 'tags'):
                        tags = [tag.term for tag in entry.tags]
                    
                    # Extract author
                    author = getattr(entry, 'author', '')
                    
                    # Clean summary text
                    clean_summary = self._extract_text(summary) if summary else ""
                    content = f"{title}. {clean_summary}"
                    
                    yield {
                        "title": title,
                        "content": content,
                        "url": link,
                        "metadata": {
                            "feed_url": feed_url,
                            "feed_title": feed_title,
                            "feed_description": feed_description,
                            "summary": clean_summary,
                            "author": author,
                            "tags": tags,
                            "platform": "rss",
                            "scraped_at": datetime.utcnow().isoformat(),
                        },
                        "published_at": published_at,
                    }
                    
                except Exception as e:
                    logger.warning(f"Error parsing feed entry: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
            return
    
    async def fetch_tech_news(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch tech news from curated feeds."""
        tech_feeds = [
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.feedburner.com/venturebeat/SZYF",
            "https://www.wired.com/feed/rss",
            "https://arstechnica.com/feed/",
        ]
        
        async for item in self.fetch_data(feeds=tech_feeds, max_items=20):
            yield item
    
    async def fetch_startup_news(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch startup and entrepreneurship news."""
        startup_feeds = [
            "https://www.reddit.com/r/startups/.rss",
            "https://www.reddit.com/r/entrepreneur/.rss",
            "https://news.ycombinator.com/rss",
            "https://feeds.feedburner.com/venturebeat/SZYF",
        ]
        
        async for item in self.fetch_data(feeds=startup_feeds, max_items=30):
            yield item
