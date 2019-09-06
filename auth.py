import os
import sys
import logging

import requests
from urllib.parse import quote
import json

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

def get_id_and_secret():
    try:
        secret_data = json.loads(open("secret.txt", "r").read())
    except Exception as e:
        logging.error("Failed to get client id and secret.\n" + e)
    
    return secret_data['CLIENT_ID'], secret_data['CLIENT_SECRET']

def get_redirect_url(client_id, scope, callback_url):
    try:
        SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
        auth_query_parameters = {
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": scope,
            # "state": STATE,
            # "show_dialog": SHOW_DIALOG_str,
            "client_id": client_id
        }
        url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query_parameters.items()])
        auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
    except Exception as e:
        logging.error("Failed to construct redirect url.\n" + e)

    return auth_url
    
def get_token(request, client_id, client_secret, callback_url):
    try:
        auth_token = request.args['code']
        # return auth_token, None, None, None
        SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
        code_payload = {
            "grant_type": "authorization_code",
            "code": str(auth_token),
            "redirect_uri": callback_url,
            'client_id': client_id,
            'client_secret': client_secret,
        }
        post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload)
    except Exception as e:
        logging.error("Failed to request token from Spotify.\n" + e)

    response_data = post_request.json()
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]

    return access_token, refresh_token, token_type, expires_in

def create_spotipy_client_session(client_id, client_secret):
    try:
        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        spotipy_session = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    except Exception as e:
        logging.error("Failed to create Spotipy session.\n" + e)
    
    return spotipy_session