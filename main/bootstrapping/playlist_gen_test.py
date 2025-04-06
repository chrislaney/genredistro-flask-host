import os
import json
import random
import numpy as np
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from flask import session, Flask, jsonify, request
from spotipy import Spotify

# Configuration
USERS_DIR = "./users_and_artists/combined"

SUPERGENRES = [
    "Pop", "Electronic", "Hip Hop", "R&B", "Latin", "Rock", "Metal",
    "Country", "Folk/Acoustic", "Classical", "Jazz", "Blues",
    "Easy listening", "New age", "World/Traditional"
]

def get_spotify_client():
    token_info = ensure_token_or_redirect()
    if isinstance(token_info, dict):
        return Spotify(auth=token_info['access_token'])
    raise Exception("Redirected due to missing or expired token.")

def load_user_vectors():
    user_vectors = {}
    for filename in os.listdir(USERS_DIR):
        if filename.endswith(".json"):
            path = os.path.join(USERS_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                user_id = data.get("user_id") or filename.replace(".json", "")
                raw_vector = data.get("supergenre_vector", {})
                vector = np.array([raw_vector.get(genre, 0.0) for genre in SUPERGENRES], dtype=np.float32)
                user_vectors[user_id] = vector
    return user_vectors

def get_similar_users(user_vector_dict, num_most_similar=30):
    user_vec = np.array([user_vector_dict.get(genre, 0.0) for genre in SUPERGENRES], dtype=np.float32).reshape(1, -1)
    all_users = load_user_vectors()
    similarities = []

    for uid, vec in all_users.items():
        sim = cosine_similarity(user_vec, vec.reshape(1, -1))[0][0]
        similarities.append((uid, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)

    most_similar = [uid for uid, _ in similarities if not np.allclose(all_users[uid], user_vec)]

    return most_similar[:num_most_similar]

def load_user_data(uid):
    filepath = os.path.join(USERS_DIR, f"{uid}.json")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"User file not found for {uid}")

    with open(filepath, "r") as f:
        return json.load(f)

def create_playlist(sp, title, track_uris, description="Generated Playlist", public=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title_with_time = f"{title} ({timestamp})"
    user_id = sp.me()['id']
    playlist = sp.user_playlist_create(user=user_id, name=title_with_time, public=public, description=description)
    sp.playlist_add_items(playlist_id=playlist['id'], items=track_uris)
    return playlist

def create_playlist_from_jsons(sp, user_ids, total_songs, playlist_name):
    all_uris = []

    if not user_ids:
        print("No users provided. Playlist not created.")
        return None

    songs_per_user = max(1, total_songs // len(user_ids))

    for uid in user_ids:
        try:
            user_data = load_user_data(uid)
            user_tracks = user_data.get('top_tracks', [])
            random.shuffle(user_tracks)
            track_uris = user_tracks[:songs_per_user]
            if track_uris:
                all_uris.extend(track_uris)
        except Exception as e:
            print(f"Error fetching tracks for user {uid}: {e}")

    if not all_uris:
        print("No tracks collected. Playlist not created.")
        return None

    return create_playlist(
        sp=sp,
        title=playlist_name,
        track_uris=all_uris,
        description="Auto-generated playlist from JSON users",
        public=False
    )

def generate_similarity_playlists(sp, user_vector, total_songs=50, group_configs=None):
    if group_configs is None:
        group_configs = {
            'most_similar': {'start': 0, 'end': 3},
            'mid_range': {'start': 5, 'end': 12},
            'least_similar': {'start': -3, 'end': None}
        }

    similar_users = get_similar_users(user_vector)
    playlists = {}

    for group, idx_range in group_configs.items():
        start, end = idx_range['start'], idx_range['end']
        user_ids = similar_users[start:end]
        playlist_name = f"{group.replace('_', ' ').title()} Users Playlist"
        playlists[group] = create_playlist_from_jsons(sp, user_ids, total_songs, playlist_name)

    return playlists