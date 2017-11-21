"""
Nose tests for an artificial database using some functions
from flask_main and some functions that are copies in this file.
Main goal of this test is to make sure index method works correctly.
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
    collection = db.nose
except Exception as err:
    print("Failed")
    print(err)
    sys.exit(1)

today = arrow.utcnow().naive


def copy_memo_idx():
    # Can't test this from within flask_main, since it gets
    # the index from the wrong database collection.
    new_index = 0
    for record in collection.find():
        if record["index"] > new_index:
            new_index = record["index"]
    new_index += 1
    return new_index


def copy_del_memo(index):
    """
    Deletes a memo at an index in the database
    """
    for record in collection.find({"index": index}):
        collection.delete_one(record)


def test_memo_idx():
    # There are no memos in this collection, so the
    # next available index should be one.
    assert copy_memo_idx() == 1


def test_create():
    record = {"type": "dated_memo",
              "date":  today,
              "text": "Test memo",
              "index": copy_memo_idx()}
    collection.insert(record)

    record = {"type": "dated_memo",
              "date":  arrow.utcnow().replace(days=+1).naive,
              "text": "Test memo number two",
              "index": copy_memo_idx()}
    collection.insert(record)

    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append(
            {"type": record['type'],
             "date": arrow.get(record['date']).to('local').isoformat(),
             "text": record['text']})

    assert len(records) == 2


def test_delete():
    copy_del_memo(2)

    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append(
            {"type": record['type'],
             "date": arrow.get(record['date']).to('local').isoformat(),
             "text": record['text'],
             "index": record['index']})
    assert len(records) == 1


def test_contents():
    records = []
    for record in collection.find({"type": "dated_memo"}):
        records.append(
            {"type": record['type'],
             "date": arrow.get(record['date']).to('local').isoformat(),
             "text": record['text'],
             "index": record['index']})
    for i in records:
        print(i)
    assert records[0]["index"] == 1
    assert records[0]["text"] == "Test memo"


def test_clear():
    for record in collection.find():
        collection.delete_one(record)
