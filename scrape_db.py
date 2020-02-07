import json
import zlib
from db import DataBase
import math
import datetime
import requests
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SPOTIFY_API_URL = "https://api.spotify.com"
# All of the API endpoints that we are interested in
API_ENDPOINTS = { 
                    "user_profile" : "/v1/me",
                    "user_albums" : "/v1/me/albums", 
                    "user_tracks" : "/v1/me/tracks",
                    "user_playlists" : "/v1/me/playlists",
                    "audio_features" : "/v1/audio-features",
                    "audio_analysis" : "/v1/audio-analysis",
                    "tracks" : "/v1/tracks",
                    "artists" : "/v1/artists",
                }
# Replace endpoints with full access URL
for key, value in API_ENDPOINTS.items():
    API_ENDPOINTS[key] = SPOTIFY_API_URL + value

def get(endpoint, token, max_retries=10, delay=4):
    authorization_header = {"Authorization": "Bearer {}".format(token)}
    try:
        logger.info("GET: " + endpoint)
        response = requests.get(endpoint, headers=authorization_header)
    except requests.exceptions.ConnectionError as e:
        response = {}
        response.status_code = 429
        logger.warn("Could not fulfill GET.\n" + e)
    # If status is anything but OK, raise an error
    if response.status_code != 200:
        if response.status_code == 429:
            if max_retries > 0:
                time.sleep(delay)
                return get(endpoint, token, max_retries=max_retries - 1, delay=delay + 1)
            else:
                msg = "Connection refused after {} retries".format(max_retries)
                logger.error(msg)
                raise RuntimeError(msg)
        logger.error(response.reason)
        raise RuntimeError(response.reason)
    
    return response	

def scrape_profile(token):
    key = "user_profile"
    endpoint = API_ENDPOINTS[key]

    response = get(endpoint, token)

    profile = response.json()

    return profile

def generate_paginated_urls(endpoint, total, limit):
    urls = []
    for i in range(int(total / limit)):
        offset = (i + 1) * limit
        urls.append(endpoint + f"?offset={offset}&limit={limit}")
    
    return urls

def scrape_paginated_data(endpoint, token, limit=None):
    if limit:
        url = endpoint + f"?limit={limit}"
    else:
        url = endpoint
    response = get(url, token)
    page = response.json()

    all_pages = [page]
    
    total = page['total']
    if not limit:
        limit = page['limit']

    urls = generate_paginated_urls(endpoint, total, limit)
    # try to perform all of these asynchronously
    for i, url in enumerate(urls):
        response = get(url, token)
        page = response.json()
        all_pages.append(page)

    return all_pages
    
def scrape_user_playlists(token):
    key = "user_playlists"
    endpoint = API_ENDPOINTS[key]

    return scrape_paginated_data(endpoint, token)

def scrape_user_albums(token):
    key = "user_albums"
    endpoint = API_ENDPOINTS[key]

    return scrape_paginated_data(endpoint, token)

# Construct a dictionary from a track JSON object that contains
# a subset of the data that we choose
def parse_track(track):
    keys_to_keep = ["name", "id", "popularity", "uri", "artists"]
    ret_track = {}
    ret_track["date"] = track["added_at"]
    for key in keys_to_keep:
        ret_track[key] = track["track"][key]

    artist_keys = ["name", "id"]
    ret_track["artists"] = [{ key : artist[key] for key in artist_keys } for artist in track["track"]["artists"]]
    
    return ret_track

def scrape_user_tracks(token):
    key = "user_tracks"
    endpoint = API_ENDPOINTS[key]

    pages = scrape_paginated_data(endpoint, token, limit=50)

    tracks = []
    for page in pages:
        page_tracks = page['items']
        for track in page_tracks:
            tracks.append(parse_track(track))

    return tracks

def parse_features(features):
    features_to_keep = ['energy', 'liveness', 'speechiness', 'acousticness', 'instrumentalness', 
                        'danceability', 'loudness', 'valence', 'tempo']
    
    ret_features = {}
    for feature in features_to_keep:
        ret_features[feature] = features[feature]
    
    return ret_features

# Gets audio features for every track id given
# don't technically need the user's token to scrape these since they are publically available
def scrape_audio_features(track_ids, token, limit=100):
    key = "audio_features"
    endpoint = API_ENDPOINTS[key]
    total = len(track_ids)
    urls = []
    for i in range(int(total / limit) + 1):
        low = i * limit
        high = (i + 1) * limit
        urls.append(endpoint + "?ids=" + ",".join(track_ids[low:high]))
    
    all_features = []
    for url in urls:
        response = get(url, token)
        track_features = response.json()['audio_features']
        for features in track_features:
            all_features.append(parse_features(features))

    return all_features

