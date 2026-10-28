#!/usr/bin/env -S uv --quiet run --script

# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///

import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "skills" / "google-docs-clipboard" / "docs-clipboard.py"
dc = SourceFileLoader("dc", str(SCRIPT)).load_module()

DRAFT = """## Step 3: Set up alerts for the account

ℹ️ The **team** must exist first.

### Step 3.1: Check the table

1. Agree with the team which channel they want alerts in.
2. Look up the existing row:
   ```
   aws dynamodb get-item \\
     --table-name example-table
   ```
3. Follow [the access runbook](https://example.com/doc#access) and run `make check`.
   - Ask in the channel first.
   - Then wait for an answer.
4. Check that the alert shows up.

Done.
"""

# Shaped like what Google Docs puts on the clipboard: a font-weight:normal <b> wrapper,
# styled spans, a nested list as a sibling inside the outer list, and aria-level.
DOCS_HTML = (
    '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1234">'
    '<h3 dir="ltr"><span style="font-size:14pt;font-weight:400;">Step 4: Order a group</span></h3><br />'
    '<ol style="margin-top:0;"><li dir="ltr" aria-level="1"><p dir="ltr" role="presentation">'
    '<span style="font-weight:400;">Read </span><a href="https://example.com/readme">'
    '<span style="color:#1155cc;">the readme</span></a><span style="font-weight:400;"> first.</span></p></li>'
    '<ul style="margin-top:0;"><li dir="ltr" aria-level="2"><p dir="ltr" role="presentation">'
    '<span style="font-weight:700;">Warning:</span><span style="font-weight:400;"> it overwrites the row.</span>'
    '</p></li></ul>'
    '<li dir="ltr" aria-level="1"><p dir="ltr" role="presentation">'
    '<span style="font-weight:400;">Run </span><span style="font-family:\'Courier New\',monospace;">make</span>'
    '<span style="font-weight:400;">.</span></p></li></ol></b>'
)


def test_round_trip_keeps_the_draft():
    assert dc.to_markdown(dc.to_html(DRAFT)) == DRAFT


def test_reads_google_docs_html():
    assert dc.to_markdown(DOCS_HTML) == (
        "### Step 4: Order a group\n"
        "\n"
        "1. Read [the readme](https://example.com/readme) first.\n"
        "   - **Warning:** it overwrites the row.\n"
        "2. Run `make`.\n"
    )


def test_headings_use_the_matching_tag():
    result = dc.to_html("## Two\n\n### Three\n")
    assert "<h2 " in result and "<h3 " in result


def test_code_in_an_item_stays_in_the_item_with_its_indentation():
    result = dc.to_html("1. Run this:\n   ```\n   a \\\n     b\n   ```\n2. Next.\n")
    assert result.count("<li ") == 2
    assert "&nbsp;&nbsp;b" in result
    assert "Courier New" in result


def test_second_paragraph_in_an_item_stays_in_the_item():
    result = dc.to_html("1. First line.\n\n   Second line.\n2. Next.\n")
    assert result.count("<li ") == 2
    assert result.count("<p ") == 2


def test_link_keeps_its_url():
    assert '<a href="https://example.com/x?a=1&amp;b=2">' in dc.to_html("[x](https://example.com/x?a=1&b=2)\n")


def test_plain_text_shows_link_urls_and_drops_markup():
    plain = dc.to_plain("## Title\n\n1. See [doc](https://example.com) and **this** `cmd`.\n")
    assert plain == "Title\n\n1. See doc (https://example.com) and this cmd."


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
