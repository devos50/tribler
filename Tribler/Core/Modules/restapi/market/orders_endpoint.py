import json

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


class OrdersEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding your orders in the market community.
    """

    def render_GET(self, request):
        """
        .. http:get:: /market/orders

        A GET request to this endpoint will return all your orders in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/orders

            **Example response**:

            .. sourcecode:: javascript

                {
                    "orders": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "timestamp": 1493906434.627721,
                        "price": 10.0,
                        "quantity_type": "MC",
                        "reserved_quantity": 0.0,
                        "is_ask": False,
                        "price_type": "BTC",
                        "timeout": 3600.0,
                        "traded_quantity": 0.0,
                        "order_number": 1,
                        "completed_timestamp": null,
                        "quantity": 10.0
                    }]
                }
        """
        orders = self.get_market_community().order_manager.order_repository.find_all()
        return json.dumps({"orders": [order.to_dictionary() for order in orders]})
