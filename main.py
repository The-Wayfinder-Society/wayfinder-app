from flask import Flask, request, redirect, render_template, url_for, send_from_directory, session
import requests
from urllib.parse import quote
import json
import datetime
import os
import logging
from pprint import pprint

import auth, api_call

app = Flask(__name__)
app.secret_key = b"dfsdfa"

logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger("")

# the scope of access we are requesting from the user
# we ask to read all playlists, library songs, recently played, and top artists / tracks
# https://developer.spotify.com/documentation/general/guides/authorization-guide/#list-of-scopes
SCOPES = " ".join(["playlist-read-private", 
                   "playlist-read-collaborative",
                   "user-library-read",
                   "user-read-recently-played",
                   "user-top-read"])

# check for environment variables
# CLIENT_ID should be the Spotify API client id
# CLIENT_SECRET should be the Spotify API client secret
# APP_URL should be the URL that the app is hosted at (including port) 
#    e.g. for development: http://127.0.0.1:5000 
#         and for deployment: http://www.musicalwayfinder.com
try:
    CLIENT_ID = os.environ["CLIENT_ID"]
except:
    logger.error("CLIENT_ID environment variable must be set!")
    exit()

try:
    CLIENT_SECRET = os.environ["CLIENT_SECRET"]
except:
    logger.error("CLIENT_SECRET environment variable must be set!")
    exit()

try:
    APP_URL = os.environ["APP_URL"]    
except:
    logger.error("APP_URL environment variable must be set!")
    exit()

try:
    PORT = os.environ["PORT"]
except:
    logger.warning("PORT environment variable not set, continuing without it set.")
    PORT = None

APP_URL = APP_URL

if PORT:
    CALLBACK_URL = APP_URL + ":" + PORT + "/callback"
else:
    CALLBACK_URL = APP_URL + "/callback"

def construct_query(params):
    # use quote to escape out bad URL characters
    query_args = []
    for key, value in params.items():
        query_args.append(f"{key}={quote(value)}")

    query = "&".join(query_args)
    return query

# Checks that the user has logged in by checking if
# we have API access to their account by looking at
# browser cookies
# Returns no response if we have API access
# Redirects to /login if no API access
# Redirects to /refresh if API access has expired
# Each redirect should land the user back at the url passed with return_page
def check_logged_in(return_page):
    user_auth_token = request.cookies.get("SpotifyUserAccessToken")
    user_refresh_token = request.cookies.get("SpotifyUserRefreshToken")

    if user_auth_token:
        return None
    else:
        if user_refresh_token:
            query = construct_query(
                {
                    "code" : user_refresh_token,
                    "next" : return_page
                }
            )
            response = redirect(url_for("refresh") + "?" + query)
            return response
        else:
            query = construct_query(
                {
                    "next" : return_page
                }
            )
            response = redirect(url_for("login") + "?" + query)
            return response

# The home page
# Return a welcome page!
@app.route("/")
def index():
    if 'profile_data' in session:
        profile_data = session['profile_data']

        # get the user's name from their profile data
        user_id = profile_data['id']
        display_name = profile_data['display_name']
        # we prefer to use the user's display name, but some don't
        # have one set, so we'll default back on their id
        if display_name:
            name = display_name
        else:
            name = user_id
    else:
        name = "User"

    return render_template("index.html", name=name, redirect=url_for("viz"))

# Login routine
# 1) Redirect user to Spotify for authorization
# Redirects user to Spotify, which then sends the user to /callback with a code that verifies
# the user gave our application permission to access the account
# https://developer.spotify.com/documentation/general/guides/authorization-guide/
@app.route("/login")
def login():
    authorize_endpoint = "https://accounts.spotify.com/authorize"
    params = {
        "client_id" : CLIENT_ID,
        "response_type" : "code", 
        "redirect_uri" : CALLBACK_URL,
        # state is useful for verifying that the callback came from the same browser
        # so can't spoof callback
        # "state" : 
        # A space separated list of [scopes](https://developer.spotify.com/documentation/general/guides/authorization-guide/#list-of-scopes)
        "scope" : SCOPES,
        # If true, the user will not be automatically redirected and will have to approve the app again.
        "show_dialog" : "false"
    }
    
    logger.info(params)
    query = construct_query(params)

    url = f"{authorize_endpoint}/?{query}"
    logger.info(f"redirecting to: {url}")
    return redirect(url)

