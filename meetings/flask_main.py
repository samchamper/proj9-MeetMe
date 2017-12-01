import flask
from flask import render_template
from flask import request
import logging
import sys

# Date handling
import arrow
from dateutil import tz  # For interpreting local times

# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services
from apiclient import discovery

# Mongo database
from pymongo import MongoClient

# For creating random event codes
import random
from string import ascii_letters as letters

# My function to go from a list of events to a list of free times:
from free import free

###
# Globals
###
import config
if __name__ == "__main__":
    CONFIG = config.configuration()
else:
    CONFIG = config.configuration(proxied=True)

app = flask.Flask(__name__)
app.debug = CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key = CONFIG.SECRET_KEY

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_KEY_FILE
APPLICATION_NAME = 'MeetMe class project'


# Connect to mongo for database of meetings.
MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST,
    CONFIG.DB_PORT,
    CONFIG.DB)

app.logger.debug("Using Mongo URL: '{}'".format(MONGO_CLIENT_URL))
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.meetings
except:
    app.logger.debug("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)


#############################
#  Pages (routed from URLs)
#############################
@app.route("/")
@app.route("/start")
@app.route("/index")
def index():
    app.logger.debug("Entering start page")
    if 'begin_date' not in flask.session:
        init_session_values()
    return render_template('start.html')


@app.route("/_check")
def check():
    app.logger.debug("Checking meeting code")
    meet_code = request.args.get("meet_code")

    records = []
    for record in collection.find({"type": "meeting"}):
        records.append(record['code'])

    if meet_code in records:
        result = {"meet_code": meet_code}
        return flask.jsonify(result=result)

    result = {"error": "1"}
    return flask.jsonify(result=result)


@app.route("/new_meeting")
def new_meeting():
    # Get a new meeting code.
    # The meeting codes are random strings of 12 ascii letters.
    # It seems pretty unlikely that the same two codes will ever be generated,
    # but this function double checks just in case.
    records = []
    for record in collection.find({"type": "meeting"}):
        records.append(record['code'])

    done = False
    while done is False:
        meetcode = ''.join(random.choice(letters) for _ in range(10))
        if meetcode not in records:
            done = True

    app.logger.debug("Adding new meeting to database with meet code: {}"
                     .format(meetcode))

    new = {"type": "meeting",
           "busy": [],
           "daterange": "None",
           "participants": [],
           "already_checked_in": [],
           "duration": 0,
           "description": "None",
           "code": meetcode}
    collection.insert(new)
    flask.session['meetcode'] = meetcode
    return render_template('new_meeting.html')


@app.route("/_get_names")
def get_names():
    """
    Get the list of names, description, and duration from
    the new meeting table, then reroute to the join meeting page.
    """
    people = request.args.get("participants")
    app.logger.debug("Got this list of participants: {}".format(people))

    desc = str(request.args.get("desc"))
    duration = int(request.args.get("duration"))
    date_rng = request.args.get("daterange")
    app.logger.debug("Event description: {}".format(desc))
    app.logger.debug("Event duration: {}".format(duration))
    app.logger.debug("Date range: {}".format(date_rng))

    # Turn the list of participants back into a list.
    people = people[2:-2].split("\",\"")
    # Might as well alphabetize it?
    people.sort()
    # Add the people going to the event to the database.
    meetcode = flask.session['meetcode']

    collection.find_one_and_update(
        {"code": meetcode},
        {'$set': {"participants": people,
                  "description": desc,
                  "duration": duration,
                  "daterange": date_rng}})

    # Now that we have the meeting in the db,
    # send the meetcode over to js so we can get redirected.
    result = {"meetcode": meetcode}
    return flask.jsonify(result=result)


@app.route("/<meetcode>/join")
def join(meetcode):
    flask.session['meetcode'] = meetcode
    if 'begin_date' not in flask.session:
        init_session_values()
    # Need authorization to list calendars
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    cal_list = list_calendars(gcal_service)

    for i in cal_list:
        i['selected'] = True

    flask.g.calendars = cal_list
    return render_template('index.html')


@app.route("/_populate")
def populate():
    """
    Populate the join page with info from the database.
    """
    meetcode = flask.session['meetcode']

    # Get the record with this meet code.
    record = dict()
    # for i in collection.find({"code": meetcode}):
        # Only one record will ever match each meetcode.
        # record = i
    record = collection.find({"code": meetcode})[0]

    duration = record['duration']
    description = record['description']
    participants = record['participants']

    result = {"description": description,
              "duration": duration,
              "participants": participants}
    return flask.jsonify(result=result)


@app.route("/_choose")
def jsonchoose():
    # Need authorization to list calendars
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    cal_list = list_calendars(gcal_service)

    for i in cal_list:
        i['selected'] = True
    flask.g.calendars = cal_list

    result = {"cal_list": cal_list}
    return flask.jsonify(result=result)


@app.route("/_events")
def events():
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    cal_list = list_calendars(gcal_service)

    for i in cal_list:
        i['selected'] = True
    flask.g.calendars = cal_list

    meetcode = flask.session['meetcode']
    # Get the record with this meet code.
    record = dict()
    for i in collection.find({"code": meetcode}):
        # Only one record will ever match each meetcode.
        record = i
    duration = record['duration']
    daterange_parts = record['daterange'].split()
    begin_date = interpret_date(daterange_parts[0])
    end_date = interpret_date(daterange_parts[2])

    chosen = request.args.get("chosen")
    app.logger.debug("The following calendars have been chosen: {}".format(chosen))

    # Get the range of days we are interested in
    begin = arrow.get(begin_date)
    end = arrow.get(end_date)
    day_range = arrow.Arrow.range('day', begin, end)

    # Manipulate open and close times to get hours and minutes.
    open_time = interpret_time(request.args.get("open"))
    close_time = interpret_time(request.args.get("close"))
    open_time = open_time[-14:-9]
    close_time = close_time[-14:-9]
    open_hr = int(open_time[:2])
    open_min = int(open_time[-2:])
    close_hr = int(close_time[:2])
    close_min = int(close_time[-2:])

    # Transfer from summary to cal id:
    chosen_ids = []
    for i in cal_list:
        if i['summary'] in chosen:
            chosen_ids.append(i['id'])

    # Build the event list.
    event_list = []
    for day in day_range:
        day_start = day.replace(hour=open_hr, minute=open_min)
        day_end = day.replace(hour=close_hr, minute=close_min)
        for cur_id in chosen_ids:
            today_events = gcal_service.events().list(
                calendarId=cur_id,
                timeMin=day_start,
                timeMax=day_end,
                singleEvents=True).execute()
            for event in today_events['items']:
                try:
                    # For repeating events.
                    e_start = str(event['originalStartTime']['dateTime'])
                except KeyError:
                    try:
                        # For standard events.
                        e_start = str(event['start']['dateTime'])
                    except KeyError:
                        try:
                            # For all day events.
                            e_start = arrow.get(event['start']['date']).replace(tzinfo='local').isoformat()
                        except KeyError:
                            continue
                try:
                    e_finish = str(event['end']['dateTime'])
                except KeyError:
                    # All day events
                    e_finish = arrow.get(event['end']['date']).replace(tzinfo='local').isoformat()

                this_event = [str(event['summary']), e_start, e_finish]
                if this_event not in event_list:
                    event_list.append(this_event)

    # Sort the event list.
    event_list.sort(key=lambda el: arrow.get(el[1]))

    # Now pass all the necessary args to the function to calculate freetime:
    min_len = int(duration)
    # free_windows = []
    free_windows, db_ready_busy = free(event_list, open_hr, open_min, close_hr, close_min, day_range, min_len)
    # Free windows is a list of pairs of arrow objects
    # representing open and close time of a window of free time.

    # Display formatting for the event list.
    for i in range(len(event_list)):
        event_list[i] = ["Event name: {}".format(event_list[i][0]),
                         "Start time: {}".format(arrow.get(event_list[i][1]).format('ddd, MMM D, h:mm a')),
                         "End time: {}".format(arrow.get(event_list[i][2]).format('ddd, MMM D, h:mm a'))]

    # Display formatting for list of free times.
    formatted_free_times = []
    for window in free_windows:
        win_str = "From {} to {}.".format(
            window[0].format('ddd, MMM D, h:mm a'),
            window[1].format('h:mm a'))
        formatted_free_times.append(win_str)

    # Return final list and free time list to js for displaying.
    result = {"event_list": event_list, "formatted_free_times": formatted_free_times, "db_ready_busy": db_ready_busy}
    return flask.jsonify(result=result)


@app.route("/_send")
def send():
    """
    Function to update the database with the person who is
    responding and their busy times.
    """
    invitee = request.args.get('invitee')
    busy_times = request.args.get('busy_times')

    meetcode = flask.session['meetcode']
    # Get the record with this meet code.
    record = dict()
    for i in collection.find({"code": meetcode}):
        # Only one record will ever match each meetcode.
        record = i

    # First indicate the person who just responded.
    if "{}".format(invitee) in record['participants']:
        # The invitee should always be in the record unless
        # users are doing something wrong, like multiple people
        # choosing the same name at the same time. This if covers
        # that case.
        record['participants'].remove("{}".format(invitee))
        record['already_checked_in'].append("{}".format(invitee))

    # Next append the new list of busy times to the list from the db.
    # First the new list will need to be converted from a str to a list.
    busy_times = busy_times[3:-3].split("\"],[\"")
    for i in range(len(busy_times)):
        record['busy'].append(busy_times[i].split("\",\""))

    # Now update the database with the new busy times,
    # and updated info on who has checked in.
    collection.find_one_and_update(
        {"code": meetcode},
        {'$set': {"participants": record['participants'],
                  "already_checked_in": record['already_checked_in'],
                  "busy": record['busy']}})

    result = {"meetcode": meetcode}
    return flask.jsonify(result=result)


@app.route("/_redir")
def redir():
    """
    Redirect to meeting status page.
    """
    meetcode = flask.session['meetcode']
    result = {"meetcode": meetcode}
    return flask.jsonify(result=result)


@app.route("/<meetcode>/<meetcode2>/status")
def status_redir(meetcode,meetcode2):
    """
    Function to correct super weird buggy behaviour
    of window.location.assign in js.
    I have no idea why the following js:
    window.location.assign(SCRIPT_ROOT + meeting_code + "/status");
    is routing me to "/<meetcode>/<meetcode2>/status".
    meetcode is in js properly, as determined by console logging.
    For now, this trashy redirect function fixes the problem.
    """
    app.logger.debug("Entering meeting status page")
    return flask.redirect(flask.url_for('status', meetcode=meetcode))


@app.route("/<meetcode>/status")
def status(meetcode):
    """
    The status page for each meeting.
    """
    app.logger.debug("Entering meeting status page")
    print(meetcode)
    return render_template('status.html')

@app.route("/_pull_info")
def pull_info():
    """
    Grabs all of the meeting details from the database,
    calculates free windows based on all busy times in
    the database, and sends it all over to user.
    """
    meetcode = flask.session['meetcode']
    # Get the record with this meet code.
    record = dict()
    for i in collection.find({"code": meetcode}):
        # Only one record will ever match each meetcode.
        record = i

    #        "busy": [],

    result = {"description": record['description'],
              "participants": record['participants'],
              "already_checked_in": record['already_checked_in'],
              "duration": record['duration']}
    return flask.jsonify(result=result)


####
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST:
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable.
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead.
####
def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value.
    """
    if 'credentials' not in flask.session:
        return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
            credentials.access_token_expired):
        return None
    return credentials


def get_gcal_service(credentials):
    """
    We need a Google calendar 'service' object to obtain
    list of calendars, busy times, etc.  This requires
    authorization. If authorization is already in effect,
    we'll just return with the authorization. Otherwise,
    control flow will be interrupted by authorization, and we'll
    end up redirected back to /choose *without a service object*.
    Then the second call will succeed without additional authorization.
    """
    app.logger.debug("Entering get_gcal_service")
    http_auth = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http_auth)
    app.logger.debug("Returning service")
    return service


@app.route('/oauth2callback')
def oauth2callback():
    """
    The 'flow' has this one place to call back to.  We'll enter here
    more than once as steps in the flow are completed, and need to keep
    track of how far we've gotten. The first time we'll do the first
    step, the second time we'll skip the first step and do the second,
    and so on.
    """
    app.logger.debug("Entering oauth2callback")
    flow = client.flow_from_clientsecrets(
        CLIENT_SECRET_FILE,
        scope=SCOPES,
        redirect_uri=flask.url_for('oauth2callback', _external=True))
    # Note we are *not* redirecting above.  We are noting *where*
    # we will redirect to, which is this function.

    # The *second* time we enter here, it's a callback
    # with 'code' set in the URL parameter.  If we don't
    # see that, it must be the first time through, so we
    # need to do step 1.
    app.logger.debug("Got flow")
    if 'code' not in flask.request.args:
        app.logger.debug("Code not in flask.request.args")
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)
    # This will redirect back here, but the second time through
    # we'll have the 'code' parameter set
    else:
        # It's the second time through ... we can tell because
        # we got the 'code' argument in the URL.
        app.logger.debug("Code was in flask.request.args")
        auth_code = flask.request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        flask.session['credentials'] = credentials.to_json()
        # Now I can build the service and execute the query,
        # but for the moment I'll just log it and go back to
        # the main screen
        app.logger.debug("Got credentials")
        return flask.redirect(flask.url_for('join', meetcode=flask.session['meetcode']))


#####
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use.
#####
@app.route('/setrange', methods=['POST'])
def setrange():
    """
    NO LONGER USED
    User chose a date range with the bootstrap daterange
    widget.
    """
    # TODO : DELETE
    app.logger.debug("Entering setrange")
    flask.flash("Setrange gave us '{}'".format(request.form.get('daterange')))
    daterange = request.form.get('daterange')

    op_time = request.form.get('open')
    close_time = request.form.get('close')

    flask.session['daterange'] = daterange
    flask.session['begin_time'] = op_time
    flask.session['end_time'] = close_time
    daterange_parts = daterange.split()

    app.logger.debug(op_time)
    app.logger.debug(close_time)

    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])

    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
        daterange_parts[0], daterange_parts[1],
        flask.session['begin_date'], flask.session['end_date']))

    return flask.redirect(flask.url_for('join', meetcode=flask.session['meetcode']))


####
#   Initialize session variables
####
def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main.
    """
    # TODO: DELETE THIS FUNCTION
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span
    flask.session["begin_time"] = "09:00"
    flask.session["end_time"] = "17:00"


def interpret_time(text):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try:
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        as_arrow = as_arrow.replace(year=2016)  # HACK see below
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
                    .format(text))
        raise
    return as_arrow.isoformat()
    # HACK #Workaround for raspberry Pi because isoformat doesn't work on some dates.


