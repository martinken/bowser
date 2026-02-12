import sys
from argparse import ArgumentParser, RawTextHelpFormatter

from PySide6.QtWidgets import QApplication

from .genmain import GenMain


def main() -> int:
    # Parse command line arguments
    arg_parser = ArgumentParser(
        description="Dueser - ComfyUI front end", formatter_class=RawTextHelpFormatter
    )
    arg_parser.add_argument(
        "--workflows", type=str, default=None, help="Path to the workflows directory"
    )
    arg_parser.add_argument(
        "--server",
        type=str,
        default=None,
        help="ComfyUI server address(es), comma-separated for multiple servers",
    )
    args = arg_parser.parse_args()

    # Initialize Qt application
    app = QApplication(sys.argv)

    # Create main window with optional args
    main_window = GenMain(workflow_root=args.workflows, server_address=args.server)

    # Show the main window and start the application
    main_window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
