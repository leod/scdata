from typing import Dict
from collections import Counter
import math

# Some somewhat arbitrary genre lists and mappings... there is no way to get this right. I try to
# follow the frequently genre tags that are frequently used on SoundCloud.
# 
# Especially for electronic stuff this seems difficult. Some of the most frequent genres are
# 'Techno' and 'Electronic', but other genres like 'Dance' occur frequently as well. Since some of
# these are subgenres of each other, we can either group everything as 'Electronic', or accept the
# fact that our list consists of genres from multiple (partially overlapping) levels of the
# hierarchy. Since I think the former would be too coarse-grained for me, I choose the latter.

# Try to unify some genres that at least refer to similar things. Also very subjective.
GENRE_MAP = {
    'blues': 'jazz & blues',
    'chill': 'chillout',
    'dance': 'dance & edm',
    'dnb': 'drum & bass',
    'drum and bass': 'drum & bass',
    'edm': 'dance & edm',
    'electro': 'electronic',
    'electro house': 'house',
    'electronica': 'electronic',
    'eletrônica': 'electronic',
    'folk': 'folk & singer-songwriter',
    'hip hop': 'hip-hop & rap',
    'hip-hop': 'hip-hop & rap',
    'hiphop': 'hip-hop & rap',
    'hip hop/rap': 'hip-hop & rap',
    'hip-hop/rap': 'hip-hop & rap',
    'hiphop/rap': 'hip-hop & rap',
    'house music': 'house',
    'jazz': 'jazz & blues',
    'lofi hip hop': 'hip-hop & rap',
    'melodic dubstep': 'dubstep',
    'rap/hip hop': 'hip-hop & rap',
    'rap/hip-hop': 'hip-hop & rap',
    'rap/hiphop': 'hip-hop & rap',
    'rap': 'hip-hop & rap',
    'r&b': 'r&b & soul',
    'rnb': 'r&b & soul',
    'singer-songwriter': 'folk & singer-songwriter',
    'soul': 'r&b & soul',
    'triphop': 'trip-hop',
}

# Ignore some genres for this project.
IGNORE_GENRES = set([
    'cover',
    'free download',
    'freedownload',
    'hoodinternet',
    'music',
    'podcast',
    'public radio',
    'remix',
    'storytelling',
    'talk',
    'vlogmusic',
])

GENRES = set([
    'acoustic',
    'alternative',
    'alternative rock',
    'ambient',
    'beats',
    'chillout',
    'chillstep',
    'chiptune',
    'cinematic',
    'classical',
    'country',
    'dance & edm',
    'dancehall',
    'deep house',
    'disco',
    'downtempo',
    'drum & bass',
    'drumstep',
    'dub',
    'dubstep',
    'electronic',
    'experimental',
    'folk',
    'folk & singer-songwriter',
    'funk',
    'gospel',
    'heavy metal',
    'hip-hop & rap',
    'house',
    'idm',
    'indie',
    'instrumental',
    'jazz & blues',
    'latin',
    'lofi',
    'mashup',
    'metal',
    'metalcore',
    'minimal',
    'nightcore',
    'noise',
    'orchestral',
    'piano',
    'pop',
    'progressive rock',
    'psytrance',
    'r&b & soul',
    'reggae',
    'rock',
    'soundtrack',
    'synthwave',
    'techno',
    'trap',
    'trip-hop',
    'urban',
    'world',
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
    if genre == '' or genre is None:
        return 'unknown'

    genre = genre.lower()
    genre = GENRE_MAP.get(genre, genre)

    if genre in IGNORE_GENRES:
        return 'ignore'
    else:
        return genre if genre in GENRES else 'others'


def genre_distr(genres):
    genres = Counter(map_genre(genre) for genre in genres)
    return normalize_distr(genres)


def pp_distr(distr):
    return str({k: round(v, 4) for k, v in distr.items()})
