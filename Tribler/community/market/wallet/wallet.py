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

    def get_identifier(self):
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
