# Main file for MeetMe, an app to find free times in common
# between a group of people (or robots or whatever)
# in oder to schedule meetings.
# Author: Sam Champer


import flask
from flask import render_template
from flask import request
import logging
import sys

# For converting strings to url format for mailto.
from urllib import parse as url_parse

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

# My functions to go from a list of events to a list of free times:
from free import free, db_free

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
# Pages and flask functions.
#############################
@app.route("/")
@app.route("/start")
@app.route("/index")
def index():
    app.logger.debug("Entering start page")
    return render_template('start.html')


@app.route("/_check")
def check():
    app.logger.debug("Checking meeting code")
    meet_code = request.args.get("meet_code")

    records = []
    for record in collection.find({"type": "meeting"}):
        records.append(record['code'])

    if meet_code in records:
        return flask.jsonify(result={})

    result = {"error": "1"}
    return flask.jsonify(result=result)


@app.route("/new_meeting")
def new_meeting():
    # Get a new meeting code.
    # The meeting codes are random strings of 10 ascii letters.
    # It seems pretty unlikely that the same two codes will  be generated
    # any time soon, but this function double checks just in case.
    records = []
    for record in collection.find({"type": "meeting"}):
        records.append(record['code'])

    meetcode = ''
    done = False
    while done is False:
        meetcode = ''.join(random.choice(letters) for _ in range(10))
        if meetcode not in records:
            done = True

    app.logger.debug("Adding new meeting to database with meet code: {}"
                     .format(meetcode))

    # Add a new entry to the database with a field for
    # everything we ever want to put in there.
    new = {"type": "meeting",
           "busy": [],
           "daterange": "None",
           "participants": [],
           "already_checked_in": [],
           "duration": 0,
           "description": "None",
           "code": meetcode}
    collection.insert(new)
    # The only thing we need to keep in the session is the meetcode.
    flask.session['meetcode'] = meetcode
    return render_template('new_meeting.html')


@app.route("/_get_names")
def get_names():
    """
    Get the list of names, description, and duration from
    the new meeting table, then reroute to the join meeting page.
    """
    people = request.args.get("participants")
    desc = str(request.args.get("desc"))
    duration = int(request.args.get("duration"))
    date_rng = request.args.get("daterange")

    app.logger.debug("Got this list of participants: {}".format(people))
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
    # Need authorization to list calendars
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))
    app.logger.debug("Returned from get_gcal_service")
    return render_template('index.html')


@app.route("/_populate")
def populate():
    """
    Populate the join page with info from the database.
    """
    meetcode = flask.session['meetcode']

    # Get the record with this meet code.
    # Only one record will ever match each meetcode.
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
    # Need authorization to list calendars.
    app.logger.debug("Checking credentials for Google calendar access.")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization.")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")

    cal_list = list_calendars(gcal_service)
    result = {"cal_list": cal_list}
    return flask.jsonify(result=result)


@app.route("/_events")
def events():
    app.logger.debug("Checking credentials for Google calendar access.")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization.")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")

    cal_list = list_calendars(gcal_service)

    meetcode = flask.session['meetcode']
    # Get the record with this meet code.
    record = collection.find({"code": meetcode})[0]

    # Get the stuff from the collection.
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

    # Get ids of chosen calendars.
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
                    # For all day events
                    e_finish = arrow.get(event['end']['date']).replace(tzinfo='local').isoformat()

                # Each event has three elements: summary, start time, and finish time.
                this_event = [str(event['summary']), e_start, e_finish]
                # For repeated events:
                if this_event not in event_list:
                    event_list.append(this_event)

    # Sort the event list.
    event_list.sort(key=lambda el: arrow.get(el[1]))

    # Now pass all the necessary args to the function to calculate free time:
    free_windows, db_ready_busy = free(event_list, open_hr, open_min, close_hr, close_min, day_range, duration)

    # Free windows is a list of pairs of arrow objects
    # representing open and close time of a window of free time.

    # Display formatting for the event list.
    for i in range(len(event_list)):
        event_list[i] = ["Event name: {}".format(event_list[i][0]),
                         "Start time: {}".format(arrow.get(event_list[i][1]).format('ddd, MMM D, h:mm a')),
                         "End time: {}".format(arrow.get(event_list[i][2]).format('ddd, MMM D, h:mm a'))]

    # Display formatting for list of free times.
    formatted_free_times = format_free_times(free_windows)

    # Return final list and free time list to js for displaying.
    result = {"event_list": event_list, "formatted_free_times": formatted_free_times, "db_ready_busy": db_ready_busy}
    return flask.jsonify(result=result)


