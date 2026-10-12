"""Public box office table -> plain, typed records; no credentials required."""
import re

import requests
from bs4 import BeautifulSoup


class BoxOfficeService:
    SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_highest-grossing_films"
    MAX_BYTES = 3_000_000

    @staticmethod
    def parse(html):
        soup = BeautifulSoup(html, "html.parser")
        for unwanted in soup.select("sup, script, style, .sortkey"):
            unwanted.decompose()
        required = {"rank", "title", "worldwide gross", "year"}
        for table in soup.select("table"):
            rows = table.select("tr")
            if not rows:
                continue
            headers = [" ".join(cell.stripped_strings).lower() for cell in rows[0].find_all(["th", "td"], recursive=False)]
            if not required.issubset(headers):
                continue
            records = []
            for row in rows[1:]:
                cells = row.find_all(["td", "th"], recursive=False)
                values = {key: " ".join(cell.stripped_strings).replace("†", "").strip() for key, cell in zip(headers, cells)}
                title = values.get("title", "")
                if not title:
                    continue
                def number(key, pattern):
                    match = re.search(pattern, values.get(key, ""))
                    return int(match.group(0).replace(",", "")) if match else None
                records.append({
                    "title": title,
                    "rank": number("rank", r"\d+"),
                    "year": number("year", r"\b\d{4}\b"),
                    "worldwide_gross_usd": number("worldwide gross", r"\d[\d,]*"),
                    "source_url": BoxOfficeService.SOURCE_URL,
                })
            if records:
                return records
        raise ValueError("The expected box office table is missing or empty.")

    def _fetch(self):
        with requests.get(
            self.SOURCE_URL,
            headers={"User-Agent": "BetterBoxd/1.0 (educational movie catalog)", "Accept": "text/html"},
            timeout=(3.05, 10), allow_redirects=False, stream=True,
        ) as response:
            response.raise_for_status()
            if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Expected an HTML page.")
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > self.MAX_BYTES:
                    raise ValueError("Source page exceeded the size limit.")
        return self.parse(bytes(content))
