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

def get_track_uris_from_cluster_users(db_handler, cluster_id, total_songs,users_per_cluster=5,  current_user_id=None):
    users = db_handler.get_users_from_cluster(cluster_id, users_per_cluster)
    
    if current_user_id:#avoid users own songs(maybe dont tho)
        users = [user for user in users if user['user_id'] != current_user_id]

    if not users:
        return []


    songs_per_user = max(1, total_songs // len(users))
    collected_uris = []

    for user in users:
        top_tracks = user.get("top_tracks", [])
        #random.shuffle(top_tracks)
        collected_uris.extend(top_tracks[:songs_per_user])

    return collected_uris[:total_songs]  # Trim if we over-collected

def generate_similarity_playlists(sp, user_vector, db_handler, clusterer, total_songs=100, clusters_to_use=2, users_per_cluster=20, playlist = ""):
    """
    Generate playlists based on similarity to user's taste profile.

    Options for `playlist`:
    - "most_similar"
    - "similar_clusters"
    - "least_similar"
    - "" (empty string) to generate all
    """
    # Get cluster distances
    similar_clusters, least_similar = clusterer.get_similar_clusters({'supergenres': user_vector}, n=8)
    user_cluster = clusterer.predict({'supergenres': user_vector})

    # Configurable weight distribution for top N similar clusters
    cluster_weights = [0.4, 0.2, 0.2, 0.1, .1]  # ENSURE sum to 1
    low_cluster_weights=[.2,.2,.2,.2,.2]
    playlists = {}

    if playlist in ["most_similar", ""]:
        same_cluster_uris = get_track_uris_from_cluster_users(
            db_handler,
            user_cluster,
            total_songs,
            current_user_id=None
        )
        playlists["most_similar"] = create_playlist(
            sp=sp,
            title="Similar to My Taste",
            track_uris=same_cluster_uris,
            description="Songs from users most like you",
            public=True
        )

    if playlist in ["similar_clusters", ""]:
        weighted_uris = []
        for (dist, cluster_id), weight in zip(similar_clusters, cluster_weights):
            count = int(total_songs * weight)
            uris = get_track_uris_from_cluster_users(
                db_handler,
                cluster_id,
                count,
                current_user_id=None
            )
            weighted_uris.extend(uris)

        playlists["similar_clusters"] = create_playlist(
            sp=sp,
            title="Expand My Horizons",
            track_uris=weighted_uris,
            description="Songs from users with similar tastes, weighted by closeness",
            public=True
        )

    if playlist in ["least_similar", ""]:
        low_weighted_uris = []
        for (dist, cluster_id), weight in zip(least_similar, low_cluster_weights):
            count = int(total_songs * weight)
            uris = get_track_uris_from_cluster_users(
                db_handler,
                cluster_id,
                count,
                current_user_id=None
            )
            low_weighted_uris.extend(uris)

        playlists["least_similar"] = create_playlist(
            sp=sp,
            title="Not Like Me",
            track_uris=low_weighted_uris,
            description="Songs from users least like you",
            public=True
        )

    return playlists

def get_playlist_tracks_details(sp, playlist_id):
    """
    Get detailed information about all tracks in a playlist.
    
    Args:
        sp: Spotify client
        playlist_id: ID of the playlist
        
    Returns:
        List of track details
    """
    tracks = []
    results = sp.playlist_items(playlist_id)
    
    while results:
        for item in results['items']:
            if item.get('track'):
                track = item['track']
                
                # Extract relevant track information
                track_info = {
                    'id': track.get('id'),
                    'name': track.get('name'),
                    'uri': track.get('uri'),
                    'url': track.get('external_urls', {}).get('spotify'),
                    'artists': [{'name': artist['name'], 'id': artist['id']} 
                               for artist in track.get('artists', [])],
                    'album': {
                        'name': track.get('album', {}).get('name'),
                        'image': track.get('album', {}).get('images', [{}])[0].get('url') if track.get('album', {}).get('images') else None
                    }
                }
                
                tracks.append(track_info)
                
        if results.get('next'):
            results = sp.next(results)
        else:
            break
            
    return tracks