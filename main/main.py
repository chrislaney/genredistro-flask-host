import os
from utils import load_genre_cache, parse_tracks, fetch_top_tracks
from playlist_utils import parse_playlist, get_all_user_playlist_ids, generate_similarity_playlists, get_playlist_distro
from clustering import assign_user_cluster
from flask import Flask, session, url_for, request, jsonify, Response, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.cache_handler import FlaskSessionCacheHandler
from werkzeug.utils import redirect
from user import User
from db_handler import DynamoDBHandler
from dotenv import load_dotenv
from datetime import datetime

print("Flask is running THIS file:", __file__)
# Create the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

# Load environment variables from .env file
load_dotenv()

# Get AWS credentials from environment variables
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_KEY')

# Initialize DynamoDB handler with environment variables
db_handler = DynamoDBHandler(
    region_name=AWS_REGION,
    aws_access_key=AWS_ACCESS_KEY,
    aws_secret_key=AWS_SECRET_KEY
)

# Create necessary tables if they don't exist
try:
    db_handler.create_tables_if_not_exist()
except Exception as e:
    print(f"Error setting up DynamoDB tables: {e}")

# Spotify OAuth Configuration
client_id = os.environ.get('SPOTIFY_CLIENT_ID')
client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')
#need all the scopes listed to fetch data wanted and create platylists 
scope = 'user-library-read, user-top-read, playlist-read-private, playlist-modify-private, playlist-modify-public'

# OAuth handler
cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)

# ensure valid token and refresh if needed
def ensure_token():
    token_info = session.get("token_info", None)

    if not token_info:
        raise Exception("No token found. User must log in.")

    if sp_oauth.is_token_expired(token_info):
        print("Token expired, refreshing...")
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  # Save updated token

    return token_info

# ensure token or redirect to login
def ensure_token_or_redirect():
    try:
        return ensure_token()
    except Exception:
        return redirect(sp_oauth.get_authorize_url())

# Home route - Checks login and redirects
@app.route('/')
def home():
    # return redirect(url_for('get_user'))
    return render_template('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Callback for Spotify OAuth, stores token info in flask session
@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info  # Save token in session
    return redirect(url_for('loading'))

@app.route('/loading')
def loading():
    return render_template('loading.html')


# Get user data and genre distributions
@app.route('/get_user')
def get_user():
    token_info = ensure_token_or_redirect()
    if isinstance(token_info, dict):
        try:
            sp = Spotify(auth=token_info['access_token'])
            genre_cache = load_genre_cache()
            
            # Get Spotify user ID
            spotify_user_id = sp.current_user()['id']

           # Try to get user from DynamoDB first
            existing_user_data = db_handler.get_user_data(spotify_user_id)
            
            # Check if we need to refresh the user data (e.g., if it's more than a day old)
            refresh_user_data = True
            if existing_user_data:
                
                # Check the last_updated timestamp
                current_time = datetime.now()
                last_updated = datetime.fromisoformat(existing_user_data.get('last_updated', '2000-01-01T00:00:00'))
                time_difference = current_time - last_updated
                
                # Only refresh if more than 24 hours have passed
                if time_difference.total_seconds() < 24 * 3600:  # Less than 24 hours
                    refresh_user_data = False
                    print(f"Using cached user data (last updated: {last_updated})")

            if refresh_user_data:
                # Create user object from Spotify API
                user = User.from_spotify(sp, genre_cache)
                # Assign cluster 
                user.cluster_id = int(assign_user_cluster(user.supergenres))
                # Save to DynamoDB
                db_handler.save_user_data(user.__dict__)
                # Also save top tracks separately
                db_handler.save_user_tracks(
                    user_id=user.user_id,
                    tracks_data=user.top_tracks,
                    time_range='medium_term'  # Default time range
                )


                # Sort subgenres and supergenres before passing to template
                sorted_subgenres = dict(sorted(user.subgenres.items(), key=lambda item: item[1], reverse=True))
                sorted_supergenres = dict(sorted(user.supergenres.items(), key=lambda item: item[1], reverse=True))

                # Update user object with sorted genres
                user.subgenres = sorted_subgenres
                user.supergenres = sorted_supergenres


                return render_template('dashboard.html', user=user.__dict__)
            else:

                # Sort subgenres and supergenres from the cached data
                existing_user_data['subgenres'] = dict(sorted(existing_user_data['subgenres'].items(), key=lambda item: item[1], reverse=True))
                existing_user_data['supergenres'] = dict(sorted(existing_user_data['supergenres'].items(), key=lambda item: item[1], reverse=True))
                return render_template('dashboard.html', user=existing_user_data)


        except Exception as e:
            print(f"Error fetching user data: {e}")
            return jsonify({'error': str(e)})
    else:
        return token_info  # Redirect response


@app.route('/get_user_data/<user_id>')
def get_user_data(user_id):
    try:
        # Try to get user from DynamoDB
        user_data = db_handler.get_user_data(user_id)
        
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
            
        # Return user data with all the necessary fields
        return jsonify(user_data)
        
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return jsonify({'error': str(e)}), 500

# Get playlist data
@app.route('/get_playlist/<playlist_id>')
def get_playlist_data(playlist_id):
    #token_info = ensure_token_or_redirect()
    try:
        # fetch from Spotify API
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )

        sp = Spotify(client_credentials_manager=client_credentials_manager)

        response = get_playlist_distro(playlist_id, sp)

        return jsonify(response)
    except Exception as e:
        print(f"Error fetching playlist data: {e}")
        return jsonify({'error': str(e)})

