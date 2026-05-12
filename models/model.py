from sqlalchemy import Column, Integer, String

from .db import Base


class GroupSettings(Base):
    __tablename__ = "group_settings"

    group_id = Column(Integer, primary_key=True)
    daily_time = Column(String(8), nullable=False)
    sleep_start = Column(String(8), nullable=False)
    sleep_end = Column(String(8), nullable=False)


class AllowedGroup(Base):
    __tablename__ = "allowed_groups"

    group_id = Column(Integer, primary_key=True)
    added_by = Column(Integer, nullable=False)
    added_at = Column(String(32), nullable=False)


class Participant(Base):
    __tablename__ = "participants"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    username = Column(String(64))
    first_name = Column(String(128))
    last_name = Column(String(128))
    joined_at = Column(String(32), nullable=False)


class Stat(Base):
    __tablename__ = "stats"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    username = Column(String(64))
    first_name = Column(String(128))
    last_name = Column(String(128))
    points = Column(Integer, nullable=False, default=100)
    wins_day = Column(Integer, nullable=False, default=0)
    wins_evil = Column(Integer, nullable=False, default=0)
    wins_sleepy = Column(Integer, nullable=False, default=0)
    bets_played = Column(Integer, nullable=False, default=0)
    bets_won = Column(Integer, nullable=False, default=0)


class GroupState(Base):
    __tablename__ = "group_state"

    group_id = Column(Integer, primary_key=True)
    last_daily_date = Column(String(16))
    last_evil_date = Column(String(16))
    last_sleepy_date = Column(String(16))
    next_sleepy_at = Column(String(64))


class Bet(Base):
    __tablename__ = "bets"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    bet_type = Column(String(16), primary_key=True)
    target_user_id = Column(Integer, primary_key=True)
    bet_date = Column(String(16), primary_key=True)
    amount = Column(Integer, nullable=False)
    settled = Column(Integer, nullable=False, default=0)


class SleepEvent(Base):
    __tablename__ = "sleep_events"

    group_id = Column(Integer, primary_key=True)
    sleep_date = Column(String(16), primary_key=True)
    closes_at = Column(String(64), nullable=False)
    message_id = Column(Integer, nullable=False)


class SleepEntry(Base):
    __tablename__ = "sleep_entries"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    sleep_date = Column(String(16), primary_key=True)
