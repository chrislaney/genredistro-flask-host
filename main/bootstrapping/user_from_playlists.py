"""
user_from_playlists.py

This script generates synthetic user profiles from public Spotify playlists to simulate diverse listening behavior,
drawing data from both real people and curated artist sources.

It contains two main functions:

- `real_people()`:
    - Creates users from a curated list of Top 100 public playlists shared by friends and family.
    - Intended to reflect authentic, diverse music taste patterns from everyday listeners in the target region.
    - For each playlist, it creates N synthetic users by chunking the playlist into groups of X tracks.

- `artist_users()`:
    - Builds users from Spotify artist radio playlists.
    - These represent narrower listening profiles centered around a specific artist or genre cluster.
    - For each artist playlist, it generates 2 users by slicing the top 50 tracks into two 25-track segments.

Each generated user is saved as a JSON file in the format defined by the `User` class in `user.py`, which includes:
- A unique username (formatted as: `{generate_fake_name()}-{playlist_id}-{chunk_id}`)
- A list of top track URIs
- A set of subgenres and supergenres derived from playlist content

These user profiles are used to prototype and test:
- Recommendation engine performance
- Clustering and segmentation strategies
- Genre distribution modeling
- Classifier bootstrapping for a live demo environment
"""

# user_from_playlists.py
import sys, os
import json
import random
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from utils import parse_tracks
from playlist_utils import parse_playlist, parse_tracks
from user import User

# Spotify App Credentials
client_id = '104ec8795164430c814e8b4e98a6d781'
client_secret = 'e1dbca47ea984b6a8256631b4bbcfab8'

# Initialize Spotify client (public playlist access only)
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=client_id,
    client_secret=client_secret
))

# output dirs
real_output_dir = "users_and_artists"
artist_output_dir = "users_and_artists"

# List of public playlist IDs
artist_playlist_ids =  ['5l7T9Q5z13VeUNVyWvxhqO', '2ntYm3kyUfO2AfVBsSAzPo', '64Oj3WwNX5pIRDqNqZ2Qjc', '4OWUKCryi1l2GuFYStGokT', '3yoS7AFclOLR1KqrdOaMcV',
'7c2bs2HJ60YGy242ZpJlzG', '1aNFkYUK4qTUe8H96jEOzA', '5Seki47tWtdSKWCIiBqsPd', '5HGPJlM2Gt9JeUTEbgf8RJ', '1CKoQPN1H7GFs04GOJqgWZ', '6IMlcf2HRrodVeL0Xfk3VD',
'5hz7XzZIM1ym4bfrM1qC5Y', '3oesM2g2EEiq2vKH8GHLA0', '16JHeU8pP3VJgjaN6cna80', '74lnx4RdPFNTh6lXu7kmjI', '4ZzhCjAa908ksareKBFyFK', '5m3qTsZchMmr6RxktXJkvb',
'7JB2J9HK5B81nrlhp5fEjH', '2mZiZyvSZCxoHtdGOydRwt', '34fty458ZfppCwtVcILtLv', '132CWpGyzC0xwlCSytPkyF', '1qIaMEuzE3apJoHg1Cn5D0', '1bcUbLMRmaIVQMeGj6zna8', 
'1swN6t0Ey7kWXDWZLXKpgj', '34zWzANNsC9bLiLYBfh4xu', '0zR0G69ovhQMFPr8jemUt4', '1QI6oJP2XX9qH9VUtzs4XO', '0a2Pozd9B8wdIweLKFqoqM', '46r9hdhyc5tz0SxTQoNGRS', 
'35suDaWu9PbLO73zuiSoaH', '3V0XrZunNamHSuv60JOLJz', '1Jg22QbjypynvCtXk6Glj0', '6L7NONohzTwgElpMyLzq0N', '1qvSgXL6BJimuqsyALKYpy', '57wlnbW8PztQxIK1cau3Ja', 
'1ZpAt7rQ7xdmJUQWT2QYfS', '41wGhbkZXokXDqqDAghvrh', '28XvQlZz8avJz6SLLEdAVo', '0NtGpbI99cjyyw8P19Q9dV', '2khXVhAHAM2o4s5FBUu31c', '1r2nh60TmpJssGag6Fb4VC',
'4QX125F8Su90D9KDp44sri', '5mIzlhkwv5ReWTeQMpjXZD', '6WVrFx3cmTJ27AaA1AizXY', '0gLJaI8oizE4uW5hnjNfWZ', '7s3nfTcn9fQDgt6X6hipQX', '4TSpzW6OlU0jt3qbWF5YS3',
'4tCndowzSB3DJNQ08S8yMO', '1FmaAHmqqfF1lb75EJAsXp', '6irxX4BFzhFTbwdN5fAO5F', '7kKn8RJ4peGisJ95zhSFk6', '7JHDFzKbOnp3SNGWBWh8bS', '142s6UsLP8kZa7LpsnN8RP', 
'13Cl7qnKBLgBDW0t1If2N2', '6ViWcperOekPr0AqXbG1GX', '3ELdIyKE6YOu3Hv4t1jfhf', '4Qe0D1C0eMebHSXclEkFqV', '4c5RI9pzBbyaZ3sPRAHjbO', '1HMGJ1bhOLlt9W0w1IDQiQ',
'5qYngBh76m6Rs2z99rAkr1', '6O3A5CbN9OEvEBda15aRKD', '2bOkXc6XQtu0rOPkTMONdE', '7ae35EX3zZi3omU8gEhjoc', '2Drk02sTIc7DzkjNPiPclZ', '33Y5wtiaQVW7C4TL3EzYPP', 
'4lUORhVikyX0refmSdBvM0', '2uRR1Bp3F1NCDLiCTfveoZ', '4pP02GCSKkGNJX6OCgLC7f', '7mJ6Sa21outbHAlSHiMtAg', '2eRxJsH4O1nWIkYZIYKhYT', '6wl7qmxZwHs2ksOjXW0Ic7',
'3SI8MGbO7Mh7IFej3quFez', '5S98I8WQZioGGtPDEgBqJL', '3lvr9d1jwvAr8qam1Pi0oW', '6EPnejp6MHtLjO2fH2IDr5', '6LcZc3RtIdrhvkPursidLa', '4OwysqVLAY5N6vuolj7EZU',
'67HpXk5Jc64XoI7v3EcALu', '3XpIl9AfsJvhewp5eVoiWG', '4n8yaiXWIqISDKbgn86oCi', '4nPaTplmjsLEBqBmhFTEd6', '48q0Ancx4BXi79PdAh4odK', '67NpGAJ9vLwg4vKt1r8f23',
'10IlBUkN2gn4114CEOackt', '28WcaBl4iErSpPhkc2kIa5', '2rZ8xIaU78OhTL5IY0wBJC', '5sqFQ0LflDNdIauWWfhsHX', '0N5SCRnRmWjS6Y2oEsxvHy', '7wrpUEtMfkIMQ2cQDKtVEb',
 '3aLutwPwoq3LPASQTYU6zX', '3cOvG4XLHBOgGGeql8vbrS' ]




