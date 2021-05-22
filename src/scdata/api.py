import json
from typing import Dict

from urllib.parse import quote

import aiohttp
import aiohttp.web

import mutagen
from mutagen.id3 import ID3, TIT2, COMM, TCON, TDRC, APIC, TPE1

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
        self.num_calls = 0

    def get_num_calls(self):
        return self.num_calls

    async def get(self, resource: str, args: Dict[str, str] = {}, root=None):
        if root is None:
            root = self.server + '/'
        args = {'client_id': self.client_id, **args}
        url_args = '&'.join(f'{key}={quote(value)}' for key, value in args.items())
        url = f'{root}{resource}?{url_args}'
        headers = {'Authorization': 'OAuth ' + self.oauth_token}

        self.num_calls += 1

        async with self.session.get(url, headers=headers) as response:
            data = await response.read()
            return json.loads(data)

    async def save_track(self, track_info, filename):
        url = None
        for transcoding in track_info['media']['transcodings']:
            if transcoding['format']['protocol'] == 'progressive':
                url = transcoding['url']
        if not url:
            raise ValueError('No progressive protocol available')

        url = (await self.get(url, root=''))['url']
        async with self.session.get(url) as response:
            with open(filename, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)

        artwork_url = track_info['artwork_url'].replace('large', 't300x300')
        async with self.session.get(artwork_url) as response:
            artwork = await response.read()

        tags = mutagen.File(filename)
        tags.add_tags()
        tags['TPE1'] = TPE1(encoding=3, text=track_info['user']['username'])
        tags['TIT2'] = TIT2(encoding=3, text=track_info['title'])
        tags['TCON'] = TCON(encoding=3, text=track_info['genre'])
        tags['TDRC'] = TDRC(encoding=3, text=track_info['created_at'])
        tags['APIC'] = APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=artwork)
        tags.save(filename, v1=2)
         

    async def resolve(self, soundcloud_url: str):
        return await self.get('resolve', {'url': soundcloud_url})

    async def track(self, track_id: int):
        return await self.get(f'tracks/{track_id}')

    async def track_likers(self, track_id: int):
        return (await self.get(f'tracks/{track_id}/likers'))['collection']

    async def track_playlists(self, track_id: int):
        return (await self.get(f'tracks/{track_id}/playlists_without_albums'))['collection']

    async def playlist(self, playlist_id: int):
        return await self.get(f'playlists/{playlist_id}')

    async def playlist_likers(self, playlist_id: int):
        return (await self.get(f'playlists/{playlist_id}/likers'))['collection']

    async def user(self, user_id: int):
        return await self.get(f'users/{user_id}')

    async def user_followings(self, user_id: int):
        return (await self.get(f'users/{user_id}/followings'))['collection']

    async def user_followers(self, user_id: int):
        return (await self.get(f'users/{user_id}/followers'))['collection']

    async def user_likes(self, user_id: int):
        return (await self.get(f'users/{user_id}/likes'))['collection']

    async def user_playlists(self, user_id: int):
        return (await self.get(f'users/{user_id}/playlists'))['collection']