def get_access_and_refresh_token(grant_type, code):
    # make a POST request to the access token endpoint
    access_token_endpoint = "https://accounts.spotify.com/api/token"
    # request requires body parameters
    # grant_type = "authorization_code"
    # and requires headers
    # Authorization: Basic *<base64 encoded client_id:client_secret>*
    # An alternative way to send the client id and secret is as request parameters (client_id and client_secret) in the POST body
    parameters = {
        "client_id" : CLIENT_ID,
        "client_secret" : CLIENT_SECRET,
        "grant_type" : grant_type, 
    }

    if grant_type == "authorization_code":
        # code = the authorization code
        # redirect_uri = the redirect uri, for validation only, does not redirect
        parameters.update(
            {
                "redirect_uri" : CALLBACK_URL,
                "code" : code,
            }
        )
    elif grant_type == "refresh_token":
        parameters.update(
            {
                "refresh_token" : code,
            }
        )
    else:
        raise Exception

    token_post_response = requests.post(access_token_endpoint, data=parameters)
    # If the POST response is okay, we expect the following data to be returned in a JSON object
    # access_token	string	An access token that can be provided in subsequent calls, for example to Spotify Web API services.
    # token_type	string	How the access token may be used: always “Bearer”.
    # scope	string	A space-separated list of scopes which have been granted for this access_token
    # expires_in	int	The time period (in seconds) for which the access token is valid.
    # refresh_token	string	A token that can be sent to the Spotify Accounts service in place of an authorization code. (When the access code expires, send a POST request to the Accounts service /api/token endpoint, but use this code in place of an authorization code. A new access token will be returned. A new refresh token might be returned too.)
    token_data = token_post_response.json()

    if token_post_response.status_code == requests.codes.ok:
        access_token = token_data.get('access_token', None)
        token_type = token_data.get('token_type', None)
        scope = token_data.get('scope', None)
        expires_in = token_data.get('expires_in', None)
        refresh_token = token_data.get('refresh_token', None)

        # a refresh token won't be returned if we are requesting a new access token
        # using a refresh token (code)
        # so just return the one that was passed to this function
        if refresh_token is None:
            refresh_token = code

        expiration_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        return access_token, refresh_token, expires_in, expiration_date
    else:
        raise Exception("Got response code:", token_post_response.status_code, 
                        "Error:", token_data['error'], 
                        "Error Description:", token_data['error_description'])

# 2) Once the user has verified we can access their account, get an API token (access_token) unique to the user
#    that lets us make API calls on their behalf
# Callback for Spotify authorization
# Stores user authorization token as cookie in user browser
@app.route("/callback")
def callback():
    # The authorization code from Spotify should be passed as ?code=AQD...X10
    # this authorization code can be exchanged for an access token to the user's data
    try:
        authorization_code = request.args['code']
    except:
        return redirect(url_for("login"))

    try:
        next_page = request.args['next']
    except:
        next_page = url_for("index")

    access_token, refresh_token, expires_in, expiration_date = (
        get_access_and_refresh_token("authorization_code", authorization_code)
    )
    response = redirect(next_page)

    response.set_cookie("SpotifyUserAccessToken", access_token, max_age=expires_in, expires=expiration_date)
    response.set_cookie("SpotifyUserRefreshToken", refresh_token)
    
    return response

# 3) If the API token (access_token) has expired, use a refresh token (refresh_token) which
#    exists indefinitely and is unique to the user to ask for a new API token
@app.route("/refresh")
def refresh():
    try:
        refresh_token = request.args['code']
    except:
        return redirect(url_for("login"))

    try:
        next_page = request.args['next']
    except:
        next_page = url_for("index")

    access_token, refresh_token, expires_in, expiration_date = (
        get_access_and_refresh_token("refresh_token", refresh_token)
    )
    response = redirect(next_page)

    response.set_cookie("SpotifyUserAccessToken", access_token, max_age=expires_in, expires=expiration_date)
    response.set_cookie("SpotifyUserRefreshToken", refresh_token)
    
    return response

# Displays the visualization
@app.route("/viz")
def viz():
    response = check_logged_in(url_for("viz"))
    if response:
        return response
    else:
        spotipy_session = auth.create_spotipy_client_session(CLIENT_ID, CLIENT_SECRET)

        user_auth_token = request.cookies.get("SpotifyUserAccessToken")
        
        profile_data = api_call.get_profile_data(user_auth_token)
        user_id = profile_data['id']

        logging.info("Scraping user data for {}...".format(user_id))
        # Scrape all of the relevant data for this user
        scrape = api_call.scrape_data(user_auth_token, spotipy_session, user_id)    

        # Combine profile and playlist data to display
        profile_data = scrape["profile"]

        user_basename = "static/data/{}".format(profile_data['id'])
        
        if PORT:
            base_url = APP_URL + ":" + PORT
        else:
            base_url = APP_URL

        return render_template("viz.html", user_id=profile_data['id'], base_url=base_url)

@app.route("/playlists")
def playlists():
    response = check_logged_in(url_for("playlists"))
    if response:
        return response
    else:
        user_auth_token = request.cookies.get("SpotifyUserAccessToken")
        profile_data = api_call.get_profile_data(user_auth_token)
        playlists = api_call.get_user_playlists(user_auth_token, profile_data['id'])
        pprint(playlists)
        return """
            {}
        """.format([p['name'] for p in playlists])

@app.route('/data/<path:filepath>')
def data(filepath):
    # print(filepath)
    return send_from_directory('/tmp/data', filepath)

if __name__ == "__main__":
    if PORT:
        app.run(debug=True, port=PORT)
    else:
        app.run(debug=True)