# real USERS THAT ARE PROCESSED
user_playlist_ids =["6ChSRuGzWIczjZrp90BQzz","298ake83n1yhQ7gkwjMWvW" , "40mZ7Gaf29yKaxrmhrprpN", "04vajMJKqrwB1O7ib4V8rt", "6YlQzadiLbJGadpoU5RLK3" ,"7zSThiDt2I7KKfZV6IwGPK",
                "6sJRtdkkDf5wbxU3VdSzbP", "76kxhBeCZ96VobdTzzdeKn","2wb0rMjJ5hutwTYJI8X4X1" , "0m5IYySEaM09FmHJIdykEp", "2tWFZzDS89QEeKFGLoks5U" , "6pHLiYgCEk5tO2NK29A9X3",
                "6NSWokS0pez4VnnkJCeIXb" ,"74TmSEjAwIqDr1wgRijfFx", "4sHoEQ24vcPxLxHzWQDyVg", "4vhKJUznLeYjQP0jbt13Qm", "1gD5khdDLnM3MsRP0delei", "2O0aXCqEqfr68dLXScLRbz" ,
                "4UPRr6AuZxCPIFLTJlCfs5", "43YS3rrnq6RuPqNlm4Ex0q", "4iKlDePfpw3uWf1jpF1Csa",
                "5l7T9Q5z13VeUNVyWvxhqO","21kb6OcIz6j06nVifm37Ga","31X0F4EGRT2FpBx990MGiJ","3V1acvna6D1D6QpOQYLI2n","6PVN4OdpFJ5iGUPuI0uY8Y","2aQhktPRgg7BakDiOItO2k",
                "6MlTnYPKMoflonRjw31UW1","6NvIDlv5yahZMUqLnNb9nv","5xAVMC8aLqRHR4PC6nsuQS","6LII3wPfVtIPoh9eeuuIUH","6x1ueDaHtIljSED4FpIS8a","0MuphdaIsEABYabIKY3Izb",
                "0YETZafYeidii0e8jfZROv","6Nb5NATlZjTCywhoCbNUDf","7r5gWYgYVfgiEcAZIIjZNZ","2K4CPmuC0XCA4glnBKBhfs","32qOp1NfNG1wkEuZQ6xyBc","5Z8kqdg7bRDKVbFxa1mbJA",
                "0y45wj8H1EFtqbn2yVx7ue","5lLQERLH7mObFu02sF1t49","6mpSYC44fBLJKtSKF4Cw9D","7hloNqEG80PX35C0InYmKT","3GV9R1UznADcHpNolaGAAL","5ZZm4tzxmceQ3T9sjsFyc9",
                "37i9dQZF1FoDDwExMHbSCU","37i9dQZF1FoJbCUxiMVyxo","37i9dQZF1FoHjotSFpTAzq","42xUPn8mIXpLFnGfyFrrqt","3xAS4ZwAs02HNkq9X4tkPU","1c8BcOZFRjCJiW60AXZh29",
                "4iVPcLfmxM7t4ykB5qCapG","1dXdZ3T4fMsiuv3nvWREOi","2SGpyIAdOHDH8F2GIrTANe","7KiGD6BDIqA6eQANfCiN0B","1Rk8qsP4nChMQuP2mUUO01","0gT261kc8QY6QlpZSkUxCH"
                "5r3GjMppXqPM1rCFRxwHqc","1BuwhD1RkZlQ93pntxudIQ","5V7El0owiHagVgsE0Bhle1","2PWNHoPdjeUeZgCQTqy3nB","3cc4HXiuQHncQ7qqj66S2S", "2bBxmcoTwQfXW1g0GPiBOn",
                "6IFJ4zyZ9J9A1zJ9x06hXo","1AIRIYNC6pOG4A4f0eOFvt","3Xu9gDzRhUEhCAoi7DVsTm","7K9SGQJ2DxiS9AkcLkAKSD"]

