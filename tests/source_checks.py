"""Verify the actual escaped HTML source panel, including on error responses."""
from html.parser import HTMLParser


class SourcePanel(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.depth = 0
        self.code = False
        self.codes = []
        self.frames = []
        self.visible = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details" and attrs.get("id") == "bhash-source":
            self.count += 1
            assert not self.depth and "open" not in attrs, "Panel must start closed"
            self.depth = 1
        elif self.depth:
            if tag == "details":
                self.depth += 1
            assert tag not in ("a", "form", "input", "script"), "Source controls must not navigate or submit"
            if tag == "iframe":
                assert attrs.get("loading") == "lazy" and set(attrs.get("sandbox", "").split()) == {"allow-same-origin", "allow-scripts"}
                assert attrs.get("allow") == "clipboard-write 'self'"
                assert attrs.get("title")
                self.frames.append(attrs["src"])
            if tag == "pre":
                assert attrs.get("tabindex") == "0", "Scrollable code must be keyboard-accessible"
            if tag == "code":
                self.code = True
                self.codes.append("")

    def handle_endtag(self, tag):
        if self.depth and tag == "details":
            self.depth -= 1
        if tag == "code":
            self.code = False

    def handle_data(self, data):
        if self.depth and self.code:
            self.codes[-1] += data
        elif not self.depth:
            self.visible.append(data)

    def check(self):
        assert self.count == 1 and self.depth == 0, "Each HTML page needs one complete source panel"
        assert len(self.frames) == 1 and self.frames[0].startswith("/source/")
        assert not self.codes, "Source should load on demand"
        return self

    def document(self, client):
        return SourceDocument(client.request(self.frames[0])[0]).check()


class SourceDocument(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.codes = []
        self.code = False
        self.lines = []
        self.tokens = set()
        self.copy_buttons = 0
        self.scripts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        assert tag not in ("form", "input", "a"), "Source must be inert escaped text"
        if tag == "script":
            assert not self.code and attrs.get("src") == "/assets/source-copy.js" and "defer" in attrs
            self.scripts.append(attrs["src"])
        if tag == "button":
            assert attrs.get("type") == "button" and attrs.get("data-copy-code") == "true"
            assert attrs.get("data-copy-ready") and attrs.get("data-copy-done") and attrs.get("data-copy-error")
            self.copy_buttons += 1
        if tag == "iframe":
            assert attrs.get("loading") == "lazy" and set(attrs.get("sandbox", "").split()) == {"allow-same-origin", "allow-scripts"}
            assert attrs.get("allow") == "clipboard-write 'self'"
            assert attrs.get("src", "").startswith("/source/") and attrs.get("title")
        if tag == "pre":
            assert attrs.get("tabindex") == "0"
        if tag == "code":
            self.code = True
            self.codes.append("")
            self.lines.append([])
        if self.code and tag == "span":
            if "data-line" in attrs:
                self.lines[-1].append(int(attrs["data-line"]))
            if attrs.get("class", "").startswith("tok-"):
                self.tokens.add(attrs["class"])

    def handle_endtag(self, tag):
        if tag == "code":
            self.code = False

    def handle_data(self, data):
        if self.code:
            self.codes[-1] += data

    def check(self):
        assert len(self.codes) >= 1
        assert all("फलन " in c or "वर्ग " in c for c in self.codes)
        assert self.copy_buttons == len(self.codes)
        assert self.scripts == ["/assets/source-copy.js"]
        for code, numbers in zip(self.codes, self.lines):
            assert numbers == list(range(1, len(code.splitlines()) + 1)), "Line numbers must match original source lines"
        assert {"tok-keyword", "tok-string"}.issubset(self.tokens)
        return self
