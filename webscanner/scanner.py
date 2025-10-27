import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY')
genai_api_key = os.environ.get('GEMINI_API_KEY')

mycookies = None
def fetch_js_page(url):
    api_url = "https://app.scrapingbee.com/api/v1/"
    params = {
        "api_key": SCRAPINGBEE_API_KEY,
        "url": url,
        "render_js": "true"  # crucial for JS-heavy pages
    }
    try:
        r = requests.get(api_url, params=params)
        mycookies = r.cookies
        print(r.cookies)
        r.raise_for_status()
        return r.text, None  # return (html, error)
    except Exception as e:
        return None, str(e)
    
def get_cookies():
    return mycookies;

def find_privacy_link(soup, base_url):
    """
    Attempt to find privacy/cookie policy link.
    Works better for JS-heavy modern sites.
    """
    patterns = ["privacy", "privacy policy", "privacy-policy", "cookie", "terms"]

    if soup:
    # 1. Search all <a> tags
        for a in soup.find_all("a", href=True):
            text = (a.get_text(" ", strip=True) or "").lower()
            href = a["href"]
            if any(p in text for p in patterns) or any(p in href.lower() for p in patterns):
                return urljoin(base_url, href)

        # 2. Search <button> tags (some sites use modals)
        for b in soup.find_all("button"):
            text = (b.get_text(" ", strip=True) or "").lower()
            if any(p in text for p in patterns):
                # No href, return base URL (modal link)
                return base_url

        # 3. Search footer text for any <a> or text containing patterns
        footer = soup.find("footer")
        if footer:
            for tag in footer.find_all(["a", "button"]):
                text = (tag.get_text(" ", strip=True) or "").lower()
                href = tag.get("href", "")
                if any(p in text for p in patterns) or any(p in href.lower() for p in patterns):
                    return urljoin(base_url, href or "")

        # 4. Search entire body text for links containing "privacy"
        for a in soup.find_all("a", href=True):
            if "privacy" in a["href"].lower():
                return urljoin(base_url, a["href"])
    else:
        return {"Failed to find privacy link"}

def extract_privacy_text(soup):
    main = soup.find(["article", "main"]) or soup.body
    return main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)


def find_hidden_forms(soup):
    hidden_forms = []
    for form in soup.find_all("form"):
        hidden_inputs = []
        for inp in form.find_all("input", {"type": "hidden"}):
            hidden_inputs.append({"name": inp.get("name"), "value": inp.get("value")})
        if hidden_inputs:
            hidden_forms.append({"action": form.get("action"), "method": form.get("method", "get"), "hidden_inputs": hidden_inputs})
    return hidden_forms


def generate_ai_summarizer(data):
    API_KEY = genai_api_key
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

    contents=f"""You are an AI assistant that performs two tasks:
                1.Summarization: Provide a concise, factual, and neutral summary of the provided text. 
                Focus in key points, important details, and overall context
                2.Risk scoring: Analyze the summarized content and assign risk score from 1(Very Low Risk) to 5(Very High Risk)
                When assessing risk, consider factors such as:
                1. severity of potential negative outcomes
                2. Likelihood of occurrence
                3. Level of uncertainty
                4. Possible impact on people, finances, operations, or reputation
                
                Text to analyze is: {data}
                
                Output format example:
                    {{
                    "summary": "Concise summary here...",
                    "risk_score": 2
                    }}
        """
    headers = {
        "x-goog-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": contents}
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        res = response.json()
                
        # Step 1: Extract the text from the first candidate
        raw_text = res['candidates'][0]['content']['parts'][0]['text']

        # Step 2: Remove the ```json ... ``` code block markers
        clean_text = raw_text.strip('`').replace('json\n', '')

        # Step 3: Parse it as JSON
        data = json.loads(clean_text)

        # Step 4: Access the fields
        summary = data['summary']
        risk_score = data['risk_score']

        print("Summary:", summary)
        print("Risk Score:", risk_score)
        return {"summary": summary, "risk_score":risk_score}
    else:
        print("Error:", response.status_code, response.text)
        return {"status_code": response.status_code, "error": response.text}
    
