"""
Tests for selenium_scraper.py - SeleniumEventScraper.

Tests static/parsing methods that don't require a running browser:
- extract_event_links
- extract_location_from_url
- extract_title_from_page
- extract_date_from_page
- parse_event_page

Selenium WebDriver calls are mocked to avoid needing Chrome installed.
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def scraper():
    """Create a SeleniumEventScraper with mocked WebDriver."""
    with patch('selenium_scraper.webdriver.Chrome') as mock_chrome:
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        from selenium_scraper import SeleniumEventScraper
        s = SeleniumEventScraper.__new__(SeleniumEventScraper)
        s.base_url = "https://asiasociety.org/events/past"
        s.driver = mock_driver
        s.headless = True
        s.is_global = True
        return s


class TestExtractEventLinks:
    def test_extracts_valid_event_links(self, scraper):
        html = """
        <html><body>
            <a href="https://asiasociety.org/new-york/events/climate-summit-2024">Climate Summit</a>
            <a href="https://asiasociety.org/switzerland/events/trade-forum-2024">Trade Forum</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 2
        assert "climate-summit-2024" in links[0]
        assert "trade-forum-2024" in links[1]

    def test_excludes_listing_pages(self, scraper):
        html = """
        <html><body>
            <a href="https://asiasociety.org/events/past">Past Events</a>
            <a href="https://asiasociety.org/new-york/events/real-event-here">Real Event</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 1
        assert "real-event-here" in links[0]

    def test_excludes_non_event_links(self, scraper):
        html = """
        <html><body>
            <a href="https://asiasociety.org/about">About</a>
            <a href="https://asiasociety.org/news/article-1">News</a>
            <a href="https://asiasociety.org/video/watch-this">Video</a>
            <a href="https://asiasociety.org/new-york/events/valid-event-title">Event</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 1

    def test_deduplicates_links(self, scraper):
        html = """
        <html><body>
            <a href="https://asiasociety.org/events/same-event-twice">Link 1</a>
            <a href="https://asiasociety.org/events/same-event-twice">Link 2</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 1

    def test_converts_relative_urls(self, scraper):
        html = """
        <html><body>
            <a href="/new-york/events/relative-url-event">Event</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 1
        assert links[0].startswith("https://asiasociety.org")

    def test_filters_short_event_slugs(self, scraper):
        """Event slugs shorter than 5 chars should be excluded."""
        html = """
        <html><body>
            <a href="https://asiasociety.org/events/ab">Too Short</a>
            <a href="https://asiasociety.org/events/valid-long-event-name">Valid</a>
        </body></html>
        """
        links = scraper.extract_event_links(html)
        assert len(links) == 1

    def test_empty_html(self, scraper):
        links = scraper.extract_event_links("<html><body></body></html>")
        assert links == []


class TestExtractLocationFromUrl:
    def test_global_url(self, scraper):
        loc = scraper.extract_location_from_url("https://asiasociety.org/events/some-event")
        assert loc == "Events"

    def test_location_url(self, scraper):
        loc = scraper.extract_location_from_url("https://asiasociety.org/new-york/events/some-event")
        assert loc == "New York"

    def test_switzerland_url(self, scraper):
        loc = scraper.extract_location_from_url("https://asiasociety.org/switzerland/events/some-event")
        assert loc == "Switzerland"

    def test_hong_kong_url(self, scraper):
        loc = scraper.extract_location_from_url("https://asiasociety.org/hong-kong/events/some-event")
        assert loc == "Hong Kong"

    def test_texas_url(self, scraper):
        loc = scraper.extract_location_from_url("https://asiasociety.org/texas/events/some-event")
        assert loc == "Texas"


class TestExtractTitleFromPage:
    def test_og_title(self, scraper):
        html = '<html><head><meta property="og:title" content="Climate Summit 2024 | Asia Society" /></head><body></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        title = scraper.extract_title_from_page(soup, "https://asiasociety.org/events/climate-summit")
        assert title == "Climate Summit 2024"

    def test_title_tag_fallback(self, scraper):
        html = '<html><head><title>Trade Forum 2024 | Asia Society</title></head><body></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        title = scraper.extract_title_from_page(soup, "https://asiasociety.org/events/trade-forum")
        assert title == "Trade Forum 2024"

    def test_h1_event_title_class(self, scraper):
        html = '<html><head></head><body><h1 class="event-title">My Great Event Title</h1></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        title = scraper.extract_title_from_page(soup, "https://asiasociety.org/events/test")
        assert title == "My Great Event Title"

    def test_url_fallback(self, scraper):
        html = '<html><head></head><body></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        title = scraper.extract_title_from_page(soup, "https://asiasociety.org/events/my-great-event-title")
        assert title == "My Great Event Title"


class TestExtractDateFromPage:
    def test_date_in_event_details_widget(self, scraper):
        html = '<html><body><div class="event-details-wdgt">March 15, 2024</div></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        date = scraper.extract_date_from_page(soup, html)
        assert date is not None
        assert "March 15, 2024" in date or "2024" in date

    def test_date_in_time_element(self, scraper):
        html = '<html><body><time datetime="2024-03-15">March 15, 2024</time></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        date = scraper.extract_date_from_page(soup, html)
        assert date is not None

    def test_date_in_meta_tag(self, scraper):
        html = '<html><head><meta name="date" content="2024-03-15" /></head><body></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        date = scraper.extract_date_from_page(soup, html)
        assert date is not None

    def test_iso_date_format(self, scraper):
        html = '<html><body><span class="date">2024-03-15</span></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        date = scraper.extract_date_from_page(soup, html)
        assert "2024-03-15" in date

    def test_no_date_found(self, scraper):
        html = '<html><body><p>No date information here at all.</p></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        date = scraper.extract_date_from_page(soup, html)
        assert date is None


class TestParseEventPage:
    def test_full_parse(self, scraper, sample_event_html):
        result = scraper.parse_event_page(sample_event_html, "https://asiasociety.org/new-york/events/climate-summit")
        assert result['title'] == "Climate Policy Summit 2024"
        assert result['location'] == "New York"
        assert result['url'] == "https://asiasociety.org/new-york/events/climate-summit"
        assert len(result['body_text']) > 0
        assert result['raw_html'] == sample_event_html

    def test_parse_extracts_date(self, scraper, sample_event_html):
        result = scraper.parse_event_page(sample_event_html, "https://asiasociety.org/new-york/events/climate-summit")
        assert result['event_date'] is not None

    def test_parse_minimal_html(self, scraper):
        html = """
        <html><head><title>Simple Event | Asia Society</title></head>
        <body>
            <article>
                <p>This is a simple event description that is long enough to be extracted by the parser
                and should appear in the body text of the parsed result because it exceeds 100 characters easily.</p>
            </article>
        </body></html>
        """
        result = scraper.parse_event_page(html, "https://asiasociety.org/events/simple-event")
        assert result['title'] == "Simple Event"
        assert len(result['body_text']) > 0
