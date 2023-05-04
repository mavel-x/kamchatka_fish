from datetime import datetime, timedelta
from pprint import pprint

import requests
from environs import Env


def get_access_token(client_id, client_secret):
    access_url = 'https://api.moltin.com/oauth/access_token'
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
    }
    response = requests.post(access_url, data=data)
    response.raise_for_status()
    return response.json()['access_token']


def ep_token_generator():
    env = Env()
    env.read_env()
    ep_client_id = env.str('EP_CLIENT_ID')
    ep_client_secret = env.str('EP_SECRET')
    token = None
    generated_at = None
    while True:
        if token is None or datetime.now() - generated_at >= timedelta(hours=1):
            token = get_access_token(ep_client_id, ep_client_secret)
            generated_at = datetime.now()
        yield token


def get_products(access_token):
    products_url = 'https://api.moltin.com/pcm/products'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(products_url, headers=headers)
    response.raise_for_status()
    products_raw = response.json()
    return products_raw['data']


def get_cart_items(access_token, customer_id):
    url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def add_item(access_token, customer_id):
    url = f'https://api.moltin.com/v2/carts/{customer_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'data': {
            'sku': 1001,
            'type': 'cart_item',
            'quantity': 1
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
