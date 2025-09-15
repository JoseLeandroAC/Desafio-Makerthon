import os
import requests


API_KEY = "OUTmMmgnd1NZh3QIDYvqAZvD3Rv4cJjS"
API_SECRET = "TTvZC61AT3b71riYHtspWvU7CrYaNo7k"
FACESET_ID = "ChamadaAlunos"

url = "https://api-us.faceplusplus.com/facepp/v3/faceset/removeface"

params = {
    "api_key": API_KEY,
    "api_secret": API_SECRET,
    "outer_id": FACESET_ID,
    "face_tokens": "RemoveAllFaceTokens"  # remove todos os rostos
}


response = requests.post(url, data=params).json()
print(response)