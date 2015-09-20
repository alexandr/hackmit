from flask import Flask, request, redirect
import twilio.twiml
import subprocess
import json
import sklearn
import random
import datetime
from sklearn.feature_extraction import DictVectorizer
from sklearn import svm
import re

app = Flask(__name__)

AMADEUS_API_KEY = 'L3BWAbodyZlr0E2PBXUY2kjm4NNcN9Xq'
LOW_FARE_URL = 'http://api.sandbox.amadeus.com/v1.2/flights/low-fare-search'
EXTENSIVE_URL = 'http://api.sandbox.amadeus.com/v1.2/flights/extensive-search'

app = Flask(__name__)

cities_regex = re.compile('(?:^|.* )([A-Z]*) to ([A-Z]*).*')
day_regex = re.compile('.*(January|February|March|April|May|June|July|August|September|October|November|December) ([0-3]?[0-9]).*')
time_regex = re.compile('.*(before|after) ([01]?[0-9]) ?([AaPp][Mm]).*')

@app.route("/", methods=['GET', 'POST'])
def respond():
    """Responds to incoming text message with hello world."""
    msg = request.form.get('Body')
    parse_msg(msg)
    resp = twilio.twiml.Response()
    resp.message("Hello, I will happily book your flight.")
    return str(resp)

def iso_to_ordinal(iso):
    return datetime.datetime.strptime(iso, '%Y-%m-%d').toordinal()

def amadeus_low_fare_request(origin, destination, departure_date, **kwargs):
    """Makes a request to Amadeus for the low fare flights according to params."""
    url_params = {
        'origin': origin,
        'destination': destination,
        'departure_date': departure_date,
    }
    url_params.update(kwargs)
    url = LOW_FARE_URL + '?' + ('apikey=%s&' % AMADEUS_API_KEY) + '&'.join(['%s=%s' % (a, b) for a, b in url_params.iteritems()])
    output = subprocess.check_output(['curl', '-X', 'GET', url])
    return json.loads(output)

def amadeus_extensive_request(origin, destination, **kwargs):
    """Makes a request to Amadeus for the low fare flights according to params."""
    url_params = {
        'origin': origin,
        'destination': destination,
        'aggregation_mode': 'DAY',
    }
    url_params.update(kwargs)
    url = EXTENSIVE_URL + '?' + ('apikey=%s&' % AMADEUS_API_KEY) + '&'.join(['%s=%s' % (a, b) for a, b in url_params.iteritems()])
    output = subprocess.check_output(['curl', '-X', 'GET', url])
    return json.loads(output)

def flat_flights(amadeus_res):
    ret = []
    for d in amadeus_res['results']:
        common = set(d.keys()) - {'itineraries'}
        for it in d['itineraries']:
            newd = {k: d[k] for k in common}
            newd.update(it)
            ret.append(newd)
    return ret

def parse_extensive(data):
    origin = data['origin']
    new_data = []
    values = []
    for i in data['results']:
        values.append(float(i['price']))
        temp = i
        del temp['price']
        del temp['airline']
        temp[u'origin'] = origin
        departure_date = iso_to_ordinal(temp['departure_date'])
        return_date = iso_to_ordinal(temp['return_date'])
        now = datetime.datetime.today().toordinal()
        days_in_advance = departure_date - now
        temp[u'departure_date'] = departure_date
        temp[u'return_date'] = return_date
        temp[u'days_in_advance'] = days_in_advance
        new_data.append(temp)
    return (new_data, values)

def find_best_time_to_buy(origin, destination, departure_date, arrive_by=None):
    """Given the parameters from a text, find the best time to buy."""

    features, values = parse_extensive(amadeus_extensive_request(origin, destination))
    vec = DictVectorizer()
    clf = svm.SVR()
    clf.fit(vec.fit_transform(features).toarray(), values)

    base = {
        u'origin': origin,
        u'destination': destination,
        u'departure_date' : iso_to_ordinal(departure_date),
        u'return_date' : iso_to_ordinal(departure_date) + 7,
    }
    now = datetime.datetime.today().toordinal()
    curr = 1000000000000.0
    best_day = now
    for days_in_advance in range(iso_to_ordinal(departure_date) - now + 1):
        temp = base
        temp[u'days_in_advance'] = days_in_advance
        price = clf.predict(vec.transform(temp).toarray()) + random.uniform(-0.5,0.5)
        if price < curr:
            curr = price
            best_day = iso_to_ordinal(departure_date) - days_in_advance
    return datetime.date.fromordinal(best_day)

def parse_msg(msg):
    origin = cities_regex.match(msg).group(1)
    destination = cities_regex.match(msg).group(2)
    month = day_regex.match(msg).group(1)
    day = day_regex.match(msg).group(2)
    hour_side = time_regex.match(msg).group(1)
    hour = time_regex.match(msg).group(2)
    m = time_regex.match(msg).group(3)

    res = {
      'origin': origin,
      'destination': destination,
      'month': month,
      'day': day,
      'hour_side': hour_side,
      'hour': hour,
      'm': m
    }
    return res

if __name__ == "__main__":
    app.run(debug=True)
