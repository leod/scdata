import random
import json
from collections import Counter
import heapq
import math
import traceback
import numpy as np

import asyncio
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
              for track_info in playlist_info['tracks']
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

        # Python supports dictionaries with integer keys, but the keys are converted to strings
        # when deserializing. This causes duplicate entries, where one of the key is a string,
        # and the other is an integer.
        #
        # Prevent this issue by converting keys back to integer after deserialization.
        self.tracks = {int(track_id): track_info for track_id, track_info
                       in state['tracks'].items()}
        self.candidate_playlists = {int(playlist_id): playlist_info for playlist_id, playlist_info
                                    in state['candidate_playlists'].items()}

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

    def is_track_complete(self, track):
        mapped_genre = map_genre(track.get('genre'))
        if mapped_genre in ['others', 'ignore', 'unknown']:
            return False
        if not self.is_free(track['license']):
            return False
        if not isinstance(track['artwork_url'], str):
            return False
        if not track['artwork_url'].startswith('https://'):
            return False
        if not track.get('title'):
            return False
        if not track['media'].get('transcodings'):
            return False
        return True

    def print_info(self):
        licenses = Counter(info['license'] for info in self.tracks.values())
        free_count = sum(1 if self.is_free(info['license']) else 0
                         for info in self.tracks.values())
        free_perc = free_count / len(self.tracks) * 100

        complete_tracks = Counter()
        complete_nodl_tracks = Counter()
        complete_count = 0
        complete_nodl_count = 0
        for track in self.tracks.values():
            if not self.is_track_complete(track):
                continue

            complete_nodl_tracks[mapped_genre] += 1
            complete_nodl_count += 1

            if track['downloadable'] != True or track['has_downloads_left'] != True:
                continue

            complete_tracks[mapped_genre] += 1
            complete_count += 1

        ignore_genres = Counter(track.get('genre') for track in self.tracks.values()
                                if map_genre(track.get('genre')) == 'ignore')
        other_genres = Counter(track.get('genre') for track in self.tracks.values()
                               if map_genre(track.get('genre')) == 'others')
        ignore_count = sum(ignore_genres.values())
        other_count = sum(other_genres.values())
        ignore_perc = ignore_count / len(self.tracks) * 100
        other_perc = other_count / len(self.tracks) * 100
        complete_perc = complete_count / len(self.tracks) * 100
        complete_nodl_perc = complete_nodl_count / len(self.tracks) * 100

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
        print(f'    #complete:        {complete_count} ({complete_perc:.2f}%)')
        print(f'    #complete_nodl:   {complete_nodl_count} ({complete_nodl_perc:.2f}%)')
        print(f'genres:               {pp_distr(self.get_tracks_genre_distr())}')
        print(f'genres_free:          {pp_distr(self.get_free_tracks_genre_distr())}')
        print(f'ignore_genres:        {ignore_genres.most_common()[:10]}')
        print(f'other_genres:         {other_genres.most_common()[:10]}')
        print(f'complete_tracks:      {complete_tracks.most_common()}')
        print(f'complete_nodl_tracks: {complete_nodl_tracks.most_common()}')
        print(f'licenses:             {licenses.most_common()[:10]}')
        print('=================================================================================')

    def get_track_freeness(self, info):
        return int('license' in info and self.is_free(info['license'])) 

    def get_tracks_genre_distr(self):
        return genre_distr(info.get('genre') for info in self.tracks.values())

    def get_free_tracks_genre_distr(self):
        return genre_distr(info.get('genre') for info in self.tracks.values()
                           if self.is_free(info['license']))

    def add_candidate_playlist(self, playlist_info):
        if playlist_info['id'] in self.visited_playlists:
            return
        if not playlist_info.get('tracks', []):
            return

        genres = [track['genre'] for track in playlist_info['tracks']
                  if track.get('genre') is not None]
        genre_counts = Counter(map_genre(genre) for genre in genres)

        self.candidate_playlists[playlist_info['id']] = playlist_info

        # We get up to five full track infos for free per playlist. Record them.
        for track_info in playlist_info['tracks']:
            if self.is_track_okay(track_info):
                self.tracks[track_info['id']] = track_info

    async def add_candidate_playlist_url(self, soundcloud_url: str):
        info = await self.api.resolve(soundcloud_url) 
        self.add_candidate_playlist(info)

    async def fill_track_info(self, track_info):
        if self.is_complete_track_info(track_info):
            return track_info
        else:
            return await self.api.track(track_info['id'])

    async def visit_playlist(self, playlist_id):
        if playlist_id in self.visited_playlists:
            return
        self.visited_playlists.add(playlist_id)

        playlist_info = await self.api.playlist(playlist_id)

        print('    genres: ' + pp_distr(playlist_distr(playlist_info)))

        track_infos = [
            self.fill_track_info(track_info)
            for track_info in playlist_info['tracks'][:100]
        ]
        track_infos = await asyncio.gather(*track_infos)

        num_known = 0
        num_total = 0
        num_incomplete = 0
        num_not_okay = 0
        num_new = 0
        num_new_free = 0
        num_free = 0

        track_scores = []
        for track_info in track_infos:
            self.visited_tracks.add(track_info['id'])

            num_total += 1
            skip = False

            if self.is_free(track_info['license']):
                num_free += 1

            if track_info['id'] in self.tracks:
                num_known += 1
                skip = True
            if not self.is_complete_track_info(track_info):
                num_incomplete += 1
                skip = True
            if not self.is_track_okay(track_info):
                num_not_okay += 1
                skip = True
            if skip:
                continue

            num_new += 1
            if self.is_free(track_info['license']):
                num_new_free += 1

            self.tracks[track_info['id']] = track_info

            track_score = self.get_track_freeness(track_info)
            track_scores.append((track_info, track_score))

        # For the top free tracks added, add the playlists that they are in as candidates.
        # I've tried doing this for all new tracks, but it takes too long to do all the API calls.
        track_scores.sort(key=lambda item: item[1], reverse=True)
        track_playlists = [
            self.api.track_playlists(track_item[0]['id'])
            for track_item in track_scores[:5]
        ]
        track_playlists = await asyncio.gather(*track_playlists)

        for playlist_infos in track_playlists:
            for playlist_info in playlist_infos:
                self.add_candidate_playlist(playlist_info)

        # Try to expand our tastes a bit:
        likers = await self.api.playlist_likers(playlist_id)
        user_likes = [
            self.api.user_likes(liker['id'])
            for liker in likers[:50]
            if liker['id'] not in self.visited_users
        ]
        user_likes = await asyncio.gather(*user_likes)

        num_new_user_tracks = 0
        num_new_user_tracks_free = 0

        for liker, likes in zip(likers[:50], user_likes):
            self.visited_users.add(liker['id'])
            for like in likes:
                if 'playlist' in like:
                    self.add_candidate_playlist(like['playlist'])
                if 'track' in like:
                    track_info = like['track']
                    if self.is_track_okay(track_info):
                        self.tracks[track_info['id']] = track_info
                        num_new_user_tracks += 1
                        if self.is_free(track_info['license']):
                            num_new_user_tracks_free += 1


        print(f'    #total={num_total}, '
              f'#known={num_known}, '
              f'#not_okay={num_not_okay}, '
              f'#new={num_new}, '
              f'#free={num_free}, '
              f'#new_free={num_new_free}; '
              f'#new_user_tracks={num_new_user_tracks}, '
              f'#new_user_tracks_free={num_new_user_tracks_free}')

    def choose_playlist(self):
        if not self.candidate_playlists:
            return None

        #print('genre_weights')

        # Note that, at this point, we only have genre information of five tracks per playlist (this
        # is the information that SoundCloud usually returns for playlist requests).
        tracks_genre_distr = list(self.get_free_tracks_genre_distr().items())
        tracks_genre_distr.sort(key=lambda item: item[1])
        self.genre_weights = {genre: math.log(0.95**(rank+1))
                                     if genre not in IGNORE_GENRES and \
                                        genre != 'others' and \
                                        genre != 'unknown'
                                     else -10000.0
                              for rank, (genre, _) in enumerate(tracks_genre_distr)}

        #print('scores')

        weights = []
        for candidate in self.candidate_playlists.values():
            track_values = []
            new_tracks = 0

            for track_info in candidate['tracks']:
                if track_info['id'] not in self.tracks:
                    new_tracks += 1

                if self.is_complete_track_info(track_info):
                    mapped_genre = map_genre(track_info['genre'])
                    if mapped_genre == 'ignore':
                        track_value = 0.0
                    else:
                        track_value = 1.0
                        track_value *= 1.0 if self.is_free(track_info['license']) else 0.005
                        track_value *= 1.0 if self.is_track_okay(track_info) else 0.01
                        track_value *= 1.0 if track_info['id'] not in self.tracks else 0.01
                        track_value *= math.exp(self.genre_weights.get(mapped_genre, 0.0))

                    track_values.append(track_value)

            if len(track_values) == 0:
                weights.append(0.0)
            else:
                size_mult = 2/(1+math.exp(-new_tracks/3))-1
                new_ratio = new_tracks / len(candidate['tracks'])
                mean_score = new_ratio * np.mean(track_values)
                score = size_mult * mean_score 
                weights.append(math.exp(2000.0 * score))

        #print('topk')

        candidates_weights = zip(self.candidate_playlists.items(), weights)
        candidates_weights = heapq.nlargest(50,
                                            candidates_weights,
                                            key=lambda pair: pair[1])
        weights = [pair[1] for pair in candidates_weights]

        #for item, weight in candidates_weights[-50:]:
        #    print(f'    {weight}\t'
        #          f'{item[1]["genre_distr"]}\t'
        #          f'{item[1]["freeness"]}\t'
        #          f'{self.calc_genre_novelty(item[1]["genre_distr"])}')

        #print('sample')

        choice_item, choice_weight = random.choices(candidates_weights, weights=weights)[0]

        print(f'    playlist_id: {choice_item[0]}, '
              f'weight: {choice_weight}')

        return choice_item[0]

    async def crawl_step(self):
        playlist_id = self.choose_playlist()
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
                if save_path is not None and step_num > 0 and step_num % save_steps == 0:
                    self.save_state(save_path)
                if print_info_steps > 0 and step_num % print_info_steps == 0:
                    self.print_info()

                print(f'step {step_num}')
                if not await self.crawl_step():
                    return
            except Exception as e:
                print(f'Caught exception {e}')
                traceback.print_exc()

