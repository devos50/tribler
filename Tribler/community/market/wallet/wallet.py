import logging
import random
import string

from Tribler.dispersy.taskmanager import TaskManager


class InsufficientFunds(Exception):
    """
    Used for throwing exception when there isn't sufficient funds available to transfer assets.
    """
    pass


class Wallet(TaskManager):
    """
    This is the base class of a wallet and contains various methods that every wallet should implement.
    To create your own wallet, subclass this class and implement the required methods.
    """
    def __init__(self):
        super(Wallet, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        # Properties for the monitor poll mechanism
        self.min_poll_interval = 1
        self.max_poll_interval = 10
        self.max_poll_duration = 180

    def generate_txid(self, length=10):
        """
        Generate a random transaction ID
        """
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

    def get_identifier(self):
        raise NotImplementedError("Please implement this method.")

    def get_name(self):
        raise NotImplementedError("Please implement this method.")

    def create_wallet(self, *args, **kwargs):
        raise NotImplementedError("Please implement this method.")

    def get_balance(self):
        raise NotImplementedError("Please implement this method.")

    def transfer(self, *args, **kwargs):
        raise NotImplementedError("Please implement this method.")

    def get_address(self):
        raise NotImplementedError("Please implement this method.")

    def get_transactions(self):
        raise NotImplementedError("Please implement this method.")

    def min_unit(self):
        raise NotImplementedError("Please implement this method.")