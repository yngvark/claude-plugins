#!/usr/bin/env -S uv --quiet run --locked --script

# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "7 days"
# ///

"""Move text between Google Docs and Markdown through the macOS clipboard.

    docs-clipboard.py read [--file HTML]
    docs-clipboard.py write DRAFT [--stdout]

`read` turns the HTML that Google Docs puts on the clipboard into Markdown,
keeping heading levels, lists, links, bold text and code. `--file` reads the
HTML from a file instead of the clipboard.

`write` turns a Markdown draft into HTML that Google Docs pastes as headings,
lists, links and code, and puts it on the clipboard together with a plain-text
version. `--stdout` prints the HTML instead.

Supported Markdown: `#` to `####` headings, paragraphs, `1.` and `-` list items
nested by 3 spaces per level, fenced code blocks (also inside list items),
`**bold**`, `` `code` `` and `[text](url)`.
"""

import argparse
import html
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

FONT = "font-family:Arial,sans-serif;"
TEXT = f"font-size:11pt;{FONT}color:#000000;"
MONO = "font-size:10pt;font-family:'Courier New',monospace;color:#000000;"
LINK = "color:#1155cc;text-decoration:underline;"
P = "line-height:1.38;margin-top:0pt;margin-bottom:0pt;"

# Google Docs' default named styles: size, color, space above, space below.
HEADINGS = {
    1: ("20pt", "#000000", "20pt", "6pt"),
    2: ("16pt", "#000000", "18pt", "6pt"),
    3: ("14pt", "#434343", "16pt", "4pt"),
    4: ("12pt", "#666666", "14pt", "4pt"),
}

INDENT = 3
ITEM = re.compile(r"^( *)(\d+\.|-) (.*)$")
INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)")


# ---------- Markdown to HTML ----------

def span(text, style=TEXT):
    return f'<span style="{style}">{html.escape(text)}</span>'


def inline(text):
    out, pos = [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            out.append(span(text[pos:m.start()]))
        bold, code, label, url = m.groups()
        if bold is not None:
            out.append(span(bold, TEXT + "font-weight:700;"))
        elif code is not None:
            out.append(span(code, MONO))
        else:
            out.append(f'<a href="{html.escape(url)}">{span(label, TEXT + LINK)}</a>')
        pos = m.end()
    if pos < len(text):
        out.append(span(text[pos:]))
    return "".join(out)


def code_lines(lines):
    # Google Docs collapses runs of normal spaces, so leading spaces become non-breaking ones.
    out = []
    for line in lines:
        stripped = line.lstrip(" ")
        lead = "&nbsp;" * (len(line) - len(stripped))
        out.append(f'<span style="{MONO}">{lead}{html.escape(stripped)}</span>')
    return "<br>".join(out)


def item_body(lines):
    """Render the lines of one list item as one paragraph. Extra paragraphs and code blocks
    become line breaks, because a second <p> inside an <li> pastes as a separate item."""
    parts, text, code, in_code = [], [], [], False
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                parts.append(code_lines(code))
                code = []
            elif text:
                parts.append(inline(" ".join(text)))
                text = []
            in_code = not in_code
        elif in_code:
            code.append(line)
        elif not line.strip():
            if text:
                parts.append(inline(" ".join(text)))
                text = []
        else:
            text.append(line.strip())
    if text:
        parts.append(inline(" ".join(text)))
    return "<br>".join(parts)


def to_html(markdown):
    lines = markdown.splitlines()
    out, i = ['<meta charset="utf-8">'], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif m := re.match(r"^(#{1,4}) (.*)$", line):
            level = len(m.group(1))
            size, color, above, below = HEADINGS[level]
            style = f"font-size:{size};{FONT}color:{color};font-weight:400;"
            out.append(f'<h{level} dir="ltr" style="line-height:1.38;margin-top:{above};margin-bottom:{below};">'
                       f'<span style="{style}">{html.escape(m.group(2))}</span></h{level}>')
            i += 1
        elif ITEM.match(line):
            i = list_block(lines, i, out)
        elif line.strip().startswith("```"):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].strip().startswith("```")), len(lines))
            out.append(f'<p dir="ltr" style="{P}">{code_lines(lines[i + 1:end])}</p>')
            i = end + 1
        else:
            text = []
            while i < len(lines) and lines[i].strip() and not ITEM.match(lines[i]) \
                    and not lines[i].startswith("#") and not lines[i].strip().startswith("```"):
                text.append(lines[i].strip())
                i += 1
            out.append(f'<p dir="ltr" style="{P}">{inline(" ".join(text))}</p>')
    return "".join(out)


