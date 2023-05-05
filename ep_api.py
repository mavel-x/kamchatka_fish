from datetime import datetime
from typing import Generator

import requests
from environs import Env


class ElasticPathClient:
    token_generator: Generator

    def __init__(self):
        env = Env()
        env.read_env()
        ep_client_id = env.str('EP_CLIENT_ID')
        ep_client_secret = env.str('EP_SECRET')
        self.token_generator = self._token_generator(ep_client_id, ep_client_secret)

    @staticmethod
    def _get_access_token(client_id, client_secret):
        access_url = 'https://api.moltin.com/oauth/access_token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        }
        response = requests.post(access_url, data=data)
        response.raise_for_status()
        return response.json()

    def _token_generator(self, ep_client_id, ep_client_secret):
        """Generates a new Elastic Path token and automatically refreshes it on expiration.
        """
        token = None
        expires_at = None
        while True:
            if token is None or datetime.now() > expires_at:
                token_response = self._get_access_token(ep_client_id, ep_client_secret)
                token = token_response['access_token']
                expires_at = datetime.fromtimestamp(token_response['expires'])
            yield token

    def get_all_products(self):
        access_token = next(self.token_generator)
        products_url = 'https://api.moltin.com/pcm/products'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(products_url, headers=headers)
        response.raise_for_status()
        products_raw = response.json()
        return products_raw['data']

    def get_product(self, product_id):
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/pcm/products/{product_id}'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        product_raw = response.json()
        return product_raw['data']

    def get_image_url(self, image_id):
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/v2/files/{image_id}'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['data']['link']['href']

    def get_cart_items(self, customer_id):
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def add_item_to_cart(self, customer_id, product_id, quantity):
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
        headers = {
            'Authorization': f'Bearer {access_token}',
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
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/v2/carts/{customer_id}/items/{product_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def create_customer(self, full_name, email):
        access_token = next(self.token_generator)
        url = f'https://api.moltin.com/v2/customers'
        headers = {
            'Authorization': f'Bearer {access_token}',
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
