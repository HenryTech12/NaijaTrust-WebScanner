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
                
                print(data.get('privacy_text'))

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

"""
def extract_privacy_link(soup):
    KEYWORDS = ['privacy','policy','data','gdpr']
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        text = link.get_text(strip=True).lower()
        if any(word in href or word in text for word in KEYWORDS):
            return urljoin(link['href'])
"""
# ✅ 5. AI summarization & risk scoring using Gemini API
async def generate_ai_summarizer(data: str):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": GENAI_API_KEY,
        "Content-Type": "application/json"
    }

    output_format = """
                {
                    "summary": "<short summary>",
                    "risk_score": "1-2 | 3 | 4-5",
                    "data_collected": ["email", "cookies", "browsing_data", "location", ...]
                }
    """
    prompt = """
                You are a privacy text and data protection expert.
                Analyze the following website privacy policy text and return:
                1. A short, clear summary in plain English(Not more than 5 sentences) make sure the summary is natural and user-friendly telling the user about the website safety.
                2. A "risk score" range from 1 to 5 that shows how risky the website's data collection practices are.
                3. A list of detected data types collected(e.g email, cookies, location, browsing data).
                
                Classify risk score as:
                "1-2" - collects minimal data, transparent usage, allow user control.
                "3" - collects some personal data, shares with third parties, unclear retention period.
                "4-5" - collects excessive or sensitive data, vague terms, unclear sharing, or lacks consent mechanisms.
                
                Return the ouput in this json format:
                {output_format}
                
                Here is the privacy policy text to analyze:
                {data}
            """.format(output_format=output_format,data=data)
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