# Fake name generator
adjectives = [
    "vibey", "sunny", "moody", "cozyy", "zesty",
    "quirk", "breez", "cloud", "sassy", "faint",
    "foggy", "spicy", "grimy", "fizzy", "sleek",
    "hasty", "tidal", "fuzzy", "stark", "dusky",
    "brisk", "silly", "nerdy", "witty", "lofty"
]
nouns = [
    "panda", "koala", "robot", "ninja", "cloud",
    "squid", "lemon", "berry", "tulip", "mossy",
    "candy", "ghost", "wheat", "petal", "storm",
    "vapor", "stone", "pearl", "flame", "honey",
    "raven", "sloth", "scone", "lilac", "bloom"
]

def generate_fake_name():
    return f"{random.choice(adjectives)}_{random.choice(nouns)}"

def make_users_from_playlist(playlist_id, chunk_size, num_chunks, output_dir, is_artist=False):
    try:
        playlist_data = parse_playlist(sp, playlist_id)
        if not playlist_data or not playlist_data.get('name'):
            print(f"Skipping playlist {playlist_id} - no name found")
            return

        tracks = playlist_data['tracks']
        playlist_name_raw = playlist_data.get('name', '').strip()
        playlist_name_clean = playlist_name_raw.lower().replace(" ", "_").replace("/", "_")[:50] if playlist_name_raw else "unknown"

        for idx in range(num_chunks):
            chunk = tracks[idx * chunk_size : (idx + 1) * chunk_size]
            if len(chunk) < chunk_size:
                print(f"Warning: Chunk {idx+1} of playlist {playlist_id} has only {len(chunk)} tracks")
                continue

            parsed_tracks, subgenres, supergenres = parse_tracks(sp, chunk, genre_cache={})
            track_uris = [track['uri'] for track in parsed_tracks]

            fake_name = generate_fake_name()

            if is_artist:
                user_id = f"{playlist_name_clean[:11]}-{playlist_id}-{idx+1}"
            else:
                user_id = f"{fake_name}-{playlist_id}-{idx+1}"

            cluster_id =  int(-1)# once trained use  assign_user_cluster(supergenres) ad save t new dir to gen user to use in batch_upload_users.py :)
            user = User(
                user_id=user_id,
                top_tracks=track_uris,
                subgenres=subgenres,
                supergenres=supergenres
            )
            user.cluster_id = cluster_id

            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{user_id}.json")

            with open(output_path, "w") as f:
                json.dump(user.__dict__, f, indent=2)

            print(f"Saved {user_id} | Tracks: {len(track_uris)} | Subgenres: {len(subgenres)} | Supergenres: {len(supergenres)}")

    except Exception as e:
        print(f"Error processing playlist {playlist_id}: {e}")

def real_people():
    output_dir = "users_and_artists/combined"
    for pid in user_playlist_ids:
        make_users_from_playlist(pid, chunk_size=33, num_chunks=3, output_dir=output_dir, is_artist=False)

def artist_users():
    output_dir = "users_and_artists/combined"
    for pid in artist_playlist_ids:
        make_users_from_playlist(pid, chunk_size=25, num_chunks=2, output_dir=output_dir, is_artist=True)

if __name__ == '__main__':
    real_people()
    artist_users()
