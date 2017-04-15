from price import Price
from quantity import Quantity


class IncrementalManager(object):
    """Incremental Manager which determines an incremental quantity list for payments"""

    MIN_QUANTITY = 1
    MAX_TRANSACTIONS = 10

    @staticmethod
    def determine_incremental_payments_list(total_price, total_quantity, min_unit_price, min_unit_quantity):
        """
        Determines an incremental payments list

        :type total_price: Price
        :type total_quantity: Quantity
        :type min_unit_price: float
        :type min_unit_quantity: float
        :return: Incremental quantity list
        :rtype: List[(Quantity, Price)]
        """

        incremental_payments = []

        # First, we determine the minimum amount of transactions needed
        transactions_needed = min(IncrementalManager.transactions_needed(float(total_price), min_unit_price),
                                  IncrementalManager.transactions_needed(float(total_quantity), min_unit_quantity))

        price_left = total_price
        quantity_left = total_quantity

        for cur_transaction in xrange(transactions_needed):
            price = Price(min_unit_price * (2 ** cur_transaction), total_price.wallet_id)
            quantity = Quantity(min_unit_quantity * (2 ** cur_transaction), total_quantity.wallet_id)
            if price > price_left:
                price = price_left
            if quantity > quantity_left:
                quantity = quantity_left

            price_left -= price
            quantity_left -= quantity

            # If we have some left in the last transaction, fill it up
            if price_left > Price(0, price.wallet_id) and cur_transaction == transactions_needed - 1:
                price += price_left
            if quantity_left > Quantity(0, quantity.wallet_id) and cur_transaction == transactions_needed - 1:
                quantity += quantity_left

            incremental_payments.append((quantity, price))

        return incremental_payments

    @staticmethod
    def transactions_needed(amount, min_amount):
        amount_left = amount
        cur_transaction = 0
        while amount_left > 0:
            amount_left -= min_amount * (2 ** cur_transaction)
            cur_transaction += 1

        return cur_transaction
