#!/usr/bin/env python3
"""Download the NLI parish-register images for Tawnawilly.

Page URL pattern:
https://registers.nli.ie/pages/vtls000631954_NNN

Install:
    python -m pip install requests beautifulsoup4

Run:
    python download_nli_register.py

The script saves original image bytes unchanged. If automated access is blocked
or the NLI page structure has changed, it reports the failure and saves the
page HTML (when accessible) for diagnosis.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_PAGE = "https://registers.nli.ie/pages/vtls000631954_{:03d}"
SITE_ROOT = "https://registers.nli.ie/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": SITE_ROOT,
}


def find_image_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    for attr, value in (
        ("property", "og:image"),
        ("name", "twitter:image"),
        ("name", "twitter:image:src"),
    ):
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            urls.append(urljoin(page_url, tag["content"]))

    for tag in soup.find_all(["img", "source"]):
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            if tag.get(attr):
                urls.append(urljoin(page_url, tag[attr]))
        if tag.get("srcset"):
            for item in tag["srcset"].split(","):
                candidate = item.strip().split()[0]
                if candidate:
                    urls.append(urljoin(page_url, candidate))

    # Look for image references embedded in JavaScript or JSON.
    patterns = [
        r'''https?://[^"'\\\s<>]+?\.(?:jpg|jpeg|png|tif|tiff|webp)(?:\?[^"'\\\s<>]*)?''',
        r"""["']([^"']*(?:iiif|image|vtls)[^"']*)["']""",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            value = match.replace("\\\\/", "/")
            urls.append(urljoin(page_url, value))

    # De-duplicate, preserving order.
    return list(dict.fromkeys(
        u for u in urls if u.startswith(("http://", "https://"))
    ))


def save_image(session, image_url, page_url, output_stem):
    response = session.get(
        image_url,
        headers={
            "Referer": page_url,
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        },
        timeout=45,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if not content_type.startswith("image/"):
        raise ValueError(
            f"Image URL returned {content_type or 'an unknown content type'}"
        )

    extension = Path(urlparse(image_url).path).suffix.lower()
    if extension not in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"):
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tif",
            "image/webp": ".webp",
        }.get(content_type.split(";")[0], ".img")

    destination = output_stem.with_suffix(extension)
    destination.write_bytes(response.content)
    return destination, len(response.content)


def main():
    parser = argparse.ArgumentParser(
        description="Download NLI parish-register images."
    )
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=45)
    parser.add_argument("--out", default="tawnawilly_nli_images")
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    if args.start < 1 or args.end < args.start:
        parser.error("Use a positive image range with --end >= --start")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    downloaded = failed = 0

    for number in range(args.start, args.end + 1):
        page_url = BASE_PAGE.format(number)
        stem = out_dir / f"vtls000631954_{number:03d}"
        print(f"[{number:03d}] {page_url}")

        try:
            page = session.get(page_url, timeout=45)
            if page.status_code == 403:
                raise PermissionError(
                    "NLI returned HTTP 403 Forbidden for automated access."
                )
            page.raise_for_status()

            candidates = find_image_urls(page.text, page_url)
            # Try URLs that look most like the register scan first.
            candidates.sort(key=lambda u: (
                0 if "vtls000631954" in u.lower() else 1,
                0 if any(x in u.lower() for x in ("iiif", "image")) else 1,
            ))

            last_error = None
            for image_url in candidates:
                try:
                    saved, size = save_image(
                        session, image_url, page_url, stem
                    )
                    print(f"    Saved {saved} ({size:,} bytes)")
                    downloaded += 1
                    break
                except Exception as exc:
                    last_error = exc
            else:
                debug_file = out_dir / f"vtls000631954_{number:03d}_page.html"
                debug_file.write_text(page.text, encoding="utf-8")
                raise RuntimeError(
                    f"No image could be downloaded. HTML saved to {debug_file}. "
                    f"Last candidate error: {last_error}"
                )

        except Exception as exc:
            failed += 1
            print(f"    FAILED: {exc}", file=sys.stderr)

        time.sleep(max(0, args.delay))

    print(f"\\nFinished: {downloaded} downloaded, {failed} failed.")
    print(f"Files are in: {out_dir.resolve()}")
    if failed:
        print(
            "If the error is HTTP 403, the NLI is refusing automated access; "
            "the script does not attempt to bypass that restriction."
        )


if __name__ == "__main__":
    main()