def scrape_genres(artist_ids, token, limit=50):
    key = "artists"
    endpoint = API_ENDPOINTS[key]
    total = len(artist_ids)
    urls = []
    for i in range(int(total / limit) + 1):
        low = i * limit
        high = (i + 1) * limit
        urls.append(endpoint + "?ids=" + ",".join(artist_ids[low:high]))
    
    all_genres = []
    for url in urls:
        response = get(url, token)
        artists = response.json()['artists']
        for artist in artists:
            all_genres.append(artist['genres'])

    return all_genres        

def compile_library(tracks, audio_features, genres):
    # compile into data structure we want
    genre_idx = 0
    for track, features in zip(tracks, audio_features):
        for feature in features.keys():
            track[feature] = features[feature]
        track_genres = []
        for artist in track['artists']:
            track_genres.append(genres[genre_idx])
            genre_idx += 1
        track["genres"] = list(set(sum(track_genres, [])))

def compress_data(data):
    return zlib.compress(json.dumps(data).encode('utf-8'))

def partition_and_compress_list(data_list):
    # max size of a parition in KB
    MAX_PARTITION_SIZE = 350
    compressed = compress_data(data_list)
    
    data_size = compressed.__sizeof__()
    data_size_kb = data_size / 1024

    # DynamoDB has an item limit of 400 KB
    # if we go beyond this, need to partition the data up into
    # pieces and store those pieces separately
    # Use 350 KB to keep a 50 KB overhead for database key sizes
    # and changes in compression efficiency over different partitions
    num_partitions = math.ceil(data_size_kb / MAX_PARTITION_SIZE)

    total_items = len(data_list)
    tracks_per_partition = math.ceil(total_items / num_partitions)
    # need to split the data into multiple partitions and store them separately
    partitions = []
    for i in range(num_partitions):
        lower = i * tracks_per_partition
        upper = (i + 1) * tracks_per_partition
        partition = data_list[lower:upper]
        partition_compressed = compress_data(partition)

        partitions.append(partition_compressed)
    
    return partitions

def get_current_time():
    return int((datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds() * 1e6)

# need try / catch to check if token has expired and ask for a new one
def scrape_library(token):
    db = DataBase("Wayfinder")

    profile = scrape_profile(token)
    user_id = profile['id']
    logger.info(f"writing {user_id} --> 'profile' : {profile} ({profile.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "profile", profile)

    scrape_time = get_current_time()
    logger.info(f"writing {user_id} --> 'scrape_time' : {scrape_time} ({scrape_time.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "scrape_time", scrape_time)

    message = "Scraping library"
    logger.info(f"writing {user_id} --> 'message' : {message} ({message.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "message", message)
    
    tracks = scrape_user_tracks(token)
    track_ids = [track["id"] for track in tracks]
    
    message = "Scraping song features"
    logger.info(f"writing {user_id} --> 'message' : {message} ({message.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "message", message)

    audio_features = scrape_audio_features(track_ids, token)

    artist_ids = sum([ [ artist["id"] for artist in track["artists"] ] for track in tracks ], [])

    message = "Scraping artist genres"
    logger.info(f"writing {user_id} --> 'message' : {message} ({message.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "message", message)

    genres = scrape_genres(artist_ids, token)

    compile_library(tracks, audio_features, genres)

    tracks_partitioned = partition_and_compress_list(tracks)

    message = "Writing to data base"
    logger.info(f"writing {user_id} --> 'message' : {message} ({message.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "message", message)

    partition_keys = []
    for i, partition in enumerate(tracks_partitioned):
        partition_key = f"{user_id}_tracks_{i}"
        partition_keys.append(partition_key)
        logger.info(f"writing {partition_key} --> 'tracks' : Bytes(partition) ({partition.__sizeof__()/1024:.1f} KB) ")
        db.update(partition_key, "tracks", partition)

    logger.info(f"writing {user_id} --> 'partition_keys' : {partition_keys} ({partition_keys.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "partition_keys", partition_keys)

    message = "Done"
    logger.info(f"writing {user_id} --> 'message' : {message} ({message.__sizeof__()/1024:.1f} KB) ")
    db.update(user_id, "message", message)

def lambda_handler(event, context):
    assert("token" in event.keys())
    token = event["token"]
    try:
        scrape_library(token)
        return { "statusCode" : 200 }
    except Exception as e:
        raise Exception("Error scraping library:", e)

def main():
    token = "BQCJvZ6F58Jaqf5VkY1nnzL5MN20TF7a3ffVhc4oLPOSpbn2xcu3jO_HWwAqG8I6w-xMxDP0CVitcRrSrvPkUDV5tgm-u6GlngdZ6TRJXga5mR548YKmFKexxjYtvZGCg3bQjXfL4O3kkmOYDPzeGfUuEjjJZJIavR4v7IjIIT_ethXLyE8hs7aCyw6R57P93QUFGvkSXkaAyvaN22piFTM2DG_J5yOQOhRYTR-YrceY" 
    scrape_library(token)

if __name__ == "__main__":
    main()
