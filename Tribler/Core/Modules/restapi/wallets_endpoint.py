import json

from twisted.web import http
from twisted.web import resource


class WalletsEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the wallets resource.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        wallets = {}
        for wallet_id in self.session.lm.wallets.keys():
            wallet = self.session.lm.wallets[wallet_id]
            wallets[wallet_id] = {'created': wallet.created, 'balance': wallet.get_balance(),
                                  'address': wallet.get_address()}
        return json.dumps({"wallets": wallets})

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

        child_handler_dict = {"balance": WalletBalanceEndpoint, "transactions": WalletTransactionsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session, self.identifier))

    def render_PUT(self, request):
        if self.session.lm.wallets[self.identifier].created:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "this wallet already exists"})

        parameters = http.parse_qs(request.content.read(), 1)

        if self.identifier == "btc":  # get the password
            password = ''
            if parameters['password'] and len(parameters['password']) > 0:
                password = parameters['password'][0]
                self.session.lm.wallets[self.identifier].create_wallet(password=password)
        else:
            # We do not support creation of other wallets besides BTC right now
            pass

        return json.dumps({"created": True})


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


class WalletTransactionsEndpoint(resource.Resource):
    """
    This class handles requests regarding the transactions of a wallet.
    """

    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier

    def render_GET(self, request):
        return json.dumps({"transactions": self.session.lm.wallets[self.identifier].get_transactions()})
