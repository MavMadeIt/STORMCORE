import sys
from PySide6.QtWidgets import QApplication
from stormcore.ui import StormCoreWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("STORMCORE")
    app.setOrganizationName("STORMCORE Weather")
    window = StormCoreWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
