import unittest

from Tribler.community.market.core.incremental_manager import IncrementalManager
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity


class IncrementalPaymentManagerTests(unittest.TestCase):
    """Incremental payment manager test cases."""

    def test_ic_1(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1, 'BTC'), Quantity(1, 'MC'), 1, 1)
        self.assertEqual(pay_list, [(Quantity(1, 'MC'), Price(1, 'BTC'))])

    def test_ic_2(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1, 'BTC'), Quantity(1, 'MC'),
                                                                          0.00001, 1)
        self.assertEqual(pay_list, [(Quantity(1, 'MC'), Price(1, 'BTC'))])

    def test_ic_3(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1, 'BTC'), Quantity(1, 'MC'),
                                                                          1, 0.00001)
        self.assertEqual(pay_list, [(Quantity(1, 'MC'), Price(1, 'BTC'))])

    def test_ic_4(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(2, 'BTC'), Quantity(2, 'MC'), 1, 1)
        self.assertEqual(pay_list, [(Quantity(1, 'MC'), Price(1, 'BTC')), (Quantity(1, 'MC'), Price(1, 'BTC'))])

    def test_ic_5(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(10, 'BTC'), Quantity(10, 'MC'), 1, 1)
        self.assertEqual(pay_list, [(Quantity(1, 'MC'), Price(1, 'BTC')), (Quantity(2, 'MC'), Price(2, 'BTC')),
                                    (Quantity(4, 'MC'), Price(4, 'BTC')), (Quantity(3, 'MC'), Price(3, 'BTC'))])

    def test_ic_6(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(1, 'EUR'), Quantity(10, 'MC'), 0.01, 1)
        self.assertEqual(len(pay_list), 4)

    def test_ic_7(self):
        pay_list = IncrementalManager.determine_incremental_payments_list(Price(0.02, 'EUR'), Quantity(10, 'MC'),
                                                                          0.01, 1)
        self.assertEqual(len(pay_list), 2)

if __name__ == '__main__':
    unittest.main()
