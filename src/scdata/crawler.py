from typing import Dict
import random
import json
from collections import Counter
import heapq
import math

import aiohttp
import aiohttp.web

from scdata import SoundCloudAPI

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

def penalized_bhattacharyya_dist(p: Dict[str, float], q: Dict[str, float]):
    p_keys = set(p.keys())
    q_keys = set(q.keys())

    keys = p_keys.union(q_keys)

    s = sum(math.sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in keys)

    # Penalize empty genre sets (now it's not bhattacharyya distance anymore)
    #j = len(p_keys.intersection(q_keys)) / (len(keys) + 0.001)

    return -math.log(s + 0.001) #* j


def map_distr_genre(genre):
    if genre is None or genre.lower() not in GENRES:
        return 'others'
    else:
        return genre.lower()


def playlist_distr(playlist_info):
    genres = Counter(map_distr_genre(track_info['genre'])
                     for track_info in playlist_info.get('tracks', [])
                     if 'genre' in track_info)
                     
    return normalize_distr(genres)


class SoundCloudCrawler:
    def __init__(self,
                 api: SoundCloudAPI,
                 max_candidates: int = 100000,
                 min_track_likes: int = 30,
                 min_track_plays: int = 200):
        self.api = api
        self.max_candidates = max_candidates
        self.min_track_likes = min_track_likes
        self.min_track_plays = min_track_plays

        self.visited_tracks = set()
        self.visited_playlists = set()

        self.candidate_playlists = {}

        self.tracks = {}

    def save_state(self, path):
        state = {
            'max_candidates': self.max_candidates,
            'min_track_likes': self.min_track_likes,
            'min_track_plays': self.min_track_plays,
            'visited_tracks': list(self.visited_tracks),
            'visited_playlists': list(self.visited_playlists),
            'candidate_playlists': self.candidate_playlists,
            'tracks': self.tracks,
        }                 

        with open(path, 'w') as f:
            json.dump(state, f, indent=4)

    def load_state(self, path):
        with open(path) as f:
            state = json.load(f)

        self.max_candidates = state['max_candidates']
        self.min_track_likes = state['min_track_likes']
        self.min_track_plays = state['min_track_plays']
        self.visited_tracks = set(state['visited_tracks'])
        self.visited_playlists = set(state['visited_playlists'])
        self.candidate_playlists = state['candidate_playlists']
        self.tracks = state['tracks']

    def is_complete_track_info(self, info):
        # Some info may be incomplete, e.g. the playlist.tracks infos are complete only for the
        # first couple of elements I think.
        required_keys = ['artwork_url',
                         'license',
                         'likes_count',
                         'playback_count',
                         'title',
                         'genre',
                         'media']
        return all(key in info for key in required_keys)

    def is_free(self, license):
        return license != 'all-rights-reserved'

    def is_track_okay(self, track):
        if not self.is_complete_track_info(track):
            return False
        #if not self.is_free(track['license'])
            #return False
        if track['likes_count'] is None or track['likes_count'] < self.min_track_likes:
            return False
        if track['playback_count'] is None or track['playback_count'] < self.min_track_plays:
            return False

        return True

    def print_info(self):
        genres = Counter(info['genre'] for info in self.tracks.values())
        genres_free = Counter(info['genre'] for info in self.tracks.values()
                              if self.is_free(info['license']))
        licenses = Counter(info['license'] for info in self.tracks.values())
        free_count = sum(1 if self.is_free(info['license']) else 0
                         for info in self.tracks.values())

        print('==============================================')
        print(f'#visited_tracks={len(self.visited_tracks)}')
        print(f'#visited_playlists={len(self.visited_playlists)}')
        print(f'#candidate_playlists={len(self.candidate_playlists)}')
        print(f'#tracks={len(self.tracks)}')
        if len(self.tracks) > 0:
            print(f'#tracks_free={free_count} ({free_count/len(self.tracks)*100:.2f}%)')
        print(f'genres={genres.most_common()[:10]}')
        print(f'genres_free={genres_free.most_common()[:10]}')
        print(f'genres_normalized={ {k:round(v,2) for k,v in self.get_tracks_distr().items()} }')
        print(f'genres_free_normalized={ {k:round(v,2) for k,v in self.get_free_tracks_distr().items()} }')
        print(f'licenses={licenses.most_common()[:10]}')
        print('==============================================')

    def get_track_score(self, info):
        return int('license' in info and self.is_free(info['license'])) 

    def get_playlist_score(self, info):
        if not info.get('tracks', []):
            return 0.0
        return sum(self.get_track_score(track_info) for track_info in info.get('tracks', []))

        # Not sure if I want to normalize. Having long playlists helps getting more hits, but might
        # degrade quality.
        #sum(int('license' in info) for track_info in info.get('tracks', []))

    def get_tracks_distr(self):
        genres_free = Counter(map_distr_genre(info.get('genre')) for info in self.tracks.values())
        return normalize_distr(genres_free)

    def get_free_tracks_distr(self):
        genres_free = Counter(map_distr_genre(info.get('genre')) for info in self.tracks.values()
                              if self.is_free(info['license']))
        return normalize_distr(genres_free)

    def add_candidate_playlist(self, playlist_info):
        if playlist_info['id'] not in self.visited_playlists:
            self.candidate_playlists[playlist_info['id']] = {
                'free': self.get_playlist_score(playlist_info),
                'genres': playlist_distr(playlist_info),
            }

            for track_info in playlist_info.get('tracks', []):
                if self.is_track_okay(track_info):
                    self.tracks[track_info['id']] = track_info

    async def add_candidate_playlist_url(self, soundcloud_url: str):
        info = await self.api.resolve(soundcloud_url) 
        self.add_candidate_playlist(info)

    async def visit_playlist(self, playlist_id):
        if playlist_id in self.visited_playlists:
            return
        self.visited_playlists.add(playlist_id)

        playlist_info = await self.api.playlist(playlist_id)
        track_scores = []

        print(playlist_distr(playlist_info),
              penalized_bhattacharyya_dist(self.get_free_tracks_distr(), playlist_distr(playlist_info)))

        for track_info in playlist_info.get('tracks', [])[:50]:
            if track_info['id'] in self.visited_tracks:
                continue
            self.visited_tracks.add(track_info['id'])

            if not self.is_complete_track_info(track_info):
                track_info = await self.api.track(track_info['id'])
                if not self.is_complete_track_info(track_info):
                    continue

            if self.is_track_okay(track_info):
                self.tracks[track_info['id']] = track_info

            track_score = self.get_track_score(track_info)
            track_scores.append((track_info, track_score))

        # For the most free tracks added, add the playlists that they are in as candidates.
        # I've tried doing this for all new tracks, but it takes too long to do all the API calls.
        track_scores.sort(key=lambda item: item[1], reverse=True)
        for track_info in track_scores[:5]:
            for playlist_info in await self.api.track_playlists(track_info[0]['id']):
                self.add_candidate_playlist(playlist_info)

        # Try to expand our tastes a bit
        likers = await self.api.playlist_likers(playlist_id)
        for liker in likers[:10]:
            for likes in await self.api.user_likes(liker['id']):
                if 'playlist' in likes:
                    self.add_candidate_playlist(likes['playlist'])

    async def crawl_step(self, mode):
        if not self.candidate_playlists:
            return False

        candidates = list(self.candidate_playlists.items())

        if mode == 'free':
            # Prefer playlists that have more free licenses
            weights = list(item[1]['free']**6 for item in candidates)
        elif mode == 'genre':
            # Prefer playlists that have different genres from what we have so far
            free_tracks_distr = self.get_free_tracks_distr()
            weights = list(item[1]['free']**0.5 + penalized_bhattacharyya_dist(free_tracks_distr, item[1]['genres'])
                           for item in candidates)

        chosen_id = random.choices(list(item[0] for item in candidates), weights=weights)[0]

        print(f'Mode {mode}: Playlist {chosen_id}, free {self.candidate_playlists[chosen_id]["free"]}')

        del self.candidate_playlists[chosen_id]
        await self.visit_playlist(chosen_id)

        return True

    async def crawl(self,
                    max_steps,
                    print_info_steps=1,
                    save_steps=10,
                    save_path=None):
        for step_num in range(max_steps):
            try:
                if save_path is not None and step_num % save_steps == 0:
                    self.save_state(save_path)
                if print_info_steps > 0 and step_num % print_info_steps == 0:
                    self.print_info()

                if not await self.crawl_step(mode='free'):
                    return
                if not await self.crawl_step(mode='genre'):
                    return
            except Exception as e:
                print(f'Caught exception {e}')
