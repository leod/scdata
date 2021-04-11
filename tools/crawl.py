import asyncio
import aiohttp

import dotenv

from scdata import SoundCloudAPI, SoundCloudCrawler


async def main(config):
    async with aiohttp.ClientSession() as session:
        api = SoundCloudAPI(session,
                            client_id=config['SC_CLIENT_ID'],
                            oauth_token=config['SC_OAUTH_TOKEN'])
        crawler = SoundCloudCrawler(api)
        #crawler.load_state('crawler_state.json')

        await crawler.add_candidate_playlist_url('https://soundcloud.com/digitalstreams/sets/newtracks')
        await crawler.crawl(max_steps=10,
                            save_path='crawler_state.json')

if __name__ == '__main__':
    config = dotenv.dotenv_values('.env')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(config))
