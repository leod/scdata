from typing import Dict
import random
import json
from collections import Counter

import aiohttp
import aiohttp.web

from scdata import SoundCloudAPI

KINDS = ['user', 'track', 'playlist']
KIND_PROBS = {'user': 1.0/3.0, 'track': 1.0/3.0, 'playlist': 1.0/3.0}

class SoundCloudCrawler:
    def __init__(self,
                 api: SoundCloudAPI,
                 kind_probs: Dict[str, float] = KIND_PROBS,
                 max_candidates: int = 100000,
                 min_track_likes: int = 100,
                 min_track_plays: int = 1000):
        self.api = api
        self.kind_probs = kind_probs
        self.max_candidates = max_candidates
        self.min_track_likes = min_track_likes
        self.min_track_plays = min_track_plays

        self.visited = {kind: set() for kind in KINDS}
        self.candidates = {kind: {} for kind in KINDS}

        self.tracks = {}

    def is_track_okay(self, track):
        # TODO: Check that track license is permissive enough

        if track['likes_count'] is not None and track['likes_count'] >= self.min_track_likes:
            return True
        if track['playback_count'] is not None and track['playback_count'] >= self.min_track_plays:
            return True

        # Track is not popular enough
        return False

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

    def add_candidate(self, info):
        if info['kind'] not in self.visited:
            return
        if info['id'] in self.visited[info['kind']]:
            return

        self.candidates[info['kind']][info['id']] = info

        # If we have complete track info, we can add it immediately (rather than later on if
        # visiting it)
        if info['kind'] == 'track':
            if self.is_complete_track_info(info) and self.is_track_okay(info):
                self.tracks[info['id']] = info

    def add_candidates(self, infos):
        for info in infos:
            self.add_candidate(info)

    def print_info(self):
        print('==============================================')
        for kind, candidates in self.candidates.items():
            print(f'#candidates_{kind}={len(candidates)}')

        for kind, visited in self.visited.items():
            print(f'#visited_{kind}={len(visited)}')

        print(f'#tracks={len(self.tracks)}')

        genres = Counter(info['genre'] for info in self.tracks.values())
        print(f'genres={genres.most_common()[:10]}')

        licenses = Counter(info['licenses'] for info in self.tracks.values())
        print(f'genres={licenses.most_common()[:10]}')

    def save_state(self, path):
        state = {
            'kind_probs': self.kind_probs,
            'max_candidates': self.max_candidates,
            'min_track_likes': self.min_track_likes,
            'min_track_plays': self.min_track_plays,
            'visited': {kind: list(visited) for kind, visited in self.visited.items()},
            'candidates': self.candidates,
            'tracks': self.tracks,
        }                 

        with open(path, 'w') as f:
            json.dump(state, f, indent=4)

    def load_state(self, path):
        with open(path) as f:
            state = json.load(f)

        self.kind_probs = state['kind_probs']
        self.max_candidates = state['max_candidates']
        self.min_track_likes = state['min_track_likes']
        self.min_track_plays = state['min_track_plays']
        self.visited = {kind: set(visited) for kind, visited in state['visited'].items()}
        self.candidates = state['candidates']
        self.tracks = state['tracks']

    async def add_candidate_url(self, soundcloud_url: str):
        info = await self.api.resolve(soundcloud_url) 
        self.add_candidate(info)

    async def visit(self, info):
        self.visited[info['kind']].add(info['id'])

        if info['kind'] == 'user':
            await self.visit_user(info)
        elif info['kind'] == 'track':
            await self.visit_track(info)
        elif info['kind'] == 'playlist':
            await self.visit_playlist(info)
        else: # Ignore
            ...

    async def visit_track(self, info):
        if not self.is_complete_track_info(info):
            info = await self.api.track(info['id'])

        if self.is_track_okay(info):
            self.tracks[info['id']] = info

        self.add_candidates(await self.api.track_likers(info['id']))

    async def visit_user(self, info):
        for like in await self.api.user_likes(info['id']):
            if 'track' in like:
                self.add_candidate(like['track'])
            if 'playlist' in like:
                # Not sure if this case ever occurs
                self.add_candidate(like['playlist'])

        self.add_candidates(await self.api.user_followings(info['id']))
        self.add_candidates(await self.api.user_followers(info['id']))
        self.add_candidates(await self.api.user_playlists(info['id']))

    async def visit_playlist(self, info):
        playlist = await self.api.playlist(info['id'])
        if 'tracks' in playlist:
            self.add_candidates(playlist['tracks'])

    async def crawl_step(self):
        kind_choices = [
            (kind, self.kind_probs[kind])
            for kind, candidates in self.candidates.items()
            if len(candidates) > 0
        ]
        if len(kind_choices) == 0:
            return

        kind = random.choices(list(kind for kind, _ in kind_choices),
                                list(weight for _, weight in kind_choices))[0]
        candidate = random.choice(list(self.candidates[kind].keys()))

        info = self.candidates[kind][candidate]
        del self.candidates[kind][candidate]

        await self.visit(info)

    async def crawl(self,
                    max_steps,
                    print_info_steps=10,
                    save_steps=10,
                    save_path=None):
        for step_num in range(max_steps):
            if save_path is not None and step_num % save_steps == 0:
                self.save_state(save_path)
            if print_info_steps > 0 and step_num % print_info_steps == 0:
                self.print_info()

            await self.crawl_step()
