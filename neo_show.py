#!/usr/bin/env python3
import dataclasses
import json
import re

import click
import requests
import bs4

ndr_base_url = 'https://www.ndr.de'


def extract_api_url_to_audio_json(html_script, base_url='https://www.ndr.de'):
    # https://www.ndr.de/kultur/audio1641990-podlove_image-81af8b05-0c64-4249-8fa7-7787cbfdd86f.json

    # var apiUrl = '/kultur/audio1641990-podlove_belongsToPodcast-_image-81af8b05-0c64-4249-8fa7-7787cbfdd86f.json',
    # playerType = 'external_embed',
    # broadcastType = '',
    # playerId = '#audioplayer-audio16419906241daf7-d1b3-4faf-9700-3332dbd4e15c',
    # pianoConfig =
    url = None
    found = [line for line in html_script.split('\n') if "var apiUrl = '/kultur/" in line]
    if found:
        url = base_url + found[0].lstrip("var apiUrl = '").rstrip("',")

    return url


def extract_config_json(javascript_source):
    # https://www.ndr.de/kultur/audio1641990-podloveplayer.html
    # var basicPianoJSON
    sophora_id = 'audio1641990'
    page_title = 'NDR Kultur Neo am 25.05.2024 mit Hendrik Haubold'
    show_name = 'NDR Kultur Neo'
    show_id = '1425'
    lines = javascript_source.split('\n')
    found = [i for i, line in enumerate(lines) if 'var basicPianoJSON' in line]
    if not found:
        return None

    begin = found[0] + 1
    end = begin + [i for i, line in enumerate(lines[begin:]) if "};" in line][0]
    json_raw = "\n".join(lines[begin:end]) + "}"
    json_dict = json.loads(json_raw)
    return json_dict


@dataclasses.dataclass
class Chapter:
    start: str
    title: str

    def __str__(self):
        return f"{self.start} - {self.title}"


@dataclasses.dataclass
class ShowAudio:
    title: str
    duration: str
    page_url: str
    audio_url: str
    audio_size_bytes: int

    chapters: list[Chapter]
    publication_date: str
    poster_url: str

    def audio_megabytes(self) -> float:
        return self.audio_size_bytes / (1024 ^ 2)

    def str_chapter_list(self):
        return '\n'.join(['* ' + str(chapter) for chapter in self.chapters])

    def __str__(self):
        return (
            f"Title (duration): {self.title} ({self.duration})\n"
            f"Audio URL (size):  {self.audio_url} ({self.audio_megabytes():,.2f} MB)\n"
            f"{len(self.chapters)} chapters:\n{self.str_chapter_list()}"
        )


def to_audio_json(url) -> ShowAudio:
    response = requests.get(url)
    response.raise_for_status()
    infos = response.json()
    # for audio and files there are title, url, mimeType, size (in bytes)
    chapters = []
    if 'chapters' in infos:
        chapters = [Chapter(c['start'], c['title']) for c in infos['chapters']]  # start-time, title

    return ShowAudio(
        infos['audio'][0]['title'],
        infos['duration'],
        infos['link'],
        infos['files'][0]['url'],
        int(infos['files'][0]['size']),
        chapters,
        infos['publicationDate'],
        infos['poster']
    )


def scrape_audio(page_uri='https://www.ndr.de/kultur/NDR-Kultur-Neo-am-19052024-mit-Hendrik-Haubold,audio1641990.html',
                 debug=False):
    response = requests.get(page_uri)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    soup_find_player(soup)
    scripts = soup.find_all('script', type='text/javascript', src=None)
    if debug:
        print(f"Found {len(scripts)} scripts without src.")
    if len(scripts) < 1:
        print(f"Failed to find first JavaScript element with URL to audio-JSON `var apiUrl = '/kultur/audio*.json`.")
        exit(1)
    source_ready_function = scripts[0].text
    source_vars = scripts[1].text
    extract_player_url(source_vars)
    audio_json_url = extract_api_url_to_audio_json(source_ready_function, ndr_base_url)
    if audio_json_url is None:
        print(f"Failed to extract URL to audio-JSON from script, line with `var apiUrl = '/kultur/`.",
              " Script beginning with '{scripts[0].text[:20]}'. Aborting.")
        exit(1)
    if debug:
        print(f"Retrieving JSON from: " + audio_json_url)
    return to_audio_json(audio_json_url)


def extract_player_url(script):
    basic_piano_json = extract_config_json(script)
    return basic_piano_json


def soup_find_player(soup):
    # div with id="audioplayer-audio16419908a21dd01-cd99-4d70-9f1c-26f8a7d7848b" data-test="podl-audioplayer"
    # (first 7 digits e.g. `1641990` is the content-/sophora-id) contains an IFRAME pointing to
    # https://www.ndr.de/kultur/sendungen/neo/audio1641990-podloveplayer.html
    sophora_id_pattern = r'\d{ 7}'
    uuid_pattern = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
    player = soup.find('div', id=re.compile(f"audioplayer-audio{sophora_id_pattern}{uuid_pattern}"))


@click.group()
@click.argument('neo_episode_url',
                default='https://www.ndr.de/kultur/NDR-Kultur-Neo-am-19052024-mit-Hendrik-Haubold,audio1641990.html')
@click.pass_context
def show(ctx, neo_episode_url):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj['neo_episode_url'] = neo_episode_url


@show.command('info')
@click.pass_context
def print_info(ctx):
    show_info = scrape_audio(ctx.obj['neo_episode_url'])
    print(show_info)


@show.command('audio-url')
@click.pass_context
def audio_url(ctx):
    episode = scrape_audio(ctx.obj['neo_episode_url'])
    print(episode.audio_url)


if __name__ == '__main__':
    show(obj={})

# Later then, download play list with detailed information about titles, albums, interprets, etc.
# > Die Titellisten der vergangenen Sendungen finden Sie hier!
# > https://www.ndr.de/kultur/programm/Titellisten,ndrkulturneoindex103.html
# https://www.ndr.de/kultur/sendungen/neo/ndrkulturneoindex103_page-1.html
# Example:
# https://www.ndr.de/kultur/sendungen/neo/kulturmusikprogramm33112.pdf
