from twisted.web import resource

from Tribler.community.market.restapi.asks_endpoint import AsksEndpoint


class RootEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the market community API where we trade MultiChain reputation.
    """

    def __init__(self, session, market_community):
        resource.Resource.__init__(self)
        self.session = session
        self.market_community = market_community

        child_handler_dict = {"asks": AsksEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.market_community))
