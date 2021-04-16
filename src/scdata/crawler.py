import random
import json
from collections import Counter
import heapq
import math
import traceback
import numpy as np

import aiohttp
import aiohttp.web

from scdata import SoundCloudAPI
from scdata.genre import (GENRES,
                          IGNORE_GENRES,
                          normalize_distr,
                          bhattacharyya_dist,
                          map_genre,
                          genre_distr,
                          pp_distr)


def playlist_distr(playlist_info):
    genres = [track_info['genre']
              for track_info in playlist_info.get('tracks', [])
              if track_info.get('genre') is not None]
    return genre_distr(genres)


class SoundCloudCrawler:
    def __init__(self,
                 api: SoundCloudAPI,
                 min_track_likes: int = 30,
                 min_track_plays: int = 200):
        self.api = api
        self.min_track_likes = min_track_likes
        self.min_track_plays = min_track_plays

        self.visited_tracks = set()
        self.visited_playlists = set()
        self.visited_users = set()

        self.candidate_playlists = {}

        self.tracks = {}

    def save_state(self, path):
        state = {
            'min_track_likes': self.min_track_likes,
            'min_track_plays': self.min_track_plays,
            'visited_tracks': list(self.visited_tracks),
            'visited_playlists': list(self.visited_playlists),
            'visited_users': list(self.visited_users),
            'candidate_playlists': self.candidate_playlists,
            'tracks': self.tracks,
        }                 

        with open(path, 'w') as f:
            json.dump(state, f)

    def load_state(self, path):
        with open(path) as f:
            state = json.load(f)

        self.min_track_likes = state['min_track_likes']
        self.min_track_plays = state['min_track_plays']
        self.visited_tracks = set(state['visited_tracks'])
        self.visited_playlists = set(state['visited_playlists'])
        self.visited_users = set(state['visited_users'])
        self.candidate_playlists = state['candidate_playlists']

        # Python supports dictionaries with integer keys, but the keys are converted to strings
        # when deserializing. This causes duplicate entries, where one of the key is a string,
        # and the other is an integer.
        #
        # Prevent this issue by converting keys back to integer after deserialization.
        self.tracks = {int(track_id): track_info for track_id, track_info in state['tracks'].zip()}

    def is_complete_track_info(self, info):
        # Some info may be incomplete, e.g. the playlist.tracks infos are complete only for the
        # first couple of elements I think.
        #
        # Only tracks with the required keys may be added to `self.tracks`.
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
        licenses = Counter(info['license'] for info in self.tracks.values())
        free_count = sum(1 if self.is_free(info['license']) else 0
                         for info in self.tracks.values())
        free_perc = free_count / len(self.tracks) * 100

        ignore_genres = Counter(track.get('genre') for track in self.tracks.values()
                                if map_genre(track.get('genre')) == 'ignore')
        other_genres = Counter(track.get('genre') for track in self.tracks.values()
                               if map_genre(track.get('genre')) == 'others')
        ignore_count = sum(ignore_genres.values())
        other_count = sum(other_genres.values())
        ignore_perc = ignore_count / len(self.tracks) * 100
        other_perc = other_count / len(self.tracks) * 100

        print('=================================================================================')
        print(f'#api_calls:           {self.api.get_num_calls()}')
        print(f'#visited_tracks:      {len(self.visited_tracks)}')
        print(f'#visited_playlists:   {len(self.visited_playlists)}')
        print(f'#visited_users:       {len(self.visited_users)}')
        print(f'#candidate_playlists: {len(self.candidate_playlists)}')
        print(f'#tracks:              {len(self.tracks)}')
        print(f'    #free:            {free_count} ({free_perc:.2f}%)')
        print(f'    #ignore_genre:    {ignore_count} ({ignore_perc:.2f}%)')
        print(f'    #other_genre:     {other_count} ({other_perc:.2f}%)')
        print(f'genres:               {pp_distr(self.get_tracks_genre_distr())}')
        print(f'genres_free:          {pp_distr(self.get_free_tracks_genre_distr())}')
        print(f'ignore_genres:        {ignore_genres.most_common()[:10]}')
        print(f'other_genres:         {other_genres.most_common()[:10]}')
        print(f'licenses:             {licenses.most_common()[:10]}')
        print('=================================================================================')

    def get_track_freeness(self, info):
        return int('license' in info and self.is_free(info['license'])) 

    def get_playlist_freeness(self, info):
        if not info.get('tracks', []):
            return 0.0
        return sum(self.get_track_freeness(track_info) for track_info in info.get('tracks', []))

    def get_tracks_genre_distr(self):
        return genre_distr(info.get('genre') for info in self.tracks.values())

    def get_free_tracks_genre_distr(self):
        return genre_distr(info.get('genre') for info in self.tracks.values()
                           if self.is_free(info['license']))

    def add_candidate_playlist(self, playlist_info):
        if playlist_info['id'] in self.visited_playlists:
            return

        genres = [track['genre'] for track in playlist_info.get('tracks', [])
                  if track.get('genre') is not None]

        self.candidate_playlists[playlist_info['id']] = {
            'freeness': self.get_playlist_freeness(playlist_info),
            'genres': genres
        }

        # We get up to five full track infos for free per playlist. Record them.
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

        print('    genres: ' + pp_distr(playlist_distr(playlist_info)))

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

                track_score = self.get_track_freeness(track_info)
                track_scores.append((track_info, track_score))


        # For the top free tracks added, add the playlists that they are in as candidates.
        # I've tried doing this for all new tracks, but it takes too long to do all the API calls.
        track_scores.sort(key=lambda item: item[1], reverse=True)
        for track_info in track_scores[:5]:
            for playlist_info in await self.api.track_playlists(track_info[0]['id']):
                self.add_candidate_playlist(playlist_info)

        # Try to expand our tastes a bit:
        likers = await self.api.playlist_likers(playlist_id)
        for liker in likers[:10]:
            if liker['id'] in self.visited_users:
                continue
            self.visited_users.add(liker['id'])
            for likes in await self.api.user_likes(liker['id']):
                if 'playlist' in likes:
                    self.add_candidate_playlist(likes['playlist'])

    def choose_playlist_id(self, mode):
        if not self.candidate_playlists:
            return None

        candidates = list(self.candidate_playlists.items())

        # Note that, at this point, we only have genre information of five tracks per playlist (this
        # is the information that SoundCloud usually returns for playlist requests).
        tracks_genre_distr = list(self.get_free_tracks_genre_distr().items())
        tracks_genre_distr.sort(key=lambda item: item[1])
        genre_weights = {genre: math.log(0.6**(rank+1)) if genre not in IGNORE_GENRES else -10000.0
                         for rank, (genre, _) in enumerate(tracks_genre_distr)}

        def genre_novelty(candidate):
            return sum(prob * genre_weights.get(genre, 0.0)
                       for genre, prob
                       in genre_distr(candidate['genres']).items())

        weights = []
        if mode == 'freeness':
            # Prefer playlists that have more free licenses.
            for _, candidate in candidates:
                # Penalize tracks from genres we don't care about.
                num_ignore = sum(int(map_genre(genre) == 'ignore')
                                 for genre in candidate['genres'])

                # Also consider genre novelty, as a sort of tie breaker. Most of the weight goes
                # towards freeness, though.
                score = candidate['freeness'] + 0.1 * genre_novelty(candidate) - num_ignore

                weights.append(np.exp(score))
        elif mode == 'genre_rank':
            # Prefer playlists that introduce more genre novelty.    
            for _, candidate in candidates:
                # Heavily penalize playlists that have no free tracks at all. Other than that,
                # freeness has no impact, in an attempt to make it easier to find cluster sfrom
                # other genres.
                score = genre_novelty(candidate) - 100 * int(candidate['freeness'] == 0)

                weights.append(np.exp(score))

        candidates_weights = list(zip(candidates, weights))
        candidates_weights.sort(key=lambda pair: pair[1])

        candidates_weights = candidates_weights[-50:]
        weights = [pair[1] for pair in candidates_weights]

        #for item, weight in candidates_weights[-50:]:
        #    print(f'{weight}\t'
        #          f'{genre_distr(item[1]["genres"])}\t'
        #          f'{item[1]["freeness"]}\t'
        #          f'{genre_novelty(item[1])}')

        #choices = list(item[0] for item in top_candidates)
        choice = random.choices(candidates_weights, weights=weights)[0]
        choice_id = choice[0][0]
        choice_value = choice[0][1]
        choice_weight = choice[1]

        print(f'    playlist_id: {choice_id}, '
              f'freeness: {choice_value["freeness"]}, '
              f'weight: {choice_weight}')

        return choice_id

    async def crawl_step(self, mode):
        playlist_id = self.choose_playlist_id(mode)
        if playlist_id is None:
            return False

        del self.candidate_playlists[playlist_id]
        await self.visit_playlist(playlist_id)

        return True

    async def crawl(self,
                    max_steps,
                    print_info_steps=1,
                    save_steps=100,
                    save_path=None):
        for step_num in range(max_steps):
            try:
                if save_path is not None and step_num % save_steps == 0:
                    self.save_state(save_path)
                if print_info_steps > 0 and step_num % print_info_steps == 0:
                    self.print_info()

                print(f'step {step_num}, mode="freeness"')
                if not await self.crawl_step(mode='freeness'):
                    return

                print(f'step {step_num}, mode="genre_rank"')
                if not await self.crawl_step(mode='genre_rank'):
                    return
            except Exception as e:
                print(f'Caught exception {e}')
                traceback.print_exc()