def list_block(lines, i, out):
    """Render a list starting at line i, and return the index after it. Nested lists sit
    next to their parent's items inside the outer list, the way Google Docs copies them."""
    open_lists = []  # list tag per level
    while i < len(lines):
        m = ITEM.match(lines[i])
        if not m:
            break
        level = len(m.group(1)) // INDENT
        tag = "ol" if m.group(2)[0].isdigit() else "ul"
        while len(open_lists) > level + 1 or (len(open_lists) == level + 1 and open_lists[-1] != tag):
            out.append(f"</{open_lists.pop()}>")
        while len(open_lists) < level + 1:
            out.append(f'<{tag} style="margin-top:0;margin-bottom:0;padding-inline-start:48px;">')
            open_lists.append(tag)
        content_indent = (level + 1) * INDENT
        body, i = [m.group(3)], i + 1
        in_code = False
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("```"):
                in_code = not in_code
            elif not in_code and line.strip() and len(line) - len(line.lstrip(" ")) < content_indent:
                break
            elif not in_code and ITEM.match(line):
                break
            if not line.strip() and not in_code:
                nxt = next((l for l in lines[i + 1:] if l.strip()), "")
                if len(nxt) - len(nxt.lstrip(" ")) < content_indent or ITEM.match(nxt):
                    i += 1
                    if not ITEM.match(nxt):
                        break
                    continue
            body.append(line[content_indent:] if line.strip() else "")
            i += 1
        style = "decimal" if tag == "ol" else ("disc" if level % 2 == 0 else "circle")
        out.append(f'<li dir="ltr" aria-level="{level + 1}" style="list-style-type:{style};{TEXT}">'
                   f'<p dir="ltr" style="{P}">{item_body(body)}</p></li>')
    while open_lists:
        out.append(f"</{open_lists.pop()}>")
    return i


def to_plain(markdown):
    out = []
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            continue
        line = re.sub(r"^#{1,4} ", "", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", line)
        out.append(line.replace("**", "").replace("`", ""))
    return "\n".join(out)


# ---------- HTML to Markdown ----------

class DocsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []  # (kind, level, ordered, text)
        self.text = []
        self.heading = 0
        self.lists = []  # "ol"/"ul" per open list
        self.item_level = None
        self.styles = []  # (tag, bold, mono) per open inline tag
        self.href = None
        self.link_text = []

    def _flush(self):
        text = "".join(self.text).strip("\n ")
        if text:
            if self.heading:
                self.blocks.append(("h", self.heading, False, text))
            elif self.item_level is not None:
                self.blocks.append(("li", self.item_level, self.lists[-1] == "ol", text))
            else:
                self.blocks.append(("p", 0, False, text))
        self.text = []

    def _emit(self, s):
        (self.link_text if self.href is not None else self.text).append(s)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = (attrs.get("style") or "").replace(" ", "")
        if re.fullmatch(r"h[1-6]", tag):
            self._flush()
            self.heading = int(tag[1])
        elif tag in ("ol", "ul"):
            self._flush()
            self.lists.append(tag)
        elif tag == "li":
            self._flush()
            self.item_level = int(attrs.get("aria-level") or len(self.lists)) - 1
        elif tag == "p":
            if self.item_level is None:
                self._flush()
        elif tag == "br":
            self._emit("\n")
        elif tag == "a":
            self.href = attrs.get("href")
            self.link_text = []
        elif tag in ("span", "b", "strong", "code"):
            bold = (tag in ("b", "strong") and "font-weight:normal" not in style) or \
                   re.search(r"font-weight:(700|bold)", style) is not None
            mono = tag == "code" or "courier" in style.lower() or "monospace" in style.lower()
            self.styles.append((tag, bold, mono))
            if mono:
                self._emit("\0")
            elif bold:
                self._emit("**")

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag):
            self._flush()
            self.heading = 0
        elif tag in ("ol", "ul"):
            self._flush()
            self.lists.pop()
            self.item_level = None if not self.lists else self.item_level
        elif tag == "li":
            self._flush()
            self.item_level = None
        elif tag == "p" and self.item_level is None:
            self._flush()
        elif tag == "a" and self.href is not None:
            label = "".join(self.link_text)
            self.href, href = None, self.href
            self._emit(f"[{label}]({href})")
        elif tag in ("span", "b", "strong", "code") and self.styles:
            _, bold, mono = self.styles.pop()
            if mono:
                self._emit("\0")
            elif bold:
                self._emit("**")

    def handle_data(self, data):
        self._emit(data.replace(" ", " "))


