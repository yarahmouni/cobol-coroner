"""Small HTML readers for the story tests (standard library only)."""
import re
from html.parser import HTMLParser


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.chunks = []
        self.rows = []
        self._row = None
        self._cell = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in ("script", "style"):
            self._skip += 1
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._skip:
            return
        self.chunks.append(data)
        if self._cell is not None:
            self._cell.append(data)


def _read(html):
    reader = _Reader()
    reader.feed(html)
    reader.close()
    return reader


def tags(html, name=None):
    """(tag, attributes) of every start tag, or only of the tags called `name`."""
    found = _read(html).tags
    return [t for t in found if name is None or t[0] == name]


def visible_text(html):
    """The text of the page with white space collapsed (script and style content left out)."""
    return " ".join("".join(_read(html).chunks).split())


def table_rows(html):
    """The cell texts of every table row, in order."""
    return _read(html).rows


def anchors(html):
    """Attributes of every <a> that has an href."""
    return [attrs for tag, attrs in tags(html, "a") if "href" in attrs]


def has_live_region_root(html):
    """True when the fragment is a live region: role=alert, or role=status with aria-live=polite."""
    for tag, attrs in tags(html):
        if attrs.get("role") == "alert":
            return True
        if attrs.get("role") == "status" and attrs.get("aria-live") == "polite":
            return True
    return False


def listing_lines(html):
    """(number, text) of every line of every COBOL listing in the page."""
    pattern = re.compile(
        r'<span class="listing-line"><span class="listing-number">(\d+)</span> (.*?)'
        r'(?: <span class="listing-executed">executed</span>)?</span>\n',
    )
    import html as html_module
    return [(int(n), html_module.unescape(text)) for n, text in pattern.findall(html)]
