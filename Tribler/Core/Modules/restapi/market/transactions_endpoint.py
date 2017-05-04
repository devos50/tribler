import json

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint


class TransactionsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding (past) transactions in the market community.
    """

    def render_GET(self, request):
        """
        .. http:get:: /market/transactions

        A GET request to this endpoint will return all performed transactions in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/transactions

            **Example response**:

            .. sourcecode:: javascript

                {
                    "transactions": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "order_number": 4,
                        "partner_trader_id": "34c406358ba05e5883a75da3f009477e4ca699a9",
                        "transaction_number": 3,
                        "price": 10,
                        "price_type": "MC",
                        "quantity": 10,
                        "quantity_type": "BTC",
                        "timestamp": 1493906434.627721,
                        "total_payments": 4,
                        "current_payment": 2,
                        "payment_complete": False
                    ]
                }
        """
        transactions = self.get_market_community().transaction_manager.find_all()
        return json.dumps({"transactions": [transaction.to_dictionary() for transaction in transactions]})
