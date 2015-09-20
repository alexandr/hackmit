from flask import Flask, request, redirect
import twilio.twiml
import subprocess
import json

app = Flask(__name__)

AMADEUS_API_KEY = 'L3BWAbodyZlr0E2PBXUY2kjm4NNcN9Xq'
LOW_FARE_URL = 'http://api.sandbox.amadeus.com/v1.2/flights/low-fare-search'

@app.route("/", methods=['GET', 'POST'])
def respond():
    """Responds to incoming text message with hello world."""

    resp = twilio.twiml.Response()
    resp.message("Hello, I will happily book your flight.")
    return str(resp)

def amadeus_low_fare_request(origin, destination, departure_date, **kwargs):
    """Makes a request to Amadeus for the low fare flights according to params."""
    url_params = {
        'origin': origin,
        'destination': destination,
        'departure_date': departure_date,
    }
    url_params.update(kwargs)
    url = LOW_FARE_URL + '?' + ('apikey=%s&' % AMADEUS_API_KEY) + '&'.join(['%s=%s' % (a, b) for a, b in url_params.iteritems()])
    print url
    output = subprocess.check_output(['curl', '-X', 'GET', url])
    return json.loads(output)


if __name__ == "__main__":
    app.run(debug=True)