def mono_to_markdown(text, indent):
    """Turn \\0-delimited monospace runs into Markdown. A run spanning whole lines becomes a
    fenced code block, a run inside a line becomes `code`."""
    lines = text.split("\n")
    out, code = [], []
    pad = " " * indent
    for line in lines:
        whole = re.fullmatch(r"(\0[^\0]*\0)+", line)
        if whole and line.replace("\0", "").strip():
            code.append(line.replace("\0", ""))
            continue
        if code:
            out += [pad + "```", *(pad + c for c in code), pad + "```"]
            code = []
        out.append(pad + re.sub(r"\0([^\0]*)\0", lambda m: f"`{m.group(1)}`" if m.group(1) else "", line))
    if code:
        out += [pad + "```", *(pad + c for c in code), pad + "```"]
    first = out[0][len(pad):] if out else ""
    return "\n".join([first] + out[1:])


def to_markdown(source):
    parser = DocsParser()
    parser.feed(source)
    parser.close()
    parser._flush()
    out, counters, prev = [], {}, None
    for kind, level, ordered, text in parser.blocks:
        text = text.replace("****", "")
        if kind == "li":
            for deeper in [k for k in counters if k > level]:
                del counters[deeper]
            counters[level] = counters.get(level, 0) + 1 if ordered else 0
            marker = f"{counters[level]}." if ordered else "-"
            if prev not in (None, "li"):
                out.append("")
            out.append(" " * (level * INDENT) + f"{marker} " +
                       mono_to_markdown(text, (level + 1) * INDENT))
        else:
            counters = {}
            if out:
                out.append("")
            body = mono_to_markdown(text, 0)
            out.append(("#" * level + " " + body) if kind == "h" else body)
        prev = kind
    return "\n".join(out) + "\n"


# ---------- Clipboard ----------

def clipboard_html():
    script = ('ObjC.import("AppKit");'
              'ObjC.unwrap($.NSPasteboard.generalPasteboard.stringForType("public.html")) || ""')
    return subprocess.run(["osascript", "-l", "JavaScript", "-e", script],
                          check=True, capture_output=True, text=True).stdout


def set_clipboard(html_text, plain_text, workdir):
    html_file, plain_file = workdir / ".docs-clipboard.html", workdir / ".docs-clipboard.txt"
    html_file.write_text(html_text)
    plain_file.write_text(plain_text)
    script = f"""
ObjC.import("AppKit");
const read = p => $.NSString.stringWithContentsOfFileEncodingError(p, $.NSUTF8StringEncoding, null);
const pb = $.NSPasteboard.generalPasteboard;
pb.clearContents;
pb.setStringForType(read({str(html_file)!r}), "public.html");
pb.setStringForType(read({str(plain_file)!r}), "public.utf8-plain-text");
"""
    try:
        subprocess.run(["osascript", "-l", "JavaScript", "-e", script], check=True, capture_output=True)
    finally:
        html_file.unlink()
        plain_file.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read")
    read.add_argument("--file", type=Path)
    write = sub.add_parser("write")
    write.add_argument("draft", type=Path)
    write.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    if args.command == "read":
        source = args.file.read_text() if args.file else clipboard_html()
        if not source.strip():
            sys.exit("The clipboard holds no HTML. Copy the text in Google Docs first.")
        if not args.file and "docs-internal-guid" not in source:
            print("Note: the clipboard HTML does not come from Google Docs.", file=sys.stderr)
        print(to_markdown(source), end="")
    else:
        markdown = args.draft.read_text()
        result = to_html(markdown)
        if args.stdout:
            print(result)
        else:
            set_clipboard(result, to_plain(markdown), args.draft.resolve().parent)
            print(f"Copied {args.draft.name} to the clipboard.")


if __name__ == "__main__":
    main()
