import random
import json

import aiohttp
import aiohttp.web

from scdata import SoundCloudAPI

class SoundCloudCrawler:
    def __init__(self,
                 api: SoundCloudAPI,
                 max_candidates: int = 100000,
                 min_track_likes: int = 100,
                 min_track_plays: int = 1000):
        self.api = api
        self.max_candidates = max_candidates
        self.min_track_likes = min_track_likes
        self.min_track_plays = min_track_plays

        self.visited = set()
        self.tracks = {}
        self.candidates = {}

    def is_track_okay(self, track):
        # TODO: Check that track license is permissive enough

        if track['likes_count'] >= self.min_track_likes:
            return True
        if track['playback_count'] >= self.min_track_plays:
            return True

        # Track is not popular enough
        return False

    def add_candidate(self, info):
        if 'id' not in info or 'kind' not in info:
            print('Missing keys: ', info)

        tag = (info['kind'], info['id'])
        if tag in self.visited:
            return
        if info['kind'] in ['user', 'track', 'playlist']:
            self.candidates[tag] = info

    def add_candidates(self, infos):
        for info in infos:
            self.add_candidate(info)

    def print_info(self):
        print(f'#candidates={len(self.candidates)}')
        for kind in ['user', 'track', 'playlist']:
            count = len(list(c for c in self.candidates.keys() if c[0] == kind))
            print(f'#candidates_{kind}={count}')
        print(f'#visited={len(self.visited)}')
        for kind in ['user', 'track', 'playlist']:
            count = len(list(c for c in self.visited if c[0] == kind))
            print(f'#visited_{kind}={count}')
        print(f'#tracks={len(self.tracks)}')
        print('==============================================')

    async def add_candidate_url(self, soundcloud_url: str):
        info = await self.api.resolve(soundcloud_url) 
        self.add_candidate(info)

    async def visit(self, info):
        tag = (info['kind'], info['id'])
        self.visited.add(tag)

        if info['kind'] == 'user':
            await self.visit_user(info)
        elif info['kind'] == 'track':
            await self.visit_track(info)
        elif info['kind'] == 'playlist':
            await self.visit_playlist(info)
        else:
            # Ignore
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
            if not self.candidates:
                return

            self.print_info()

            candidate = random.choice(list(self.candidates.keys()))

            print(f'Candidate: {candidate}')
            info = self.candidates[candidate]
            del self.candidates[candidate]

            await self.visit(info)
