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

        urls = [
            'https://soundcloud.com/digitalstreams/sets/newtracks',
            #'https://soundcloud.com/agamidae/sets/instrumental',
            #'https://soundcloud.com/digitalstreams/sets/newtracks',
            #'https://soundcloud.com/yourparadis/sets/jazz-hip-4-1',
            #'https://soundcloud.com/lolollov2/sets/cosy-night-autumn',
            #'https://soundcloud.com/khushpreet-singh-6/sets/motivational-rap',
            #'https://soundcloud.com/discover/sets/charts-trending:all-music',
            #'https://soundcloud.com/discover/sets/charts-top:hiphoprap',
            #'https://soundcloud.com/discover/sets/charts-top:pop',
            #'https://soundcloud.com/discover/sets/charts-top:rock',
            #'https://soundcloud.com/discover/sets/charts-top:rbsoul',
            #'https://soundcloud.com/discover/sets/charts-top:drumbass',
            #'https://soundcloud.com/discover/sets/charts-top:classical',
            #'https://soundcloud.com/discover/sets/charts-top:world',
            #'https://soundcloud.com/soundcloud-hustle/sets/drippin-best-rap-right-now',
        ]

        for url in urls:
            await crawler.add_candidate_playlist_url(url)

        await crawler.crawl(max_steps=101,
                            save_path='crawler_state.json')

if __name__ == '__main__':
    config = dotenv.dotenv_values('.env')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(config))
