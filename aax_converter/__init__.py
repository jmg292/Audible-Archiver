import os
import sys
import time
import queue
import random
import string
import ffmpeg
import atexit
import tempfile
import threading
import subprocess

from synchronized_cache_file import SynchronizedCacheFile


class AaxFileMetadata:

    def __init__(self):
        self.title = ""
        self.album = ""
        self.artist = ""
        self.copyright = ""
        self.date = ""  # Publication date
        self.aax_file = ""

    @property
    def safe_title(self):
        return ''.join([x for x in self.title if x not in (string.punctuation + string.whitespace)])

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_dict(meta_dict):
        metadata = AaxFileMetadata()
        metadata.date = meta_dict["date"]
        metadata.title = meta_dict["title"]
        metadata.album = meta_dict["album"]
        metadata.artist = meta_dict["artist"]
        metadata.copyright = meta_dict["copyright"]
        return metadata


class ConversionThreadWrapper:

    def __init__(self, conversion_function, args):
        self._args = args
        self.active = True
        self._conversion_function = conversion_function

    def run(self):
        self._conversion_function(self._args)
        self.active = False


class AaxConverter:

    class __AaxConverter:

        def __init__(self, config, auth_bytes):
            self._alive = False
            self._watcher_thread = None
            self._requiring_cleanup = []
            self._conversion_threads = []
            self._auth_bytes = auth_bytes
            self._ffmpeg = config["ffmpeg_path"]
            self._ffprobe = config["ffprobe_path"]
            self._max_threads = config["max_threads"]
            self._library_dir = config["library_directory"]
            self._pending_conversions = queue.Queue()
            self.conversion_finished_event = None

        def _conversion_worker(self, aax_file):
            probed_data = ffmpeg.probe(aax_file, cmd=self._ffprobe)
            aax_metadata = AaxFileMetadata.from_dict(probed_data["format"]["tags"])
            aax_metadata.aax_file = aax_file
            output_file = os.path.join(self._library_dir, aax_metadata.safe_title + ".mp3")
            command = ' '.join([
                self._ffmpeg,
                "-loglevel", "error",
                "-stats",
                "-activation_bytes", self._auth_bytes,
                "-i", '"{0}"'.format(aax_file),
                "-vn", "-codec:a", "libmp3lame",
                "-ab", probed_data["streams"][0]["bit_rate"],
                "-map_metadata", "-1",
                "-metadata", r'title="{0}"'.format(aax_metadata.title),
                "-metadata", r'artist="{0}"'.format(aax_metadata.artist),
                "-metadata", r'album="{0}"'.format(aax_metadata.album),
                "-metadata", r'date="{0}"'.format(aax_metadata.date),
                "-metadata", r'genre="Audiobook"',
                "-metadata", r'copyright="{0}"'.format(aax_metadata.copyright),
                output_file, "& pause & exit"
            ])
            tmp_batch = ''.join(random.choices(string.ascii_letters, k=16)) + ".bat"
            with open(tmp_batch, "w") as outfile:
                outfile.write(command)
            self._requiring_cleanup.append(tmp_batch)
            os.system("start /wait cmd /k {0}".format(tmp_batch))
            if self.conversion_finished_event is not None:
                self.conversion_finished_event(aax_metadata)

        def _watcher(self):
            while self._alive:
                if not self._pending_conversions.empty():
                    if not len(self._conversion_threads) >= self._max_threads:
                        aax_file_path = self._pending_conversions.get()
                        conversion_wrapper = ConversionThreadWrapper(self._conversion_worker, aax_file_path)
                        self._conversion_threads.append(conversion_wrapper)
                        t = threading.Thread(target=conversion_wrapper.run)
                        t.setDaemon(True)
                        t.start()
                        continue
                self._conversion_threads = [x for x in self._conversion_threads if x.active]
                time.sleep(0.5)

        def start(self):
            self._alive = True
            self._watcher_thread = threading.Thread(target=self._watcher)
            self._watcher_thread.setDaemon(True)
            self._watcher_thread.start()

        def convert_file(self, file_path):
            self._pending_conversions.put(file_path)

        def cleanup(self):
            for filename in self._requiring_cleanup:
                if os.path.isfile(filename):
                    os.unlink(filename)

        def wait_for_conversion_completion(self):
            while not self._pending_conversions.empty() and len(self._conversion_threads):
                time.sleep(10)

    __instance = None

    def __new__(cls, config=None, auth_bytes=""):
        if not AaxConverter.__instance:
            AaxConverter.__instance = AaxConverter.__AaxConverter(config, auth_bytes)
            atexit.register(AaxConverter.__instance.cleanup)
        return AaxConverter.__instance
