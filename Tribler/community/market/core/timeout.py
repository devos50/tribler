import datetime
import time

from timestamp import Timestamp


class Timeout(object):
    """Used for having a validated instance of a timeout that we can easily check if it still valid."""

    def __init__(self, timeout):
        """
        :param timeout: Float representation of a timeout
        :type timeout: float
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Timeout, self).__init__()

        if not isinstance(timeout, (float, int)):
            raise ValueError("Timeout must be a float or an integer")

        if timeout < 0:
            raise ValueError("Timeout must be positive or zero")

        self._timeout = timeout

    def is_timed_out(self, timestamp):
        """
        Return if a timeout has occurred

        :param timestamp: A timestamp
        :type timestamp: Timestamp
        :return: True if timeout has occurred, False otherwise
        :rtype: bool
        """
        assert isinstance(timestamp, Timestamp), type(timestamp)

        if (time.time() + self._timeout) < timestamp:
            return True
        else:
            return False

    def __float__(self):
        return float(self._timeout)

    def __str__(self):
        return "%s" % datetime.datetime.fromtimestamp(self._timeout)

    def __hash__(self):
        return hash(self._timeout)
