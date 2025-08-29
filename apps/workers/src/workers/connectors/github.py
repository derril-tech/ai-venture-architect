"""GitHub trending connector."""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import structlog

from workers.connectors.base import BaseConnector

logger = structlog.get_logger()


class GitHubConnector(BaseConnector):
    """Connector for GitHub trending repositories."""
    
    def __init__(self, token: Optional[str] = None):
        super().__init__("github")
        self.token = token
        self.api_base = "https://api.github.com"
        self.trending_base = "https://github.com/trending"
    
    def get_source_name(self) -> str:
        """Get the source name."""
        return "github"
    
    async def fetch_data(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch GitHub trending data."""
        language = kwargs.get("language", "")
        period = kwargs.get("period", "daily")  # daily, weekly, monthly
        
        # Fetch trending repositories
        async for repo in self.fetch_trending_repos(language, period):
            yield repo
    
    async def fetch_trending_repos(
        self, 
        language: str = "", 
        period: str = "daily"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch trending repositories."""
        # GitHub doesn't have an official trending API, so we scrape the trending page
        url = f"{self.trending_base}"
        params = {}
        
        if language:
            params["l"] = language
        if period != "daily":
            params["since"] = period
        
        response = await self._make_request(url, params=params)
        if not response:
            return
        
        async for repo in self._parse_trending_page(response.text):
            yield repo
    
    async def _parse_trending_page(self, html: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Parse trending repositories from GitHub trending page."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find repository articles
        repos = soup.find_all('article', class_='Box-row')
        
        for repo in repos:
            try:
                # Extract repository name and URL
                title_elem = repo.find('h2', class_='h3')
                if not title_elem:
                    continue
                
                link_elem = title_elem.find('a')
                if not link_elem:
                    continue
                
                repo_name = link_elem.get_text().strip().replace('\n', '').replace(' ', '')
                repo_url = f"https://github.com{link_elem['href']}"
                
                # Extract description
                desc_elem = repo.find('p', class_='col-9')
                description = desc_elem.get_text().strip() if desc_elem else ""
                
                # Extract language
                lang_elem = repo.find('span', {'itemprop': 'programmingLanguage'})
                language = lang_elem.get_text().strip() if lang_elem else ""
                
                # Extract stars and forks
                stars_elem = repo.find('a', href=lambda x: x and '/stargazers' in x)
                stars = 0
                if stars_elem:
                    stars_text = stars_elem.get_text().strip().replace(',', '')
                    try:
                        stars = int(stars_text)
                    except ValueError:
                        pass
                
                forks_elem = repo.find('a', href=lambda x: x and '/forks' in x)
                forks = 0
                if forks_elem:
                    forks_text = forks_elem.get_text().strip().replace(',', '')
                    try:
                        forks = int(forks_text)
                    except ValueError:
                        pass
                
                # Extract today's stars
                today_stars_elem = repo.find('span', class_='d-inline-block')
                today_stars = 0
                if today_stars_elem:
                    today_text = today_stars_elem.get_text().strip()
                    try:
                        today_stars = int(today_text.split()[0].replace(',', ''))
                    except (ValueError, IndexError):
                        pass
                
                yield {
                    "title": repo_name,
                    "content": f"{repo_name}: {description}",
                    "url": repo_url,
                    "metadata": {
                        "repository_name": repo_name,
                        "description": description,
                        "language": language,
                        "stars": stars,
                        "forks": forks,
                        "today_stars": today_stars,
                        "platform": "github",
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    "published_at": datetime.utcnow().isoformat(),
                }
                
            except Exception as e:
                logger.warning(f"Error parsing repository: {e}")
                continue
    
    async def fetch_repo_details(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed repository information using GitHub API."""
        if not self.token:
            logger.warning("GitHub token not provided, skipping API call")
            return None
        
        url = f"{self.api_base}/repos/{owner}/{repo}"
        headers = {"Authorization": f"token {self.token}"}
        
        response = await self._make_request(url, headers=headers)
        if not response:
            return None
        
        try:
            data = response.json()
            return {
                "name": data.get("name"),
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "html_url": data.get("html_url"),
                "language": data.get("language"),
                "stargazers_count": data.get("stargazers_count"),
                "forks_count": data.get("forks_count"),
                "open_issues_count": data.get("open_issues_count"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "topics": data.get("topics", []),
            }
        except Exception as e:
            logger.error(f"Error parsing GitHub API response: {e}")
            return None
