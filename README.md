# scdata

`scdata` is a dataset of tracks downloaded from [SoundCloud](https://soundcloud.com). It only
includes tracks that are licensed under [Creative Commons](https://creativecommons.org/).

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Data Preparation

The following steps describe how the dataset was prepared.

Note that this is a non-deterministic process, and it depends on the current state of SoundCloud.
Thus, if you re-run this process, you will not reproduce the exact same dataset.

### 1 Crawling

The crawler can be started like this
```
tools/crawl.py | tee -a crawl.log
```

The state is written to `crawler_state.json` every 500 steps, and the process can be resumed from
this.

The crawler requires a `.env` file to be available in the current directory, containing the keys
`SC_CLIENT_ID` and `SC_OAUTH_TOKEN`. The values for these can be inferred by visiting SoundCloud
and using the developer tools to inspect network calls made by your browser. This is necessary for
using the SoundCloud API.

#### Implementation Details

The crawler maintains the following state:
- Sets of visited tracks, playlists, and users.
- A dictionary of candidate playlists.
- A dictionary of all tracks that were found so far.

The crawler starts from a single candidate playlist and then iteratively performs the following
steps:

1. Determine a playlist to expand according to the playlist score (see below for more detail).
2. Download the metadata of the first 100 tracks in that playlist, and record them in the state.
3. For some of the new tracks, check which other playlists they are contained in, and add these
   as candidates.
4. Query for users that have liked the current playlists, and add other playlists liked by these
   users to our candidates. Also add tracks liked by these users to our state.

#### Playlist Score

The playlist score determines which playlists are more likely to get expanded by the crawler. It is
an essential part of the crawler.

The playlist score has two goals:
1. Favor playlists that contain songs with a free license.
2. Favor playlists that have genres which are underrepresented so far.

   The genre names are normalized towards a canonical representation, since otherwise the crawler
   would consistently prefer playlists with made up genre names.

Balancing the two goals seems to be difficult. If you want to improve the crawling process, the
playlist score is a good place to start. In initial experiments, without the playlist score, the
crawler ended up finding too few free tracks.

Note that the playlist score usually only has access to full information of the *first five* tracks
in the playlist. For the other tracks, we would need to make individual requests, which is something
we want to do only for the playlist that has been chosen for expansion. This makes the job of the
playlist score more difficult, since it has only limited genre and license information.

### Output

The crawler prints some statistics every 10 steps. See [`logs/crawl.log`](logs/crawl.log) for
example output.

### 2 Scraping

Once the crawler has finished, we should have a `crawler_state.json` with a dictionary of tracks. So
far, we only have the track metadata. Next, we download the actual tracks with this call:
```
tools/scrape.py --crawler_state crawler_state.json --out audio
```

Audio files will be written to the specified `out` directory. Most likely, the download will fail
for some of the tracks.

Only tracks that satisfy all of the following conditions are downloaded:
1. The license is either Creative Commons or `no-rights-reserved`.
2. The track has a genre name.
3. The track has artwork.
4. The track has a title.
5. The track has a download link.

Some metadata, as well as the artwork, is added to the downloaded `.mp3` files.
