from dotenv import load_dotenv
import os
import requests

# Load environment variables from .env
load_dotenv()

url = os.getenv("QDRANT_URL") + "/collections"
headers = {"api-key": os.getenv("QDRANT_API_KEY")}
r = requests.get(url, headers=headers)
print(r.status_code, r.text)
