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

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(100, int(self.price2))
        self.assertEqual(float('2.3'), self.price1.__float__())

    def test_addition(self):
        # Test for addition
        self.assertEqual(Price(102.3), self.price1 + self.price2)
        self.assertFalse(self.price1 is (self.price1 + self.price2))
        self.assertEqual(NotImplemented, self.price1.__add__(10))

    def test_subtraction(self):
        # Test for subtraction
        self.assertEqual(Price(97.7), self.price2 - self.price1)
        self.assertFalse(self.price2 is (self.price2 - self.price2))
        self.assertEqual(NotImplemented, self.price1.__sub__(10))
        with self.assertRaises(ValueError):
            self.price1 - self.price2

    def test_comparison(self):
        # Test for comparison
        self.assertTrue(self.price1 < self.price2)
        self.assertTrue(self.price1 <= self.price1)
        self.assertTrue(self.price2 > self.price1)
        self.assertTrue(self.price3 >= self.price3)
        self.assertEqual(NotImplemented, self.price1.__le__(10))
        self.assertEqual(NotImplemented, self.price1.__lt__(10))
        self.assertEqual(NotImplemented, self.price1.__ge__(10))
        self.assertEqual(NotImplemented, self.price1.__gt__(10))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.price1 == Price(2.3))
        self.assertTrue(self.price1 != self.price2)
        self.assertFalse(self.price1 == 2.3)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.price1.__hash__(), Price(2.3).__hash__())
        self.assertNotEqual(self.price1.__hash__(), self.price2.__hash__())


if __name__ == '__main__':
    unittest.main()
