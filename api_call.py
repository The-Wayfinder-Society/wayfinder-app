import json

import os
import sys
import logging

import requests
from urllib.parse import quote

import spotipy
import utils

import subprocess
from glob import glob
import time

# Spotify URLS
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

user_profile_api_endpoint = "{}/me".format(SPOTIFY_API_URL)
user_tracks_endpoint = "{}/tracks".format(user_profile_api_endpoint)

recently_played_endpoint = "{}/player/recently-played".format(user_profile_api_endpoint)
top_tracks_endpoint = "{}/top/tracks".format(user_profile_api_endpoint)
top_artists_endpoint = "{}/top/artists".format(user_profile_api_endpoint)

def get(endpoint, token, max_retries=10, delay=4):
    authorization_header = {"Authorization": "Bearer {}".format(token)}
    try:
        response = requests.get(endpoint, headers=authorization_header)
    except requests.exceptions.ConnectionError as e:
        response = {}
        response.status_code = 429
        logging.warn("Could not fulfill GET.\n" + e)
    # If status is anything but OK, raise an error
    if response.status_code != 200:
        if response.status_code == 429:
            if max_retries > 0:
                # print("Hit rate limit! Sleeping for {} seconds before retrying...".format(delay))
                time.sleep(delay)
                return get(endpoint, token, max_retries=max_retries - 1, delay=delay + 1)
            else:
                msg = "Connection refused after {} retries".format(max_retries)
                logging.error(msg)
                raise RuntimeError(msg)
        logging.error(response.reason)
        raise RuntimeError(response.reason)
    
    return response	

def get_profile_data(token):
    user_profile_api_endpoint = "{}/me".format(SPOTIFY_API_URL)
    profile_response = get(user_profile_api_endpoint, token)
    profile_data = profile_response.json()

    return profile_data

def get_user_playlists(token, user_id):
    # print("Getting playlists for  {}".format(user_id))

    # Get user playlist data
    playlist_api_endpoint = "{}/users/{}/playlists".format(SPOTIFY_API_URL, user_id)
    
    playlists_response = get(playlist_api_endpoint, token)
    playlist_data = playlists_response.json()

    all_playlists = []
    all_playlists.append(playlist_data)

    while playlist_data['next']:
        playlists_response = get(playlist_data['next'], token)
        playlist_data = playlists_response.json()
        all_playlists.append(playlist_data)

    playlists = sum([playlist['items'] for playlist in all_playlists], [])

    return playlists

def scrape_library(token, spotipy_session, user_id, limit=50):
    # print("Scraping library of {}".format(user_id))
    assert(limit <= 50)

    # Scrape entire library
    library_data = get(user_tracks_endpoint + "?limit={}".format(limit), token).json()
    all_library_data = []
    all_library_data.append(library_data)    
    while library_data['next']:
        # print(library_data['next'])
        library_data = get(library_data['next'], token).json()
        all_library_data.append(library_data)
        
    # Aggregate all results
    user_tracks = sum([data['items'] for data in all_library_data], [])

    # Get information about each track
    # print("Featurizing tracks")
    track_names, track_uris, data = utils.featurize_tracks(user_tracks, spotipy_session, verbose=True)
    # print("Getting song genres")
    artist_names, artist_uris, genres = utils.get_song_genres(user_tracks, spotipy_session, verbose=True)
    dates = utils.get_dates_added(user_tracks)

    # Aggregate tracks into a single JSON object
    user_library_data = []
    num_tracks = len(user_tracks)
    for i in range(num_tracks):
        track_name = track_names[i]
        date_added = dates[i]
        track_uri = track_uris[i]
        track_features = data['features'][i]
        track_genres = genres[i]
        track_artists = artist_names[i]
        user_library_data.append({ 'name' : track_name,
                                'uri' : track_uri,
                                'date' : date_added,
                                'genres' : track_genres, 
                                'artists' : track_artists,
                                })
        for feature, feature_name in zip(track_features, data['feature_names']):
            user_library_data[-1][feature_name] = feature

    return user_library_data

def scrape_top_artists(token, spotipy_session, user_id, limit=50):
    # print("Getting top artists for {}".format(user_id))
    assert(limit <= 50)
    
    top_artists_data_all = {}
    time_ranges = ["short_term", "medium_term", "long_term"]
    for time_range in time_ranges:
        response = get(top_artists_endpoint + "?time_range={}&limit={}".format(time_range, limit), token)

        top_artists = response.json()
        
        names = [artist['name'] for artist in top_artists['items']]
        genres = [artist['genres'] for artist in top_artists['items']]
        popularities = [artist['popularity'] for artist in top_artists['items']]
        artist_uris = [artist['uri'] for artist in top_artists['items']]
        
        top_artists_data = []

        for i in range(len(top_artists['items'])):
            top_artists_data.append({ "name" : names[i],
                                    "genres" : genres[i],
                                    "popularity" : popularities[i],
                                    "uri" : artist_uris[i]
                                    })
        top_artists_data_all[time_range] = top_artists_data

    return top_artists_data_all

