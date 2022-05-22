# Application
from invoices import base


def main():
    app = base.main()
    app.serve()


if __name__ == "__main__":
    main()
