"""
Starting from the track metadata in the crawler state, download the actual tracks.
"""

import argparse
import os
from tqdm import tqdm

import asyncio
import aiohttp

import dotenv

from scdata import SoundCloudAPI, SoundCloudCrawler
from scdata.load import get_audio_path
from scdata.genre import map_genre


async def main(crawler_state, out_audio_dir, config):
    async with aiohttp.ClientSession() as session:
        api = SoundCloudAPI(session,
                            client_id=config['SC_CLIENT_ID'],
                            oauth_token=config['SC_OAUTH_TOKEN'])

        print(f'Loading crawler state from "{crawler_state}"')

        crawler = SoundCloudCrawler(api)
        if os.path.exists('crawler_state.json'):
            crawler.load_state('crawler_state.json')

        print('Finished loading crawler state')

        tracks = []
        for track_info in crawler.tracks.values():
            if crawler.is_track_complete(track_info):
                tracks.append(track_info)

        print(f'Complete tracks: {len(tracks)}/{len(crawler.tracks)}')

        missing_tracks = []
        for track_info in tracks:
            audio_path = get_audio_path(out_audio_dir, track_info['id'])
            if not os.path.exists(audio_path):
                missing_tracks.append((track_info, audio_path))

        print(f'Missing tracks: {len(missing_tracks)}')

        fails = 0
        for track_info, audio_path in tqdm(missing_tracks):
            print(track_info['user']['username'], '|||',
                  track_info['title'], '|||',
                  track_info['genre'], '|||',
                  map_genre(track_info['genre']))
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)
            try:
                await api.save_track(track_info, audio_path)
            except Exception as e:
                fails += 1
                print(f'Caught exception {e}')

        print(f'#fails: {fails}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crawler_state',
                        help='Path of the crawler state JSON, as written by crawl.py',
                        required=True)
    parser.add_argument('--out_audio_dir', help='Directory to save tracks in', required=True)
    parser.add_argument('--env',
                        help='Env file that contains the SC_CLIENT_ID and SC_OAUTH_TOKEN fields',
                        default='.env')
    args = parser.parse_args()

    config = dotenv.dotenv_values(args.env)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args.crawler_state, args.out_audio_dir, config))
