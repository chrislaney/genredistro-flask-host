import sys, os, time
from random import random

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import json

from cosine_similarity_test import build_fixed_vectors, build_dynamic_vectors, load_users, load_flat_genres, HARDCODED_SUPERGENRES


def gen_clusters(user_matrix, user_ids, clusterer, scaler=None):
    """
    Creates clusters based off of parameters above. Returns a dataframe with users and their respective clusters.
    Any sci-kit clusterer can be used.
    Primarily in use for testing different clustering methods, but can be used behind the scenes, if desired
    """
    if scaler is not None:
        user_matrix = scaler.fit_transform(user_matrix)
    clusterer.fit(user_matrix)
    mapping = pd.DataFrame({'User-Id': user_ids,
                            'Cluster': clusterer.labels_})
    return mapping, clusterer

def kmeans_tests(users, random_state, max_clusters, filename):
    """
    Test the kmeans clustering algorithm with a variety of parameters, data, and more;
    This will give us a good idea as to the best model to use for our product
    Parameters will be tested with: n_clusters (3 - 15), init (++ or random), and algorithm(lloyd or elkan)
    Creates a json object from a dictionary; the dictionary will consist of the format:
        genre_type(sub, super, dynamic) -> scaler (standard, none) -> num_clusters -> init (k-means++, random)
        -> algo(lloyd, elkan) -> results
    """
    output_dir = 'kmeans_tests'
    os.makedirs(output_dir, exist_ok=True)

    # get genres, users
    flat_genres=load_flat_genres()
    super_matrix, user_ids = build_fixed_vectors(users, HARDCODED_SUPERGENRES, field='supergenres')
    sub_matrix, _ = build_fixed_vectors(users, flat_genres, field='subgenres')
    dynamic_matrix, _ = build_dynamic_vectors(users)
    scaler = StandardScaler()

    genre_type = [('sub', sub_matrix), ('super', super_matrix), ('dynamic', dynamic_matrix)]
    num_clusters = range(3, max_clusters + 1)
    init = ['k-means++', 'random'] # ++ seems to be better than random, almost always
    #algo = ['lloyd', 'elkan'] Seems to not matter
    scalers = [('standard', scaler), ('None', None)]
    max_ss = {}
    for cluster_count in num_clusters: # we want to find the max ss for each cluster count
        max_ss[cluster_count] = -10
    return_dict = {}

    for genre, matrix in genre_type:
        return_dict[genre] = {}
        for scaler_label, scaler_type in scalers:
            return_dict[genre][scaler_label] = {}
            for cluster_count in num_clusters:
                return_dict[genre][scaler_label][cluster_count] = {}
                for initialization in init:
                    kmeans = KMeans(cluster_count,
                                    init=initialization,
                                    random_state=random_state,)
                                    #algorithm=algorithm)
                    _, kmeans = gen_clusters(matrix, user_ids, kmeans, scaler_type)

                    labels = kmeans.labels_
                    #inertia measures how close clusters are
                    inertia = kmeans.inertia_
                    #silhouette score measures how well-separated clusters are; 0.7 is something to aim for
                    ss = silhouette_score(matrix, labels)
                    if ss > max_ss[cluster_count]:
                        max_ss[cluster_count] = ss
                        print(f"Max ss of {ss} found with {cluster_count} clusters with the following parameters:\n"
                                      f"Genre:{genre}; init:{initialization}; scaler:{scaler_label};")
                    return_dict[genre][scaler_label][cluster_count][initialization] = {
                        'inertia': inertia,
                        'silhouette_score': ss,
                        'iterations': kmeans.n_iter_
                    }
    output_path = os.path.join(output_dir, f"{filename}.json")
    with open(output_path, 'w') as f:
        json.dump(return_dict, f, indent=2)
    print(f'Saved to {output_path}')
    return

