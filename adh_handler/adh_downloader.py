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
    from synchronized_cache_file import SynchronizedCacheFile
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
    def _get_max_library_page(audible_library_html):
        available_pages = []
        soup = BeautifulSoup(audible_library_html, "html.parser")
        page_links = soup.find_all("a", {"class": "pageNumberElement", "data-name": "page"})
        for page_link in page_links:
            try:
                page_number = int(page_link['data-value'])
                available_pages.append(page_number)
            except ValueError:
                pass
        return max(available_pages)

    @staticmethod
    def _get_adh_download_urls(audible_library_html):
        download_urls = []
        soup = BeautifulSoup(audible_library_html, "html.parser")
        library_content = soup.findAll("div", id=lambda x: x and x.startswith("library-download-popover"))
        for content_row in library_content:
            content_adh_link = content_row.find_all("a", {"class": "bc-link", "aria-label": "DownloadFull"}, href=True)
            if content_adh_link:
                download_urls.append(content_adh_link[0]['href'])
        return download_urls

    def _download_adh_file(self, session, download_link, destination_file):
        response = session.get(download_link, headers={"User-Agent": self._config.browser_user_agent})
        with open(destination_file, "wb") as outfile:
            outfile.write(response.content)

    def _process_adh_link(self, download_link, session):
        with self._load_adh_cache() as adh_cache:
            adh_identifier = AdhParser.get_adh_identifier(download_link)
            if adh_identifier not in adh_cache:
                filename = "{0}.adh".format(''.join(random.choices(string.ascii_letters + string.digits, k=32)))
                dest_file = os.path.join(self._adh_download_folder, filename)
                adh_cache[adh_identifier] = dest_file
                self._download_adh_file(session, download_link, dest_file)
                self._save_adh_cache(adh_cache)

    def _load_adh_cache(self):
        return SynchronizedCacheFile(self._adm_cache_file)

    def _save_adh_cache(self, cache_data):
        cache_data.flush()

    def download_adh_files(self, audible_session_data):
        library_page = 1
        adm_download_links = []
        session = self._get_prepared_session(audible_session_data)
        max_page = self._get_max_library_page(
            str(session.get(
                self._config.library_url.format("1"),
                headers={"User-Agent": self._config.browser_user_agent}
            ).content, 'utf-8')
        )
        for library_page in range(1, max_page + 1):
            print("[*] Processing library page {0} . . .".format(library_page))
            response = session.get(self._config.library_url.format(library_page),
                                   headers={"User-Agent": self._config.browser_user_agent})
            download_links = self._get_adh_download_urls(str(response.content, 'utf-8'))
            if not download_links:
                break
            adm_download_links.extend(download_links)
        print("[*] Found {0} audiobooks in your library.".format(len(adm_download_links)))
        print("[*] Processing required helper files . . .")
        i = 0
        with progressbar.ProgressBar(max_value=len(adm_download_links)) as bar:
            for download_link in adm_download_links:
                self._process_adh_link(download_link, session)
                i += 1
                bar.update(i)