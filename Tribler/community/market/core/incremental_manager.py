from price import Price
from quantity import Quantity


class IncrementalQuantityManager(object):
    """Incremental Quantity Manager which determines an incremental quantity list for payments"""

    INITIAL_QUANTITY = 20
    MAX_TRANSACTIONS = 10
    INCREMENTAL_QUANTITY = 200

    @staticmethod
    def determine_incremental_quantity_list(total_quantity):
        """
        Determines an incremental quantity list

        :type total_quantity: Quantity
        :return: Incremental quantity list
        :rtype: List[Quantity]
        """

        # Check whether we should change the INCREMENTAL_QUANTITY to avoid not going over our MAX transactions
        quantity_per_trade = IncrementalQuantityManager.INCREMENTAL_QUANTITY
        if quantity_per_trade * IncrementalQuantityManager.MAX_TRANSACTIONS < int(total_quantity):
            quantity_per_trade = int(total_quantity) / IncrementalQuantityManager.MAX_TRANSACTIONS

        incremental_quantities = []
        remaining_quantity = int(total_quantity)
        if remaining_quantity > 0:
            initial_quantity = min(IncrementalQuantityManager.INITIAL_QUANTITY, remaining_quantity)
            incremental_quantities.append(Quantity(initial_quantity))
            remaining_quantity -= initial_quantity

            while remaining_quantity > 0:
                incremental_quantity = min(quantity_per_trade, remaining_quantity)
                incremental_quantities.append(Quantity(incremental_quantity))
                remaining_quantity -= incremental_quantity
        return incremental_quantities


class IncrementalPriceManager(object):
    """Incremental Price Manager which determines an incremental price list for payments"""

    @staticmethod
    def determine_incremental_price_list(price, incremental_quantities):
        """
        Determines an incremental price list parallel to the incremental quantity list

        :type price: Price
        :type incremental_quantities: List[Quantity]
        :return: Incremental price list
        :rtype: List[Price]
        """
        incremental_prices = []

        for incremental_quantity in incremental_quantities:
            incremental_prices.append(Price(float(price) * int(incremental_quantity)))

        return incremental_prices
