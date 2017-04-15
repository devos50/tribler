import logging

from Tribler.community.market.core.order import Order
from payment import Payment
from timeout import Timeout
from timestamp import Timestamp
from trade import AcceptedTrade
from transaction import TransactionId, Transaction, StartTransaction
from transaction_repository import TransactionRepository


class TransactionManager(object):
    """Manager for retrieving and creating transactions"""

    def __init__(self, transaction_repository):
        """
        :type transaction_repository: TransactionRepository
        """
        super(TransactionManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Transaction Manager initialized")

        assert isinstance(transaction_repository, TransactionRepository), type(transaction_repository)

        self.transaction_repository = transaction_repository

    def create_from_accepted_trade(self, accepted_trade):
        """
        :type accepted_trade: AcceptedTrade
        :rtype: Transaction
        """
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)

        transaction = Transaction.from_accepted_trade(accepted_trade, self.transaction_repository.next_identity())
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: %s, quantity: %s",
                          str(transaction.transaction_id), str(transaction.total_quantity))
        return transaction

    def create_from_start_transaction(self, start_transaction, order):
        """
        :type start_transaction: StartTransaction
        :type order: Order
        :rtype: Transaction
        """
        assert isinstance(start_transaction, StartTransaction), type(start_transaction)
        assert isinstance(order, Order), type(order)

        transaction = Transaction(start_transaction.transaction_id, start_transaction.transaction_id.trader_id,
                                  start_transaction.price, start_transaction.quantity, order.order_id,
                                  order.timeout, Timestamp.now())
        self.transaction_repository.add(transaction)

        self._logger.info("Transaction created with id: %s, quantity: %s, price: %s",
                          str(transaction.transaction_id), str(transaction.total_quantity), str(transaction.price))

        return transaction

    def create_payment_message(self, message_id, payment_id, transaction, payment):
        payment_message = Payment(message_id, transaction.transaction_id, payment[0], payment[1],
                                      transaction.outgoing_address, transaction.partner_incoming_address,
                                      payment_id, Timestamp.now())
        transaction.add_payment(payment_message)
        self.transaction_repository.update(transaction)

        return payment_message

    def find_by_id(self, transaction_id):
        """
        :param transaction_id: The transaction id to look for
        :type transaction_id: TransactionId
        :return: The transaction or null if it cannot be found
        :rtype: Transaction
        """
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        return self.transaction_repository.find_by_id(transaction_id)

    def find_all(self):
        """
        :rtype: [Transaction]
        """
        return self.transaction_repository.find_all()
