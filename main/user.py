from utils import parse_tracks, load_genre_cache, get_top_100, fetch_top_tracks
from datetime import datetime

class User:
    def __init__(self, user_id, display_name, top_tracks, subgenres, supergenres):
        self.user_id = user_id
        self.display_name = display_name
        self.top_tracks = top_tracks  # Only track URIs stored
        self.subgenres = subgenres
        self.supergenres = supergenres
        self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
        self.cluster = -1

    def __repr__(self):
        return (f"User(user_id={self.user_id}, "
                f"top_tracks_count={len(self.top_tracks)}, "
                f"subgenres_count={len(self.subgenres)}, "
                f"supergenres_count={len(self.supergenres)})")

    @classmethod
    def from_spotify(cls, sp, genre_cache, num_tracks=100, time_range='long_term'): ##
        """
        Create a User object from Spotify API data

        Args:
            sp: Authenticated Spotify client
            genre_cache: Dictionary of cached artist genres
            num_tracks: Number of top tracks to fetch
            time_range: Time range for top tracks ('short_term', 'medium_term', 'long_term')

        Returns:
            User: A new User object populated with Spotify data
        """
        # Get basic user profile
        profile = sp.current_user()
        user_id = profile['id']
        display_name = profile['display_name']
        
        # Get top tracks and digest
        tracks_raw = fetch_top_tracks(sp, num_tracks=num_tracks, time_range=time_range)
        parsed_tracks, subgenre_distro, supergenre_distro = parse_tracks(sp, tracks_raw, genre_cache)

        top_tracks_uris = [track['uri'] for track in parsed_tracks]

        return cls(
            user_id=user_id,
            display_name = display_name,
            top_tracks=top_tracks_uris,
            subgenres=subgenre_distro,
            supergenres=supergenre_distro
        )

    @classmethod
    def from_dynamodb(cls, user_data):
        """
        Create a User object from DynamoDB data

        Args:
            user_data: Dictionary of user data from DynamoDB

        Returns:
            User: A User object populated with data from DynamoDB
        """
        user = cls(
            user_id=user_data.get('user_id'),
            display_name=user_data.get('display_name'),
            top_tracks=user_data.get('top_tracks', []),
            subgenres=user_data.get('subgenres', {}),
            supergenres=user_data.get('supergenres', {})
        )

        # Add any additional attributes from DynamoDB
        for key, value in user_data.items():
            if not hasattr(user, key):
                setattr(user, key, value)

        return user