from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from bs4 import BeautifulSoup
import ipaddress, socket, json, asyncio, requests, os
from urllib.parse import urlparse
from asgiref.sync import sync_to_async
from dotenv import load_dotenv
from asgiref.sync import async_to_sync

from .scanner import (  # import your async helper functions
    fetch_js_page,
    get_cookies,
    find_privacy_link,
    find_hidden_forms,
    extract_privacy_text,
    generate_ai_summarizer
)

load_dotenv()
safe_api_key = os.getenv("SAFE_API_KEY")


class APIScannerView(APIView):
    def post(self, request):
        try:
            data = request.data if isinstance(request.data, dict) else json.loads(request.body)
            url = data.get("url")
            print("🌐 URL received:", url)

            if not is_url_valid(url):
                return Response({"error": "Invalid URL"}, status=400)

            # Run async tasks in sync context
            result = async_to_sync(self._run_async_tasks)(url)
            return Response(result, status=200)

        except Exception as e:
            print("❌ Error:", e)
            return Response({"error": str(e)}, status=500)

    async def _run_async_tasks(self, url):
        html_task = fetch_js_page(url)
        safety_task = sync_to_async(is_safe_url)(url)

        html_result, safety_data = await asyncio.gather(html_task, safety_task)
        html_content, error = html_result if isinstance(html_result, tuple) else (html_result, None)

        if error:
            return {"error": error}

        soup = BeautifulSoup(html_content, "lxml")

        cookies = get_cookies()
        hidden_fields = find_hidden_forms()
        privacy_link = find_privacy_link(soup, url)
        privacy_text = extract_privacy_text(soup)

        data = {
            "url": url,
            "safe_check":safety_data,
            "hidden_fields":hidden_fields,
            "cookies": cookies,
            "privacy_link":privacy_link,
            "privacy_text": privacy_text[:3000]
        }
        ai_summary = await generate_ai_summarizer(data)

        return {
            "url": url,
            "safe_check": safety_data,
            "privacy_link": privacy_link,
            "hidden_fields": hidden_fields,
            "cookies": cookies,
            "summary": ai_summary.get("summary"),
            "risk_score": ai_summary.get("risk_score"),
        }

# ========================
# 🔒 HELPER FUNCTIONS
# ========================

def is_url_valid(url):
    validator = URLValidator()
    try:
        validator(url)
        return True
    except ValidationError:
        return False


def is_safe_url(url):
    """
    Google Safe Browsing API (sync call).
    """
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={safe_api_key}"
    body = {
        "client": {"clientId": "naijatrust", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    response = requests.post(url=endpoint, json=body)
    result = response.json()

    if result == {}:
        return {"url": url, "safe": True, "message": "The URL is flagged safe"}
    else:
        return {
            "url": url,
            "safe": False,
            "message": "The URL is flagged unsafe.",
            "threat_response": result,
        }


def is_private(hostname):
    try:
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback
    except Exception:
        return True