@app.route("/_send")
def send():
    """
    Updates the database with the person who is responding and their busy times.
    """
    invitee = request.args.get('invitee')
    busy_times = request.args.get('busy_times')

    meetcode = flask.session['meetcode']
    # Get the record with this meet code.
    record = collection.find({"code": meetcode})[0]

    # First indicate the person who just responded.
    if "{}".format(invitee) in record['participants']:
        # The invitee should always be in the record unless
        # users are doing something wrong, like multiple people
        # choosing the same name at the same time.
        # Either way, this if statement protects in that case.
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
    return flask.jsonify(result={"meetcode": meetcode})


@app.route("/<meetcode>/<meetcode2>/status")
def status_redir(meetcode, meetcode2):
    """
    Function to correct super weird buggy behaviour
    of window.location.assign in js.
    I have no idea why the following js:
        window.location.assign(SCRIPT_ROOT + meeting_code + "/status");
    is routing me to "/<meetcode>/<meetcode>/status".
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
    record = collection.find({"code": meetcode})[0]

    # Get the range of days from the db.
    daterange_parts = record['daterange'].split()
    begin_date = interpret_date(daterange_parts[0])
    end_date = interpret_date(daterange_parts[2])
    begin = arrow.get(begin_date)
    end = arrow.get(end_date)
    day_range = arrow.Arrow.range('day', begin, end)

    # Calc free times based on everyone's busy times:
    free = db_free(record["busy"], day_range, record["duration"])

    # Format the free times
    formatted_free_times = format_free_times(free)

    # Generate a string to place into html as a mailto link.
    # Wow is this ugly. Python is really not a word processor I guess:
    mail_str = "<a href='mailto:recipient?subject=Join%20the%20meeting!&amp;body="
    mail_str += url_parse.quote(record['description'])
    mail_str += "%0A%0ATo%20join%20the%20meeting%20go%20to" \
                "%3A%0Awherever_MeetMe_is_hosted%2F" + meetcode + "%2Fjoin"
    mail_str += "%0ATo%20check%20the%20status%20of%20the%20meeting%2C%20go%20to" \
                "%3A%0Awherever_MeetMe_is_hosted%2F" + meetcode + "%2Fstatus"
    mail_str += url_parse.quote(
        "\n\nIf MeetMe isn't hosted, you'll have to go hardcore and install it!\n To do so, "
        "open a command prompt or terminal in the folder you want to install it, then you'll need to have"
        " git installed and then to run:\ngit clone https://github.com/samchamper/proj9-MeetMe.git\n\n"
        "Then you'll need to place a credentials file and Google calendar access token "
        "in proj9-MeetMe/meetings \nThen from the proj9-MeetMe directory run:\nmake run\n"
        "Now you use MeetMe by navigating to http://localhost:8000/")
    mail_str += "'>Send an invitation to the meeting!</a>"

    result = {"description": record['description'],
              "participants": record['participants'],
              "already_checked_in": record['already_checked_in'],
              "duration": record['duration'],
              "free": formatted_free_times,
              "mail_str": mail_str,
              "meetcode": meetcode}
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
    credentials in the session. This is a 'truthy' value.
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
    list of calendars, busy times, etc. This requires
    authorization. If authorization is already in effect,
    we'll just return with the authorization. Otherwise,
    control flow will be interrupted by authorization, and we'll
    end up redirected *without a service object*.
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


# ###############
#
# Non-page functions
#
# ###############
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
        # Workaround for raspberry Pi because isoformat doesn't work on some dates:
        as_arrow = as_arrow.replace(year=2016)
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
                    .format(text))
        raise
    return as_arrow.isoformat()


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


def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars. Each calendar is represented by a dict.
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


def format_free_times(free_time_list):
    """
    Format a list of free times for display purposes.
    """
    formatted_free_times = []
    for free_time in free_time_list:
        free_str = "From {} to {}.".format(
            free_time[0].format('ddd, MMM D, h:mm a'),
            free_time[1].format('h:mm a'))
        formatted_free_times.append(free_str)
    return formatted_free_times


if __name__ == "__main__":
    # App is created above so that it will
    # exist whether this is 'main' or not
    # (e.g., if we are running under green unicorn)
    app.run(port=CONFIG.PORT, host="localhost")
