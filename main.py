try:
    import json

    import os
    import logging
    import sys

    # PUBLIC_HTML_PATH="/nfs/bronfs/uwfs/dw00/d95/stevengs"
    # FLASK_PATH = "cse512/flaskenv/lib/python3.6/site-packages"

    # sys.path.append(os.path.join(PUBLIC_HTML_PATH, FLASK_PATH))

    from flask import Flask, request, redirect, g, render_template, send_from_directory
    import requests
    from urllib.parse import quote
    import auth, api_call
    import shutil

except ImportError as e:
    logging.error("Error importing modules!\n" + e)

# Authentication Steps, paramaters, and responses are defined at https://developer.spotify.com/web-api/authorization-guide/
# Visit this url to see all the steps, parameters, and expected response.

app = Flask(__name__)

if os.getenv("BASE_URL") is None:
    BASE_URL = "http://students.washington.edu/stevengs/cse512"
    PORT = None
else:
    BASE_URL = os.getenv("BASE_URL")
    PORT = os.getenv("APP_PORT")

VIZ_PAGE = "/viz"

if PORT:
    CALLBACK_URL = "{}:{}{}".format(BASE_URL, PORT, VIZ_PAGE)
else:
    CALLBACK_URL = "{}{}".format(BASE_URL, VIZ_PAGE)

CLIENT_ID, CLIENT_SECRET = auth.get_id_and_secret()

SCOPES = " ".join(["playlist-read-private", 
                   "playlist-read-collaborative",
                   "user-library-read",
                   "user-read-recently-played",
                   "user-top-read"])

logging.basicConfig(level=logging.DEBUG)

if not os.path.exists("/tmp/data/data_genres_average_features.json"):
    os.makedirs("/tmp/data")
    shutil.copyfile("data/data_genres_average_features.json", "/tmp/data/data_genres_average_features.json")

@app.errorhandler(500)
def internal_error(error):
    logging.error(error)
    return "500 error"

@app.route("/")
def index():
    auth_url = auth.get_redirect_url(CLIENT_ID, SCOPES, CALLBACK_URL)
    logging.info("Redirecting user to {}".format(auth_url))

    return redirect(auth_url)

@app.route("/viz")
def callback():
    logging.info("User redirected to viz page...")
    # Get access token etc from the call back information
    access_token, refresh_token, token_type, expires_in = auth.get_token(request, CLIENT_ID, CLIENT_SECRET, CALLBACK_URL) 
    # Create a spotipy session for scraping data
    spotipy_session = auth.create_spotipy_client_session(CLIENT_ID, CLIENT_SECRET)

    profile_data = api_call.get_profile_data(access_token)
    user_id = profile_data['id']

    logging.info("Scraping user data for {}...".format(user_id))
    # Scrape all of the relevant data for this user
    scrape = api_call.scrape_data(access_token, spotipy_session, user_id)    

    # Combine profile and playlist data to display
    profile_data = scrape["profile"]
    # playlist_data = scrape["playlists"]

    # Save their token for later
    # open("tokens.txt", "a").write("{}\t{}\n".format(profile_data['id'], access_token))

    # display_arr = [profile_data] + playlist_data

    user_basename = "static/data/{}".format(profile_data['id'])
    
    if PORT:
        base_url = BASE_URL + ":" + PORT
    else:
        base_url = BASE_URL

    return render_template("viz.html", user_id=profile_data['id'], base_url=base_url)
    # return render_template("index.html", sorted_array=display_arr)

@app.route('/data/<path:filepath>')
def data(filepath):
    # print(filepath)
    return send_from_directory('/tmp/data', filepath)

if __name__ == "__main__":
    app.run(debug=True, port=PORT)
