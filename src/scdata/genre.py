from typing import Dict
import math

GENRES = set([
    'classical',
    'instrumental',
    'ambient',
    'rock',
    'alternative rock',
    'progressive rock',
    'heavy metal',
    'metal',
    'metalcore',
    'techno',
    'idm',
    'dubstep',
    'house',
    'rap',
    'hip-hop',
    'hip hop',
    'hip-hop & rap',
    'indie',
    'pop',
    'noise',
    'cinematic',
    'orchestral',
    'piano',
    'lofi',
    'folk',
    'experimental',
    'electronic',
    'jazz',
    'blues',
    'rnb',
    'soul',
    'r&b',
    'r&b & soul',
    'country',
])


def normalize_distr(weights: Dict[str, float]):
    weights = dict(weights)
    if 'others' not in weights:
        weights['others'] = 0.0 if len(weights) else 1.0
    total = sum(weights.values())
    return {key: value/total for key, value in weights.items()}


def kl_div(p: Dict[str, float], q: Dict[str, float]):
    s = 0.0
    for genre, prob_q in q.items():
        if genre in p:
            s += p[genre] * math.log(p[genre] / prob_q)

    return s


def bhattacharyya_dist(p: Dict[str, float], q: Dict[str, float]):
    p_keys = set(p.keys())
    q_keys = set(q.keys())

    keys = p_keys.union(q_keys)

    s = sum(math.sqrt(p.get(k, 0.001) * q.get(k, 0.001)) for k in keys)

    return -math.log(s + 0.001)


def map_genre(genre):
    if genre is None or genre.lower() not in GENRES:
        return 'others'
    else:
        return genre.lower()
