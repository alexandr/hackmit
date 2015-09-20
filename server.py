from flask import Flask, request, redirect
import twilio.twiml

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def respond():
    """Responds to incoming text message with hello world."""

    resp = twilio.twiml.Response()
    resp.message("Hello, I will happily book your flight.")
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
