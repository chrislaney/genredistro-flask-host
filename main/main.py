import os
from .utils import parse_saved_tracks, load_genre_cache, get_top_100
from flask import Flask, session, url_for, request, jsonify, Response, render_template

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from werkzeug.utils import redirect
from .user import User



#this creates the flask app
app = Flask(__name__)

#this secret key is to secure the flask session so data cannot be tampered with between running and display on webpage
#in a production env you want this to be a fixed string stored in an env variable or in a secure cred store
app.config['SECRET_KEY'] = os.urandom(64)

#these are got when you create a spotify developer app on spotify.com
client_id = '222e77fb40c5487186ac94b242ef4175'
client_secret = '17b609e97e204cdfaa6de949bfcd6f21'
redirect_uri = 'https://genre-distro.onrender.com/callback'

#need all the scopes listed to fetch data wanted
scope = 'user-library-read, user-top-read, playlist-read-private' #to add more scopes you just seperate them within the string with a comma

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)

#instance of spotify client, with the oauth credentials
sp = Spotify(auth_manager=sp_oauth)


#END POINTS -------------------------------

#directs user to homepage, and makes them log in if needed
@app.route('/')
def home():
    # cache_handler.get_cached_token checks to see if user has a prexisting cached token, if not directs them to auth
    # if not sp_oauth.validate_token(cache_handler.get_cached_token()):
    #     #this if not checks if user is not logged in, and directs them to auth_url
    #     auth_url = sp_oauth.get_authorize_url()
    #     return redirect(auth_url) #if user not logged in, directs them to auth
    # return redirect(url_for('get_data')) #if user is logged in, fires get_playlists
    return render_template('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

#auth manager, refreshes token upon expiration. This is what provides a continuous experience and no need to manually fetch token
@app.route('/callback')
def callback():
    # sp_oauth.get_access_token(request.args['code'])
    # return redirect(url_for('get_data'))
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('loading'))  # Go to loading screen

@app.route('/loading')
def loading():
    return render_template('loading.html')


@app.route('/get_data')
def get_data():

    if not sp_oauth.validate_token(cache_handler.get_cached_token()): #This token validation could/should be its own method
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    try:
        genre_cache = load_genre_cache()
        user = User.from_spotify(sp, genre_cache)  # Create user using class method

        top_subgenres = sorted(user.subgenres.items(), key=lambda x: x[1], reverse=True)[:10]
        top_supergenres = sorted(user.supergenres.items(), key=lambda x: x[1], reverse=True)[:10]

        user_data = {
            "user_id": user.user_id,
            "top_tracks": user.top_tracks,  # Already a list, no need to modify
            #"subgenres": list(user.subgenres.items()),  # Convert dict to list of tuples
            "subgenres": top_subgenres,  # Convert dict to list of tuples
            "supergenres": top_supergenres  # Convert dict to list of tuples
        }

        print("top subgenres ferda!!")
        print(top_subgenres)
        # return jsonify(user_data)
        # return jsonify({"user": user.__dict__})
        # return render_template('dashboard.html', user=user.__dict__)
        print("Static folder path:", os.path.abspath('static'))
        return render_template('dashboard.html', user=user_data)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# this runs the flask app - it is created at the top of the file
if __name__ == '__main__':
    # app.run(debug=True)
    app.run()
