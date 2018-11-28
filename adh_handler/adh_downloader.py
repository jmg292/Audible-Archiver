import os
import sys
import json
import string
import random
import requests
import progressbar

from bs4 import BeautifulSoup

using_python3 = sys.version_info[0] == 3

try:
    from adh_handler.adh_parser import AdhParser
    from audible_driver.driver_config import AudibleDriverConfig
except ImportError:
    from adh_parser import AdhParser
    from driver_config import AudibleDriverConfig


class AdhDownloader:

    def __init__(self, config: AudibleDriverConfig, adm_cache_file, adh_download_folder):
        self._config = config
        self._adm_cache_file = adm_cache_file
        self._adh_download_folder = adh_download_folder

    @staticmethod
    def _get_prepared_session(audible_session_data):
        session = requests.Session()
        for cookie in audible_session_data["cookies"]:
            session.cookies.set(cookie["name"], cookie["value"])
        return session

    @staticmethod
    def _get_adh_download_urls(audible_library_html):
        download_urls = []
        soup = BeautifulSoup(audible_library_html, "html.parser")
        library_content = soup.findAll("tr", id=lambda x: x and x.startswith("adbl-library-content-row"))
        for content_row in library_content:
            content_adh_link = content_row.findAll("a", class_="bc-button-text", href=True)
            if content_adh_link:
                download_urls.append(content_adh_link[0]['href'])
        return download_urls

    def _download_adh_file(self, session, download_link, destination_file):
        response = session.get(download_link, headers={"User-Agent": self._config.browser_user_agent})
        with open(destination_file, "wb") as outfile:
            outfile.write(response.content)

    def _process_adh_link(self, download_link, session):
        adh_cache = self._load_adh_cache()
        adh_identifier = AdhParser.get_adh_identifier(download_link)
        if adh_identifier not in adh_cache:
            filename = "{0}.adh".format(''.join(random.choices(string.ascii_letters + string.digits, k=32)))
            dest_file = os.path.join(self._adh_download_folder, filename)
            adh_cache[adh_identifier] = dest_file
            self._download_adh_file(session, download_link, dest_file)
            self._save_adh_cache(adh_cache)

    def _load_adh_cache(self):
        adm_cache = {}
        if os.path.isfile(self._adm_cache_file):
            with open(self._adm_cache_file, "r") as infile:
                adm_cache = json.loads(infile.read())
        return adm_cache

    def _save_adh_cache(self, cache_data):
        with open(self._adm_cache_file, "w") as outfile:
            outfile.write(json.dumps(cache_data, sort_keys=True, indent=4))

    def download_adh_files(self, audible_session_data):
        library_page = 1
        adm_download_links = []
        session = self._get_prepared_session(audible_session_data)
        while True:
            print("[*] Processing library page {0} . . .".format(library_page))
            response = session.get(self._config.library_url.format(library_page),
                                   headers={"User-Agent": self._config.browser_user_agent})
            download_links = self._get_adh_download_urls(str(response.content, 'utf-8'))
            if not download_links:
                break
            adm_download_links.extend(download_links)
            library_page += 1
        print("[*] Found {0} audiobooks in your library.".format(len(adm_download_links)))
        print("[*] Processing required helper files . . .")
        i = 0
        with progressbar.ProgressBar(max_value=len(adm_download_links)) as bar:
            for download_link in adm_download_links:
                self._process_adh_link(download_link, session)
                i += 1
                bar.update(i)