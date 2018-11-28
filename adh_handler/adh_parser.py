import sys
import hashlib

using_python3 = sys.version_info[0] == 3

if using_python3:
    from urllib.parse import urlparse, parse_qsl
else:
    from urlparse import urlparse, parse_qsl

class AdmData:

    def __init__(self):
        self.user_id = ""
        self.cust_id = ""
        self.product_id = ""
        self.codec = ""
        self.awtype = ""
        self.source = ""
        self.title = ""

    def to_http_params(self):
        return "user_id={0}&product_id={1}&codec={2}&awtype={3}&cust_id={4}".format(
            self.user_id, self.product_id, self.codec, self.awtype, self.cust_id
        )


class AdhParser:

    def __init__(self, adm_file):
        self._adm_file = adm_file

    @staticmethod
    def get_adh_identifier(adm_download_url):
        # Keep track of the ADM files we've already downloaded by using a hash of the static content in the ADM file
        static_adm_content = ""
        static_adm_content_key = ["product_id", "awtype"]
        adm_content = dict(parse_qsl(urlparse(adm_download_url).query))
        for content_key in static_adm_content_key:
            if content_key in adm_content:
                static_adm_content += adm_content[content_key].strip()
        return hashlib.sha1(bytes(static_adm_content, 'utf-8')).hexdigest()

    def _get_split_file_content(self):
        with open(self._adm_file, "r") as infile:
            file_contents = infile.read()
        return file_contents.split("&")

    def parse_adm_file(self):
        adm_data = AdmData()
        for content_part in self._get_split_file_content():
            if "=" not in content_part:
                continue
            split_content_part = content_part.split("=")
            if len(split_content_part) <= 1:
                continue
            part_data = split_content_part[1]
            if content_part.startswith("user_id"):
                adm_data.user_id = part_data
            elif content_part.startswith("cust_id"):
                adm_data.cust_id = part_data
            elif content_part.startswith("product_id"):
                adm_data.product_id = part_data
            elif content_part.startswith("codec"):
                if len(part_data) > 16:
                    adm_data.codec = part_data[:16]
                else:
                    adm_data.codec = part_data
            elif content_part.startswith("awtype"):
                adm_data.awtype = part_data
            elif content_part.startswith("source"):
                adm_data.source = part_data
            elif content_part.startswith("title"):
                adm_data.title = part_data
        return adm_data


if __name__ == "__main__":
    print(AdhParser(r"C:\Users\me\Downloads\admhelper.adh").parse_adm_file().to_http_params())
