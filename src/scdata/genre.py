from typing import Dict
from collections import Counter
import math

# Some somewhat arbitrary genre lists and mappings... there is no way to get this right. I try to
# follow the frequently genre tags that are frequently used on SoundCloud; some genres occur rarely,
# so I merge them with the most fitting super-genre. 
# 
# Especially for electronic stuff this seems difficult. Some of the most frequent genres are
# 'Techno' and 'Electronic', but other genres like 'Dance' occur frequently as well. Since some of
# these are subgenres of each other, we can either group everything as 'Electronic', or accept the
# fact that our list consists of genres from multiple (partially overlapping) levels of the
# hierarchy. Since I think the former would be too coarse-grained for me, I choose the latter.

# Try to unify some genres that at least refer to similar things. Also very subjective and noisy.
GENRE_MAP = {
    'alternative': 'alternative rock', # alias?
    'blues': 'jazz & blues', # rare, merge with super
    'chill': 'chillout', # alias
    'dance': 'dance & edm', # merge with super
    'dnb': 'drum & bass', # alias
    'drum and bass': 'drum & bass', # alias
    'edm': 'dance & edm', # merge with super
    'electro': 'electronic', # alias
    'electro house': 'house', # alias
    'electronica': 'electronic', # alias
    'eletrônica': 'electronic', # alias
    'folk': 'folk & singer-songwriter', # rare, merge with super
    'heavy metal': 'metal', # very rare
    'hip hop': 'hip-hop & rap', # alias
    'hip-hop': 'hip-hop & rap', # alias
    'hiphop': 'hip-hop & rap', # alias
    'hip hop/rap': 'hip-hop & rap', # alias
    'hip-hop/rap': 'hip-hop & rap', # alias
    'hiphop/rap': 'hip-hop & rap', # alias
    'house music': 'house', # alias
    'idm': 'electronic', # very rare
    'indie': 'indie rock', # alias?
    'jazz': 'jazz & blues', # merge with super
    'liquid d&b': 'drum & bass', # very rare
    'lofi hip hop': 'hip-hop & rap', # rare
    'melodic dubstep': 'dubstep', # rare
    'psychedelic trance': 'psytrance', # alias
    'progressive rock': 'rock', # very rare
    'rap/hip hop': 'hip-hop & rap', # alias
    'rap/hip-hop': 'hip-hop & rap', # alias
    'rap/hiphop': 'hip-hop & rap', # alias
    'rap': 'hip-hop & rap', # alias
    'r&b': 'r&b & soul', # merge with super
    'rnb': 'r&b & soul', # merge with super
    'singer-songwriter': 'folk & singer-songwriter', # merge with super
    'soul': 'r&b & soul', # merge with super
    'triphop': 'trip-hop', # alias
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
    'indie rock',
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
    'progressive house',
    'progressive trance',
    'psytrance',
    'r&b & soul',
    'reggae',
    'rock',
    'soundtrack',
    'synthwave',
    'techno',
    'trance',
    'trap',
    'trip-hop',
    'tropical house',
    'urban',
    'world',
])


def normalize_distr(weights: Dict[str, float]):
    weights = dict(weights)
    total = sum(weights.values()) + 0.0001
    return {
        'others': 0.0,
        **{key: value/total for key, value in weights.items()}
    }


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
    genre = genre.strip()
    genre = GENRE_MAP.get(genre, genre)

    if genre in IGNORE_GENRES:
        return 'ignore'
    else:
        return genre if genre in GENRES else 'others'


def genre_distr(genres):
    genres = Counter(map_genre(genre) for genre in genres)
    return normalize_distr(genres)


def pp_distr(distr):
    distr = list(distr.items())
    distr.sort(key=lambda item: item[1], reverse=True)
    return ', '.join(f'{genre} {prob*100:.2f}%' for genre, prob in distr)
