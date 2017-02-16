import json

from twisted.web import http
from twisted.web import resource

from Tribler.community.market.utils import has_param, get_param


class AsksEndpoint(resource.Resource):
    """
    This class handles requests regarding asks in the market community.
    """

    def __init__(self, market_community):
        resource.Resource.__init__(self)
        self.market_community = market_community

    def render_GET(self, request):
        asks = []
        for _, price_level in self.market_community.order_book.asks.price_level_list.items():
            for ask in price_level:
                asks.append({'price': str(ask.price), 'quantity': str(ask.quantity),
                             'timestamp': float(ask.tick.timestamp)})

        return json.dumps({"asks": asks})

    def render_PUT(self, request):
        parameters = http.parse_qs(request.content.read(), 1)

        if not has_param(parameters, 'price') or not has_param(parameters, 'quantity'):
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "price or quantity parameter missing"})

        timeout = 3600
        if has_param(parameters, 'timeout'):
            timeout = float(get_param(parameters, 'timeout'))

        price = float(get_param(parameters, 'price'))
        quantity = float(get_param(parameters, 'quantity'))

        self.market_community.create_ask(price, quantity, timeout)
        return json.dumps({"created": True})
