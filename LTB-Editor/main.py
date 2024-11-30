import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from editor import LTBEditor
import logging
import os

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("ltb_editor.log"),
            logging.StreamHandler()
        ]
    )

    app = QApplication(sys.argv)

    # Set the application icon
    icon_path = os.path.join(os.path.dirname(__file__), "editoricon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        logging.warning(f"Icon file not found at {icon_path}. Using default icon.")

    editor = LTBEditor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
