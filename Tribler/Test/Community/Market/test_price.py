import unittest

from Tribler.community.market.core.price import Price
from decimal import Decimal


class PriceTestSuite(unittest.TestCase):
    """Price test cases."""

    def setUp(self):
        # Object creation
        self.price1 = Price(2.3)
        self.price2 = Price(100)
        self.price3 = Price(0)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            Price(-1)
        with self.assertRaises(ValueError):
            Price(1.0)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(63400, int(self.price))
        self.assertEqual(63400, int(self.price2))
        self.assertEqual('6.3400', str(self.price))
        self.assertEqual('6.3400', str(self.price2))
        self.assertEqual(float('6.3400'), self.price.__float__())
        self.assertEqual(float('6.3400'), self.price2.__float__())

    def test_addition(self):
        # Test for addition
        self.assertEqual(Price(102.3), self.price1 + self.price2)
        self.assertFalse(self.price1 is (self.price1 + self.price2))
        self.assertEqual(NotImplemented, self.price1.__add__(10))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(Price.from_float(11.96), self.price4 - self.price2)
        self.assertFalse(self.price is (self.price - self.price))
        self.price3 -= self.price5
        self.assertEqual(Price.from_float(6.34), self.price3)
        self.assertEqual(NotImplemented, self.price.__sub__(10))
        with self.assertRaises(ValueError):
            self.price - self.price4

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.price2 < self.price4)
        self.assertTrue(self.price4 <= self.price4)
        self.assertTrue(self.price4 > self.price2)
        self.assertTrue(self.price4 >= self.price4)
        self.assertEqual(NotImplemented, self.price.__le__(10))
        self.assertEqual(NotImplemented, self.price.__lt__(10))
        self.assertEqual(NotImplemented, self.price.__ge__(10))
        self.assertEqual(NotImplemented, self.price.__gt__(10))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.price == self.price3)
        self.assertTrue(self.price == self.price)
        self.assertTrue(self.price != self.price4)
        self.assertFalse(self.price == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.price.__hash__(), self.price3.__hash__())
        self.assertNotEqual(self.price.__hash__(), self.price4.__hash__())


if __name__ == '__main__':
    unittest.main()
