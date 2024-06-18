#!/usr/bin/env python3
from dataclasses import dataclass

import click
import requests
import bs4


@dataclass
class Episode:
    title: str
    url: str


class NeoScraper:
    ndr_base_url = 'https://www.ndr.de'

    def absolute_url(self, link: str):
        if link.startswith('/'):
            return self.ndr_base_url + link
        return link

    def scrape_episodes(self, episode_list_url='/kultur/sendungen/neo/index.html'):
        # The show with index page, listing previous episodes
        if episode_list_url.startswith('/'):
            episode_list_url = self.ndr_base_url + episode_list_url
        response = requests.get(episode_list_url)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        found_teaser_links = soup.select('div.teaserpadding > h2 > a')

        return [Episode(a.text.strip(), self.absolute_url(a['href'])) for a in found_teaser_links]

    @classmethod
    def print_episodes(cls, episodes):
        for episode in episodes:
            print(f"* {episode.title} ({episode.url})")


@click.command()
@click.argument('ndr_index_url', default='/kultur/sendungen/neo/index.html')
def list_shows(ndr_index_url):
    scraper = NeoScraper()
    print("Searching for episodes ..")
    found_episodes = scraper.scrape_episodes(ndr_index_url)
    print(f"Found {len(found_episodes)} episodes:")
    NeoScraper.print_episodes(found_episodes)


if __name__ == '__main__':
    list_shows()
