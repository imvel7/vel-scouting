#!/usr/bin/env python3
"""Print the text of the publisher's public event-map PDF (documentation only, no event data).

Needs the ``pypdf`` package (installed by the CI step). Prints at most MAX_CHARS characters.
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from io import BytesIO

REPO = "Afriskaut/dynasty-scouting-league-2024-open-data"
PDF_NAME = "Afriskaut Event Map - 2024.pdf"
MAX_CHARS = 90_000


def main() -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf is not installed; cannot extract the event map text.")
        return 1
    url = f"https://raw.githubusercontent.com/{REPO}/main/{urllib.parse.quote(PDF_NAME)}"
    request = urllib.request.Request(url, headers={"User-Agent": "VelScout-Research-Probe/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    reader = PdfReader(BytesIO(data))
    print(f"pages={len(reader.pages)} bytes={len(data)}")
    printed = 0
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        chunk = f"\n--- page {number} ---\n{text}\n"
        if printed + len(chunk) > MAX_CHARS:
            print("\n[truncated]")
            break
        print(chunk)
        printed += len(chunk)
    if printed == 0:
        print("No extractable text (the PDF may be image-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
