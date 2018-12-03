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
from aax_converter import AaxConverter
from audible_activator import AudibleActivator
from synchronized_cache_file import SynchronizedCacheFile

from adh_handler import AudibleDownloader
from adh_handler.adh_parser import AdhParser
from adh_handler.adh_downloader import AdhDownloader


class DownloadProgressBar:

    def __init__(self, config):
        self._config = config
        self._progress_bar = None
        self.title = ""
        self.destination_file = ""

    @staticmethod
    def clean_title(title):
        return ''.join([x for x in title if x not in (string.punctuation + string.whitespace)])

    def _finalize(self, update_progress):
        time.sleep(2)
        self._progress_bar.finish()
        self.title = update_progress.title
        dest_file = os.path.join(self._config["aax_download_directory"], "{0}_{1}.aax".format(
            self.clean_title(update_progress.title), ''.join(random.choices(string.ascii_letters + string.digits, k=16))))
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
        self.aax_converter = None

    def _get_adh_file_identifier(self, adh_file):
        return AdhParser.get_adh_identifier("https://{0}/download?{1}".format(
            self._config["audible_cdn"], AdhParser(adh_file).parse_adm_file().to_http_params()))

    def _load_adh_download_cache(self):
        return SynchronizedCacheFile("adh_cache_file")

    def _load_aax_download_cache(self):
        return SynchronizedCacheFile("aax_cache_file")

    def _save_aax_download_cache(self, cache_data):
        cache_data.flush()

    def _get_adh_file_list(self):
        pending_downloads = []
        aax_download_cache = self._load_aax_download_cache()
        adh_download_cache = self._load_adh_download_cache()
        for identifier in adh_download_cache:
            if identifier in aax_download_cache:
                if "converted" in aax_download_cache[identifier] and aax_download_cache[identifier]["converted"]:
                    continue
                elif os.path.isfile(aax_download_cache[identifier]["filepath"]):
                    if aax_download_cache[identifier]["download_finished"]:
                        self.aax_converter.convert_file(aax_download_cache[identifier]["filepath"])
                        continue
                    else:
                        os.unlink(aax_download_cache[identifier]["filepath"])
            pending_downloads.append(adh_download_cache[identifier])
        return pending_downloads

    def _finalize_download(self, adh_file, destination_file):
        if os.path.isfile(destination_file):
            with self._load_aax_download_cache() as download_cache:
                adh_identifier = self._get_adh_file_identifier(adh_file)
                download_cache[adh_identifier] = {
                    "filepath": destination_file,
                    "download_finished": True
                }
                self._save_aax_download_cache(download_cache)
            return True
        return False

    def _write_to_tsv(self, metadata):
        write_header = False
        csv_columns = ["title", "album", "artist", "date", "copyright"]
        if not os.path.isfile(self._config["tsv_path"]):
            write_header = True
        with open(self._config["tsv_path"], "a") as outfile:
            if write_header:
                outfile.write("{0}\r\n".format("\t".join(csv_columns)))
            outfile.write("{0}\r\n".format("\t".join([metadata.to_dict()[x] for x in csv_columns])))

    def finalize_conversion(self, metadata):
        prospective_filepath = os.path.join(
            self._config["converter_config"]["library_directory"],
            DownloadProgressBar.clean_title(metadata.title)
        ) + ".mp3"
        if os.path.isfile(prospective_filepath):
            with self._load_aax_download_cache() as download_data:
                for key in download_data:
                    if download_data[key]["filepath"] == metadata.aax_file:
                        download_data[key]["converted"] = True
                        if self._config["remove_after_conversion"]:
                            os.unlink(metadata.aax_file)
                            download_data[key]["download_finished"] = False
                        break
            self._write_to_tsv(metadata)

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
                self.aax_converter.convert_file(download_progressbar.destination_file)
            else:
                print("[*] Download failed, will retry on next run.")


if __name__ == "__main__":
    print("[*] Loading configuration file . . .")
    with open("config.json", "r") as infile:
        config = json.loads(infile.read())
    print("[*] Initializing download and conversion caches . . .")
    SynchronizedCacheFile.initialize(config)
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
    print("[*] Starting AAX to MP3 converter . . .")
    converter = AaxConverter(config["converter_config"], config["activation_bytes"])
    converter.start()
    adm_downloader = AdhDownloader(driver_config, "adh_cache_file", config["adh_directory"])
    adm_downloader.download_adh_files(activation_session_data)
    downloader = AudibleLibraryDownloader(config)
    print("[*] Linking download and conversion threads . . .")
    converter.conversion_finished_event = downloader.finalize_conversion
    downloader.aax_converter = converter
    print("[*] Starting library archival process, this is gonna take a while.")
    downloader.download_all_files()
    converter.wait_for_conversion_completion()

