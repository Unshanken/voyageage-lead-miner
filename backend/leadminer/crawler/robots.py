from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from leadminer.config import Settings
from leadminer.crawler.fetcher import HttpFetcher


@dataclass(slots=True)
class RobotsPolicy:
    parser: RobotFileParser | None
    status: str
    robots_url: str
    error: str | None = None

    def allowed(self, user_agent: str, url: str) -> bool:
        return True if self.parser is None else self.parser.can_fetch(user_agent, url)


async def fetch_robots(fetcher: HttpFetcher, website_url: str, settings: Settings) -> RobotsPolicy:
    parsed = urlsplit(website_url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    result = await fetcher.fetch(robots_url, allow_text=True)
    if not result.ok:
        return RobotsPolicy(None, "unavailable_allow", robots_url, result.error_code)
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse((result.body or "").splitlines())
    return RobotsPolicy(parser, "loaded", robots_url)