def interpret_date(text):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
        as_arrow = arrow.get(text, "MM/DD/YYYY").replace(tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()


def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()


####
#  Functions (NOT pages) that return some information
####
def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict.
    The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")
    calendar_list = service.calendarList().list().execute()["items"]
    result = []
    for cal in calendar_list:
        kind = cal["kind"]
        cal_id = cal["id"]
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]

        result.append(
           {"kind": kind,
            "id": cal_id,
            "summary": summary,
            "selected": selected,
            "primary": primary})
    return sorted(result, key=cal_sort_key)


def cal_sort_key(cal):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
        selected_key = " "
    else:
        selected_key = "X"
    if cal["primary"]:
        primary_key = " "
    else:
        primary_key = "X"
    return primary_key, selected_key, cal["summary"]


#################
# Functions used within the templates
#################
@app.template_filter('fmtdate')
def format_arrow_date(date):
    try:
        normal = arrow.get(date)
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"


@app.template_filter('fmttime')
def format_arrow_time(time):
    try:
        normal = arrow.get(time)
        return normal.format("HH:mm")
    except:
        return "(bad time)"

#############


if __name__ == "__main__":
    # App is created above so that it will
    # exist whether this is 'main' or not
    # (e.g., if we are running under green unicorn)
    app.run(port=CONFIG.PORT, host="localhost")
    # app.run(port=CONFIG.PORT,host="0.0.0.0")
