import sys
from controller import MainWindow
from PyQt5 import QtWidgets



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())