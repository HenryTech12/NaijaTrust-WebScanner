from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
import requests
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from bs4 import BeautifulSoup
import ipaddress, socket
from urllib.parse import urlparse
from .scanner import *
import os
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# Create your views here.
safe_api_key = os.environ.get('SAFE_API_KEY')


class APIScannerView(APIView):
    def post(self,request):
        try:
            url = request.data.get('url')
            print('url:', url)
            is_valid = is_url_valid(url)
            if is_valid:
                print(is_valid)
                safe_data = is_safe_url(url)
                print(safe_data)
            
                soup = extract_html(url)
                privacy_link = find_privacy_link(soup,url)
                privacy_text = extract_privacy_text(soup)
                hidden_forms = find_hidden_forms(soup)
                """
                js_page = fetch_js_page(url)
                """

                """
                print(privacy_link)
                print(privacy_text)
                print(hidden_forms)
                print(js_page)
                """
                
                
                
                body = {
                    "status":"success",
                    "code": 200,
                    "url" : url,
                    "is_valid": is_valid,
                    "safety": safe_data,
                    "privacy_link": privacy_link,
                    "privacy_text":privacy_text,
                    "hidden_fields": hidden_forms,
                    "cookies": get_cookies()
                }
                ai_analyzer = generate_ai_summarizer(body)
                body['ai_summary'] = ai_analyzer
                body = json.dumps(body,indent=2)
                print(ai_analyzer)
                return Response(body, status=200)
            else:
                return Response({"error":"Invalid URL", "is_valid":is_valid},status=500)
        except requests.ConnectionError:
            err_status = 500
            error = {
                "error": "check your internet connection",
                "status": err_status
            }
            return Response(error, status=err_status)
        except requests.RequestException:
            err_status = 500
            error = {
                "error": "your request timed out",
                "status": err_status
            }
            return Response(error, status=err_status)
        except Exception as e:
            err_status = 500
            error = {
                "error": "an error occurred!!",
                "status": err_status
            }
            print(str(e))
            return Response(error, status=err_status)

def is_url_valid(url):
    validator = URLValidator()
    try:
        validator(url)
        return True
    except ValidationError:
        return False
    
def is_safe_url(url):
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={safe_api_key}"
    body = {
        "client": {"clientId": "naijatrust", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    response = requests.post(url=endpoint,json=body)
    result = response.json()
    if result == {}:
        return {"url":url, "safe":True, "message":"The URL is flagged safe"}
    else:
        r_data = {"url":url, "safe":False,"message":"The URL is flagged unsafe.", "threat_response":result}
        return r_data
    
def extract_html(url):
    html, error = fetch_js_page(url)
    if html:
        soup = BeautifulSoup(html, "lxml")
        return soup
    else:
        return error
    
def is_private(hostname):
    try:
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback
    except Exception:
        return True
    