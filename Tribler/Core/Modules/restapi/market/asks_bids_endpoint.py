import json

from twisted.web import http

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.community.market.utils import has_param, get_param


class BaseAsksBidsEndpoint(BaseMarketEndpoint):
    """
    This class acts as the base class for the asks/bids endpoint.
    """

    def create_ask_bid_from_params(self, parameters):
        """
        Create an ask/bid from the provided parameters in a request. This method returns a tuple with the price,
        quantity and timeout of the ask/bid.
        """
        timeout = 3600
        if has_param(parameters, 'timeout'):
            timeout = float(get_param(parameters, 'timeout'))

        price = float(get_param(parameters, 'price'))
        quantity = int(get_param(parameters, 'quantity'))

        return price, quantity, timeout


class AsksEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding asks in the market community.
    """

    def render_GET(self, request):
        asks = []
        for _, price_level in self.get_market_community().order_book.asks.price_level_list.items():
            for ask in price_level:
                asks.append(ask.tick.to_dictionary())

        return json.dumps({"asks": asks})

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'price') or not has_param(parameters, 'quantity'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price or quantity parameter missing"})

        self.get_market_community().create_ask(*self.create_ask_bid_from_params(parameters))
        return json.dumps({"created": True})


class BidsEndpoint(BaseAsksBidsEndpoint):
    """
    This class handles requests regarding bids in the market community.
    """

    def render_GET(self, request):
        bids = []
        for _, price_level in self.get_market_community().order_book.bids.price_level_list.items():
            for bid in price_level:
                bids.append(bid.tick.to_dictionary())

        return json.dumps({"bids": bids})

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'price') or not has_param(parameters, 'quantity'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price or quantity parameter missing"})

        self.get_market_community().create_bid(*self.create_ask_bid_from_params(parameters))
        return json.dumps({"created": True})
