import unittest

from Tribler.community.market.core.incremental_manager import IncrementalManager
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity


class IncrementalPaymentManagerTests(unittest.TestCase):
    """Incremental payment manager test cases."""

    def test_single_payment(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1), Quantity(1))
        self.assertEqual(pay_list, [(Quantity(1), Price(1))])

    def test_payment_unround(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1), Quantity(2))
        self.assertEqual(pay_list, [(Quantity(1), Price(1)), (Quantity(1), Price(1))])

    def test_payment_max(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(300), Quantity(2000))
        self.assertEqual(len(pay_list), IncrementalManager.MAX_TRANSACTIONS)
        self.assertEqual(pay_list[-1], (Quantity(200), Price(200 * 300)))

    def test_payment_last_not_fit(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1), Quantity(12))
        self.assertEqual(len(pay_list), IncrementalManager.MAX_TRANSACTIONS)
        self.assertEqual(pay_list[-1], (Quantity(3), Price(3)))

if __name__ == '__main__':
    unittest.main()
