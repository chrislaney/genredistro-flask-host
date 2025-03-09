# user.py
from utils import parse_saved_tracks, load_genre_cache, get_top_100

class User:
    def __init__(self, user_id, top_tracks, subgenres, supergenres):
        self.user_id = user_id
        self.top_tracks = top_tracks
        self.subgenres = subgenres
        self.supergenres = supergenres

    def __repr__(self):
        return (f"User(user_id={self.user_id}, "
                f"top_tracks={self.top_tracks[:3]}..., "
                f"subgenres={self.subgenres}, "
                f"supergenres={self.supergenres})")

    @classmethod
    def from_spotify(cls, sp, genre_cache):
        user_id = sp.current_user()['id']
        top_100_raw = get_top_100(sp)
        parsed_tracks, subgenre_distro, supergenre_distro = parse_saved_tracks(sp, top_100_raw, genre_cache)

        return cls(user_id, parsed_tracks, subgenre_distro, supergenre_distro)
