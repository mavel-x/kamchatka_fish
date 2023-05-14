from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass
class ElasticPathToken:
    token: str = None
    expiration: int = 0
    
    @property
    def is_expired(self):
        return int(datetime.now().timestamp()) > self.expiration


class ElasticPathClient:
    def __init__(self, ep_client_id: str, ep_client_secret: str):
        self.client_id = ep_client_id
        self.client_secret = ep_client_secret
        self._token = ElasticPathToken()

    @property
    def token(self):
        if self._token.is_expired:
            self._refresh_token()
        return self._token.token
        
    def _refresh_token(self):
        access_url = 'https://api.moltin.com/oauth/access_token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        response = requests.post(access_url, data=data)
        response.raise_for_status()
        token_response = response.json()
        self._token = ElasticPathToken(
            token=token_response['access_token'],
            expiration=token_response['expires'],
        )

    def get_all_products(self):
        products_url = 'https://api.moltin.com/pcm/products'
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(products_url, headers=headers)
        response.raise_for_status()
        products_raw = response.json()
        return products_raw['data']

    def get_product(self, product_id):
        url = f'https://api.moltin.com/pcm/products/{product_id}'
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        product_raw = response.json()
        return product_raw['data']

    def _get_image_url(self, image_id):
        url = f'https://api.moltin.com/v2/files/{image_id}'
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['data']['link']['href']

    def get_product_image(self, product: dict):
        image_id = product['relationships']['main_image']['data']['id']
        try:
            image_url = self._get_image_url(image_id=image_id)
        except requests.exceptions.HTTPError:
            image_url = 'https://i.ytimg.com/vi/1I0BXMwwti4/maxresdefault.jpg'
        return image_url

    def get_cart_items(self, customer_id):
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
        headers = {
            'Authorization': f'Bearer {self.token}',
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def add_item_to_cart(self, customer_id, product_id, quantity):
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'data': {
                'id': product_id,
                'type': 'cart_item',
                'quantity': int(quantity)
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_cart_item(self, customer_id, product_id):
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items/{product_id}'
        headers = {
            'Authorization': f'Bearer {self.token}',
        }
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def create_customer(self, full_name, email):
        url = f'https://api.moltin.com/v2/customers'
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'data': {
                'type': 'customer',
                'name': full_name,
                'email': email,
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
