import asyncio
import aiohttp

import dotenv

from scdata.api import SoundCloudAPI


async def main(config):
    async with aiohttp.ClientSession() as session:
        api = SoundCloudAPI(session,
                            client_id=config['SC_CLIENT_ID'],
                            oauth_token=config['SC_OAUTH_TOKEN'])

        print(await api.resolve('https://soundcloud.com/tydollasign/your-turn'))
        print('')
        print(await api.track(251164884))


if __name__ == '__main__':
    config = dotenv.dotenv_values('.env')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(config))
