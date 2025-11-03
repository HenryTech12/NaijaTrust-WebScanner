import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from lxml import html
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")

# Globals
mycookies = []
hidden_forms = []


# ✅ 1. Fetch JS-rendered page asynchronously
async def fetch_js_page(url: str):
    api_url = "https://app.scrapingbee.com/api/v1/"
    params = {
        "api_key": SCRAPINGBEE_API_KEY,
        "url": url,
        "render_js": "true",
        "json_response": "true",
        "wait_browser": "networkidle2",
        "block_ads": "true"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as resp:
                if resp.status != 200:
                    return None, f"Error {resp.status}: {await resp.text()}"

                data = await resp.json()
                html_content = data.get("body", "")

                # Parse the HTML
                tree = html.fromstring(html_content)
                fields = tree.xpath('//input[@type="hidden"]/@name')
                hidden_forms.append(fields)

                cookies = resp.headers.get("set-cookie")
                mycookies.append(cookies)

                return html_content, None

    except Exception as e:
        return None, str(e)


# ✅ 2. Extract cookies and hidden fields
def get_cookies():
    return mycookies


def find_hidden_forms():
    return hidden_forms


# ✅ 3. Find privacy / cookie / terms link
def find_privacy_link(soup, base_url):
    patterns = ["privacy", "privacy policy", "privacy-policy", "cookie", "terms"]

    if not soup:
        return {"error": "Soup object is None"}

    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) or "").lower()
        href = a["href"].lower()
        if any(p in text for p in patterns) or any(p in href for p in patterns):
            return urljoin(base_url, a["href"])

    for b in soup.find_all("button"):
        text = (b.get_text(" ", strip=True) or "").lower()
        if any(p in text for p in patterns):
            return base_url

    footer = soup.find("footer")
    if footer:
        for tag in footer.find_all(["a", "button"], href=True):
            text = (tag.get_text(" ", strip=True) or "").lower()
            href = tag.get("href", "")
            if any(p in text for p in patterns) or any(p in href.lower() for p in patterns):
                return urljoin(base_url, href or "")

    for a in soup.find_all("a", href=True):
        if "privacy" in a["href"].lower():
            return urljoin(base_url, a["href"])

    return None


# ✅ 4. Extract visible page text
def extract_privacy_text(soup):
    if not soup:
        return ""
    main = soup.find(["article", "main"]) or soup.body
    return main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)


# ✅ 5. AI summarization & risk scoring using Gemini API
async def generate_ai_summarizer(data: str):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": GENAI_API_KEY,
        "Content-Type": "application/json"
    }

    prompt = f"""
You are an AI assistant that performs two tasks:
1. Summarization: Provide a natural, simple telling user why it is safe or not summary of the site using the provided text.
2. Risk Scoring: Assign a risk score from 1 (Very Low Risk) to 5 (Very High Risk)
   based on severity, likelihood, uncertainty, and impact on people or reputation.

Make the summary simple and easy for anyone to understand.

Text to analyze:
{data}

Output JSON Example:
{{
    "summary": "Concise, easy-to-understand summary.",
    "risk_score": 2
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                err = await response.text()
                return {"status_code": response.status, "error": err}

            res = await response.json()
            raw_text = res["candidates"][0]["content"]["parts"][0]["text"]

            # Clean JSON-like output
            clean_text = raw_text.strip("`").replace("json\n", "")
            try:
                parsed = json.loads(clean_text)
                return parsed
            except json.JSONDecodeError:
                return {"summary": raw_text, "risk_score": "N/A"}

