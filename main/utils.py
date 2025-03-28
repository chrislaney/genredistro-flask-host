import json
from collections import Counter
from io import BytesIO
import base64
import spotipy
import os


# Load JSON file into a dictionary
# Load genre cache from file_path
def load_genre_cache(file_name='genre_cache.json'):
    # Get the absolute file path relative to the current script directory
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # If the file is not found, create an empty file
        with open(file_path, 'w') as f:
            json.dump({}, f, indent=4)  # Create an empty JSON object
        return {}


# saves genre_cache dict to file_path - THIS MIGHT BE SLOWER BC I AM REWRITING ALL GENRE CACHE
def save_genre_cache(genre_cache, file_name='genre_cache.json'):
    # Get the absolute file path relative to the current script directory
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    
    with open(file_path, 'w') as f:
        json.dump(genre_cache, f, indent=4)

# Save unknown genres, merging counts if the file already exists
def save_unknown_genres(unknown_genres, unknown_genres_file="unknown_genres.json"):
    if not unknown_genres:
        return  # No unknown genres to save

    # Get the absolute file path relative to the current script directory
    file_path = os.path.join(os.path.dirname(__file__), unknown_genres_file)
    
    try:
        with open(file_path, "r") as f:
            existing_unknowns = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_unknowns = {}

    # Merge counts with existing unknown genres
    for genre, count in unknown_genres.items():
        existing_unknowns[genre] = existing_unknowns.get(genre, 0) + count

    # Save updated unknown genres to file
    with open(file_path, "w") as f:
        json.dump(existing_unknowns, f, indent=4)

# Fetch top 100 tracks from Spotify
def get_top_100(sp):
    top_tracks = []
    limit = 50  # Spotify API max limit for top tracks per request
    time_range = 'medium_term'  # Approx. last 6 months (includes this year)

    try:
        # Fetch first 50 tracks
        response = sp.current_user_top_tracks(limit=limit, offset=0, time_range=time_range)
        top_tracks.extend(response['items'])

        # Fetch next 50 tracks if available
        if len(response['items']) == limit:
            response = sp.current_user_top_tracks(limit=limit, offset=50, time_range=time_range)
            top_tracks.extend(response['items'])

        return top_tracks
    except spotipy.exceptions.SpotifyException as e:
        print(f"Error fetching top tracks: {e}")
        return []


# gets users top tracks for time range. DEFAULT: num_tracks=100, time_range='medium_term'
# long_term  last ~1 year, medium_term last ~6 months,short_term last ~4 weeks
def fetch_top_tracks(sp, num_tracks=100, time_range='medium_term'):
    top_tracks = []
    limit = 50  # Spotify API max limit for top tracks per request
    VALID_TIME_RANGES = ['short_term', 'medium_term', 'long_term']

    # Validate
    if time_range not in VALID_TIME_RANGES:
        raise ValueError(f"Invalid time_range: {time_range}. Must be one of {VALID_TIME_RANGES}.")
    if num_tracks <= 0:
        raise ValueError("num_tracks must be a positive integer.")

    offset = 0
    try:
        # Fetch first num_tracks%50 tracks to ensure spotify API max limit for top tracks per request is followed
        if num_tracks % limit != 0:
            response = sp.current_user_top_tracks(limit=num_tracks % limit, offset=offset, time_range=time_range)
            offset += num_tracks % limit
            top_tracks.extend(response['items'])

        # Fetch next 50 tracks till num_tracks is met
        for _ in range(num_tracks // limit):
            response = sp.current_user_top_tracks(limit=limit, offset=offset, time_range=time_range)
            offset += limit
            top_tracks.extend(response['items'])

        # Return raw track data
        return top_tracks

    except spotipy.exceptions.SpotifyException as e:
        print(f"Error fetching top tracks: {e}")
        return []


# Parse saved tracks and compute genre distributions
def parse_saved_tracks(sp, raw_tracks, genre_cache):
    parsed_tracks = []
    unknown_artist_ids = set()
    subgenre_count = {}  # Dictionary to store genre counts

    for track in raw_tracks:  # raw_tracks is now a flat list of tracks
        artist_id = track['artists'][0]['id']  # grabbing artist_id
        if artist_id not in genre_cache:  # checking if in genre cache
            unknown_artist_ids.add(artist_id)  # adding to unknown set if not in

        parsed_tracks.append({
            "track_name": track['name'],
            "artist_names": [artist['name'] for artist in track['artists']],
            "artist_id": track['artists'][0]['id'],
            "album_name": track['album']['name'],
            "uri": track['uri'],
            "url": track["external_urls"]['spotify'],
            "album_cover": track['album']['images'][0]['url'],
        })

    # Fetching unknown artist genres and adding to our genre_cache
    if unknown_artist_ids:
        fetched_genres = fetch_unknown_artist_genres(sp, list(unknown_artist_ids))
        genre_cache.update(fetched_genres)

    # Adding all genres to parsed tracks and updating genre counts
    for track in parsed_tracks:
        genres = genre_cache.get(track['artist_id'], [])
        track['genres'] = genres  # Assigning genres to track

        for genre in genres:
            subgenre_count[genre] = subgenre_count.get(genre, 0) + 1

    save_genre_cache(genre_cache)

    supergenre_count = get_super_genre_counts(subgenre_count)

    supergenre_distro = normalize_genre_counts(supergenre_count)
    subgenre_distro = normalize_genre_counts(subgenre_count)

    return parsed_tracks, subgenre_distro, supergenre_distro


# Normalize genre counts to frequency
def normalize_genre_counts(genre_counts):
    total_count = sum(genre_counts.values())
    normalized_counts = {genre: count / total_count for genre, count in genre_counts.items()}
    return normalized_counts


# Finds super genre for a genre using genre map
# Function to get the correct file path for genre_map.json
def get_genre_map_path(filename='genre_map.json'):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# Function to find the super genre for a given genre
def find_super_genre(genre, genre_map_file=None):
    if genre_map_file is None:
        genre_map_file = get_genre_map_path()  # Default to 'genre_map.json' in the current directory
    
    try:
        with open(genre_map_file, "r") as f:
            data = json.load(f)
            for super_genre, sub_genres in data["genres_map"].items():
                if genre in sub_genres:
                    return super_genre  # return when match found
    except FileNotFoundError:
        print(f"Error: {genre_map_file} not found")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {genre_map_file}")
    
    return None


# Get genre distributions (subgenre and supergenre)
def get_super_genre_counts(subgenre_count):
    super_genre_counts = {}
    unknown_genres = {}

    for genre, count in subgenre_count.items():
        super_genre = find_super_genre(genre)

        if super_genre:
            super_genre_counts[super_genre] = super_genre_counts.get(super_genre, 0) + count
        else:
            unknown_genres[genre] = count

    save_unknown_genres(unknown_genres)
    return super_genre_counts


# Fetch genres for unknown artists
def fetch_unknown_artist_genres(sp, unknown_artist_genres):
    genres = {}  # dict to store artist_id and genre
    try:
        for i in range(0, len(unknown_artist_genres), 50):  # iterates over unknown_genre_list in sequences of 50
            response = sp.artists(unknown_artist_genres[i:i + 50])  # fetches in batches of 50
            for artist in response['artists']:  # this iterates over our artist information
                genres[artist['id']] = artist.get('genres', [])  # this gets the genre from each and adds it to the dict
    except Exception as e:
        print(f"Error fetching genres: {e}")
    return genres
