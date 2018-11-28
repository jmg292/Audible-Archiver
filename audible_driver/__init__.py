import sys
import time

from selenium import webdriver

using_python3 = sys.version_info[0] == 3

try:
    import audible_driver.driver_config
except ImportError:
    import driver_config

if using_python3:
    from urllib.parse import urlencode, urlparse, parse_qsl
else:
    from urllib import urlencode
    from urlparse import urlparse, parse_qsl


class AudibleDriver(object):

    def __init__(self, config: driver_config.AudibleDriverConfig):
        self.config = config
        self._driver_handle = None

    def __enter__(self):
        self.start_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_driver()

    def start_driver(self):
        if not self._driver_handle:
            opts = webdriver.ChromeOptions()
            opts.add_argument("silent")
            opts.add_argument("user-agent={0}".format(self.config.browser_user_agent))
            self._driver_handle = webdriver.Chrome(options=opts, executable_path=self.config.chromedriver_path)
        self._driver_handle.get(self.config.base_url + "?ipRedirectOverride=true")

    def stop_driver(self):
        self._driver_handle.quit()
        self._driver_handle = None

    def log_on(self, username, password, mfa_token=None):
        self.config.set_login_username(username)
        query_string = urlencode(self.config.payload)
        self._driver_handle.get(self.config.login_url + query_string)
        if not mfa_token:
            login_elements = self.config.login_elements
            self._driver_handle.find_element_by_id(login_elements["username"]).send_keys(username)
            password_box = self._driver_handle.find_element_by_id(login_elements["password"])
            password_box.send_keys(password)
            password_box.submit()
            time.sleep(2)  # Let the page load
        else:
            # I'll implement this some day
            raise NotImplementedError("MFA Not yet supported.")

    def get_activation_session_data(self):
        self._driver_handle.get(self.config.activation_url)
        session_data = dict(parse_qsl(urlparse(self._driver_handle.current_url).query))
        session_cookies = self._driver_handle.get_cookies()
        return {"data": session_data, "cookies": session_cookies}
