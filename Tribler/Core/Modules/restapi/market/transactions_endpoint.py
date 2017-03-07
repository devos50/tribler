import json

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


class TransactionsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding (past) transactions in the market community.
    """

    def render_GET(self, request):
        transactions = self.get_market_community().transaction_manager.find_all()
        return json.dumps({"transactions": [transaction.to_dictionary() for transaction in transactions]})
