import unittest

from Tribler.community.market.core.payment_id import PaymentId


class PaymentIdTestSuite(unittest.TestCase):
    """Payment Id test cases."""

    def setUp(self):
        self.payment_id1 = PaymentId(b"3")
        self.payment_id2 = PaymentId(b"4")

    def test_bytes(self):
        """
        Test the bytes representation of a payment id
        """
        self.assertEqual(bytes(self.payment_id1), b"3")

    def test_equality(self):
        """
        Test equality between payment ids
        """
        self.assertEqual(self.payment_id1, PaymentId(b"3"))
        self.assertNotEqual(self.payment_id1, self.payment_id2)
        self.assertEqual(NotImplemented, self.payment_id1.__eq__(b"3"))

    def test_hash(self):
        """
        Test the hash creation of a payment id
        """
        self.assertEqual(self.payment_id1.__hash__(), b"3".__hash__())
        self.assertNotEqual(self.payment_id1.__hash__(), self.payment_id2.__hash__())
