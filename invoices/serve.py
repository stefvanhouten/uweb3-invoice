# Application

from . import main as setup


def main():
    app = setup()
    app.serve()


if __name__ == "__main__":
    main()
