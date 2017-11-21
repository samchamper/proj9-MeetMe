"""
Nose tests for most of the functions in the memo application.
"""
import nose
from flask_main import *
import pymongo
from pymongo import MongoClient
import arrow
import sys
import config

"""
Connect to database so we can test stuff:
"""
CONFIG = config.configuration()
MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST,
    CONFIG.DB_PORT,
    CONFIG.DB)
try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, str(CONFIG.DB))
    collection = db.memos
except Exception as err:
    print("Failed")
    print(err)
    sys.exit(1)

today = arrow.utcnow()
tomorrow = arrow.utcnow().replace(days=+1)
yesterday = arrow.utcnow().replace(days=-1)
future = arrow.utcnow().replace(years=+10)
past = arrow.utcnow().replace(years=-10)

East_of_Greenwhich = arrow.now().isoformat()[-6]
if East_of_Greenwhich == "-":
    today = today.shift(days=-1)
    tomorrow = tomorrow.shift(days=-1)
    yesterday = yesterday.shift(days=-1)
    future = future.shift(days=-1)
    past = past.shift(days=-1)


def test_create():
    """
    Create five memos.
    The memos will have negative indexes in order to make
    sure these ones don't have the same indexes as a memo
    already in the database.
    """
    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append({
            "type": record['type'],
            "date": arrow.get(record['date']).isoformat(),
            "text": record['text']})

    initial_len = len(records)

    record = {"type": "dated_memo",
              "date":  today.format('YYYY-M-D'),
              "text": "Today's memo.",
              "index": -1}
    collection.insert(record)

    record = {"type": "dated_memo",
              "date":  tomorrow.format('YYYY-M-D'),
              "text": "Tomorrow's memo",
              "index": -2}
    collection.insert(record)

    record = {"type": "dated_memo",
              "date":  yesterday.format('YYYY-M-D'),
              "text": "Yesterday's memo",
              "index": -3}
    collection.insert(record)

    record = {"type": "dated_memo",
              "date":  future.format('YYYY-M-D'),
              "text": "Memo of the future.",
              "index": -4}
    collection.insert(record)

    record = {"type": "dated_memo",
              "date":  past.format('YYYY-M-D'),
              "text": "Memo of the past.",
              "index": -5}
    collection.insert(record)

    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append({
            "type": record['type'],
            "date": arrow.get(record['date']).isoformat(),
            "text": record['text']})

    assert len(records) == initial_len + 5


def test_order():
    """
    Test to make sure that memos are being correctly sorted by date.
    """
    records = get_memos()
    for i in range(1, len(records)):
        assert arrow.get(records[i-1]['a_date']) <= arrow.get(records[i]['a_date'])


def test_humanity():
    """
    Test that dates are being humanized the way they should be.
    """
    assert humanize_arrow_date(today.isoformat()) == "Today"
    assert humanize_arrow_date(tomorrow.isoformat()) == 'Tomorrow'
    assert humanize_arrow_date(yesterday.isoformat()) == 'Yesterday'
    assert humanize_arrow_date(future.isoformat()) == 'in 10 years'
    assert humanize_arrow_date(past.isoformat()) == '10 years ago'


def test_delete():
    """
    Test that memos can be deleted properly.
    We want to delete these fake memos anyway.
    """
    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append({
            "type": record['type'],
            "date": arrow.get(record['date']).isoformat(),
            "text": record['text']})

    initial_len = len(records)

    del_memo(-1)
    del_memo(-2)
    del_memo(-3)
    del_memo(-4)
    del_memo(-5)

    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append(
            {"type": record['type'],
             "date": arrow.get(record['date']).isoformat(),
             "text": record['text'],
             "index": record['index']})

    assert len(records) == initial_len - 5
