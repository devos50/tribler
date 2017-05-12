import unittest

from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction, StartTransaction
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade


class TransactionNumberTestSuite(unittest.TestCase):
    """Message number test cases."""

    def setUp(self):
        # Object creation
        self.transaction_number = TransactionNumber(1)
        self.transaction_number2 = TransactionNumber(1)
        self.transaction_number3 = TransactionNumber(3)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(1, int(self.transaction_number))
        self.assertEqual('1', str(self.transaction_number))

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            TransactionNumber(1.0)

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_number == self.transaction_number2)
        self.assertTrue(self.transaction_number == self.transaction_number)
        self.assertTrue(self.transaction_number != self.transaction_number3)
        self.assertFalse(self.transaction_number == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_number.__hash__(), self.transaction_number2.__hash__())
        self.assertNotEqual(self.transaction_number.__hash__(), self.transaction_number3.__hash__())


class TransactionIdTestSuite(unittest.TestCase):
    """Transaction ID test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId('0'), TransactionNumber(1))
        self.transaction_id2 = TransactionId(TraderId('0'), TransactionNumber(1))
        self.transaction_id3 = TransactionId(TraderId('0'), TransactionNumber(2))

    def test_properties(self):
        # Test for properties
        self.assertEqual(TraderId('0'), self.transaction_id.trader_id)
        self.assertEqual(TransactionNumber(1), self.transaction_id.transaction_number)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('0.1', str(self.transaction_id))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_id == self.transaction_id2)
        self.assertTrue(self.transaction_id == self.transaction_id)
        self.assertTrue(self.transaction_id != self.transaction_id3)
        self.assertFalse(self.transaction_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_id.__hash__(), self.transaction_id2.__hash__())
        self.assertNotEqual(self.transaction_id.__hash__(), self.transaction_id3.__hash__())


class TransactionTestSuite(unittest.TestCase):
    """Transaction test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, TraderId("2"), Price(100, 'BTC'), Quantity(30, 'MC'),
                                       OrderId(TraderId('3'), OrderNumber(2)), Timestamp(0.0))
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('1')),
                                       OrderId(TraderId('0'), OrderNumber(2)),
                                       OrderId(TraderId('1'), OrderNumber(3)),
                                       Price(100, 'BTC'), Quantity(30, 'MC'), Timestamp(0.0))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('1')),
                                           Timestamp(0.0), proposed_trade)

    def test_from_accepted_trade(self):
        # Test from accepted trade
        transaction = Transaction.from_accepted_trade(self.accepted_trade, self.transaction_id)
        self.assertEqual(transaction.price, self.transaction.price)
        self.assertEqual(transaction.total_quantity, self.transaction.total_quantity)
        self.assertEqual(transaction.timestamp, self.transaction.timestamp)


class StartTransactionTestSuite(unittest.TestCase):
    """Start transaction test cases."""

    def setUp(self):
        # Object creation
        self.start_transaction = StartTransaction(MessageId(TraderId('0'), MessageNumber('1')),
                                                  TransactionId(TraderId("0"), TransactionNumber(1)),
                                                  OrderId(TraderId('0'), OrderNumber(1)),
                                                  OrderId(TraderId('1'), OrderNumber(1)),
                                                  Price(30, 'BTC'), Quantity(40, 'MC'), Timestamp(0.0))

    def test_from_network(self):
        # Test for from network
        data = StartTransaction.from_network(
            type('Data', (object,), {"trader_id": TraderId('0'),
                                     "message_number": MessageNumber("1"),
                                     "transaction_trader_id": TraderId('0'),
                                     "transaction_number": TransactionNumber(1),
                                     "order_trader_id": TraderId('0'),
                                     "order_number": OrderNumber(1),
                                     "recipient_trader_id": TraderId('1'),
                                     "recipient_order_number": OrderNumber(2),
                                     "price": Price(300, 'BTC'),
                                     "quantity": Quantity(20, 'MC'),
                                     "timestamp": Timestamp(0.0)}))

        self.assertEquals(MessageId(TraderId("0"), MessageNumber("1")), data.message_id)
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber(1)), data.transaction_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber(1)), data.order_id)
        self.assertEquals(Timestamp(0.0), data.timestamp)

    if __name__ == '__main__':
        unittest.main()
