from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_WALLET_NONE, PAGE_WALLET_BTC, PAGE_WALLET_MC, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class MarketWalletsPage(QWidget):
    """
    This page displays information about wallets.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False
        self.wallets_to_create = []
        self.wallets = None
        self.dialog = None

    def initialize_wallets_page(self):
        if not self.initialized:
            self.window().wallets_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_NONE)
            self.window().wallet_btc_overview_button.clicked.connect(self.on_btc_wallet_clicked)
            self.window().wallet_mc_overview_button.clicked.connect(self.on_mc_wallet_clicked)
            self.window().add_wallet_button.clicked.connect(self.on_add_wallet_clicked)
            self.window().wallet_mc_overview_button.hide()
            self.window().wallet_btc_overview_button.hide()
            self.window().wallet_paypal_overview_button.hide()

            self.initialized = True

        self.load_wallets()

    def load_wallets(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets", self.on_wallets)

    def on_wallets(self, wallets):
        self.wallets = wallets["wallets"]

        if 'MC' in self.wallets and self.wallets["MC"]["created"]:
            self.window().wallet_mc_overview_button.show()

        if 'BTC' in self.wallets and self.wallets["BTC"]["created"]:
            self.window().wallet_btc_overview_button.show()

        if 'PP' in self.wallets and self.wallets["PP"]["created"]:
            self.window().wallet_paypal_overview_button.show()

        # Find out which wallets we still can create
        self.wallets_to_create = []
        for identifier, wallet in self.wallets.iteritems():
            if not wallet["created"]:
                self.wallets_to_create.append(identifier)

        if len(self.wallets_to_create) > 0:
            self.window().add_wallet_button.setEnabled(True)

    def on_btc_wallet_clicked(self):
        self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_BTC)
        self.load_btc_wallet_balance()

    def on_mc_wallet_clicked(self):
        self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_MC)
        self.load_mc_wallet_balance()

    def load_btc_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/btc/balance", self.on_btc_wallet_balance)

    def on_btc_wallet_balance(self, balance):
        self.window().btc_wallet_confirmed_label.setText("%s" % balance["balance"]["confirmed"])
        self.window().btc_wallet_unconfirmed_label.setText("%s" % balance["balance"]["unconfirmed"])
        self.window().btc_wallet_unmatured_label.setText("%s" % balance["balance"]["unmatured"])
        self.load_btc_transactions()

    def load_btc_transactions(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/btc/transactions", self.on_btc_transactions)

    def on_btc_transactions(self, transactions):
        self.window().btc_wallet_transactions_list.clear()
        for transaction in transactions["transactions"]:
            item = QTreeWidgetItem(self.window().btc_wallet_transactions_list)
            item.setText(0, "sent" if transaction["value"] < 0 else "received")
            item.setText(1, transaction["txid"])
            item.setText(2, transaction["date"])
            item.setText(3, "%f" % transaction["value"])
            item.setText(4, "%d" % transaction["confirmations"])
            self.window().btc_wallet_transactions_list.addTopLevelItem(item)

    def load_mc_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/mc/balance", self.on_mc_wallet_balance)

    def on_mc_wallet_balance(self, balance):
        self.window().mc_wallet_given_label.setText("%s" % balance["balance"]["total_up"])
        self.window().mc_wallet_taken_label.setText("%s" % balance["balance"]["total_down"])
        self.window().mc_wallet_balance_label.setText("%s" % balance["balance"]["net"])

    def on_add_wallet_clicked(self):
        menu = TriblerActionMenu(self)

        for wallet_id in self.wallets_to_create:
            wallet_action = QAction(self.wallets[wallet_id]['name'], self)
            wallet_action.triggered.connect(lambda: self.should_create_wallet(wallet_id))
            menu.addAction(wallet_action)

        menu.exec_(QCursor.pos())

    def should_create_wallet(self, wallet_id):
        if wallet_id == 'BTC':
            self.dialog = ConfirmationDialog(self, "Create Bitcoin wallet",
                                             "Please enter the password of your Bitcoin wallet below:",
                                             [('CREATE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                             show_input=True)
            self.dialog.dialog_widget.dialog_input.setPlaceholderText('Wallet password')
            self.dialog.button_clicked.connect(self.on_create_btc_wallet_dialog_done)
            self.dialog.show()
        else:
            self.request_mgr.perform_request("wallets/%s" % wallet_id, self.on_btc_wallet_created,
                                             method='PUT', data='')

    def on_create_btc_wallet_dialog_done(self, action):
        password = self.dialog.dialog_widget.dialog_input.text()

        if action == 1:  # Remove the dialog right now
            self.dialog.setParent(None)
            self.dialog = None
        elif action == 0:
            self.dialog.buttons[0].setEnabled(False)
            self.dialog.buttons[1].setEnabled(False)
            self.dialog.buttons[0].setText("CREATING...")
            self.request_mgr = TriblerRequestManager()
            post_data = str("password=%s" % password)
            self.request_mgr.perform_request("wallets/btc", self.on_btc_wallet_created, method='PUT', data=post_data)

    def on_btc_wallet_created(self, response):
        self.dialog.setParent(None)
        self.dialog = None
        self.window().wallet_btc_overview_button.show()
