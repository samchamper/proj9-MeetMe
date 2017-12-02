# Nose tests for free.
# Author Sam Champer

import nose
from free import free
import arrow

day_range = [arrow.get("2017-11-21T00:00:00-08:00"),
             arrow.get("2017-11-22T00:00:00-08:00"),
             arrow.get("2017-11-23T00:00:00-08:00"),
             arrow.get("2017-11-24T00:00:00-08:00"),
             arrow.get("2017-11-25T00:00:00-08:00"),
             arrow.get("2017-11-26T00:00:00-08:00"),
             arrow.get("2017-11-27T00:00:00-08:00")]


def output_format(times_list):
    """
    For formatting outputs from the free function.
    For testing purposes.
    """
    formatted_free_times = []
    for i in times_list:
        fmt_str = "{} to {}.".format(
            i[0].format('ddd, MMM D, h:mm a'),
            i[1].format('ddd, MMM D, h:mm a'))
        formatted_free_times.append(fmt_str)
    return formatted_free_times


def test_free_one():
    """
    Test to see if free time matches expectation when
    we throw a single event into the daterange.
    """
    events = [['Event', '2017-11-21T10:00:00-08:00', '2017-11-21T11:20:00-08:00']]
    freetimes, _ = free(events, 9, 0, 17, 0, day_range, 30)  # From 9 to 5.
    fmt_freetime = output_format(freetimes)
    for i in fmt_freetime:
        print(i)
    assert fmt_freetime == ['Tue, Nov 21, 9:00 am to Tue, Nov 21, 10:00 am.',
                            'Tue, Nov 21, 11:20 am to Tue, Nov 21, 5:00 pm.',
                            'Wed, Nov 22, 9:00 am to Wed, Nov 22, 5:00 pm.',
                            'Thu, Nov 23, 9:00 am to Thu, Nov 23, 5:00 pm.',
                            'Fri, Nov 24, 9:00 am to Fri, Nov 24, 5:00 pm.',
                            'Sat, Nov 25, 9:00 am to Sat, Nov 25, 5:00 pm.',
                            'Sun, Nov 26, 9:00 am to Sun, Nov 26, 5:00 pm.',
                            'Mon, Nov 27, 9:00 am to Mon, Nov 27, 5:00 pm.']


def test_nothing_fits():
    """
    Test a situation where we don't have any room to fit
    a 10 hour long meeting, and make sure free correctly
    doesn't give us any options.
    """
    freetimes, _ = free([], 9, 0, 17, 0, day_range, 600)
    fmt_freetime = output_format(freetimes)
    for i in fmt_freetime:
        print(i)
    assert fmt_freetime == []


def test_overlap():
    """
    Test that free correctly handles overlapping events.
    """
    events = [['Event', '2017-11-21T10:00:00-08:00', '2017-11-21T11:00:00-08:00'],
              ['Event', '2017-11-21T10:30:00-08:00', '2017-11-21T11:20:00-08:00']]
    freetimes, _ = free(events, 9, 0, 17, 0, day_range, 30)
    fmt_freetime = output_format(freetimes)
    for i in fmt_freetime:
        print(i)
    assert fmt_freetime == ['Tue, Nov 21, 9:00 am to Tue, Nov 21, 10:00 am.',
                            'Tue, Nov 21, 11:20 am to Tue, Nov 21, 5:00 pm.',
                            'Wed, Nov 22, 9:00 am to Wed, Nov 22, 5:00 pm.',
                            'Thu, Nov 23, 9:00 am to Thu, Nov 23, 5:00 pm.',
                            'Fri, Nov 24, 9:00 am to Fri, Nov 24, 5:00 pm.',
                            'Sat, Nov 25, 9:00 am to Sat, Nov 25, 5:00 pm.',
                            'Sun, Nov 26, 9:00 am to Sun, Nov 26, 5:00 pm.',
                            'Mon, Nov 27, 9:00 am to Mon, Nov 27, 5:00 pm.']


def test_shotgun():
    """
    Test to see that free times match those expected for a typical
    situation where we have a bunch of events.
    """
    events = [['Event', '2017-11-22T11:30:00-08:00', '2017-11-22T12:10:00-08:00'],
              ['Event', '2017-11-22T12:00:00-08:00', '2017-11-22T13:00:00-08:00'],
              ['Event', '2017-11-22T12:30:00-08:00', '2017-11-22T13:30:00-08:00'],
              ['Event', '2017-11-23T10:00:00-08:00', '2017-11-23T11:20:00-08:00'],
              ['Event', '2017-11-23T14:00:00-08:00', '2017-11-23T15:00:00-08:00'],
              ['Event', '2017-11-24T14:30:00-08:00', '2017-11-25T19:00:00-08:00'],
              ['Event', '2017-11-25T12:00:00-08:00', '2017-11-25T13:00:00-08:00'],
              ['Event', '2017-11-26T11:30:00-08:00', '2017-11-26T12:10:00-08:00'],
              ['Event', '2017-11-26T12:30:00-08:00', '2017-11-26T13:30:00-08:00'],
              ['Event', '2017-11-28T10:00:00-08:00', '2017-11-28T11:20:00-08:00'],
              ['Event', '2017-11-28T12:00:00-08:00', '2017-11-28T13:00:00-08:00'],
              ['Event', '2017-11-28T14:00:00-08:00', '2017-11-28T15:00:00-08:00']]

    freetimes, _ = free(events, 9, 0, 17, 0, day_range, 30)
    fmt_freetime = output_format(freetimes)
    print(fmt_freetime)
    for i in fmt_freetime:
        print(i)
    assert fmt_freetime == ['Tue, Nov 21, 9:00 am to Tue, Nov 21, 5:00 pm.',
                            'Wed, Nov 22, 9:00 am to Wed, Nov 22, 11:30 am.',
                            'Wed, Nov 22, 1:30 pm to Wed, Nov 22, 5:00 pm.',
                            'Thu, Nov 23, 9:00 am to Thu, Nov 23, 10:00 am.',
                            'Thu, Nov 23, 11:20 am to Thu, Nov 23, 2:00 pm.',
                            'Thu, Nov 23, 3:00 pm to Thu, Nov 23, 5:00 pm.',
                            'Fri, Nov 24, 9:00 am to Fri, Nov 24, 2:30 pm.',
                            'Sun, Nov 26, 9:00 am to Sun, Nov 26, 11:30 am.',
                            'Sun, Nov 26, 1:30 pm to Sun, Nov 26, 5:00 pm.',
                            'Mon, Nov 27, 9:00 am to Mon, Nov 27, 5:00 pm.',
                            'Tue, Nov 28, 9:00 am to Tue, Nov 28, 10:00 am.',
                            'Tue, Nov 28, 11:20 am to Tue, Nov 28, 12:00 pm.',
                            'Tue, Nov 28, 1:00 pm to Tue, Nov 28, 2:00 pm.']
