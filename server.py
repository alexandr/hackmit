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
import nltk
import datetime

app = Flask(__name__)

AMADEUS_API_KEY = 'L3BWAbodyZlr0E2PBXUY2kjm4NNcN9Xq'
LOW_FARE_URL = 'http://api.sandbox.amadeus.com/v1.2/flights/low-fare-search'
EXTENSIVE_URL = 'http://api.sandbox.amadeus.com/v1.2/flights/extensive-search'

app = Flask(__name__)

cities_regex = re.compile('(?:^|.* )([A-Z]*) to ([A-Z]*).*')
day_regex = re.compile('.*(January|February|March|April|May|June|July|August|September|October|November|December) ([0-3]?[0-9]).*')
time_regex = re.compile('.*(before|after) ([01]?[0-9]) ?([AaPp][Mm]).*')
month_to_num = {
  'January': 1,
  'February': 2,
  'March': 3,
  'April': 4,
  'May': 5,
  'June': 6,
  'July': 7,
  'August': 8,
  'September': 9,
  'October': 10,
  'November': 11,
  'December': 12
}

@app.route("/", methods=['GET', 'POST'])
def respond():
    """Responds to incoming text message with hello world."""
    msg = request.form.get('Body')
    msg_params = parse_msg(msg)
    today = datetime.date.today()
    month = month_to_num[msg_params['month']]
    day = int(msg_params['day'])
    year = today.year if today < datetime.date(today.year, month, day) else today.year + 1
    datestr = str(datetime.date(year, month, day))
    best_time, saved_amt = find_best_time_to_buy(msg_params['origin'], msg_params['destination'], datestr)
    buy_in_days = (best_time - today).days
    buy_in_days_str = 'in %d days' % buy_in_days if buy_in_days > 0 else 'now'
    resp = twilio.twiml.Response()
    resp.message("Sure thing! I'll book them for you %s. Have a safe trip!" % buy_in_days_str)
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
    try:
        output = subprocess.check_output(['curl', '-X', 'GET', url])
    except Exception:
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

def get_best_current_flight(origin, destination, departure_date):
    res = amadeus_low_fare_request(origin, destination, departure_date, number_of_results=1)
    depart_time = res['results'][0]['itineraries'][0]['outbound']['flights'][0]['departs_at']
    arrival_time = res['results'][0]['itineraries'][0]['outbound']['flights'][-1]['arrives_at']
    depart_time = depart_time.split('T')[-1]
    arrival_time = arrival_time.split('T')[-1]
    depart_time = datetime.datetime.strptime(depart_time, "%H:%M").strftime("%I:%M %p")
    arrival_time = datetime.datetime.strptime(arrival_time, "%H:%M").strftime("%I:%M %p")
    fare = res['results'][0]['fare']['total_price']
    return depart_time, arrival_time, fare

def find_best_time_to_buy(origin, destination, departure_date, arrive_by=None):
    """Given the parameters from a text, find the best time to buy."""

    features, values = parse_extensive(amadeus_extensive_request(origin, destination))
    vec = DictVectorizer()
    clf = svm.SVR()
    clf.fit(vec.fit_transform(features).toarray(), values)
    print vec.get_feature_names()

    base = {
        u'origin': origin,
        u'destination': destination,
        u'departure_date' : iso_to_ordinal(departure_date),
        u'return_date' : iso_to_ordinal(departure_date) + 7,
    }
    now = datetime.datetime.today().toordinal()
    curr = 1000000000000.0
    best_day = now
    worst = 0.0
    for days_in_advance in range(iso_to_ordinal(departure_date) - now + 1):
        temp = base
        temp[u'days_in_advance'] = days_in_advance
        price = clf.predict(vec.transform(temp).toarray()) + random.uniform(-0.3,0.3)
        if price < curr:
            curr = price
            best_day = iso_to_ordinal(departure_date) - days_in_advance
        worst = max(worst, price)
    best_day = min(best_day, max(iso_to_ordinal(departure_date) - 47, now))
    amount_saved = worst - curr if best_day != now else 0.0
    return datetime.date.fromordinal(best_day), amount_saved * 100.0

def parse_msg(msg):
    origin = cities_regex.match(msg).group(1)
    destination = cities_regex.match(msg).group(2)
    month = day_regex.match(msg).group(1)
    day = day_regex.match(msg).group(2)
    hour_side = ''
    hour = ''
    m = ''
    try:
      hour_side = time_regex.match(msg).group(1)
      hour = time_regex.match(msg).group(2)
      m = time_regex.match(msg).group(3)
    except Exception:
      pass

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
