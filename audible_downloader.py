import os
import time
import json
import shutil
import random
import string
import getpass
import threading
import progressbar

import audible_driver
from audible_activator import AudibleActivator

from adh_handler import AudibleDownloader
from adh_handler.adh_parser import AdhParser
from adh_handler.adh_downloader import AdhDownloader


class DownloadProgressBar:

    def __init__(self, config):
        self._config = config
        self._progress_bar = None
        self.title = ""
        self.destination_file = ""

    def _finalize(self, update_progress):
        time.sleep(2)
        self._progress_bar.finish()
        self.title = update_progress.title
        dest_file = os.path.join(self._config["aax_download_directory"], "{0}_{1}.aax".format(
            update_progress.title, ''.join(random.choices(string.ascii_letters + string.digits, k=16))))
        shutil.move(update_progress.tempfile, dest_file)
        self.destination_file = dest_file

    def update_progress(self, download_data):
        if not self._progress_bar:
            print("Downloading audiobook: {0}".format(download_data.title))
            self._progress_bar = progressbar.ProgressBar(max_value=download_data.content_length)
            self._progress_bar.start()
        finish = False
        if download_data.download_progress < download_data.content_length:
            update_progress = download_data.download_progress
        else:
            update_progress = download_data.content_length
            finish = True
        self._progress_bar.update(update_progress)
        if finish:
            t = threading.Thread(target=self._finalize, args=(download_data,))
            t.start()


class AudibleLibraryDownloader:

    def __init__(self, config):
        self._config = config

    def _get_adh_file_identifier(self, adh_file):
        return AdhParser.get_adh_identifier("https://{0}/download?{1}".format(
            self._config["audible_cdn"], AdhParser(adh_file).parse_adm_file().to_http_params()))

    def _load_adh_download_cache(self):
        adm_cache = {}
        if os.path.isfile(self._config["adh_cache_file"]):
            with open(self._config["adh_cache_file"], "r") as infile:
                adm_cache = json.loads(infile.read())
        return adm_cache

    def _load_aax_download_cache(self):
        download_cache = {}
        cache_file = self._config["aax_cache_file"]
        if os.path.isfile(cache_file):
            with open(cache_file, "r") as infile:
                download_cache = json.loads(infile.read())
        return download_cache

    def _save_aax_download_cache(self, cache_data):
        with open(self._config["aax_cache_file"], "w") as outfile:
            outfile.write(json.dumps(cache_data, indent=4))

    def _get_adh_file_list(self):
        pending_downloads = []
        aax_download_cache = self._load_aax_download_cache()
        adh_download_cache = self._load_adh_download_cache()
        for identifier in adh_download_cache:
            if identifier in aax_download_cache:
                if os.path.isfile(aax_download_cache[identifier]["filepath"]):
                    if aax_download_cache[identifier]["download_finished"]:
                        continue
                    else:
                        os.unlink(aax_download_cache[identifier]["filepath"])
            pending_downloads.append(adh_download_cache[identifier])
        return pending_downloads

    def _finalize_download(self, adh_file, destination_file):
        if os.path.isfile(destination_file):
            download_cache = self._load_aax_download_cache()
            adh_identifier = self._get_adh_file_identifier(adh_file)
            download_cache[adh_identifier] = {
                "filepath": destination_file,
                "download_finished": True
            }
            self._save_aax_download_cache(download_cache)
            return True
        return False

    def download_all_files(self):
        i = 0
        adh_files = self._get_adh_file_list()
        print("[*] {0} files pending download.".format(len(adh_files)))
        for adh_file in adh_files:
            i += 1
            print("[*] Downloading audiobook {0}/{1}".format(i, len(adh_files)))
            download_progressbar = DownloadProgressBar(self._config)
            adh_downloader = AudibleDownloader(self._config["audible_cdn"], self._config["user_agent"])
            adh_downloader.download_data_callback = download_progressbar.update_progress
            adh_downloader.download_audiobook(adh_file)
            timeout = 0
            while timeout < 10:
                if download_progressbar.destination_file:
                    break
                time.sleep(1)
                timeout += 1
            if self._finalize_download(adh_file, download_progressbar.destination_file):
                print("[*] Successfully downloaded title: {0}".format(download_progressbar.title))
            else:
                print("[*] Download failed, will retry on next run.")



if __name__ == "__main__":
    print("[*] Loading configuration file . . .")
    with open("config.json", "r") as infile:
        config = json.loads(infile.read())
    print("[*] Preparing Audible Driver configuration . . .")
    driver_config = audible_driver.driver_config.AudibleDriverConfig(config["driver_config"])
    username = input("Audible username > ")
    password = getpass.getpass("Audible password > ")
    print("[*] Creating valid Audible session . . .")
    with audible_driver.AudibleDriver(driver_config) as driver:
        driver.log_on(username, password)
        activation_session_data = driver.get_activation_session_data()
    if not config["activation_bytes"]:
        print("[*] Activation bytes not found, retrieving them.")
        activator = AudibleActivator(driver_config, config["user_agent"], activation_session_data)
        activation_bytes = activator.retrieve_activation_bytes()
        print("[*] Successfully retrieved activation bytes: {0}".format(activation_bytes))
        config["activation_bytes"] = activation_bytes
        with open("config.json", "w") as outfile:
            outfile.write(json.dumps(config, indent=4))
            print("[*] Config file updated with activation byte values.")
    adm_downloader = AdhDownloader(driver_config, config["adh_cache_file"], config["adh_directory"])
    adm_downloader.download_adh_files(activation_session_data)
    downloader = AudibleLibraryDownloader(config)
    downloader.download_all_files()

