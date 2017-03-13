import json

from twisted.web import resource


class WalletsEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the wallets resource.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        return json.dumps({"wallets": self.session.lm.wallets.keys()})

    def getChild(self, path, request):
        return WalletEndpoint(self.session, path)


class WalletEndpoint(resource.Resource):
    """
    This class represents the endpoint for a single wallet.
    """
    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier

        child_handler_dict = {"balance": WalletBalanceEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session, self.identifier))


class WalletBalanceEndpoint(resource.Resource):
    """
    This class handles requests regarding the balance in a wallet.
    """

    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier

    def render_GET(self, request):
        return json.dumps({"balance": self.session.lm.wallets[self.identifier].get_balance()})
