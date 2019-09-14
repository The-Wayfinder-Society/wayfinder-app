from flask import Flask, request, redirect, render_template, url_for, send_from_directory
import requests
from urllib.parse import quote
import json
import datetime
import os
import logging

import auth, api_call

from scrape_db import scrape_profile

app = Flask(__name__)

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
    print("CLIENT_ID environment variable must be set!")
    exit()

try:
    CLIENT_SECRET = os.environ["CLIENT_SECRET"]
except:
    print("CLIENT_SECRET environment variable must be set!")
    exit()

try:
    APP_URL = os.environ["APP_URL"]
    CALLBACK_URL = APP_URL + "/callback"
except:
    print("APP_URL environment variable must be set!")
    exit()

# Checks if the user has cookies set
# Redirects to login page if not
# Refreshes access token if it has expired
def check_cookies():
    user_auth_token = request.cookies.get("SpotifyVizAccessToken")
    user_refresh_token = request.cookies.get("SpotifyVizRefreshToken")

    print("Auth Token:", user_auth_token)
    print("Refresh Token:", user_refresh_token)

    if user_auth_token:
        return None
    else:
        if user_refresh_token:
            response = redirect(url_for("refresh") + "?code=" + user_refresh_token)
            return response
        else:
            response = redirect(url_for("login"))
            return response

# The home page
# Return a welcome page!
@app.route("/")
def index():
    response = check_cookies()
    if response:
        return response
    else:
        return "Welcome to our viz. Click here: <a href=" + url_for("viz") + ">" + url_for("viz") + "</a>"

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
    
    print(params)

    # use quote to escape out bad URL characters
    query_args = []
    for key, value in params.items():
        query_args.append(f"{key}={quote(value)}")

    query = "&".join(query_args)

    url = f"{authorize_endpoint}/?{query}"
    print(f"redirecting to: {url}")
    return redirect(url)

# 2) Once the user has verified we can access their account, get an API token (access_token) unique to the user
#    that lets us make API calls on their behalf
# Callback for Spotify authorization
# Stores user authorization token as cookie in user browser
@app.route("/callback")
def callback():
    # The authorization code from Spotify should be passed as ?code=AQD...X10
    # this authorization code can be exchanged for an access token to the user's data
    authorization_code = request.args['code']

    # make a POST request to the access token endpoint
    # request requires body parameters
    # grant_type = "authorization_code"
    # code = the authorization code
    # redirect_uri = the redirect uri, for validation only, does not redirect
    # and requires headers
    # Authorization: Basic *<base64 encoded client_id:client_secret>*
    # An alternative way to send the client id and secret is as request parameters (client_id and client_secret) in the POST body
    access_token_endpoint = "https://accounts.spotify.com/api/token"

    parameters = { 
                    "grant_type" : "authorization_code", 
                    "code" : authorization_code,
                    "redirect_uri" : CALLBACK_URL,
                    "client_id" : CLIENT_ID,
                    "client_secret" : CLIENT_SECRET,
                }

    token_post_response = requests.post(access_token_endpoint, data=parameters)
    # If the POST response is okay, we expect the following data to be returned in a JSON object
    # access_token	string	An access token that can be provided in subsequent calls, for example to Spotify Web API services.
    # token_type	string	How the access token may be used: always “Bearer”.
    # scope	string	A space-separated list of scopes which have been granted for this access_token
    # expires_in	int	The time period (in seconds) for which the access token is valid.
    # refresh_token	string	A token that can be sent to the Spotify Accounts service in place of an authorization code. (When the access code expires, send a POST request to the Accounts service /api/token endpoint, but use this code in place of an authorization code. A new access token will be returned. A new refresh token might be returned too.)
    token_data = token_post_response.json()

    if token_post_response.status_code == requests.codes.ok:
        access_token = token_data['access_token']
        token_type = token_data['token_type']
        scope = token_data['scope']
        expires_in = token_data['expires_in']
        refresh_token = token_data['refresh_token']

        print(json.dumps(token_data, indent=2))

        response = redirect(url_for("viz"))
        expiration_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        print("Callback Auth Token:", access_token)
        print("Callback Refresh Token:", refresh_token)

        response.set_cookie("SpotifyVizAccessToken", access_token, max_age=expires_in, expires=expiration_date)
        response.set_cookie("SpotifyVizRefreshToken", refresh_token)

        return response
    else:
        raise Exception("Got response code:", token_post_response.status_code, 
                        "Error:", token_data['error'], 
                        "Error Description:", token_data['error_description'])

