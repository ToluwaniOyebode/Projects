from service import App
from webcore import run

if __name__ == "__main__":
    run(lambda path: App(path, auto_worker=True), 8106)
