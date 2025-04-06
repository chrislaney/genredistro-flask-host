# clustering.py
import random
import numpy as np



def assign_user_cluster(user_vector, num_clusters=50):
    """
    Placeholder for user cluster assignment.
    
    Args:
        user_vector (dict): User genre distribution vector.
        num_clusters (int): Number of clusters, can prob delete thjis.
    
    Returns:
        int: Cluster ID
    """
    return int(random.randint(0, num_clusters - 1)) #ENSURETHIS IS AN INT


# --- Full supergenre vector keys
SUPERGENRES = [
    "Pop", "Hip Hop", "Rock", "Metal", "Indie",
    "Electronic", "Jazz", "R&B", "Latin", "Country",
    "Classical", "Folk", "Punk", "Reggae", "World"
]

# Fake placeholder cluster profiles (replace with real centroids later)
CLUSTER_VECTORS = {
    0: {"Pop": 0.7, "Hip Hop": 0.1, "Electronic": 0.1, "Latin": 0.1},
    1: {"Rock": 0.5, "Indie": 0.3, "Punk": 0.1, "Folk": 0.1},
    2: {"Hip Hop": 0.7, "R&B": 0.2, "Electronic": 0.1},
    3: {"Jazz": 0.4, "Classical": 0.3, "World": 0.3},
    4: {"Metal": 0.5, "Rock": 0.3, "Punk": 0.2},
}

def cosine_similarity(vec1, vec2, all_keys):
    v1 = np.array([vec1.get(k, 0.0) for k in all_keys])
    v2 = np.array([vec2.get(k, 0.0) for k in all_keys])
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    return float(np.dot(v1, v2) / (norm1 * norm2)) if norm1 and norm2 else 0.0

# using cosine sim atm but swithc out if better method
def get_similar_clusters(user_vector, top_n=1):
    similarities = []
    for cluster_id, cluster_vector in CLUSTER_VECTORS.items():
        sim = cosine_similarity(user_vector, cluster_vector, SUPERGENRES)
        similarities.append((cluster_id, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    most_similar = similarities[:top_n]
    least_similar = similarities[-top_n:] if top_n < len(similarities) else similarities[top_n:]
    return [(-1, 1.0)], [(-1, 0.0)]# most_similar,least_similar