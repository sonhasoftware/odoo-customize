# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import re
import requests
import unicodedata
from lxml import html

_logger = logging.getLogger(__name__)


class HTMLExtractor:
    """
    Extracts text content from HTML sources (URLs or HTML strings) as a series of paragraphs,
    simplifying the hierarchical structure into a clean text format.
    """

    def __init__(self):
        # Define non-content XPaths to exclude
        self.exclude_xpath = [
            "//script", "//style", "//noscript", "//iframe",
            "//nav", "//footer", "//header", "//aside",
            "//*[contains(@class, 'menu')]",
            "//*[contains(@class, 'footer')]",
            "//*[contains(@class, 'header')]",
            "//*[contains(@class, 'navigation')]",
            "//*[contains(@class, 'nav')]",
            "//*[contains(@class, 'sidebar')]",
            "//*[contains(@id, 'menu')]",
            "//*[contains(@id, 'navigation')]",
            "//*[contains(@id, 'footer')]",
            "//*[contains(@id, 'header')]",
            "//*[contains(@style, 'display:none')]",
            "//*[contains(@style, 'display: none')]",
            "//*[contains(@style, 'visibility:hidden')]",
            "//*[contains(@style, 'visibility: hidden')]",
            "//comment()"
        ]

    def scrap(self, url):
        """
        Scrape a webpage and extract text content.
        Args:
            url (str): The URL to scrape
        Returns:
            dict: Dictionary with 'content' and 'title' keys, or None if scraping fails
        """
        html_content, error_message = self._fetch_url(url)
        if not html_content:
            return {"content": None, "title": None, "error": error_message}

        parser = html.HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True)
        tree = html.fromstring(html_content, parser=parser)

        # Extract metadata
        title = self._get_title(tree)

        # Clean HTML tree
        self._clean_html_tree(tree)

        # Extract content as paragraphs
        content = self._extract_content(tree)
        if not content:
            return {"content": None, "title": None, "error": "No extractable content found on the page."}

        return {"content": content, "title": title, "error": None}

    def extract_from_html(self, html_content):
        """
        Extract text content from HTML string (e.g., from a knowledge HTML field body).
        Args:
            html_content (str): The HTML content as a string
            title (str, optional): Optional title for the content
        Returns:
            dict: Dictionary with 'content' and 'title' keys
        """
        if not html_content:
            return {"content": ""}

        # Wrap content in a proper HTML structure to ensure _clean_html_tree works correctly
        wrapped_html = f"<html><body>{html_content}</body></html>"
        parser = html.HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True)
        tree = html.fromstring(wrapped_html, parser=parser)

        # Clean HTML tree
        self._clean_html_tree(tree)

        # Extract content as paragraphs
        content = self._extract_content(tree)

        return {"content": content}

    def _fetch_url(self, url):
        """Fetch URL content"""
        try:
            headers = {
                "User-Agent": "Odoobot/1.0 (+https://www.odoo.com)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Check content type to ensure we're dealing with HTML
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                error_msg = f"URL {url} returned non-HTML content: {content_type}"
                _logger.warning(error_msg)
                return None, error_msg

            if not response.content:
                error_msg = f"URL {url} returned empty content"
                _logger.warning(error_msg)
                return None, error_msg

            return response.content, None
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch URL: {e!s}"
            _logger.error(error_msg)
            return None, error_msg

    def _get_title(self, tree):
        """Extract page title."""
        titles = tree.xpath("//title/text()")
        if titles:
            return titles[0].strip()
        return ""

    def _clean_html_tree(self, tree):
        """Clean HTML by removing unwanted elements."""
        # Remove unwanted elements
        for xpath in self.exclude_xpath:
            for element in tree.xpath(xpath):
                if element.getparent() is not None:
                    element.getparent().remove(element)

    def _extract_content(self, tree):
        """
        Extract content as a series of paragraphs
        """
        main_content = tree.xpath("//main|//article|//div[@role='main']|//div[@id='content']|//div[@class='content']")
        if not main_content:
            main_content = tree.xpath("//body")
            if not main_content:
                _logger.warning("Could not find any content container in the HTML")
                return ""

        paragraphs = []

        current_heading = None
        current_paragraph_parts = []

        for element in main_content[0].xpath(".//*"):
            tag = element.tag

            # Check if this is a heading element
            if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # If we have a previous heading, add it (with or without content)
                if current_heading:
                    if current_paragraph_parts:
                        paragraph = f"{current_heading}. {' '.join(current_paragraph_parts)}"
                    else:
                        paragraph = current_heading
                    paragraphs.append(paragraph)
                    current_paragraph_parts = []

                # Set the new heading
                heading_text = self._get_element_text(element)
                if heading_text:
                    current_heading = self._normalize_text(heading_text)

            # Process paragraph content
            elif tag == 'p':
                text = self._get_element_text(element)
                if text:
                    text = self._normalize_text(text)
                    if current_heading:
                        current_paragraph_parts.append(text)
                    else:
                        # No heading, add as standalone paragraph
                        paragraphs.append(text)

            # Process unordered lists
            elif tag == 'ul':
                # Skip navigation and menu lists
                if any(cls in (element.get("class", "") or "").lower() for cls in ["menu", "nav", "navigation"]):
                    continue

                list_items = []
                for li in element.xpath("./li"):
                    item_text = self._get_element_text(li)
                    if item_text:
                        list_items.append(f"• {item_text}")

                if list_items:
                    list_text = " ".join(list_items)
                    if current_heading:
                        current_paragraph_parts.append(list_text)
                    else:
                        paragraphs.append(list_text)

            # Process ordered lists
            elif tag == 'ol':
                list_items = []
                for i, li in enumerate(element.xpath("./li")):
                    item_text = self._get_element_text(li)
                    if item_text:
                        list_items.append(f"{i + 1}. {item_text}")

                if list_items:
                    list_text = " ".join(list_items)
                    if current_heading:
                        current_paragraph_parts.append(list_text)
                    else:
                        paragraphs.append(list_text)

            # Process tables
            elif tag == 'table':
                # Skip layout tables
                if element.get("role") == "presentation":
                    continue

                table_text = self._process_table_as_text(element)
                if table_text:
                    if current_heading:
                        current_paragraph_parts.append(table_text)
                    else:
                        paragraphs.append(table_text)

            # Process div and span elements with direct text
            elif tag in ['div', 'span'] and element.xpath(".//text()") and not element.xpath("./p"):
                # Check if this element directly contains text (not just in its children)
                direct_text = "".join(t.strip() for t in element.xpath("./text()") if t.strip())

                if direct_text:
                    text = self._normalize_text(direct_text)
                    if current_heading:
                        current_paragraph_parts.append(text)
                    else:
                        paragraphs.append(text)

        if current_heading:
            if current_paragraph_parts:
                paragraph = f"{current_heading}. {' '.join(current_paragraph_parts)}"
            else:
                paragraph = current_heading
            paragraphs.append(paragraph)

        return "\n\n".join(p.strip() for p in paragraphs if p.strip())

    def _process_table_as_text(self, table):
        """Process a table element and return its text content."""

        captions = table.xpath("./caption")
        caption_text = self._get_element_text(captions[0]) if captions else ""

        # Process table headers
        headers = []
        for th in table.xpath(".//th"):
            text = self._get_element_text(th)
            headers.append(text if text else "")

        # Process table rows
        table_rows = []
        for tr in table.xpath(".//tr[td]"):
            row_data = []
            for td in tr.xpath("./td"):
                text = self._get_element_text(td)
                row_data.append(text if text else "")

            if row_data:
                table_rows.append(" | ".join(row_data))

        # Combine table content
        table_content = []
        if caption_text:
            table_content.append(caption_text + ":")

        if headers:
            table_content.append(" | ".join(headers))

        table_content.extend(table_rows)

        return " ".join(table_content)

    def _get_element_text(self, element):
        """Get text content from an element, preserving whitespace where appropriate."""
        if element is None:
            return ""

        # Get all text nodes
        texts = []
        for t in element.xpath(".//text()"):
            if t.is_text:
                parent = t.getparent()
                if parent is not None and parent.tag in ["pre", "code"]:
                    # Preserve whitespace in pre/code blocks
                    texts.append(t)
                else:
                    # Normalize whitespace in regular text
                    texts.append(t.strip())

        return " ".join(t for t in texts if t)

    def _normalize_text(self, text):
        """Normalize text by handling whitespace, unicode, and other issues."""
        if not text:
            return ""
        # Normalize unicode characters
        text = unicodedata.normalize("NFKC", text)
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        # Remove excessive newlines
        text = re.sub(r'\n+', ' ', text)
        # Remove control characters and special characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        # Remove HTML tags
        text = re.sub(r'[<>{}[\]\\]', '', text)
        return text.strip()
