import random
import re
from datetime import datetime
from clustering import get_similar_clusters
from utils import load_genre_cache, parse_tracks

from db_handler import DynamoDBHandler

import re

def get_playlist_distro(playlist_id, sp=None):
    genre_cache = load_genre_cache()

    playlist_data = parse_playlist(sp, playlist_id)

    parsed_tracks, subgenre_distro, supergenre_distro = parse_tracks(
        sp, playlist_data['tracks'], genre_cache
    )

    # Ensure genre distribution values are floats
    subgenre_distro = {k: float(v) for k, v in subgenre_distro.items()}
    supergenre_distro = {k: float(v) for k, v in supergenre_distro.items()}
    # Sort subgenres and supergenres by their values in descending order and convert to list of tuples
    sorted_subgenres = sorted([(k, float(v) * 100) for k, v in subgenre_distro.items()], key=lambda item: item[1],
                              reverse=True)
    sorted_supergenres = sorted([(k, float(v) * 100) for k, v in supergenre_distro.items()], key=lambda item: item[1],
                                reverse=True)

    response = {
        "playlist_id": playlist_id,
        "playlist_metadata": {
            "id": playlist_data['id'],
            "name": playlist_data['name'],
            "track_count": playlist_data['track_count']
        },
        "subgenre_distribution": sorted_subgenres,
        "supergenre_distribution": sorted_supergenres
    }

    # Return the response with a source indicator
    return response

def extract_id(url):
    try:
        # Regex pattern to match both playlist and user IDs
        pattern = r'open\.spotify\.com/(playlist|user)/([^?]+)'

        # Search for the pattern in the given URL
        match = re.search(pattern, url)
        if match:
            return match.group(2)  # Return the ID part
        return None  # Return None if no match found
    except Exception as e:
        print(f"Error extracting ID: {e}")
        return None


# Fetch playlist metadata and all track items from a Spotify playlist.
def parse_playlist(sp, playlist_id):
    """

    Returns:
        dict: {
            'id': str,
            'name': str,
            'description': str,
            'owner': str,
            'image_url': str or None,
            'track_count': int,
            'tracks': list of track dicts
        }
    """
    metadata = {}
    tracks = []

    try:
        # Fetch playlist metadata
        playlist_info = sp.playlist(playlist_id)
        
        metadata = {
            'id': playlist_info.get('id'),
            'name': playlist_info.get('name'),
            #'description': playlist_info.get('description', ''),
            #'owner': playlist_info.get('owner', {}).get('display_name', 'Unknown'),
            #'image_url': playlist_info['images'][0]['url'] if playlist_info.get('images') and len(playlist_info['images']) > 0 else None,
            'track_count': playlist_info.get('tracks', {}).get('total', 0),
            'tracks': []  # Will populate below
        }
        
        # Fetch tracks (handle pagination)
        results = sp.playlist_items(playlist_id)
        
        while results:
            for item in results['items']:
                track = item.get('track')
                if track:
                    tracks.append(track)
            if results.get('next'):
                results = sp.next(results)
            else:
                break

        metadata['tracks'] = tracks
        return metadata
    except Exception as e:
        print(f"Error fetching playlist metadata or tracks: {e}")


def get_all_user_playlist_ids(sp):
    """
    Fetch all playlists owned or followed by the current user.
    
    Args:
        sp (spotipy.Spotify): Authenticated Spotify client.
        
    Returns:
        list of str: Playlist IDs.
    """
    playlist_ids = []
    offset = 0
    limit = 50

    while True:
        response = sp.current_user_playlists(limit=limit, offset=offset)
        items = response.get('items', [])
        if not items:
            break

        for playlist in items:
            playlist_ids.append(playlist['id'])

        if response.get('next') is None:
            break

        offset += limit

    return playlist_ids


def create_playlist(sp, title, track_uris, description="Generated Playlist", public=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    full_title = f"{title} ({timestamp})"
    user_id = sp.me()['id']
    playlist = sp.user_playlist_create(user=user_id, name=full_title, public=public, description=description)
    sp.playlist_add_items(playlist_id=playlist['id'], items=track_uris)
    return playlist

def get_track_uris_from_cluster_users(db_handler, cluster_id, total_songs, users_per_cluster=5):
    users = db_handler.get_users_from_cluster(cluster_id, users_per_cluster)
    if not users:
        return []

    songs_per_user = max(1, total_songs // len(users))
    collected_uris = []

    for user in users:
        top_tracks = user.get("top_tracks", [])
        random.shuffle(top_tracks)
        collected_uris.extend(top_tracks[:songs_per_user])

    return collected_uris[:total_songs]  # Trim if we over-collected

def generate_similarity_playlists(sp, user_vector, db_handler, total_songs=100, clusters_to_use=2, users_per_cluster=5):
    """
    Returns a dictionary of 3 playlists:
        - Most similar clusters
        - Mid-range (optional: skipped here for simplicity)
        - Least similar clusters
    """
    most_sim, least_sim = get_similar_clusters(user_vector, top_n=clusters_to_use)
    
    playlists = {}

    for group_name, clusters in {
        "most_similar": most_sim,
        "least_similar": least_sim
    }.items():
        group_uris = []
        for cluster_id, _ in clusters:
            uris = get_track_uris_from_cluster_users(db_handler, cluster_id, total_songs // clusters_to_use, users_per_cluster)
            group_uris.extend(uris)

        playlist = create_playlist(
            sp=sp,
            title=f"{group_name.replace('_', ' ').title()} Playlist",
            track_uris=group_uris[:total_songs],
            description=f"Spotify Stats Generated from {group_name.replace('_', ' ')} clusters - Discover your sound :) ",
            public=False
        )
        playlists[group_name] = playlist

    return playlists

