from flask import Flask, send_from_directory

app = Flask(__name__, static_folder=".")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/callback")
def callback():
    return send_from_directory(".", "callback.html")


@app.route("/<path:path>")
def serve_static_files(path):
    return send_from_directory(".", path)


if __name__ == "__main__":
    app.run(port=3001, debug=True)
