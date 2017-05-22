"""
This file contains everything related to persistence for TradeChain.
"""
from os import path

from Tribler.community.market.core.order import Order
from Tribler.community.market.core.transaction import Transaction
from Tribler.dispersy.database import Database
from Tribler.community.tradechain.block import TradeChainBlock


DATABASE_DIRECTORY = path.join(u"sqlite")
# Path to the database location + dispersy._workingdirectory
DATABASE_PATH = path.join(DATABASE_DIRECTORY, u"market.db")
# Version to keep track if the db schema needs to be updated.
LATEST_DB_VERSION = 1
# Schema for the Market DB.
schema = u"""
CREATE TABLE IF NOT EXISTS orders(
 trader_id            TEXT NOT NULL,
 order_number         INTEGER NOT NULL,
 price                DOUBLE NOT NULL,
 price_type           TEXT NOT NULL,
 quantity             DOUBLE NOT NULL,
 quantity_type        TEXT NOT NULL,
 traded_quantity      DOUBLE NOT NULL,
 timeout              DOUBLE NOT NULL,
 order_timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
 completed_timestamp  TIMESTAMP,
 is_ask               INTEGER NOT NULL,

 PRIMARY KEY (trader_id, order_number)
 );

 CREATE TABLE IF NOT EXISTS transactions(
  trader_id                TEXT NOT NULL,
  partner_trader_id        TEXT NOT NULL,
  transaction_number       INTEGER NOT NULL,
  order_trader_id          TEXT NOT NULL,
  order_number             INTEGER NOT NULL,
  price                    DOUBLE NOT NULL,
  price_type               TEXT NOT NULL,
  transferred_price        DOUBLE NOT NULL,
  quantity                 DOUBLE NOT NULL,
  quantity_type            TEXT NOT NULL,
  transferred_quantity     DOUBLE NOT NULL,
  transaction_timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  sent_wallet_info         INTEGER NOT NULL,
  received_wallet_info     INTEGER NOT NULL,
  incoming_address         TEXT NOT NULL,
  outgoing_address         TEXT NOT NULL,
  partner_incoming_address TEXT NOT NULL,
  partner_outgoing_address TEXT NOT NULL,

  PRIMARY KEY (trader_id, transaction_number)
 );

CREATE TABLE IF NOT EXISTS traders(
 trader_id            TEXT NOT NULL,
 ip_address           TEXT NOT NULL,
 port                 INTEGER NOT NULL,

 PRIMARY KEY(trader_id)
 );

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_DB_VERSION) + u"""');
"""


class MarketDB(Database):
    """
    Persistence layer for the Market Community.
    Connection layer to SQLiteDB.
    Ensures a proper DB schema on startup.
    """

    def __init__(self, working_directory):
        """
        Sets up the persistence layer ready for use.
        :param working_directory: Path to the working directory
        that will contain the the db at working directory/DATABASE_PATH
        :return:
        """
        super(MarketDB, self).__init__(path.join(working_directory, DATABASE_PATH))
        self.open()

    def get_all_orders(self):
        """
        Return all orders in the database.
        """
        db_result = self.execute(u"SELECT * FROM orders").fetchall()
        return [Order.from_database(db_item) for db_item in db_result]

    def get_order(self, order_id):
        """
        Return an order with a specific id.
        """
        db_result = self.execute(u"SELECT * FROM orders WHERE trader_id = ? AND order_number = ?",
                                 (unicode(order_id.trader_id), unicode(order_id.order_number))).fetchone()
        return Order.from_database(db_result) if db_result else None

    def add_order(self, order):
        """
        Add a specific order to the database
        """
        self.execute(
            u"INSERT INTO orders (trader_id, order_number, price, price_type, quantity, quantity_type,"
            u"traded_quantity, timeout, order_timestamp, completed_timestamp, is_ask) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            order.to_database())
        self.commit()

    def delete_order(self, order_id):
        """
        Delete a specific order from the database
        """
        self.execute(u"DELETE FROM orders WHERE trader_id = ? AND order_number = ?",
                     (unicode(order_id.trader_id), unicode(order_id.order_number)))

    def get_next_order_number(self):
        """
        Return the next order number from the database
        """
        highest_order_number = self.execute(u"SELECT MAX(order_number) FROM orders").fetchone()
        if not highest_order_number[0]:
            return 1
        return highest_order_number[0] + 1

    def get_all_transactions(self):
        """
        Return all transactions in the database.
        """
        db_result = self.execute(u"SELECT * FROM transactions").fetchall()
        return [Transaction.from_database(db_item) for db_item in db_result]

    def get_transaction(self, transaction_id):
        """
        Return a transaction with a specific id.
        """
        db_result = self.execute(u"SELECT * FROM transactions WHERE trader_id = ? AND transaction_number = ?",
                                 (unicode(transaction_id.trader_id),
                                  unicode(transaction_id.transaction_number))).fetchone()
        return Transaction.from_database(db_result) if db_result else None

    def add_transaction(self, transaction):
        """
        Add a specific transaction to the database
        """
        self.execute(
            u"INSERT INTO transactions (trader_id, partner_trader_id, transaction_number, order_trader_id, order_number,"
            u"price, price_type, transferred_price, quantity, quantity_type, transferred_quantity,"
            u"transaction_timestamp, sent_wallet_info, received_wallet_info,"
            u"incoming_address, outgoing_address, partner_incoming_address, partner_outgoing_address) "
            u"VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", transaction.to_database())
        self.commit()

    def delete_transaction(self, transaction_id):
        """
        Delete a specific transaction from the database
        """
        self.execute(u"DELETE FROM transactions WHERE trader_id = ? AND transaction_number = ?",
                     (unicode(transaction_id.trader_id), unicode(transaction_id.transaction_number)))

    def get_next_transaction_number(self):
        """
        Return the next transaction number from the database
        """
        highest_transaction_number = self.execute(u"SELECT MAX(transaction_number) FROM transactions").fetchone()
        if not highest_transaction_number[0]:
            return 1
        return highest_transaction_number[0] + 1

    def add_trader_identity(self, trader_id, ip, port):
        self.execute(u"INSERT OR REPLACE INTO traders VALUES(?,?,?)", (unicode(trader_id), unicode(ip), port))
        self.commit()

    def get_traders(self):
        return self.execute(u"SELECT * FROM traders").fetchall()

    def open(self, initial_statements=True, prepare_visioning=True):
        return super(MarketDB, self).open(initial_statements, prepare_visioning)

    def close(self, commit=True):
        return super(MarketDB, self).close(commit)

    def check_database(self, database_version):
        """
        Ensure the proper schema is used by the database.
        :param database_version: Current version of the database.
        :return:
        """
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        if database_version < LATEST_DB_VERSION:
            self.executescript(schema)
            self.commit()

        return LATEST_DB_VERSION
