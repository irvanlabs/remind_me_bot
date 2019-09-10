from dateutil.parser import parse
from db.Remind import Remind, Base
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Boolean, cast, Date
from sqlalchemy import desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from utils.constants import DATETIME_FORMAT, LAST_REMIND_TIME, LIST_ALL_FLAG, LIST_WEEK_FLAG, START_WEEK_FORMAT, END_WEEK_FORMAT
import datetime 
import json
import logging
import os

load_dotenv()

logger = logging.getLogger('database')


engine = create_engine(os.environ['DB_URL'], pool_size=20, max_overflow=100)
Session = sessionmaker(bind=engine)

# Detailed query logging
if os.getenv('DEBUG'): logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class RemindEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Remind):
            return obj.__dict__


# Generate database schema
Base.metadata.create_all(engine)

# Create new remind in DB
def create(chat_id, time, text, expired=False, done=False):
    logger.info("Creating remind...")
    # Create a new session
    session = Session()
    parsed_time = parse(time)
    today=datetime.datetime.today().strftime('%Y-%m-%d %H:00:00')
    if parsed_time >= today: 
        remind = Remind(chat_id, parsed_time, text, expired, done)
        session.add(remind)
        # Commit and close session
    else:
        raise Exception
    session.commit()
    session.close()


def _update(chat_id, id, time, text):
    logger.info("Updating remind...")
    session = Session()
    new_time = parse(time)
    session.query(Remind).filter_by(chat_id=chat_id, id=id).update({"remind_time": new_time, "remind_text": text, "expired": "false"})
    
    # Commit and close session
    session.commit()
    session.close()


def expire_remind(delete_id):
    session = Session()
    for i in delete_id:
        session.query(Remind).filter_by(id=i.id, done=False).update({"expired": True}, synchronize_session=False)

    # Commit and close session
    session.commit()
    session.close()


def get_reminds(user_chat_id, interval):
    logger.info("Getting reminds...")
    session = Session()
    if interval == '':
        reminds_list = session.query(Remind).filter_by(chat_id=user_chat_id).\
            filter(cast(Remind.remind_time, Date) == datetime.datetime.today().date() ).\
                order_by(Remind.remind_time).all()
        json_data = json.loads(json.dumps(reminds_list, cls=RemindEncoder, indent=4))
    elif interval == LIST_ALL_FLAG:
        # Select all reminds, user is defined by chat_id
        reminds_list = session.query(Remind).filter_by(chat_id=user_chat_id).order_by(Remind.remind_time).all()
    elif interval ==  LIST_WEEK_FLAG:
        today = datetime.datetime.today()
        weekday = today.weekday()
        mon = (today - datetime.timedelta(days=weekday)).strftime(START_WEEK_FORMAT)
        sun = (today + datetime.timedelta(days=(6 - weekday))).strftime(END_WEEK_FORMAT)
        reminds_list = session.query(Remind).filter_by(chat_id=user_chat_id).\
            filter(cast(Remind.remind_time, Date) >= mon, cast(Remind.remind_time, Date) <= sun ).\
                order_by(Remind.remind_time).all()

    json_data = json.loads(json.dumps(reminds_list, cls=RemindEncoder, indent=4))
    # Close session
    session.close()
    if json_data:
        return json_data


def check_remind(*time):
    logger.info("Checking reminds...")
    session = Session()
    current_time=datetime.datetime.now().strftime(DATETIME_FORMAT)

    if not time:
        remind_time = current_time
        remind = session.query(Remind).filter_by(remind_time=remind_time).filter_by(expired=False).filter_by(done=False).all()
    else:
        if time[0] <= LAST_REMIND_TIME:
            remind_time = (datetime.datetime.strptime(current_time, DATETIME_FORMAT) - datetime.timedelta(minutes=time[0])).strftime(DATETIME_FORMAT)
            remind = session.query(Remind).filter_by(remind_time=remind_time).filter_by(expired=False).filter_by(done=False).all()
            logger.info("Checking NONEXPIRED...")
        else:
            delta = (datetime.datetime.strptime(current_time, DATETIME_FORMAT) - datetime.timedelta(minutes=time[0])).strftime(DATETIME_FORMAT)
            logger.info('delta time: ' + delta)
            remind = session.query(Remind).filter_by(expired=False).filter_by(done=False).filter(Remind.remind_time <= delta).all()
            remind_j = json.loads(json.dumps(remind, cls=RemindEncoder, indent=4))
            expire_remind(remind)
            logger.info('expiring remind')
            return 'expired', remind_j

    remind_j = json.loads(json.dumps(remind, cls=RemindEncoder, indent=4))
    if remind_j: 
        return remind_j
    # Close session
    session.close()


def close(user_chat_id, id):
    logger.info("Closing reminds...")    
    session = Session()
    current_time=datetime.datetime.now().strftime(DATETIME_FORMAT)
    if not id:
        # TODO 
        # check if last remind exists
        remind = session.query(Remind).filter_by(chat_id=user_chat_id).filter_by(done=False).filter(Remind.remind_time <= current_time).order_by(desc(Remind.remind_time)).first()
        if remind is not None:
            session.query(Remind).filter_by(chat_id=user_chat_id).filter_by(id=remind.id).update({"done": True}, synchronize_session=False)
    else:
        for i in id:
            session.query(Remind).filter_by(chat_id=user_chat_id).filter_by(id=i).update({"done": True}, synchronize_session=False)
    # Commit and close session
    session.commit()
    session.close()


def delete(delete_id, chat_id):
    logger.info("Deleting reminds...")
    session = Session()
    for i in delete_id:
        deleted_remind = session.query(Remind).filter_by(chat_id=chat_id, id=i).delete(synchronize_session=False)
        if delete_id == 0:
            raise Exception

    # Commit and close session
    session.commit()
    session.close()

