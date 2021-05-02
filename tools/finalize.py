#!/usr/bin/env python3
"""
Finalize dataset creation and write JSON file with metadata.
"""

import argparse
import os
import random
import json
from collections import defaultdict

from scdata import SoundCloudAPI, SoundCloudCrawler
from scdata.load import get_audio_path


def finalize_dataset(crawler_state, audio_dir, out_file, p_dev, p_test):
    print(f'Loading crawler state from "{crawler_state}"')

    crawler = SoundCloudCrawler(api=None)
    if os.path.exists(crawler_state):
        crawler.load_state(crawler_state)

    print('Finished loading crawler state')

    tracks = []
    for track_info in crawler.tracks.values():
        audio_path = get_audio_path(audio_dir, track_info['id'])
        if os.path.exists(audio_path):
            tracks.append(track_info)

    print(f'Found tracks: {len(tracks)}/{len(crawler.tracks)}')

    # Group tracks by user in preparation for train/dev/test split.
    tracks_by_user = defaultdict(list)
    for track_info in tracks:
        tracks_by_user[track_info['user_id']].append(track_info)

    print(f'Found users: {len(tracks_by_user)}')
    print(f'Tracks per user: {len(tracks)/len(tracks_by_user):.4f}')

    # Perform the split
    tracks_by_user = list(tracks_by_user.items())
    random.shuffle(tracks_by_user)

    num_train = 0
    num_dev = 0
    num_test = 0

    for user in tracks_by_user[:p_train * len(tracks_by_user))]:
        for track in user:
            track['scdata_split'] = 'train'
            num_train += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crawler_state',
                        help='Path of the crawler state JSON, as written by crawl.py',
                        required=True)
    parser.add_argument('--audio_dir',
                        help='Audio directory, as written by scrape.py',
                        required=True)
    parser.add_argument('--out_file',
                        help='Path for the JSON output file to be written',
                        required=True)
    parser.add_argument('--p_dev',
                        help='Proportion of users to assign to the dev set',
                        default=0.01,
                        type=float)
    parser.add_argument('--p_test',
                        help='Proportion of users to assign to the test set',
                        default=0.01,
                        type=float)
    args = parser.parse_args()

    finalize_dataset(**vars(args))
