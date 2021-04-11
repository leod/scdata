import json

import asyncio
import aiohttp

import dotenv

from scdata.api import SoundCloudAPI


async def main(config):
    async with aiohttp.ClientSession() as session:
        api = SoundCloudAPI(session,
                            client_id=config['SC_CLIENT_ID'],
                            oauth_token=config['SC_OAUTH_TOKEN'])

        info = await api.resolve('https://soundcloud.com/5_lin/hana-kotoba')
        print('track info:', info['id'], info['kind'])

        track = await api.track(info['id'])
        print('track genre:', track['genre'])
        print('track artwork:', track['artwork_url'])

        likers = await api.track_likers(info['id'])
        print('liker:', likers[0]['kind'], likers[0]['id'])

        info = await api.resolve('https://soundcloud.com/user727372658')
        print('user:', info['id'], info['kind'])

        followings = await api.user_followings(info['id'])
        print('following:', followings[0]['id'], followings[0]['kind'])

        info = await api.resolve('https://soundcloud.com/digitalstreams/sets/newtracks')
        print('set:', info['id'], info['kind'])


        print(json.dumps(info, indent=4))

if __name__ == '__main__':
    config = dotenv.dotenv_values('.env')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(config))
