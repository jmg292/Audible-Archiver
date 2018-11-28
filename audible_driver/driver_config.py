import re
import hashlib


class AudibleDriverConfig:

    def __init__(self, config_dict):
        self._config_dict = config_dict
        self.player_id = None

    def _handle_localization(self, url):
        if self._config_dict["language"].lower() != "us":
            return url.replace(".com", ".co.{0}".format(self._config_dict["language"]))
        return url

    def get_player_id(self):
        player_id = self.player_id
        if not self.player_id:
            player_id = hashlib.sha1(b"").hexdigest()
        return player_id

    def set_login_username(self, username):
        self._config_dict["audible_username"] = username

    @property
    def base_url(self):
        return self._handle_localization(self._config_dict["base_url"])

    @property
    def base_licensing_url(self):
        return self._config_dict["base_licensing_url"]

    @property
    def login_elements(self):
        return self._config_dict["audible_login_elements"]

    @property
    def chromedriver_path(self):
        return self._config_dict["chromedriver_path"]

    @property
    def login_url(self):
        if re.match(r"[^@]+@[^@]+\.[^@]+", self._config_dict["audible_username"]):
            login_url = self._config_dict["amazon_login_url"]
        else:
            login_url = self._config_dict["audible_login_url"]
        return self._handle_localization(login_url)

    @property
    def activation_url(self):
        return self._config_dict["activation_url"].format(self.base_url, self.get_player_id())

    @property
    def registration_url(self):
        return self._config_dict["registration_url"].format(self.base_url, self.get_player_id())

    @property
    def deregistration_url(self):
        return self.registration_url + self._config_dict["deregistration_suffix"]

    @property
    def library_url(self):
        return self.base_url + self._config_dict["library_url"]

    @property
    def browser_user_agent(self):
        return self._config_dict["browser_user_agent"]

    @property
    def payload(self):
        payload = self._config_dict["activation_payload"]
        payload["openid.assoc_handle"] = payload["openid.assoc_handle"].format(self._config_dict["language"])
        payload["openid.return_to"] = self.activation_url
        return payload