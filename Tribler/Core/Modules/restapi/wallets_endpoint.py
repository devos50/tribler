import json

from twisted.internet.defer import DeferredList
from twisted.web import http
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET


class WalletsEndpoint(resource.Resource):
    """
    This class represents the root endpoint of the wallets resource.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        wallets = {}
        balance_deferreds = []
        for wallet_id in self.session.lm.market_community.wallets.keys():
            wallet = self.session.lm.market_community.wallets[wallet_id]
            wallets[wallet_id] = {'created': wallet.created, 'address': wallet.get_address(), 'name': wallet.get_name()}
            balance_deferreds.append(wallet.get_balance().addCallback(
                lambda balance, wid=wallet_id: (wid, balance)))

        def on_received_balances(balances):
            for error, balance_info in balances:
                wallets[balance_info[0]]['balance'] = balance_info[1]

            request.write(json.dumps({"wallets": wallets}))
            request.finish()

        balance_deferred_list = DeferredList(balance_deferreds)
        balance_deferred_list.addCallback(on_received_balances)

        return NOT_DONE_YET

    def getChild(self, path, request):
        return WalletEndpoint(self.session, path)


class WalletEndpoint(resource.Resource):
    """
    This class represents the endpoint for a single wallet.
    """
    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier.upper()

        child_handler_dict = {"balance": WalletBalanceEndpoint, "transactions": WalletTransactionsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session, self.identifier))

    def render_PUT(self, request):
        if self.session.lm.market_community.wallets[self.identifier].created:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "this wallet already exists"})

        def on_wallet_created(_):
            request.write(json.dumps({"created": True}))
            request.finish()

        parameters = http.parse_qs(request.content.read(), 1)

        if self.identifier == "BTC":  # get the password
            if parameters['password'] and len(parameters['password']) > 0:
                password = parameters['password'][0]
                self.session.lm.market_community.wallets[self.identifier].create_wallet(password=password)\
                    .addCallback(on_wallet_created)
        else:
            self.session.lm.market_community.wallets[self.identifier].create_wallet().addCallback(on_wallet_created)

        return NOT_DONE_YET


class WalletBalanceEndpoint(resource.Resource):
    """
    This class handles requests regarding the balance in a wallet.
    """

    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier

    def render_GET(self, request):
        return json.dumps({"balance": self.session.lm.market_community.wallets[self.identifier].get_balance()})


class WalletTransactionsEndpoint(resource.Resource):
    """
    This class handles requests regarding the transactions of a wallet.
    """

    def __init__(self, session, identifier):
        resource.Resource.__init__(self)
        self.session = session
        self.identifier = identifier

    def render_GET(self, request):
        return json.dumps({"transactions": self.session.lm.market_community.wallets[self.identifier].get_transactions()})