def scrape_top_songs(token, spotipy_session, user_id, limit=50):
    # print("Getting top songs for {}".format(user_id))
    assert(limit <= 50)

    top_tracks_data_all = {}
    time_ranges = ["short_term", "medium_term", "long_term"]
    for time_range in time_ranges:
        response = get(top_tracks_endpoint + "?time_range={}&limit={}".format(time_range, limit), token)

        top_tracks = response.json()
        
        # print("Featurizing tracks")
        track_names, track_uris, data = utils.featurize_tracks([{ 'track' : track } for track in top_tracks['items']], spotipy_session, verbose=True)
        # print("Getting song genres")
        artist_names, artist_uris, genres = utils.get_song_genres([{ 'track' : track } for track in top_tracks['items']], spotipy_session, verbose=True)

        top_tracks_data = []

        num_tracks = len(top_tracks['items'])
        for i in range(num_tracks):
            track_name = track_names[i]
            track_uri = track_uris[i]
            track_features = data['features'][i]
            track_genres = genres[i]
            track_artists = artist_names[i]
            top_tracks_data.append({ 'name' : track_name,
                                    'uri' : track_uri,
                                    'genres' : track_genres, 
                                    'artists' : track_artists,
                                })
            for feature, feature_name in zip(track_features, data['feature_names']):
                top_tracks_data[-1][feature_name] = feature
        
        top_tracks_data_all[time_range] = top_tracks_data
       
    return top_tracks_data_all

def scrape_recently_played(token, spotipy_session, user_id, limit=50):
    # print("Getting recently played artists for {}".format(user_id))
    assert(limit <= 50)

    response = get(recently_played_endpoint + "?limit={}".format(limit), token)

    recently_played = response.json()
    
    # print("Featurizing tracks")
    track_names, track_uris, data = utils.featurize_tracks(recently_played['items'], spotipy_session, verbose=True)
    # print("Getting song genres")
    artist_names, artist_uris, genres = utils.get_song_genres(recently_played['items'], spotipy_session, verbose=True)

    dates = [track['played_at'] for track in recently_played['items']]

    recently_played_data = []
    num_tracks = len(recently_played['items'])
    for i in range(num_tracks):
        track_name = track_names[i]
        date_added = dates[i]
        track_uri = track_uris[i]
        track_features = data['features'][i]
        track_genres = genres[i]
        track_artists = artist_names[i]
        recently_played_data.append({ 'name' : track_name,
                                      'uri' : track_uri,
                                      'date' : date_added,
                                      'genres' : track_genres, 
                                      'artists' : track_artists,
                                    })
        for feature, feature_name in zip(track_features, data['feature_names']):
            recently_played_data[-1][feature_name] = feature
    
    return recently_played_data

def write_json(file_name, data):
    logging.info("Writing song data to {}.".format(file_name))
    open(file_name, "w").write(json.dumps(data, indent=4))

def read_json(file_name):
    logging.info("Reading cached data from {}.".format(file_name))
    return json.loads(open(file_name, "r").read())

def scrape_data(token, spotipy_session, user_id):
    # Output data to file
    user_folder = os.path.join("/tmp/data", user_id)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    
    time_ranges = ["short_term", "medium_term", "long_term"]
    profile_file = os.path.join(user_folder, "profile.json")
    playlists_file = os.path.join(user_folder, "playlists.json")
    library_file = os.path.join(user_folder, "library.json")
    top_artists_file = os.path.join(user_folder, "top_artists.json")
    top_tracks_file = os.path.join(user_folder, "top_tracks.json")
    recently_played_file = os.path.join(user_folder, "recently_played.json")

    def scrape_if_not_cached(file_name, scraper, *args):
        if not os.path.exists(file_name):
            data = scraper(*args)
            write_json(file_name, data)
        else:
            data = read_json(file_name)
        
        return data

    profile_data = scrape_if_not_cached(profile_file, get_profile_data, token)
    user_id = profile_data['id']

    playlists_data = scrape_if_not_cached(playlists_file, get_user_playlists, token, user_id)
    library_data = scrape_if_not_cached(library_file, scrape_library, token, spotipy_session, user_id)
    recently_played = scrape_if_not_cached(recently_played_file, scrape_recently_played, token, spotipy_session, user_id)
    top_artists = scrape_if_not_cached(top_artists_file, scrape_top_artists, token, spotipy_session, user_id)
    top_songs = scrape_if_not_cached(top_tracks_file, scrape_top_songs, token, spotipy_session, user_id)

    # Package everything into a dictionary for easy return
    ret_dict = {
                "profile" : profile_data,
                "playlists" : playlists_data,
                "library" : library_data,
                "top_tracks" : top_songs,
                "top_artists" : top_artists,
                "recently_played" : recently_played,
                }

    return ret_dict