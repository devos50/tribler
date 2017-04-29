import json

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


class OrdersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your orders in the market community.
    """

    def render_GET(self, request):
        orders = self.get_market_community().order_manager.order_repository.find_all()
        return json.dumps({"orders": [order.to_dictionary() for order in orders]})