def dbscan_test(users, random_state, filename):
    """
    Function to test dbscan algorithm with variety of parameters to give us idea of what to use in production
    Consider using city-block distance?
    Should 100% time this; prob takes forever
    """

    output_dir = 'dbscan_tests'
    os.makedirs(output_dir, exist_ok=True)

    flat_genres = load_flat_genres()
    super_matrix, user_ids = build_fixed_vectors(users, HARDCODED_SUPERGENRES, field='supergenres')
    sub_matrix, _ = build_fixed_vectors(users, flat_genres, field='subgenres')
    dynamic_matrix, _ = build_dynamic_vectors(users)
    scaler = StandardScaler()
    ret_dict = {}

    genre_type = [ ('sub', sub_matrix),('super', super_matrix), ('dynamic', dynamic_matrix)]
    metrics = ['euclidean', 'cosine']
    eps_range = range(1, 22, 2)
    eps_list = [x * 0.1 for x in eps_range]
    min_samples_range = range(2, 9)#range(2, 10)
    leaf_range = range(10, 61, 10)
    p_range = range(1, 14)
    scalers = [('standard', scaler), ('None', None)]
    max_ss = -10
    for genre, matrix in genre_type:
        ret_dict[genre] = {}
        for eps in eps_list:
            ret_dict[genre][eps] = {}
            for min_sample in min_samples_range:
                ret_dict[genre][eps][min_sample] = {}
                for p in p_range:
                    ret_dict[genre][eps][min_sample][p] = {}
                    for scaler_label, scale in scalers:
                        ret_dict[genre][eps][min_sample][p][scaler_label] = {}
                        for metric in metrics:


                            db_scan = DBSCAN(eps=eps,
                                             min_samples=min_sample,
                                             metric=metric,
                                             p=p)
                            #print(f'Calculating cluster for genre:{genre}, eps:{eps}, '
                            #      f'min_sample:{min_sample}, p:{p}')
                            _, db_scan = gen_clusters(matrix, user_ids, db_scan, scale)

                            labels = db_scan.labels_
                            try:
                                ss = silhouette_score(matrix, labels)
                            except:
                                ret_dict[genre][eps][min_sample][p][scaler_label][metric] = {
                                    'status': 'FAIL'
                                }
                                continue
                            if ss > max_ss:
                                max_ss = ss
                                print(f"Max ss of {ss} found with the following parameters:\n"
                                      f"Genre:{genre}; eps:{eps}; p:{p}; scaler:{scaler_label}; metric:{metric}")
                            ret_dict[genre][eps][min_sample][p][scaler_label][metric] = {
                                'silhouette_score': ss,
                            }
    output_path = os.path.join(output_dir, f"{filename}.json")
    with open(output_path, 'w') as f:
        json.dump(ret_dict, f, indent=2)
    print(f'Saved to {output_path}')
    return

# This needs to be put in a cluster class
# Returns an n/dimensional vector by summing a dataframe's distances, u kno dat shi
def get_cluster_centroid(matrix, ):
    pass



if __name__ == '__main__':
    gen_users_dir = "generated_users"
    top_artist_user_dir = "top_artist_users"
    gen_users = load_users(gen_users_dir)
    top_artist_users = load_users(top_artist_user_dir)
    flat_genres = load_flat_genres()
    random_state = 10 #random state for testing differences in scaling, etc. to see differences
    super_matrix, user_ids = build_fixed_vectors(gen_users, HARDCODED_SUPERGENRES, field='supergenres')
    top_super_matrix, artist_ids = build_fixed_vectors(top_artist_users, HARDCODED_SUPERGENRES, field='supergenres')
    kmeans = KMeans(n_clusters=8, n_init=30)
    labeled_ids, kmeans = gen_clusters(super_matrix, user_ids, kmeans, None)
    labeld_users = super_matrix.join(labeled_ids)
    scaler = StandardScaler()

    #scaled_super_matrix = scaler.fit_transform(super_matrix)
    #scaled_kmeans = KMeans(n_clusters=10,random_state=random_state)
    #dynamic_matrix, dynamic_ids = build_dynamic_vectors(gen_users)




    #dbscan = DBSCAN(eps=0.5, min_samples=5)
    #df, dbscan = gen_clusters(top_super_matrix, artist_ids, dbscan, scaler)
    #print(df['Cluster'].unique())
    #print(df[df['Cluster'] == -1].count())


    #print(dynamic_ids)
    #print(user_ids)
    #kmeans_tests(gen_users, random_state, 15, 'gen_users')
    #kmeans_tests(top_artist_users, random_state, 15, 'top_artist_users')
    #dbscan_test(top_artist_users, random_state, 'top_artist_users')
    #dbscan_test(gen_users, random_state, 'gen_users')
    #dbscan = DBSCAN()
    #df, dbscan = gen_clusters(super_matrix, user_ids, dbscan)
    #print(df)










