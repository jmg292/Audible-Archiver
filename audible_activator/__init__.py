import binascii
import requests


class AudibleActivator:

    def __init__(self, driver_config, adm_user_agent, audible_session_data):
        self._driver_config = driver_config
        self._adm_user_agent = adm_user_agent
        self._audible_session_data = audible_session_data
        self._driver_config.player_id = audible_session_data["data"]["playerToken"]

    def _get_prepared_session(self):
        session = requests.Session()
        for cookie in self._audible_session_data["cookies"]:
            session.cookies.set(cookie["name"], cookie["value"])
        return session

    def register(self, session=None):
        if not session:
            session = self._get_prepared_session()
        response = session.get(self._driver_config.registration_url, headers={"User-Agent": self._adm_user_agent})
        return response.content

    def unregister(self, session=None):
        if not session:
            session = self._get_prepared_session()
        session.get(self._driver_config.deregistration_url, headers={"User-Agent": self._adm_user_agent})

    def retrieve_activation_bytes(self):
        session = self._get_prepared_session()
        self.unregister(session)
        activation_blob = self.register(session)
        self.unregister(session)
        return self.extract_activation_bytes(activation_blob)

    @staticmethod
    def extract_activation_bytes(blob_content):
        if (b"BAD_LOGIN" in blob_content or b"WHOOPS" in blob_content) or b"group_id" not in blob_content:
            raise ValueError("Invalid blob content supplied.  Failed to extract activation bytes.")
        k = blob_content.rfind(b"group_id")
        l = blob_content[k:].find(b")")
        keys = blob_content[k + l + 1 + 1:]
        output = []
        output_keys = []
        # each key is of 70 bytes
        for i in range(0, 8):
            key = keys[i * 70 + i:(i + 1) * 70 + i]
            h = binascii.hexlify(bytes(key))
            h = [h[i:i+2] for i in range(0, len(h), 2)]
            h = b",".join(h)
            output_keys.append(h)
            output.append(h.decode('utf-8'))
        # only 4 bytes of output_keys[0] are necessary for decryption! ;)
        activation_bytes = str(output_keys[0].replace(b",", b"")[0:8], 'utf-8')
        # get the endianness right (reverse string in pairs of 2)
        activation_bytes = "".join(reversed([activation_bytes[i:i + 2] for i in
                                             range(0, len(activation_bytes), 2)]))
        return activation_bytes
