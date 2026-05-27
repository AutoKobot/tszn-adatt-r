import urllib.request
import json

try:
    url = "http://127.0.0.1:8000/schools/public"
    print(f"Querying local API: {url} ...")
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("API Response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print("Failed to query API:", e)
