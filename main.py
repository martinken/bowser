import sys
from argparse import ArgumentParser, RawTextHelpFormatter

from PySide6.QtWidgets import QApplication

from bowsermain import BowserMain

if __name__ == "__main__":
    arg_parser = ArgumentParser(
        description="Image Viewer", formatter_class=RawTextHelpFormatter
    )
    arg_parser.add_argument("file", type=str, nargs="?", help="Image file or folder")
    args = arg_parser.parse_args()

    app = QApplication(sys.argv)
    
    # If a file/folder is provided, pass it to the main window
    folder_path = args.file if args.file else None
    main_window = BowserMain(folder_path=folder_path)

    main_window.show()
    sys.exit(app.exec())
