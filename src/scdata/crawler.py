from typing import Dict
import random
import json
from collections import Counter
import heapq

import aiohttp
import aiohttp.web

from scdata import SoundCloudAPI


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

    def add_candidate_playlist(self, info):
        if info['id'] not in self.visited_playlists:
            self.candidate_playlists[info['id']] = self.get_playlist_score(info)

    async def add_candidate_playlist_url(self, soundcloud_url: str):
        info = await self.api.resolve(soundcloud_url) 
        self.add_candidate_playlist(info)

    async def visit_playlist(self, playlist_id):
        if playlist_id in self.visited_playlists:
            return
        self.visited_playlists.add(playlist_id)

        playlist_info = await self.api.playlist(playlist_id)
        track_scores = []

        for track_info in playlist_info.get('tracks', []):
            if track_info['id'] in self.visited_tracks:
                continue
            self.visited_tracks.add(track_info['id'])

            if not self.is_complete_track_info(track_info):
                track_info = await self.api.track(track_info['id'])
                if not self.is_complete_track_info(track_info):
                    continue

            #print(track_info['license'], track_info['likes_count'], track_info['playback_count'])

            if self.is_track_okay(track_info):
                self.tracks[track_info['id']] = track_info

            track_score = self.get_track_score(track_info)
            track_scores.append((track_info, track_score))

        # For the most free tracks added, add the playlists that they are in as candidates.
        # I've tried doing this for all new tracks, but it takes too long to do all the API calls.
        track_scores.sort(key=lambda item: item[1], reverse=True)
        for track_info in track_scores[:10]:
            for playlist_info in await self.api.track_playlists(track_info[0]['id']):
                self.add_candidate_playlist(playlist_info)

    async def crawl_step(self):
        if not self.candidate_playlists:
            return False

        best_id = max(self.candidate_playlists.items(), key=lambda item: item[1])[0]
        print(f'Playlist {best_id} with score {self.candidate_playlists[best_id]}')

        del self.candidate_playlists[best_id]
        await self.visit_playlist(best_id)

        return True

    async def crawl(self,
                    max_steps,
                    print_info_steps=10,
                    save_steps=100,
                    save_path=None):
        for step_num in range(max_steps):
            if save_path is not None and step_num % save_steps == 0:
                self.save_state(save_path)
            if print_info_steps > 0 and step_num % print_info_steps == 0:
                self.print_info()

            if not await self.crawl_step():
                return
