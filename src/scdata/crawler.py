from typing import Dict
import random
import json

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

        if track['likes_count'] >= self.min_track_likes:
            return True
        if track['playback_count'] >= self.min_track_plays:
            return True

        # Track is not popular enough
        return False

    def add_candidate(self, info):
        if info['kind'] not in self.visited:
            return
        if info['id'] in self.visited[info['kind']]:
            return

        self.candidates[info['kind']][info['id']] = info

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
        print('==============================================')

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
        # Some info may be incomplete, e.g. the playlist.tracks infos are complete only for the
        # first couple of elements I think.
        if 'artwork_url' not in info or 'genre' not in info:
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
        self.add_candidates(playlist['tracks'])

    async def crawl(self, max_steps):
        for step_num in range(max_steps):
            kind_choices = [
                (kind, self.kind_probs[kind])
                for kind, candidates in self.candidates.items()
                if len(candidates) > 0
            ]
            if len(kind_choices) == 0:
                return

            self.print_info()

            kind = random.choices(list(kind for kind, _ in kind_choices),
                                  list(weight for _, weight in kind_choices))[0]
            candidate = random.choice(list(self.candidates[kind].keys()))

            print(f'Candidate: {kind}, {candidate}')
            info = self.candidates[kind][candidate]
            del self.candidates[kind][candidate]

            await self.visit(info)