@app.route('/show_playlist/<playlist_id>')
def show_playlist_data(playlist_id):
    #token_info = ensure_token_or_redirect()
    try:
        # fetch from Spotify API
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )

        sp = Spotify(client_credentials_manager=client_credentials_manager)

        response = get_playlist_distro(playlist_id, sp)

        return render_template('playlistdashboard.html', playlist=response)
    except Exception as e:
        print(f"Error fetching playlist data: {e}")
        return jsonify({'error': str(e)})

# Get user's analyzed playlists
@app.route('/get_user_playlists')
def get_user_playlists():
    token_info = ensure_token_or_redirect()
    if isinstance(token_info, dict):
        try:
            sp = Spotify(auth=token_info['access_token'])
            user_id = sp.current_user()['id']
            
            # Get all analyzed playlists for this user from DynamoDB
            playlists = db_handler.get_user_playlists(user_id)
            
            return jsonify({
                "user_id": user_id,
                "playlists": playlists
            })
            
        except Exception as e:
            print(f"Error fetching user playlists: {e}")
            return jsonify({'error': str(e)})
    else:
        return token_info  # Redirect response

# Get user's top tracks for a specific time range
@app.route('/get_top_tracks/<time_range>')
def get_top_tracks(time_range):
    if time_range not in ['short_term', 'medium_term', 'long_term']:
        return jsonify({'error': 'Invalid time range. Use short_term, medium_term, or long_term'})
        
    token_info = ensure_token_or_redirect()
    if isinstance(token_info, dict):
        try:
            sp = Spotify(auth=token_info['access_token'])
            user_id = sp.current_user()['id']
            
            # Try to get from database first
            tracks_data = db_handler.get_user_latest_tracks(user_id, time_range)
            
            if tracks_data:
                return jsonify({**tracks_data, "source": "database"})
            
            genre_cache = load_genre_cache()
            top_tracks_raw = fetch_top_tracks(sp, num_tracks=50, time_range=time_range)
            
            parsed_tracks, subgenre_distro, supergenre_distro = parse_tracks(
                sp, top_tracks_raw, genre_cache
            )
            
            # Save to database
            entry_id = db_handler.save_user_tracks(
                user_id=user_id,
                tracks_data=parsed_tracks,
                time_range=time_range
            )
            
            response = {
                "entry_id": entry_id,
                "user_id": user_id,
                "time_range": time_range,
                "tracks": parsed_tracks,
                "subgenre_distribution": subgenre_distro,
                "supergenre_distribution": supergenre_distro,
                "source": "spotify_api"
            }
            
            return jsonify(response)
            
        except Exception as e:
            print(f"Error fetching top tracks: {e}")
            return jsonify({'error': str(e)})
    else:
        return token_info  # Redirect response

@app.route('/generate_similarity_playlists')
def similarity_playlists():
    token_info = ensure_token_or_redirect()
    if isinstance(token_info, dict):
        sp = Spotify(auth=token_info['access_token'])
        manual = request.args.get("manual") == "true"
        playlist_length = int(request.args.get("length", 100))

        if manual:
            user_vector = {"Pop": 0.2, "Hip Hop": 0.3, "Electronic": 0.1}
        else:
            genre_cache = load_genre_cache()
            user = User.from_spotify(sp, genre_cache)
            user_vector = user.supergenres
        playlists = generate_similarity_playlists(sp, user_vector, db_handler, total_songs=playlist_length)

        return jsonify({
            group: pl['external_urls']['spotify'] if pl else None
            for group, pl in playlists.items()
        })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run()