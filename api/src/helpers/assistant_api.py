import requests

# Helper to fetch vector_db from Assistant API

def fetch_vector_db(base_url, assistant_endpoint, assistant_product_key, assistant_id, token):
    url = f"{base_url}{assistant_endpoint}/{assistant_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'api-key': assistant_product_key,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), dict):
            return data['data'].get('vectorTable')
    return None
