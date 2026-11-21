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


def executed_listing_numbers(html):
    """Line numbers of the listing lines that carry the word "executed"."""
    pattern = re.compile(
        r'<span class="listing-line"><span class="listing-number">(\d+)</span> [^\n]*? '
        r'<span class="listing-executed">executed</span></span>\n',
    )
    return [int(n) for n in pattern.findall(html)]


def example_block(html):
    """The text of the <pre class="story-example"> block, or None."""
    import html as html_module
    match = re.search(r'<pre class="story-example">(.*?)</pre>', html, re.S)
    return html_module.unescape(match.group(1)) if match else None


def headings(html, level="h3"):
    """The text of every heading of one level."""
    return [h.strip() for h in re.findall(rf"<{level}[^>]*>(.*?)</{level}>", html, re.S)]


class _FormReader(HTMLParser):
    def __init__(self, hx_post):
        super().__init__(convert_charrefs=True)
        self.hx_post = hx_post
        self.fields = {}
        self._inside = False
        self._select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._inside = attrs.get("hx-post") == self.hx_post
        elif self._inside and tag == "input" and "name" in attrs:
            self.fields[attrs["name"]] = attrs.get("value", "")
        elif self._inside and tag == "select":
            self._select = attrs.get("name")
        elif self._inside and tag == "option" and self._select and "selected" in attrs:
            self.fields[self._select] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._inside = False
        elif tag == "select":
            self._select = None


def form_fields(html, hx_post):
    """name -> value of the inputs (and the selected option) of the form whose hx-post is `hx_post`."""
    reader = _FormReader(hx_post)
    reader.feed(html)
    reader.close()
    return reader.fields


_VOID = {"input", "br", "hr", "img", "meta", "link", "source", "col", "area", "base", "wbr"}


def _is_live(attrs):
    """True for an element that is a live region: aria-live other than off, or role status or alert."""
    return (
        attrs.get("aria-live") not in (None, "off")
        or attrs.get("role") in ("status", "alert", "log")
    )


class _LiveCounter(HTMLParser):
    def __init__(self, element_id):
        super().__init__(convert_charrefs=True)
        self.element_id = element_id
        self.count = 0
        self.found = False
        self._open = 0
        self._inside = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self._inside and attrs.get("id") == self.element_id:
            self._inside = True
            self.found = True
            self._open = 0
        if self._inside:
            if _is_live(attrs):
                self.count += 1
            if tag not in _VOID:
                self._open += 1

    def handle_endtag(self, tag):
        if self._inside and tag not in _VOID:
            self._open -= 1
            if self._open == 0:
                self._inside = False


def live_regions_within(html, element_id):
    """Number of live regions in the element with this id, the element itself included."""
    counter = _LiveCounter(element_id)
    counter.feed(html)
    counter.close()
    assert counter.found, f"no element with id {element_id}"
    return counter.count


def live_regions(html):
    """Number of live regions in a whole page or fragment."""
    reader = _read(html)
    return sum(1 for _, attrs in reader.tags if _is_live(attrs))


def into_container(page, element_id, fragment):
    """The page with `fragment` placed inside its empty container <div id="element_id"></div>."""
    empty = f'<div id="{element_id}"></div>'
    assert page.count(empty) == 1, f"{empty} is not in the page exactly once"
    return page.replace(empty, f'<div id="{element_id}">{fragment}</div>')