# 3) If the API token (access_token) has expired, use a refresh token (refresh_token) which
#    exists indefinitely and is unique to the user to ask for a new API token
# The code flow here is similar to /callback, except the POST request parameters are different
# we provide "refresh_token" instead of "code"
@app.route("/refresh")
def refresh():
    refresh_token = request.args['code']
    access_token_endpoint = "https://accounts.spotify.com/api/token"

    parameters = { 
                    "grant_type" : "refresh_token", 
                    "refresh_token" : refresh_token,
                    "client_id" : CLIENT_ID,
                    "client_secret" : CLIENT_SECRET,
                }
    
    token_post_response = requests.post(access_token_endpoint, data=parameters)
    token_data = token_post_response.json()

    if token_post_response.status_code == requests.codes.ok:
        access_token = token_data['access_token']
        token_type = token_data['token_type']
        scope = token_data['scope']
        expires_in = token_data['expires_in']
        # a new refresh_token may be passed, update if we get one back from Spotify
        try:
            refresh_token = token_data['refresh_token']
        except:
            pass
        
        print(json.dumps(token_data, indent=2))

        response = redirect(url_for("viz"))
        expiration_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        print("Callback Auth Token:", access_token)
        print("Callback Refresh Token:", refresh_token)

        response.set_cookie("SpotifyVizAccessToken", access_token, max_age=expires_in, expires=expiration_date)
        response.set_cookie("SpotifyVizRefreshToken", refresh_token)

        return response
    else:
        raise Exception("Got response code:", token_post_response.status_code, 
                        "Error:", token_data['error'], 
                        "Error Description:", token_data['error_description'])

# Displays the visualization
@app.route("/viz")
def viz():
    response = check_cookies()
    if response:
        return response
    else:
        spotipy_session = auth.create_spotipy_client_session(CLIENT_ID, CLIENT_SECRET)

        user_auth_token = request.cookies.get("SpotifyVizAccessToken")
        
        profile_data = api_call.get_profile_data(user_auth_token)
        user_id = profile_data['id']

        logging.info("Scraping user data for {}...".format(user_id))
        # Scrape all of the relevant data for this user
        scrape = api_call.scrape_data(user_auth_token, spotipy_session, user_id)    

        # Combine profile and playlist data to display
        profile_data = scrape["profile"]

        user_basename = "static/data/{}".format(profile_data['id'])
        
        return render_template("viz.html", user_id=profile_data['id'], base_url=APP_URL)

@app.route("/read-db")
def read_db():
    user = request.args['user']
    from db import DataBase
    db = DataBase("Wayfinder")
    return json.dumps(db.get(user), default=str)

@app.route("/viz-2")
def viz_2():
    response = check_cookies()
    if response:
        return response
    else:
        import boto3

        user_auth_token = request.cookies.get("SpotifyVizAccessToken")

        client = boto3.client('lambda')

        function_name = "scrape_db"
        invocation_type = "Event"
        payload = json.dumps({ "token" : user_auth_token })

        response = client.invoke(
                FunctionName=function_name,
                InvocationType=invocation_type,
                Payload=payload,
            )

        if not response['StatusCode'] == 202:
            raise Exception(f"Lambda invoke failed with payload: {payload}. Response received:\n{response}")
        
        user_id = scrape_profile(user_auth_token)['id']

        return """
                <html>
                    <body>
                        <p>
                        Check console.
                        </p>
                        <p id="status">
                        Status.
                        </p>
                        <script>
                            poll_db = function() {
                                fetch('/read-db?user=""" + user_id + """')
                                .then(function(response) { 
                                    return response.json();
                                }).then(function(json_data) {
                                    console.log(json_data);
                                    document.getElementById("status").innerHTML = json_data["message"];
                                    console.log(json_data["message"]);
                                    if (json_data["message"] === "Done") {
                                        clearInterval(interval);
                                    }
                                });
                            }
                            interval = setInterval(poll_db, 1000)
                        </script>
                    </body>
                </html>
                """


@app.route('/data/<path:filepath>')
def data(filepath):
    # print(filepath)
    return send_from_directory('/tmp/data', filepath)
