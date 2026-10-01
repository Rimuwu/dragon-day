from sqlalchemy import Column, Integer, String

from .db import Base


class GroupSettings(Base):
    __tablename__ = "group_settings"

    group_id = Column(Integer, primary_key=True)
    daily_time = Column(String(8), nullable=False)
    sleep_start = Column(String(8), nullable=False)
    sleep_end = Column(String(8), nullable=False)
    points_day = Column(Integer, nullable=False, default=100)
    points_evil = Column(Integer, nullable=False, default=-50)
    points_sleepy = Column(Integer, nullable=False, default=120)


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

    # Win streak tracking
    current_streak_day = Column(Integer, nullable=False, default=0)
    current_streak_day_start = Column(String(16))
    current_streak_day_end = Column(String(16))
    max_streak_day = Column(Integer, nullable=False, default=0)
    max_streak_day_start = Column(String(16))
    max_streak_day_end = Column(String(16))

    current_streak_evil = Column(Integer, nullable=False, default=0)
    current_streak_evil_start = Column(String(16))
    current_streak_evil_end = Column(String(16))
    max_streak_evil = Column(Integer, nullable=False, default=0)
    max_streak_evil_start = Column(String(16))
    max_streak_evil_end = Column(String(16))

    current_streak_sleepy = Column(Integer, nullable=False, default=0)
    current_streak_sleepy_start = Column(String(16))
    current_streak_sleepy_end = Column(String(16))
    max_streak_sleepy = Column(Integer, nullable=False, default=0)
    max_streak_sleepy_start = Column(String(16))
    max_streak_sleepy_end = Column(String(16))

    # Minigames tracking
    duels_played = Column(Integer, nullable=False, default=0)
    duels_won = Column(Integer, nullable=False, default=0)
    duels_points_won = Column(Integer, nullable=False, default=0)

    lottery_played = Column(Integer, nullable=False, default=0)
    lottery_won = Column(Integer, nullable=False, default=0)
    lottery_points_won = Column(Integer, nullable=False, default=0)

    # Daily Games & Max Streak tracking
    current_streak_daily_max = Column(Integer, nullable=False, default=0)
    max_streak_daily_max = Column(Integer, nullable=False, default=0)
    last_daily_max_date = Column(String(16))


class GroupState(Base):
    __tablename__ = "group_state"

    group_id = Column(Integer, primary_key=True)
    last_daily_date = Column(String(16))
    last_evil_date = Column(String(16))
    last_sleepy_date = Column(String(16))
    next_sleepy_at = Column(String(64))
    last_day_winner_id = Column(Integer)
    last_evil_winner_id = Column(Integer)
    last_sleepy_winner_id = Column(Integer)


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


class Roll(Base):
    __tablename__ = "rolls"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    roll_date = Column(String(16), primary_key=True)


class MessageCleanup(Base):
    __tablename__ = "message_cleanups"

    group_id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, primary_key=True)
    message_id = Column(Integer, primary_key=True)
    created_at = Column(String(64), nullable=False)
    is_event = Column(Integer, nullable=True, default=0, server_default="0")


class Duel(Base):
    __tablename__ = "duels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=False)
    target_id = Column(Integer, nullable=True)
    bet = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending, finished, canceled, expired
    created_at = Column(String(32), nullable=False)
    message_id = Column(Integer, nullable=True)
    opponent_id = Column(Integer, nullable=True)
    winner_id = Column(Integer, nullable=True)  # creator_id, opponent_id, or 0 for draw
    creator_dice1 = Column(Integer, nullable=True)
    creator_dice2 = Column(Integer, nullable=True)
    opponent_dice1 = Column(Integer, nullable=True)
    opponent_dice2 = Column(Integer, nullable=True)


class Lottery(Base):
    __tablename__ = "lotteries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=False)
    bet = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="active")  # active, finished, canceled
    created_at = Column(String(32), nullable=False)
    closes_at = Column(String(32), nullable=False)
    message_id = Column(Integer, nullable=True)
    winner_id = Column(Integer, nullable=True)
    total_bank = Column(Integer, nullable=False, default=0)
    winning_ticket = Column(Integer, nullable=True)


class LotteryParticipant(Base):
    __tablename__ = "lottery_participants"

    lottery_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    joined_at = Column(String(32), nullable=False)
    tickets = Column(String(512), nullable=True)  # JSON list of ticket numbers, e.g. "[3, 17, 42]"


class DailyBetPool(Base):
    __tablename__ = "daily_bet_pools"

    group_id = Column(Integer, primary_key=True)
    bet_type = Column(String(16), primary_key=True)
    bet_date = Column(String(16), primary_key=True)
    user_id = Column(Integer, primary_key=True)
    order_idx = Column(Integer, nullable=False, default=0)


class ShadowUser(Base):
    __tablename__ = "shadow_users"

    user_id = Column(Integer, primary_key=True)
    created_at = Column(String(32), nullable=False)


class DailyGame(Base):
    __tablename__ = "daily_games"

    group_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    game_type = Column(String(16), primary_key=True)  # "dice", "basket", "bowling", "football"
    roll_date = Column(String(16), primary_key=True)
    value = Column(Integer, nullable=False, default=0)
    points = Column(Integer, nullable=False, default=0)
    is_max = Column(Integer, nullable=False, default=0)


class DragonEffect(Base):
    __tablename__ = "dragon_effects"

    group_id = Column(Integer, primary_key=True)
    dragon_type = Column(String(16), primary_key=True)  # "day", "evil"
    effect_date = Column(String(16), primary_key=True)  # "YYYY-MM-DD"
    user_id = Column(Integer, nullable=False)
    effect_key = Column(String(32), nullable=False)
    effect_emoji = Column(String(8), nullable=False)
    effect_name = Column(String(64), nullable=False)


