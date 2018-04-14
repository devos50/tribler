import logging

from Tribler.community.market.core.order import OrderId, Order
from Tribler.community.market.core.order_repository import OrderRepository
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class OrderManager(object):
    """Provides an interface to the user to manage the users orders"""

    def __init__(self, order_repository):
        """
        :type order_repository: OrderRepository
        """
        super(OrderManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Market OrderManager initialized")

        assert isinstance(order_repository, OrderRepository), type(order_repository)

        self.order_repository = order_repository

    def create_ride_offer(self, latitude, longitude, quantity, timeout):
        """
        Create a taxi ride order (sell order)

        :param latitude: The latitude of the taxi driver
        :param longitude: The longitude of the taxi driver
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type latitude: float
        :type longitude: float
        :type quantity: Quantity
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(latitude, float), type(latitude)
        assert isinstance(longitude, float), type(longitude)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)

        order = Order(self.order_repository.next_identity(), latitude, longitude, quantity, timeout, Timestamp.now(),
                      True)
        self.order_repository.add(order)

        self._logger.info("Ride offer order created with id: " + str(order.order_id))

        return order

    def create_ride_request(self, latitude, longitude, quantity, timeout):
        """
        Create a taxi ride offer (buy order)

        :param latitude: The latitude of the taxi requester
        :param longitude: The longitude of the taxi requester
        :param quantity: The quantity of the order
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type latitude: float
        :type longitude: float
        :type quantity: Quantity
        :type timeout: Timeout
        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(latitude, float), type(latitude)
        assert isinstance(longitude, float), type(longitude)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)

        order = Order(self.order_repository.next_identity(), latitude, longitude, quantity, timeout, Timestamp.now(),
                      False)
        self.order_repository.add(order)

        self._logger.info("Ride request order created with id: " + str(order.order_id))

        return order

    def cancel_order(self, order_id):
        """
        Cancel an order that was created by the user.
        :return: The order that is created
        :rtype: Order
        """
        assert isinstance(order_id, OrderId), type(order_id)

        order = self.order_repository.find_by_id(order_id)

        if order:
            order.cancel()
            self.order_repository.update(order)

        self._logger.info("Order cancelled with id: " + str(order_id))
