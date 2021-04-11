from typing import Dict

from urllib.parse import quote

import aiohttp
import aiohttp.web
import asyncio

# API v1 does not work for me, defaulting to v2 (which is the one being used by their frontend).
# See also <https://twitter.com/gdemey/status/639547648970760192>.
DEFAULT_SERVER = 'https://api-v2.soundcloud.com'


class SoundCloudAPI:
    def __init__(self,
                 session: aiohttp.ClientSession,
                 client_id: str,
                 oauth_token: str,
                 server: str = DEFAULT_SERVER):
        self.session = session
        self.client_id = client_id
        self.oauth_token = oauth_token
        self.server = server

    async def get(self, resource: str, args: Dict[str, str] = {}, json=True):
        args = {'client_id': self.client_id, **args}
        url_args = '&'.join(f'{key}={quote(value)}' for key, value in args.items())
        url = f'{self.server}/{resource}?{url_args}'
        headers = {'Authorization': 'OAuth ' + self.oauth_token}

        async with self.session.get(url, headers=headers) as response:
            return await response.json()

    async def resolve(self, soundcloud_url: str):
        return await self.get('resolve', {'url': soundcloud_url})

    async def track(self, track_id: int):
        return await self.get(f'tracks/{track_id}')

    async def track_likers(self, track_id: int):
        return (await self.get(f'tracks/{track_id}/likers'))['collection']

    async def playlist(self, playlist_id: int):
        return await self.get(f'playlists/{playlist_id}')

    async def user(self, user_id: int):
        return await self.get(f'users/{user_id}')

    async def user_followings(self, user_id: int):
        return (await self.get(f'users/{user_id}/followings'))['collection']

    async def user_followers(self, user_id: int):
        return (await self.get(f'users/{user_id}/followers'))['collection']

    async def user_likes(self, user_id: int):
        return (await self.get(f'users/{user_id}/likes'))['collection']
