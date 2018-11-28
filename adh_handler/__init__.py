import requests
import tempfile
import progressbar

try:
    import adh_handler.adh_parser
except ImportError:
    import adm_parser


class DownloadData(object):

    def __init__(self):
        self.title = ""
        self.content_length = 0
        self.download_progress = 0
        self.tempfile = tempfile.mktemp()


class AudibleDownloader:

    def __init__(self, cdn_hostname, user_agent_string):
        self._headers = {"User-Agent": user_agent_string}
        self._cdn_hostname = cdn_hostname
        self.download_data_callback = None

    @staticmethod
    def _get_adm_data(adm_file):
        return adh_parser.AdhParser(adm_file).parse_adm_file()

    def _handle_multipart_download(self, response, download_data):
        download_data.content_length = response.headers.get("content-length")
        if not download_data.content_length:
            return False
        download_data.content_length = int(download_data.content_length)
        with open(download_data.tempfile, "wb") as outfile:
            for data in response.iter_content(chunk_size=4096):
                download_data.download_progress += len(data)
                outfile.write(data)
                outfile.flush()
                if self.download_data_callback:
                    self.download_data_callback(download_data)

    def download_audiobook(self, adm_file):
        adm_data = self._get_adm_data(adm_file)
        download_progress = DownloadData()
        download_progress.title = adm_data.title
        response = requests.get("http://{0}/download?{1}".format(self._cdn_hostname, adm_data.to_http_params()),
                                headers=self._headers, stream=True)
        self._handle_multipart_download(response, download_progress)


class DownloadProgressBar:

    def __init__(self):
        self._progress_bar = None

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
            self._progress_bar.finish()


if __name__ == "__main__":
    progress_bar = DownloadProgressBar()
    downloader = AudibleDownloader("cds.audible.com", "Audible ADM 6.6.0.19;Windows Vista  Build 9200")
    downloader.download_data_callback = progress_bar.update_progress
    downloader.download_audiobook(r"C:\Users\me\Downloads\admhelper.adh")
