import json

from twisted.web import resource


class WalletEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the wallet resource.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        child_handler_dict = {"balance": WalletBalanceEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))


class WalletBalanceEndpoint(resource.Resource):
    """
    This class handles requests regarding asks in the market community.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        return json.dumps({"balance": self.session.lm.wallet_manager.get_balance()})
