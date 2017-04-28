from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QVBoxLayout

from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class IomInputDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, required_input):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('iom_input_dialog.ui'), self.dialog_widget)

        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.confirm_button.clicked.connect(lambda: self.button_clicked.emit(1))

        vlayout = QVBoxLayout()
        self.dialog_widget.input_container.setLayout(vlayout)

        for specific_input in required_input['required_fields']:
            label_widget = QLabel(self.dialog_widget.input_container)
            label_widget.setText(specific_input['text'] + ":")
            label_widget.show()
            vlayout.addWidget(label_widget)

            input_widget = QLineEdit(self.dialog_widget.input_container)
            input_widget.setPlaceholderText(specific_input['placeholder'])
            input_widget.show()
            vlayout.addWidget(input_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()
