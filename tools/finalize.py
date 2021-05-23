#!/usr/bin/env python3
"""
Finalize dataset creation and write JSON file with metadata.
"""

import argparse
import os
import json
from collections import defaultdict, Counter
from io import BytesIO

import PIL.Image
from mutagen.id3 import ID3

from numpy import random

from scdata import SoundCloudAPI, SoundCloudCrawler, map_genre
from scdata.load import get_audio_path


def load_checksums(checksum_file):
    """
    Load the precomputed track checksums from the given file.

    This is used for deduplication. See readme for how to build this file. Some example lines:
    ```
    d41d8cd98f00b204e9800998ecf8427e  audio/877/877780213.mp3
    ddf83bfc7b2ecfff567e5b6cebbdf7ef  audio/877/877647832.mp3
    b2b9c7d2a00c8240daf2a0b57a38abed  audio/877/877244914.mp3
    d41d8cd98f00b204e9800998ecf8427e  audio/877/877669081.mp3
    ```
    """
    tracks_by_checksum = defaultdict(list)
    num_checksum_tracks = 0

    with open(checksum_file) as f:
        for line in f:
            cols = line.strip().split()
            assert len(cols) == 2
            assert os.path.exists(cols[1])

            track_id = int(os.path.splitext(os.path.basename(cols[1]))[0])
            tracks_by_checksum[cols[0]].append(track_id)

            num_checksum_tracks += 1
    
    return tracks_by_checksum, num_checksum_tracks


def sample_unique(tracks_by_checksum):
    """
    Select one track from each group of tracks that has the same checksum.

    While the MP3 files are identical, the metadata as returned by the SoundCloud API could still
    be differerent, so we need choose one representative per group.
    """
    unique_tracks = []

    for tracks in tracks_by_checksum.values():
        unique_tracks.append(random.choice(tracks))

    return unique_tracks


def finalize_dataset(audio_dir,
                     crawler_state,
                     out_file,
                     p_dev,
                     p_test,
                     checksum_file,
                     min_tracks_per_genre,
                     seed):
    random.seed(args.seed)

    print(f'Loading track MP3 checksums from "{checksum_file}"')
    tracks_by_checksum, num_checksum_tracks = load_checksums(checksum_file)
    unique_tracks = sample_unique(tracks_by_checksum)

    print(f'Sampled {len(unique_tracks)} unique tracks out of {num_checksum_tracks}')

    # Load track metadata from crawler state.
    print(f'Loading crawler state from "{crawler_state}"')
    crawler = SoundCloudCrawler(api=None)
    crawler.load_state(crawler_state)
    crawler.print_info()
    print('Finished loading crawler state')

    # Count tracks per genre to filter out rare genres.
    num_tracks_by_genre = Counter()
    for track_id in unique_tracks:
        track_info = crawler.tracks[track_id]
        num_tracks_by_genre[map_genre(track_info['genre'])] += 1
    print(f'Genre counts: {num_tracks_by_genre.most_common()}')

    # Filter tracks:
    #tracks_by_user = defaultdict(list)
    filtered_tracks = []
    for track_id in unique_tracks:
        track_info = crawler.tracks[track_id]

        # A couple of tracks seem to have bad image data.
        audio_path = get_audio_path(audio_dir, track_info['id'])
        try:
            tags = ID3(audio_path)
            PIL.Image.open(BytesIO(tags.getall('APIC')[0].data))
        except:
            continue

        if num_tracks_by_genre[map_genre(track_info['genre'])] < min_tracks_per_genre:
            continue

        if track_info['duration'] < 10000:
            continue

        if os.path.getsize(audio_path) < 1000:
            continue

        filtered_tracks.append(track_info)
        #tracks_by_user[track_info['user_id']].append(track_info)

    #print(f'Found users: {len(tracks_by_user)}')
    #print(f'Tracks per user: {len(filtered_tracks)/len(tracks_by_user):.4f}')
    print(f'Ignored {len(unique_tracks) - len(filtered_tracks)} tracks')

    # Perform the train/dev/test split.
    assert p_test > 0.0
    assert p_dev > 0.0
    assert p_dev + p_test < 1.0

    splits = random.choice(['training', 'validation', 'test'],
                           len(filtered_tracks),
                           p=[1.0 - p_dev - p_test, p_dev, p_test])

    split_counts = Counter()

    for split, track_info in zip(splits, filtered_tracks):
        track_info['scdata_split'] = split
        split_counts[split] += 1

    print(f'Split counts: {split_counts}')

    # Write metadata file.
    print(f'Writing metadata JSON to "{args.out_file}"')
    with open(out_file, 'w') as f:
        tracks = {track_info['id']: track_info for track_info in filtered_tracks}
        json.dump(tracks, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio_dir',
                        help='Directory that contains the MP3 audio files',
                        required=True)
    parser.add_argument('--crawler_state',
                        help='Path of the crawler state JSON, as written by crawl.py',
                        required=True)
    parser.add_argument('--out_file',
                        help='Path for the JSON output file to be written',
                        required=True)
    parser.add_argument('--p_dev',
                        help='Proportion of users to assign to the dev set',
                        default=0.05,
                        type=float)
    parser.add_argument('--p_test',
                        help='Proportion of users to assign to the test set',
                        default=0.05,
                        type=float)
    parser.add_argument('--checksum_file',
                        help='File computing the checksums precomputed for each track',
                        required=True)
    parser.add_argument('--min_tracks_per_genre',
                        help='Minimum number of tracks per genre',
                        default=100,
                        type=int)
    parser.add_argument('--seed',
                        help='Random seed',
                        default=43,
                        type=int)
    args = parser.parse_args()

    print(f'Arguments: {json.dumps(vars(args), indent=4)}')

    finalize_dataset(**vars(args))
