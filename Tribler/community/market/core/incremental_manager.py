from price import Price
from quantity import Quantity


class IncrementalManager(object):
    """Incremental Manager which determines an incremental quantity list for payments"""

    MIN_QUANTITY = 1
    MAX_TRANSACTIONS = 10

    @staticmethod
    def determine_incremental_payments_list(price, total_quantity):
        """
        Determines an incremental payments list

        :type price: Price
        :type total_quantity: Quantity
        :return: Incremental quantity list
        :rtype: List[(Quantity, Price)]
        """

        if int(total_quantity) < IncrementalManager.MIN_QUANTITY * IncrementalManager.MAX_TRANSACTIONS:
            num_transactions = int(total_quantity)
            min_quantity_per_trade = IncrementalManager.MIN_QUANTITY
        else:
            num_transactions = IncrementalManager.MAX_TRANSACTIONS
            min_quantity_per_trade = int(total_quantity) / IncrementalManager.MAX_TRANSACTIONS

        incremental_payments = []
        remaining_quantity = int(total_quantity)
        for ind in xrange(num_transactions):
            if ind == num_transactions - 1:  # We are at the last transaction
                transfer_quantity = remaining_quantity
            else:
                transfer_quantity = min_quantity_per_trade
            remaining_quantity -= transfer_quantity
            incremental_payments.append((Quantity(transfer_quantity),
                                         Price(float(price) * transfer_quantity, price.wallet_id)))

        return incremental_payments
