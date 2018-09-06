"""
Configuration object for a download in Tribler.
"""
import logging
import os

from configobj import ConfigObj
from validate import Validator

from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.exceptions import InvalidConfigException
from Tribler.Core.osutils import get_home_dir

SPEC_FILENAME = 'download_config.spec'
CONFIG_SPEC_PATH = os.path.join(get_lib_path(), 'Core', 'Config', SPEC_FILENAME)


def get_default_dest_dir():
    """
    Returns the default dir to save content to.

    If Downloads/ exists: Downloads/TriblerDownloads
    else: Home/TriblerDownloads
    """
    download_dir = u"TriblerDownloads"

    downloads_dir = os.path.join(get_home_dir(), u"Downloads")
    if os.path.isdir(downloads_dir):
        return os.path.join(downloads_dir, download_dir)
    else:
        return os.path.join(get_home_dir(), download_dir)


class TriblerDownloadConfig(object):
    """
    Holds all Tribler download configurable variables.
    """

    def __init__(self, infohash, config_path):
        """
        Create a new TriblerDownloadConfig instance.

        :raises an InvalidConfigException if ConfigObj is invalid
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        if os.path.exists(config_path):
            config = ConfigObj(config_path, configspec=CONFIG_SPEC_PATH, encoding='latin_1')
        else:
            config = ConfigObj(configspec=CONFIG_SPEC_PATH, encoding='latin_1')

        self.config = config
        self.infohash = infohash
        self.validate()

    def validate(self):
        """
        Validate the ConfigObj using Validator.

        Note that `validate()` returns `True` if the ConfigObj is correct and a dictionary with `True` and `False`
        values for keys who's validation failed if at least one key was found to be incorrect.
        """
        validator = Validator()
        validation_result = self.config.validate(validator)
        if validation_result is not True:
            raise InvalidConfigException(msg="TriblerDownloadConfig is invalid: %s" % str(validation_result))

    # General

    def set_dest_dir(self, path):
        self.config['general']['path'] = path

    def get_dest_dir(self):
        """ Gets the directory where to save this Download.
        """
        dest_dir = self.config['general']['path']
        if not dest_dir:
            dest_dir = get_default_dest_dir()
            self.set_dest_dir(dest_dir)

        return dest_dir

    def set_hops(self, hops):
        self.config['general']['hops'] = hops

    def get_hops(self):
        return self.config['general']['hops']

    def set_credit_mining(self, value):
        self.config['general']['credit_mining'] = value

    def get_credit_mining(self):
        return self.config['general']['credit_mining']

    def set_user_stopped(self, value):
        self.config['general']['user_stopped'] = value

    def get_user_stopped(self):
        return self.config['general']['user_stopped']

    def set_time_added(self, value):
        self.config['general']['time_added'] = value

    def get_time_added(self):
        return self.config['general']['time_added']

    def set_selected_files(self, files):
        self.config['general']['selected_files'] = files

    def get_selected_files(self):
        return self.config['general']['selected_files']

    # Seeding

    def set_safe_seeding(self, value):
        self.config['seeding']['safe'] = value

    def get_safe_seeding(self):
        return self.config['seeding']['safe']

    def set_seeding_mode(self, value):
        self.config['seeding']['mode'] = value

    def get_seeding_mode(self):
        return self.config['seeding']['mode']

    def set_seeding_time(self, value):
        self.config['seeding']['time'] = value

    def get_seeding_time(self):
        return self.config['seeding']['time']

    def set_seeding_ratio(self, value):
        self.config['seeding']['ratio'] = value

    def get_seeding_ratio(self):
        return self.config['seeding']['ratio']
