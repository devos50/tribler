import hashlib

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_MARKET_TRANSACTIONS
from TriblerGUI.dialogs.newmarketorderdialog import NewMarketOrderDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path
from TriblerGUI.widgets.tickwidgetitem import TickWidgetItem


class MarketPage(QWidget):
    """
    This page displays the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.btc_request_mgr = None
        self.mc_request_mgr = None
        self.request_mgr = None
        self.dialog = None
        self.initialized = False

    def initialize_market_page(self):

        if not self.initialized:
            self.window().market_back_button.setIcon(QIcon(get_image_path('page_back.png')))

            self.window().core_manager.events_manager.received_market_ask.connect(self.on_ask)
            self.window().core_manager.events_manager.received_market_bid.connect(self.on_bid)
            self.window().core_manager.events_manager.market_transaction_complete.connect(self.on_transaction_complete)

            self.window().create_ask_button.clicked.connect(self.on_create_ask_clicked)
            self.window().create_bid_button.clicked.connect(self.on_create_bid_clicked)
            self.window().market_transactions_button.clicked.connect(self.on_transactions_button_clicked)

            # Sort asks ascending and bids descending
            self.window().asks_list.sortItems(2, Qt.AscendingOrder)
            self.window().bids_list.sortItems(2, Qt.DescendingOrder)

            self.window().asks_list.itemSelectionChanged.connect(
                lambda: self.on_tick_item_clicked(self.window().asks_list))
            self.window().bids_list.itemSelectionChanged.connect(
                lambda: self.on_tick_item_clicked(self.window().bids_list))

            self.window().tick_detail_container.hide()

            self.initialized = True

        self.load_btc_wallet_balance()
        self.load_mc_wallet_balance()
        self.load_asks()

    def load_btc_wallet_balance(self):
        self.btc_request_mgr = TriblerRequestManager()
        self.btc_request_mgr.perform_request("wallets/btc/balance", self.on_btc_wallet_balance)

    def on_btc_wallet_balance(self, balance):
        balance = balance["balance"]
        self.window().btc_amount_label.setText("%s" % balance["confirmed"])

    def load_mc_wallet_balance(self):
        self.mc_request_mgr = TriblerRequestManager()
        self.mc_request_mgr.perform_request("wallets/mc/balance", self.on_mc_wallet_balance)

    def on_mc_wallet_balance(self, balance):
        balance = balance["balance"]
        self.window().net_score_label.setText("%s" % balance)

    def create_widget_item_from_tick(self, tick_list, tick, is_ask=True):
        tick["type"] = "ask" if is_ask else "bid"
        item = TickWidgetItem(tick_list, tick)
        item.setText(0, hashlib.sha1(tick["trader_id"]).hexdigest()[:10])
        item.setText(1, "%d" % tick["quantity"])
        item.setText(2, tick["price"])
        return item

    def load_asks(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/asks", self.on_received_asks)

    def on_received_asks(self, asks):
        self.window().asks_list.clear()
        for ask in asks["asks"]:
            self.window().asks_list.addTopLevelItem(
                self.create_widget_item_from_tick(self.window().asks_list, ask, is_ask=True))
        self.load_bids()

    def load_bids(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/bids", self.on_received_bids)

    def on_received_bids(self, bids):
        self.window().bids_list.clear()
        for bid in bids["bids"]:
            self.window().bids_list.addTopLevelItem(
                self.create_widget_item_from_tick(self.window().bids_list, bid, is_ask=False))

    def on_ask(self, ask):
        self.window().asks_list.addTopLevelItem(
            self.create_widget_item_from_tick(self.window().asks_list, ask, is_ask=True))

    def on_bid(self, bid):
        self.window().bids_list.addTopLevelItem(
            self.create_widget_item_from_tick(self.window().bids_list, bid, is_ask=False))

    def on_transaction_complete(self, transaction):
        main_text = "Transaction with price %f and quantity %d completed." \
                    % (float(transaction["price"]), int(transaction["quantity"]))
        self.window().tray_icon.showMessage("Transaction completed", main_text)

        # Reload transactions
        self.window().market_transactions_page.load_transactions()

    def create_order(self, is_ask, price, quantity):
        post_data = str("price=%f&quantity=%d" % (price, quantity))
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/%s" % ('asks' if is_ask else 'bids'),
                                         self.on_order_created, data=post_data, method='PUT')

    def on_transactions_button_clicked(self):
        self.window().market_transactions_page.initialize_transactions_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET_TRANSACTIONS)

    def on_order_created(self, response):
        print response

    def on_tick_item_clicked(self, tick_list):
        if len(tick_list.selectedItems()) == 0:
            return
        tick = tick_list.selectedItems()[0].tick

        if tick_list == self.window().asks_list:
            self.window().bids_list.clearSelection()
        else:
            self.window().asks_list.clearSelection()

        self.window().market_detail_order_id_label.setText(
            hashlib.sha1(tick["trader_id"] + tick["order_id"]).hexdigest())
        self.window().market_detail_trader_id_label.setText(hashlib.sha1(tick["trader_id"]).hexdigest())
        self.window().market_detail_credits_label.setText("%d" % tick["quantity"])
        self.window().market_detail_price_label.setText(tick["price"])
        self.window().market_detail_time_created_label.setText(tick["timestamp"])

        self.window().tick_detail_container.show()

    def on_create_ask_clicked(self):
        self.show_new_order_dialog(True)

    def on_create_bid_clicked(self):
        self.show_new_order_dialog(False)

    def show_new_order_dialog(self, is_ask):
        self.dialog = NewMarketOrderDialog(self.window().stackedWidget, is_ask)
        self.dialog.button_clicked.connect(self.on_new_order_action)
        self.dialog.show()

    def on_new_order_action(self, action):
        if action == 1:
            self.create_order(self.dialog.is_ask, self.dialog.price, self.dialog.quantity)

        self.dialog.setParent(None)
        self.dialog = None
