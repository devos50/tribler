import datetime
from PyQt5.QtWidgets import QTreeWidgetItem


class TransactionWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays a transaction.
    """

    def __init__(self, parent, transaction):
        QTreeWidgetItem.__init__(self, parent)
        self.transaction = transaction

    def update_item(self):
        transaction_time = datetime.datetime.fromtimestamp(
            int(self.transaction["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')

        self.setText(0, "%d" % self.transaction["transaction_number"])
        self.setText(1, "%s %s" % (self.transaction["price"], self.transaction["price_type"]))
        self.setText(2, "%s %s" % (self.transaction["quantity"], self.transaction["quantity_type"]))
        self.setText(3, "%s %s" % (self.transaction["transferred_price"], self.transaction["price_type"]))
        self.setText(4, "%s %s" % (self.transaction["transferred_quantity"], self.transaction["quantity_type"]))
        self.setText(5, transaction_time)
