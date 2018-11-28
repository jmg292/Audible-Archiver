import os
import time
import json
import queue
import atexit
import threading


class SynchronizedCacheFile(object):
    """
        Okay, but really.  I don't know why I thought this was necessary.  I mean, it's neat.  But it seems to cause
        more harm than good.  That being said, I'm keeping it.  Cuz it's neat.
    """
    class __SynchronizedCacheFile(object):

        def __init__(self, file_path):
            self._state = {}
            self._active = False
            self._no_write = False
            self._write_thread = None
            self._file_path = file_path
            self._access_queue = queue.Queue()

        def __getitem__(self, item):
            self._wait_for_changes()
            return self._state[item]

        def __setitem__(self, key, value):
            self._access_queue.put((key, value))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.flush()

        def _worker_thread(self):
            i = 0
            while self._active:
                if not self._access_queue.empty():
                    key, value = self._access_queue.get()
                    self._state[key] = value
                    i = (i + 1) % 3
                    if not i and not self._no_write:
                        self._save_state(self._state)
                    continue
                time.sleep(0.1)

        def _wait_for_changes(self, timeout=1):
            while not self._access_queue.empty() and timeout:
                time.sleep(0.1)
                timeout -= 1

        def _load_state(self):
            state = {}
            if os.path.isfile(self._file_path):
                with open(self._file_path, "r") as infile:
                    state_content = infile.read()
                state = json.loads(state_content)
            return state

        def _save_state(self, state):
            with open(self._file_path, "w") as outfile:
                outfile.write(json.dumps(state, indent=4))

        def flush(self):
            self._no_write = True
            self._wait_for_changes(5)
            self._save_state(self._state)
            self._no_write = False

        def start(self):
            self._state = self._load_state()
            self._active = True
            self._write_thread = threading.Thread(target=self._worker_thread)
            self._write_thread.setDaemon(True)
            self._write_thread.start()

        def stop(self):
            if self._active:
                self.flush()
                self._active = False
                if self._write_thread:
                    self._write_thread.join()
                    self._write_thread = None
                self._save_state(self._state)

    __instances = {}

    @staticmethod
    def _cleanup():
        for instance_type in SynchronizedCacheFile.__instances:
            SynchronizedCacheFile.__instances[instance_type].stop()

    def __new__(cls, arg):
        if type(arg) is dict:
            for instance_type in arg:
                new_instance = SynchronizedCacheFile.__SynchronizedCacheFile(arg[instance_type])
                new_instance.start()
                SynchronizedCacheFile.__instances[instance_type] = new_instance
                atexit.register(SynchronizedCacheFile._cleanup)
        elif arg in SynchronizedCacheFile.__instances:
            return SynchronizedCacheFile.__instances[arg]
        elif not SynchronizedCacheFile.__instances:
            raise ValueError("Cache files currently uninitialized.")
        else:
            raise ValueError("Invalid cache file: {0}".format(arg))


def test_function(cache, index):
    import hashlib
    print(i)
    value = hashlib.sha1(bytes(index)).hexdigest()
    cache[value] = index


if __name__ == "__main__":
    caches = {
        "aax_cache": "aax.test",
        "adh_cache": "adh.test"
    }
    SynchronizedCacheFile(caches)

    for cache_file in caches:
        with SynchronizedCacheFile(cache_file) as cache:
            for i in range(5000):
                for value in [i, i*2]:
                    t = threading.Thread(target=test_function, args=(cache, value))
                    t.start()