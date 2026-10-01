import random
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, func, select, text

from models.db import Base, build_engine, build_session_factory
from models.model import (
    AllowedGroup,
    Bet,
    DailyBetPool,
    DailyGame,
    DragonEffect,
    Duel,
    GroupSettings,
    GroupState,
    Lottery,
    LotteryParticipant,
    MessageCleanup,
    Participant,
    Roll,
    ShadowUser,
    SleepEntry,
    SleepEvent,
    Stat,
)


class Database:
    def __init__(self, path: str) -> None:
        self.engine = build_engine(path)
        self.SessionLocal = build_session_factory(self.engine)

    def _normalize_stat(self, stat: Stat) -> None:
        stat_data = cast(Any, stat)
        if stat_data.points is None:
            stat_data.points = 100
        if stat_data.wins_day is None:
            stat_data.wins_day = 0
        if stat_data.wins_evil is None:
            stat_data.wins_evil = 0
        if stat_data.wins_sleepy is None:
            stat_data.wins_sleepy = 0
        if stat_data.bets_played is None:
            stat_data.bets_played = 0
        if stat_data.bets_won is None:
            stat_data.bets_won = 0
        for suffix in ("day", "evil", "sleepy"):
            if getattr(stat_data, f"current_streak_{suffix}") is None:
                setattr(stat_data, f"current_streak_{suffix}", 0)
            if getattr(stat_data, f"max_streak_{suffix}") is None:
                setattr(stat_data, f"max_streak_{suffix}", 0)
        for field in ("duels_played", "duels_won", "duels_points_won", "lottery_played", "lottery_won", "lottery_points_won", "current_streak_daily_max", "max_streak_daily_max"):
            if getattr(stat_data, field, None) is None:
                setattr(stat_data, field, 0)

    @contextmanager
    def _session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def init(self) -> None:
        Base.metadata.create_all(bind=self.engine)
        self._ensure_group_settings_columns()
        self._ensure_group_state_columns()
        self._ensure_stat_columns()
        self._ensure_message_cleanups_columns()
        self._ensure_daily_bet_pools_table()

    def _ensure_group_settings_columns(self) -> None:
        with self.engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(group_settings)")).fetchall()
            columns = {row[1] for row in rows}
            if "points_day" not in columns:
                conn.execute(text("ALTER TABLE group_settings ADD COLUMN points_day INTEGER"))
            if "points_evil" not in columns:
                conn.execute(text("ALTER TABLE group_settings ADD COLUMN points_evil INTEGER"))
            if "points_sleepy" not in columns:
                conn.execute(text("ALTER TABLE group_settings ADD COLUMN points_sleepy INTEGER"))
            if "dragons_topic_id" not in columns:
                conn.execute(text("ALTER TABLE group_settings ADD COLUMN dragons_topic_id INTEGER"))
            if "commands_topic_id" not in columns:
                conn.execute(text("ALTER TABLE group_settings ADD COLUMN commands_topic_id INTEGER"))

    def _ensure_group_state_columns(self) -> None:
        state_cols = [
            ("last_evil_date", "TEXT"),
            ("last_day_winner_id", "INTEGER"),
            ("last_evil_winner_id", "INTEGER"),
            ("last_sleepy_winner_id", "INTEGER"),
        ]
        with self.engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(group_state)")).fetchall()
            columns = {row[1] for row in rows}
            for col_name, col_type in state_cols:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE group_state ADD COLUMN {col_name} {col_type}"))

    def _ensure_stat_columns(self) -> None:
        stat_cols = [
            ("current_streak_day", "INTEGER DEFAULT 0"),
            ("current_streak_day_start", "TEXT"),
            ("current_streak_day_end", "TEXT"),
            ("max_streak_day", "INTEGER DEFAULT 0"),
            ("max_streak_day_start", "TEXT"),
            ("max_streak_day_end", "TEXT"),
            ("current_streak_evil", "INTEGER DEFAULT 0"),
            ("current_streak_evil_start", "TEXT"),
            ("current_streak_evil_end", "TEXT"),
            ("max_streak_evil", "INTEGER DEFAULT 0"),
            ("max_streak_evil_start", "TEXT"),
            ("max_streak_evil_end", "TEXT"),
            ("current_streak_sleepy", "INTEGER DEFAULT 0"),
            ("current_streak_sleepy_start", "TEXT"),
            ("current_streak_sleepy_end", "TEXT"),
            ("max_streak_sleepy", "INTEGER DEFAULT 0"),
            ("max_streak_sleepy_start", "TEXT"),
            ("max_streak_sleepy_end", "TEXT"),
            ("duels_played", "INTEGER DEFAULT 0"),
            ("duels_won", "INTEGER DEFAULT 0"),
            ("duels_points_won", "INTEGER DEFAULT 0"),
            ("lottery_played", "INTEGER DEFAULT 0"),
            ("lottery_won", "INTEGER DEFAULT 0"),
            ("lottery_points_won", "INTEGER DEFAULT 0"),
            ("current_streak_daily_max", "INTEGER DEFAULT 0"),
            ("max_streak_daily_max", "INTEGER DEFAULT 0"),
            ("last_daily_max_date", "TEXT"),
        ]
        with self.engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(stats)")).fetchall()
            columns = {row[1] for row in rows}
            for col_name, col_type in stat_cols:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE stats ADD COLUMN {col_name} {col_type}"))

    def _ensure_message_cleanups_columns(self) -> None:
        with self.engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(message_cleanups)")).fetchall()
            columns = {row[1] for row in rows}
            if "is_event" not in columns:
                conn.execute(text("ALTER TABLE message_cleanups ADD COLUMN is_event INTEGER NOT NULL DEFAULT 0"))

    def _ensure_daily_bet_pools_table(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS daily_bet_pools (
                        group_id INTEGER NOT NULL,
                        bet_type VARCHAR(16) NOT NULL,
                        bet_date VARCHAR(16) NOT NULL,
                        user_id INTEGER NOT NULL,
                        order_idx INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (group_id, bet_type, bet_date, user_id)
                    )
                    """
                )
            )

    def ensure_group(self, group_id: int, defaults: dict) -> None:
        with self._session() as session:
            settings = session.get(GroupSettings, group_id)
            if settings is None:
                settings = GroupSettings(
                    group_id=group_id,
                    daily_time=defaults["daily_time_default"],
                    sleep_start=defaults["sleep_start_default"],
                    sleep_end=defaults["sleep_end_default"],
                    points_day=defaults["points_day"],
                    points_evil=defaults["points_evil"],
                    points_sleepy=defaults["points_sleepy"],
                )
                session.add(settings)
            else:
                if settings.points_day is None:
                    settings.points_day = defaults["points_day"]
                if settings.points_evil is None:
                    settings.points_evil = defaults["points_evil"]
                if settings.points_sleepy is None:
                    settings.points_sleepy = defaults["points_sleepy"]
            state = session.get(GroupState, group_id)
            if state is None:
                session.add(GroupState(group_id=group_id))

    def is_group_allowed(self, group_id: int) -> bool:
        with self._session() as session:
            return session.get(AllowedGroup, group_id) is not None

    def allow_group(self, group_id: int, added_by: int, added_at: str, defaults: dict) -> bool:
        with self._session() as session:
            existing = session.get(AllowedGroup, group_id)
            if existing is not None:
                return False
            session.add(AllowedGroup(group_id=group_id, added_by=added_by, added_at=added_at))
        self.ensure_group(group_id, defaults)
        return True

    def get_groups(self) -> list[int]:
        with self._session() as session:
            rows = session.execute(select(AllowedGroup.group_id)).all()
        return [row[0] for row in rows]

    def get_group_settings(self, group_id: int, defaults: dict) -> dict:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
        return {
            "daily_time": row.daily_time,
            "sleep_start": row.sleep_start,
            "sleep_end": row.sleep_end,
            "points_day": row.points_day,
            "points_evil": row.points_evil,
            "points_sleepy": row.points_sleepy,
            "dragons_topic_id": getattr(row, "dragons_topic_id", None),
            "commands_topic_id": getattr(row, "commands_topic_id", None),
        }

    def set_group_time(self, group_id: int, daily_time: str, defaults: dict) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.daily_time = daily_time

    def set_group_sleep_range(self, group_id: int, sleep_start: str, sleep_end: str, defaults: dict) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.sleep_start = sleep_start
            row.sleep_end = sleep_end

    def set_group_points(
        self,
        group_id: int,
        points_day: int,
        points_evil: int,
        points_sleepy: int,
        defaults: dict,
    ) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.points_day = points_day
            row.points_evil = points_evil
            row.points_sleepy = points_sleepy

    def set_group_dragons_topic(self, group_id: int, topic_id: int | None, defaults: dict) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.dragons_topic_id = topic_id

    def set_group_commands_topic(self, group_id: int, topic_id: int | None, defaults: dict) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.commands_topic_id = topic_id

    def reset_group_topics(self, group_id: int, defaults: dict) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupSettings, group_id)
            row.dragons_topic_id = None
            row.commands_topic_id = None

    def set_group_state(
        self,
        group_id: int,
        last_daily_date: str | None,
        last_evil_date: str | None,
        last_sleepy_date: str | None,
        next_sleepy_at: str | None,
        defaults: dict,
    ) -> None:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupState, group_id)
            row.last_daily_date = last_daily_date
            row.last_evil_date = last_evil_date
            row.last_sleepy_date = last_sleepy_date
            row.next_sleepy_at = next_sleepy_at

    def get_group_state(self, group_id: int, defaults: dict) -> dict:
        self.ensure_group(group_id, defaults)
        with self._session() as session:
            row = session.get(GroupState, group_id)
        return {
            "last_daily_date": row.last_daily_date,
            "last_evil_date": row.last_evil_date,
            "last_sleepy_date": row.last_sleepy_date,
            "next_sleepy_at": row.next_sleepy_at,
        }

    def upsert_user(
        self,
        group_id: int,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(
                    group_id=group_id,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
                session.add(stat)
            else:
                if username is not None:
                    stat.username = username
                if first_name is not None:
                    stat.first_name = first_name
                if last_name is not None:
                    stat.last_name = last_name

            participant = session.get(Participant, (group_id, user_id))
            if participant is not None:
                if username is not None:
                    participant.username = username
                if first_name is not None:
                    participant.first_name = first_name
                if last_name is not None:
                    participant.last_name = last_name

    def sync_user(self, group_id: int, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is not None:
                if username is not None:
                    stat.username = username
                if first_name is not None:
                    stat.first_name = first_name
                if last_name is not None:
                    stat.last_name = last_name
            participant = session.get(Participant, (group_id, user_id))
            if participant is not None:
                if username is not None:
                    participant.username = username
                if first_name is not None:
                    participant.first_name = first_name
                if last_name is not None:
                    participant.last_name = last_name

    def add_participant(
        self,
        group_id: int,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        joined_at: str,
    ) -> None:
        with self._session() as session:
            row = session.get(Participant, (group_id, user_id))
            if row is None:
                row = Participant(
                    group_id=group_id,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    joined_at=joined_at,
                )
                session.add(row)
            else:
                row.username = username
                row.first_name = first_name
                row.last_name = last_name
                row.joined_at = joined_at
        self.upsert_user(group_id, user_id, username, first_name, last_name)

    def is_participant(self, group_id: int, user_id: int) -> bool:
        with self._session() as session:
            return session.get(Participant, (group_id, user_id)) is not None

    def remove_participant(self, group_id: int, user_id: int) -> None:
        with self._session() as session:
            session.execute(
                delete(Participant).where(
                    Participant.group_id == group_id,
                    Participant.user_id == user_id,
                )
            )

    def list_participants(self, group_id: int) -> list[dict]:
        with self._session() as session:
            p_rows = (
                session.execute(
                    select(Participant)
                    .where(Participant.group_id == group_id)
                    .order_by(Participant.joined_at)
                )
                .scalars()
                .all()
            )
            s_rows = (
                session.execute(
                    select(Stat)
                    .where(Stat.group_id == group_id)
                )
                .scalars()
                .all()
            )
            users: dict[int, dict] = {}
            for row in p_rows:
                users[row.user_id] = {
                    "user_id": row.user_id,
                    "username": row.username,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                }
            for row in s_rows:
                if row.user_id not in users:
                    users[row.user_id] = {
                        "user_id": row.user_id,
                        "username": row.username,
                        "first_name": row.first_name,
                        "last_name": row.last_name,
                    }
                else:
                    if not users[row.user_id].get("username") and row.username:
                        users[row.user_id]["username"] = row.username
                    if not users[row.user_id].get("first_name") and row.first_name:
                        users[row.user_id]["first_name"] = row.first_name
                    if not users[row.user_id].get("last_name") and row.last_name:
                        users[row.user_id]["last_name"] = row.last_name
            return list(users.values())

    def get_user_stats(self, group_id: int, user_id: int) -> dict | None:
        with self._session() as session:
            row = session.get(Stat, (group_id, user_id))
        if row is None:
            return None
        self._normalize_stat(row)
        return {
            "points": row.points,
            "wins_day": row.wins_day,
            "wins_evil": row.wins_evil,
            "wins_sleepy": row.wins_sleepy,
            "bets_played": row.bets_played,
            "bets_won": row.bets_won,
            "username": row.username,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "current_streak_day": row.current_streak_day,
            "current_streak_day_start": row.current_streak_day_start,
            "current_streak_day_end": row.current_streak_day_end,
            "max_streak_day": row.max_streak_day,
            "max_streak_day_start": row.max_streak_day_start,
            "max_streak_day_end": row.max_streak_day_end,
            "current_streak_evil": row.current_streak_evil,
            "current_streak_evil_start": row.current_streak_evil_start,
            "current_streak_evil_end": row.current_streak_evil_end,
            "max_streak_evil": row.max_streak_evil,
            "max_streak_evil_start": row.max_streak_evil_start,
            "max_streak_evil_end": row.max_streak_evil_end,
            "current_streak_sleepy": row.current_streak_sleepy,
            "current_streak_sleepy_start": row.current_streak_sleepy_start,
            "current_streak_sleepy_end": row.current_streak_sleepy_end,
            "max_streak_sleepy": row.max_streak_sleepy,
            "max_streak_sleepy_start": row.max_streak_sleepy_start,
            "max_streak_sleepy_end": row.max_streak_sleepy_end,
            "duels_played": getattr(row, "duels_played", 0) or 0,
            "duels_won": getattr(row, "duels_won", 0) or 0,
            "duels_points_won": getattr(row, "duels_points_won", 0) or 0,
            "lottery_played": getattr(row, "lottery_played", 0) or 0,
            "lottery_won": getattr(row, "lottery_won", 0) or 0,
            "lottery_points_won": getattr(row, "lottery_points_won", 0) or 0,
            "current_streak_daily_max": getattr(row, "current_streak_daily_max", 0) or 0,
            "max_streak_daily_max": getattr(row, "max_streak_daily_max", 0) or 0,
            "last_daily_max_date": getattr(row, "last_daily_max_date", None),
        }

    def get_user_identity(self, group_id: int, user_id: int) -> dict | None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            participant = session.get(Participant, (group_id, user_id))

            if not stat and not participant:
                return None

            username = None
            first_name = None
            last_name = None

            if stat:
                username = stat.username
                first_name = stat.first_name
                last_name = stat.last_name

            if participant:
                if not username and participant.username:
                    username = participant.username
                if not first_name and participant.first_name:
                    first_name = participant.first_name
                if not last_name and participant.last_name:
                    last_name = participant.last_name

            return {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            }

    def adjust_points(self, group_id: int, user_id: int, delta: int) -> None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)
            stat_data = cast(Any, stat)
            self._normalize_stat(stat)
            stat_data.points += delta

    def record_win(
        self,
        group_id: int,
        user_id: int,
        win_type: str,
        points_delta: int,
        win_date: str | None = None,
    ) -> None:
        column = {
            "day": "wins_day",
            "evil": "wins_evil",
            "sleepy": "wins_sleepy",
        }[win_type]
        date_val = win_date or datetime.now().date().isoformat()
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)
            stat_data = cast(Any, stat)
            self._normalize_stat(stat)
            setattr(stat_data, column, getattr(stat_data, column) + 1)
            stat_data.points += points_delta

            state = session.get(GroupState, group_id)
            if state is None:
                state = GroupState(group_id=group_id)
                session.add(state)

            last_winner_attr = f"last_{win_type}_winner_id"
            last_winner_id = getattr(state, last_winner_attr, None)

            current_streak_attr = f"current_streak_{win_type}"
            current_start_attr = f"current_streak_{win_type}_start"
            current_end_attr = f"current_streak_{win_type}_end"
            max_streak_attr = f"max_streak_{win_type}"
            max_start_attr = f"max_streak_{win_type}_start"
            max_end_attr = f"max_streak_{win_type}_end"

            if last_winner_id == user_id:
                # Победил тот же участник подряд
                cur_val = (getattr(stat_data, current_streak_attr) or 0) + 1
                setattr(stat_data, current_streak_attr, cur_val)
                if not getattr(stat_data, current_start_attr):
                    setattr(stat_data, current_start_attr, date_val)
                setattr(stat_data, current_end_attr, date_val)
            else:
                # Победил другой участник - сбрасываем серию предыдущего победителя
                if last_winner_id is not None:
                    prev_stat = session.get(Stat, (group_id, last_winner_id))
                    if prev_stat is not None:
                        setattr(prev_stat, current_streak_attr, 0)
                # Новый победитель начинает серию
                setattr(stat_data, current_streak_attr, 1)
                setattr(stat_data, current_start_attr, date_val)
                setattr(stat_data, current_end_attr, date_val)
                setattr(state, last_winner_attr, user_id)

            cur_streak = getattr(stat_data, current_streak_attr) or 0
            max_streak = getattr(stat_data, max_streak_attr) or 0
            if cur_streak > max_streak:
                setattr(stat_data, max_streak_attr, cur_streak)
                setattr(stat_data, max_start_attr, getattr(stat_data, current_start_attr))
                setattr(stat_data, max_end_attr, getattr(stat_data, current_end_attr))

    def get_leaderboard(self, group_id: int, kind: str, limit: int, offset: int) -> list[dict]:
        column = {
            "points": Stat.points,
            "day": Stat.wins_day,
            "evil": Stat.wins_evil,
            "sleepy": Stat.wins_sleepy,
        }[kind]
        with self._session() as session:
            rows = (
                session.execute(
                    select(Stat)
                    .where(Stat.group_id == group_id)
                    .order_by(column.desc(), Stat.user_id.asc())
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )
        for row in rows:
            self._normalize_stat(row)
        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "points": row.points,
                "wins_day": row.wins_day,
                "wins_evil": row.wins_evil,
                "wins_sleepy": row.wins_sleepy,
            }
            for row in rows
        ]

    def get_leaderboard_all(self, group_id: int, kind: str) -> list[dict]:
        column = {
            "points": Stat.points,
            "day": Stat.wins_day,
            "evil": Stat.wins_evil,
            "sleepy": Stat.wins_sleepy,
        }[kind]
        with self._session() as session:
            rows = (
                session.execute(
                    select(Stat)
                    .where(Stat.group_id == group_id)
                    .order_by(column.desc(), Stat.user_id.asc())
                )
                .scalars()
                .all()
            )
        for row in rows:
            self._normalize_stat(row)
        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "points": row.points,
                "wins_day": row.wins_day,
                "wins_evil": row.wins_evil,
                "wins_sleepy": row.wins_sleepy,
            }
            for row in rows
        ]

    def count_stats(self, group_id: int) -> int:
        with self._session() as session:
            total = session.execute(
                select(func.count()).select_from(Stat).where(Stat.group_id == group_id)
            ).scalar_one()
        return int(total)

    def get_points(self, group_id: int, user_id: int) -> int:
        with self._session() as session:
            row = session.get(Stat, (group_id, user_id))
        return int(row.points) if row else 0

    def get_bet_amounts(self, group_id: int, user_id: int, bet_type: str, bet_date: str) -> dict[int, int]:
        with self._session() as session:
            rows = session.execute(
                select(Bet.target_user_id, Bet.amount)
                .where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_type == bet_type,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).all()
        return {row[0]: row[1] for row in rows}

    def list_active_bets(self, group_id: int, user_id: int, bet_date: str) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(Bet).where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalars().all()
        return [
            {
                "bet_type": row.bet_type,
                "target_user_id": row.target_user_id,
                "amount": row.amount,
                "bet_date": row.bet_date,
            }
            for row in rows
        ]

    def adjust_bet(
        self,
        group_id: int,
        user_id: int,
        bet_type: str,
        target_user_id: int,
        bet_date: str,
        delta: int,
    ) -> tuple[bool, str]:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)

            bet = session.get(Bet, (group_id, user_id, bet_type, target_user_id, bet_date))
            current_amount = bet.amount if bet else 0
            new_amount = current_amount + delta
            if new_amount < 0:
                return False, "Ставка не может быть меньше 0."

            if delta > 0 and stat.points < delta:
                return False, "Недостаточно очков для ставки."

            if new_amount == 0:
                if bet:
                    session.delete(bet)
            elif bet:
                bet.amount = new_amount
            else:
                session.add(
                    Bet(
                        group_id=group_id,
                        user_id=user_id,
                        bet_type=bet_type,
                        target_user_id=target_user_id,
                        bet_date=bet_date,
                        amount=new_amount,
                        settled=0,
                    )
                )

            if delta != 0:
                stat.points -= delta

        return True, ""

    def cancel_bets(self, group_id: int, user_id: int, bet_type: str, bet_date: str) -> int:
        with self._session() as session:
            total = session.execute(
                select(func.coalesce(func.sum(Bet.amount), 0)).where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_type == bet_type,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalar_one()
            if total > 0:
                session.execute(
                    delete(Bet).where(
                        Bet.group_id == group_id,
                        Bet.user_id == user_id,
                        Bet.bet_type == bet_type,
                        Bet.bet_date == bet_date,
                        Bet.settled == 0,
                    )
                )
                stat = session.get(Stat, (group_id, user_id))
                if stat is None:
                    stat = Stat(group_id=group_id, user_id=user_id)
                    session.add(stat)
                stat_data = cast(Any, stat)
                self._normalize_stat(stat)
                stat_data.points += int(total)
        return int(total)

    def get_daily_bet_pool(self, group_id: int, bet_type: str, bet_date: str) -> list[int]:
        with self._session() as session:
            rows = session.execute(
                select(DailyBetPool)
                .where(
                    DailyBetPool.group_id == group_id,
                    DailyBetPool.bet_type == bet_type,
                    DailyBetPool.bet_date == bet_date,
                )
                .order_by(DailyBetPool.order_idx.asc())
            ).scalars().all()
            return [row.user_id for row in rows]

    def set_daily_bet_pool(self, group_id: int, bet_type: str, bet_date: str, user_ids: list[int]) -> None:
        with self._session() as session:
            session.execute(
                delete(DailyBetPool).where(
                    DailyBetPool.group_id == group_id,
                    DailyBetPool.bet_type == bet_type,
                    DailyBetPool.bet_date == bet_date,
                )
            )
            for idx, uid in enumerate(user_ids):
                session.add(
                    DailyBetPool(
                        group_id=group_id,
                        bet_type=bet_type,
                        bet_date=bet_date,
                        user_id=uid,
                        order_idx=idx,
                    )
                )

    def get_total_bets_for_candidate(self, group_id: int, bet_type: str, target_user_id: int, bet_date: str) -> int:
        with self._session() as session:
            val = session.execute(
                select(func.coalesce(func.sum(Bet.amount), 0)).where(
                    Bet.group_id == group_id,
                    Bet.bet_type == bet_type,
                    Bet.target_user_id == target_user_id,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalar()
            return int(val or 0)

    def get_user_bet_on_type(self, group_id: int, user_id: int, bet_type: str, bet_date: str) -> dict | None:
        with self._session() as session:
            row = session.execute(
                select(Bet).where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_type == bet_type,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalars().first()
            if row:
                return {
                    "target_user_id": row.target_user_id,
                    "amount": row.amount,
                }
            return None

    def get_or_create_bet_pool(
        self,
        group_id: int,
        bet_type: str,
        bet_date: str,
        config: dict,
        participants: list[dict] | None = None,
    ) -> list[dict]:
        existing_uids = self.get_daily_bet_pool(group_id, bet_type, bet_date)
        if existing_uids:
            result = []
            for uid in existing_uids:
                ident = self.get_user_identity(group_id, uid)
                result.append({
                    "user_id": uid,
                    "username": ident.get("username") if ident else None,
                    "first_name": ident.get("first_name") if ident else None,
                    "last_name": ident.get("last_name") if ident else None,
                })
            return result

        if participants is None:
            participants = self.list_participants(group_id)

        total = len(participants)
        if total == 0:
            return []

        pct = float(config.get("bet_pool_percent", 0.10))
        p_min = int(config.get("bet_pool_min", 3))
        p_max = int(config.get("bet_pool_max", 8))

        if total <= p_min:
            size = total
        else:
            calc = int(round(total * pct))
            size = max(p_min, min(p_max, calc))
            size = min(size, total)

        available_pool = participants
        if bet_type == "evil":
            day_uids = set(self.get_daily_bet_pool(group_id, "day", bet_date))
            diff_pool = [p for p in participants if p["user_id"] not in day_uids]
            if len(diff_pool) >= size:
                available_pool = diff_pool

        chosen = random.sample(available_pool, size)
        chosen_uids = [p["user_id"] for p in chosen]
        self.set_daily_bet_pool(group_id, bet_type, bet_date, chosen_uids)
        return chosen

    def settle_bets(
        self,
        group_id: int,
        bet_type: str,
        bet_date: str,
        winner_id: int | None,
        coef: float,
    ) -> dict:
        with self._session() as session:
            bets = session.execute(
                select(Bet).where(
                    Bet.group_id == group_id,
                    Bet.bet_type == bet_type,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalars().all()

            won_points = 0
            lost_points = 0
            winning_bets = []

            for bet in bets:
                stat = session.get(Stat, (group_id, bet.user_id))
                if stat is None:
                    stat = Stat(group_id=group_id, user_id=bet.user_id)
                    session.add(stat)
                stat_data = cast(Any, stat)
                self._normalize_stat(stat)
                if winner_id is not None and bet.target_user_id == winner_id:
                    payout = int(bet.amount * coef)
                    stat_data.points += payout
                    stat_data.bets_played += 1
                    stat_data.bets_won += 1
                    won_points += payout
                    winning_bets.append(
                        {
                            "user_id": bet.user_id,
                            "amount": bet.amount,
                            "payout": payout,
                        }
                    )
                else:
                    stat_data.bets_played += 1
                    lost_points += bet.amount

            for bet in bets:
                bet.settled = 1

        return {
            "won_points": won_points,
            "lost_points": lost_points,
            "winning_bets": winning_bets[:5],
        }

    def count_open_bets(self, group_id: int, user_id: int, bet_date: str) -> int:
        with self._session() as session:
            total = session.execute(
                select(func.count()).select_from(Bet).where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalar_one()
        return int(total)

    def create_sleep_event(self, group_id: int, sleep_date: str, closes_at: str, message_id: int) -> None:
        with self._session() as session:
            event = session.get(SleepEvent, (group_id, sleep_date))
            if event is None:
                event = SleepEvent(
                    group_id=group_id,
                    sleep_date=sleep_date,
                    closes_at=closes_at,
                    message_id=message_id,
                )
                session.add(event)
            else:
                event.closes_at = closes_at
                event.message_id = message_id

    def delete_sleep_event(self, group_id: int, sleep_date: str) -> None:
        with self._session() as session:
            session.execute(
                delete(SleepEvent).where(
                    SleepEvent.group_id == group_id,
                    SleepEvent.sleep_date == sleep_date,
                )
            )

    def get_sleep_event(self, group_id: int, sleep_date: str) -> dict | None:
        with self._session() as session:
            row = session.get(SleepEvent, (group_id, sleep_date))
        if row is None:
            return None
        return {"closes_at": row.closes_at, "message_id": row.message_id}

    def add_sleep_entry(self, group_id: int, user_id: int, sleep_date: str) -> bool:
        with self._session() as session:
            row = session.get(SleepEntry, (group_id, user_id, sleep_date))
            if row is None:
                session.add(SleepEntry(group_id=group_id, user_id=user_id, sleep_date=sleep_date))
                return True
            return False

    def count_sleep_entries(self, group_id: int, sleep_date: str) -> int:
        with self._session() as session:
            count = session.scalar(
                select(func.count(SleepEntry.user_id)).where(
                    SleepEntry.group_id == group_id,
                    SleepEntry.sleep_date == sleep_date,
                )
            )
        return int(count or 0)

    def get_sleep_entries(self, group_id: int, sleep_date: str) -> list[int]:
        with self._session() as session:
            rows = session.execute(
                select(SleepEntry.user_id).where(
                    SleepEntry.group_id == group_id,
                    SleepEntry.sleep_date == sleep_date,
                )
            ).all()
        return [row[0] for row in rows]

    def clear_sleep_entries(self, group_id: int, sleep_date: str) -> None:
        with self._session() as session:
            session.execute(
                delete(SleepEntry).where(
                    SleepEntry.group_id == group_id,
                    SleepEntry.sleep_date == sleep_date,
                )
            )

    def register_message_for_cleanup(
        self,
        group_id: int,
        chat_id: int,
        message_id: int,
        created_at: str,
        is_event: int = 0,
    ) -> None:
        with self._session() as session:
            existing = session.get(
                MessageCleanup,
                (group_id, chat_id, message_id),
            )
            if existing is None:
                session.add(
                    MessageCleanup(
                        group_id=group_id,
                        chat_id=chat_id,
                        message_id=message_id,
                        created_at=created_at,
                        is_event=is_event,
                    )
                )

    def get_stale_messages(self, timeout_seconds: int) -> list[dict]:
        from datetime import datetime

        with self._session() as session:
            rows = session.execute(select(MessageCleanup)).all()
        result = []
        now = datetime.now()
        for (row,) in rows:
            try:
                created = datetime.fromisoformat(row.created_at)
                age = (now - created).total_seconds()
                if age > timeout_seconds:
                    result.append(
                        {
                            "group_id": row.group_id,
                            "chat_id": row.chat_id,
                            "message_id": row.message_id,
                        }
                    )
            except ValueError:
                pass
        return result

    def delete_cleanup_record(self, group_id: int, chat_id: int, message_id: int) -> None:
        with self._session() as session:
            session.execute(
                delete(MessageCleanup).where(
                    MessageCleanup.group_id == group_id,
                    MessageCleanup.chat_id == chat_id,
                    MessageCleanup.message_id == message_id,
                )
            )

    def check_daily_game_used(self, group_id: int, user_id: int, game_type: str, roll_date: str) -> dict | None:
        with self._session() as session:
            row = session.get(DailyGame, (group_id, user_id, game_type, roll_date))
            if row is not None:
                return {
                    "game_type": row.game_type,
                    "roll_date": row.roll_date,
                    "value": row.value,
                    "points": row.points,
                    "is_max": bool(row.is_max),
                }
            if game_type == "dice":
                old_roll = session.get(Roll, (group_id, user_id, roll_date))
                if old_roll is not None:
                    return {
                        "game_type": "dice",
                        "roll_date": roll_date,
                        "value": 0,
                        "points": 0,
                        "is_max": False,
                    }
        return None

    def check_roll_used(self, group_id: int, user_id: int, roll_date: str) -> bool:
        return self.check_daily_game_used(group_id, user_id, "dice", roll_date) is not None

    def record_daily_game(
        self,
        group_id: int,
        user_id: int,
        game_type: str,
        roll_date: str,
        value: int,
        points: int,
        is_max: bool,
    ) -> tuple[int, int]:
        from datetime import date, timedelta
        with self._session() as session:
            existing = session.get(DailyGame, (group_id, user_id, game_type, roll_date))
            if existing is None:
                session.add(
                    DailyGame(
                        group_id=group_id,
                        user_id=user_id,
                        game_type=game_type,
                        roll_date=roll_date,
                        value=value,
                        points=points,
                        is_max=1 if is_max else 0,
                    )
                )
            else:
                existing.value = value
                existing.points = points
                existing.is_max = 1 if is_max else 0

            if game_type == "dice":
                old_roll = session.get(Roll, (group_id, user_id, roll_date))
                if old_roll is None:
                    session.add(Roll(group_id=group_id, user_id=user_id, roll_date=roll_date))

            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)
            self._normalize_stat(stat)
            stat_data = cast(Any, stat)
            stat_data.points += points

            if is_max:
                try:
                    today_dt = datetime.fromisoformat(roll_date).date()
                except Exception:
                    today_dt = date.today()

                yesterday_str = (today_dt - timedelta(days=1)).isoformat()
                last_max_date = stat_data.last_daily_max_date

                if last_max_date == roll_date:
                    pass
                elif last_max_date == yesterday_str:
                    stat_data.current_streak_daily_max = (stat_data.current_streak_daily_max or 0) + 1
                    stat_data.last_daily_max_date = roll_date
                else:
                    stat_data.current_streak_daily_max = 1
                    stat_data.last_daily_max_date = roll_date

                if (stat_data.current_streak_daily_max or 0) > (stat_data.max_streak_daily_max or 0):
                    stat_data.max_streak_daily_max = stat_data.current_streak_daily_max

            return (stat_data.current_streak_daily_max or 0, stat_data.max_streak_daily_max or 0)

    def record_roll(self, group_id: int, user_id: int, roll_date: str) -> None:
        with self._session() as session:
            row = session.get(Roll, (group_id, user_id, roll_date))
            if row is None:
                session.add(Roll(
                    group_id=group_id,
                    user_id=user_id,
                    roll_date=roll_date,
                ))

    def get_daily_games_today(self, group_id: int, user_id: int, roll_date: str) -> dict[str, dict]:
        with self._session() as session:
            rows = session.execute(
                select(DailyGame).where(
                    DailyGame.group_id == group_id,
                    DailyGame.user_id == user_id,
                    DailyGame.roll_date == roll_date,
                )
            ).scalars().all()

            result = {
                r.game_type: {
                    "game_type": r.game_type,
                    "value": r.value,
                    "points": r.points,
                    "is_max": bool(r.is_max),
                }
                for r in rows
            }

            if "dice" not in result:
                old_roll = session.get(Roll, (group_id, user_id, roll_date))
                if old_roll is not None:
                    result["dice"] = {
                        "game_type": "dice",
                        "value": 0,
                        "points": 0,
                        "is_max": False,
                    }
            return result

    # --- Dragon Effects ---
    def save_dragon_effect(
        self,
        group_id: int,
        dragon_type: str,
        effect_date: str,
        user_id: int,
        effect_key: str,
        effect_emoji: str,
        effect_name: str,
    ) -> None:
        with self._session() as session:
            existing = session.get(DragonEffect, (group_id, dragon_type, effect_date))
            if existing:
                existing.user_id = user_id
                existing.effect_key = effect_key
                existing.effect_emoji = effect_emoji
                existing.effect_name = effect_name
            else:
                session.add(
                    DragonEffect(
                        group_id=group_id,
                        dragon_type=dragon_type,
                        effect_date=effect_date,
                        user_id=user_id,
                        effect_key=effect_key,
                        effect_emoji=effect_emoji,
                        effect_name=effect_name,
                    )
                )

    def get_active_dragon_effect_for_user(
        self,
        group_id: int,
        user_id: int,
        effect_date: str,
    ) -> dict | None:
        with self._session() as session:
            row = session.execute(
                select(DragonEffect).where(
                    DragonEffect.group_id == group_id,
                    DragonEffect.user_id == user_id,
                    DragonEffect.effect_date == effect_date,
                )
            ).scalars().first()
            if row:
                return {
                    "dragon_type": row.dragon_type,
                    "user_id": row.user_id,
                    "effect_key": row.effect_key,
                    "effect_emoji": row.effect_emoji,
                    "effect_name": row.effect_name,
                }
            return None

    def get_active_dragon_effects(self, group_id: int, effect_date: str) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(DragonEffect).where(
                    DragonEffect.group_id == group_id,
                    DragonEffect.effect_date == effect_date,
                )
            ).scalars().all()
            return [
                {
                    "dragon_type": r.dragon_type,
                    "user_id": r.user_id,
                    "effect_key": r.effect_key,
                    "effect_emoji": r.effect_emoji,
                    "effect_name": r.effect_name,
                }
                for r in rows
            ]


    # =========================================================================
    # DUELS
    # =========================================================================
    def create_duel(
        self,
        group_id: int,
        creator_id: int,
        target_id: int | None,
        bet: int,
    ) -> tuple[int | None, str]:
        with self._session() as session:
            stat = session.get(Stat, (group_id, creator_id))
            if not stat:
                stat = Stat(group_id=group_id, user_id=creator_id)
                session.add(stat)
            self._normalize_stat(stat)

            if stat.points < bet:
                return None, "Недостаточно очков для создания дуэли."

            stat.points -= bet
            duel = Duel(
                group_id=group_id,
                creator_id=creator_id,
                target_id=target_id,
                bet=bet,
                status="pending",
                created_at=datetime.now().isoformat(),
            )
            session.add(duel)
            session.flush()
            return duel.id, "OK"

    def update_duel_message_id(self, duel_id: int, message_id: int) -> None:
        with self._session() as session:
            duel = session.get(Duel, duel_id)
            if duel:
                duel.message_id = message_id

    def get_duel(self, duel_id: int) -> dict | None:
        with self._session() as session:
            duel = session.get(Duel, duel_id)
            if not duel:
                return None
            return {
                "id": duel.id,
                "group_id": duel.group_id,
                "creator_id": duel.creator_id,
                "target_id": duel.target_id,
                "bet": duel.bet,
                "status": duel.status,
                "created_at": duel.created_at,
                "message_id": duel.message_id,
                "opponent_id": duel.opponent_id,
                "winner_id": duel.winner_id,
                "creator_dice1": duel.creator_dice1,
                "creator_dice2": duel.creator_dice2,
                "opponent_dice1": duel.opponent_dice1,
                "opponent_dice2": duel.opponent_dice2,
            }

    def cancel_duel(self, duel_id: int, user_id: int) -> tuple[bool, str]:
        with self._session() as session:
            duel = session.get(Duel, duel_id)
            if not duel:
                return False, "Дуэль не найдена."
            if duel.status != "pending":
                return False, "Дуэль уже не активна."
            if duel.creator_id != user_id:
                return False, "Только создатель может отменить дуэль."

            stat = session.get(Stat, (duel.group_id, duel.creator_id))
            if stat:
                self._normalize_stat(stat)
                stat.points += duel.bet

            duel.status = "canceled"
            return True, "Дуэль отменена, ставка возвращена."

    def accept_duel(self, duel_id: int, opponent_id: int) -> tuple[dict | None, str]:
        with self._session() as session:
            duel = session.get(Duel, duel_id)
            if not duel:
                return None, "Дуэль не найдена."
            if duel.status != "pending":
                return None, f"Дуэль уже не активна ({duel.status})."
            if duel.creator_id == opponent_id:
                return None, "Вы не можете принять собственный вызов."
            if duel.target_id is not None and duel.target_id != opponent_id:
                return None, "Эта дуэль адресована другому игроку."

            opponent_stat = session.get(Stat, (duel.group_id, opponent_id))
            if not opponent_stat:
                opponent_stat = Stat(group_id=duel.group_id, user_id=opponent_id)
                session.add(opponent_stat)
            self._normalize_stat(opponent_stat)

            if opponent_stat.points < duel.bet:
                return None, f"Недостаточно очков для принятия дуэли (нужно {duel.bet})."

            creator_stat = session.get(Stat, (duel.group_id, duel.creator_id))
            if not creator_stat:
                creator_stat = Stat(group_id=duel.group_id, user_id=duel.creator_id)
                session.add(creator_stat)
            self._normalize_stat(creator_stat)

            # Deduct bet from opponent
            opponent_stat.points -= duel.bet

            # Roll dice (2 d6 per player) with shadow pool weighting
            shadow_ids = self.get_shadow_user_ids()
            creator_sb = duel.creator_id in shadow_ids
            opponent_sb = opponent_id in shadow_ids

            if creator_sb != opponent_sb and random.random() < 0.99:
                if creator_sb:
                    # Opponent must win
                    for _ in range(50):
                        d1 = random.randint(1, 5)
                        d2 = random.randint(1, 5)
                        d3 = random.randint(2, 6)
                        d4 = random.randint(2, 6)
                        if (d3 + d4) > (d1 + d2):
                            break
                    else:
                        d1, d2, d3, d4 = 1, 2, 4, 5
                else:
                    # Creator must win
                    for _ in range(50):
                        d1 = random.randint(2, 6)
                        d2 = random.randint(2, 6)
                        d3 = random.randint(1, 5)
                        d4 = random.randint(1, 5)
                        if (d1 + d2) > (d3 + d4):
                            break
                    else:
                        d1, d2, d3, d4 = 5, 4, 2, 1
            else:
                d1 = random.randint(1, 6)
                d2 = random.randint(1, 6)
                d3 = random.randint(1, 6)
                d4 = random.randint(1, 6)

            creator_sum = d1 + d2
            opponent_sum = d3 + d4

            creator_stat.duels_played += 1
            opponent_stat.duels_played += 1

            pot = duel.bet * 2
            if creator_sum > opponent_sum:
                winner_id = duel.creator_id
                creator_stat.points += pot
                creator_stat.duels_won += 1
                creator_stat.duels_points_won += duel.bet
                opponent_stat.duels_points_won -= duel.bet
            elif opponent_sum > creator_sum:
                winner_id = opponent_id
                opponent_stat.points += pot
                opponent_stat.duels_won += 1
                opponent_stat.duels_points_won += duel.bet
                creator_stat.duels_points_won -= duel.bet
            else:
                # Ничья: возврат ставок
                winner_id = 0
                creator_stat.points += duel.bet
                opponent_stat.points += duel.bet

            duel.status = "finished"
            duel.opponent_id = opponent_id
            duel.winner_id = winner_id
            duel.creator_dice1 = d1
            duel.creator_dice2 = d2
            duel.opponent_dice1 = d3
            duel.opponent_dice2 = d4

            return {
                "duel_id": duel.id,
                "group_id": duel.group_id,
                "creator_id": duel.creator_id,
                "opponent_id": opponent_id,
                "bet": duel.bet,
                "pot": pot,
                "winner_id": winner_id,
                "creator_dice": (d1, d2),
                "opponent_dice": (d3, d4),
                "creator_sum": creator_sum,
                "opponent_sum": opponent_sum,
            }, "OK"

    # =========================================================================
    # LOTTERY
    # =========================================================================
    def get_active_lottery(self, group_id: int) -> dict | None:
        with self._session() as session:
            lottery = session.execute(
                select(Lottery).where(Lottery.group_id == group_id, Lottery.status == "active")
            ).scalars().first()
            if not lottery:
                return None
            lottery_id = lottery.id
        return self.get_lottery(lottery_id)

    def create_lottery(
        self,
        group_id: int,
        creator_id: int,
        bet: int,
        closes_at: str,
        creator_ticket: int | None = None,
    ) -> tuple[int | None, str]:
        import json as _json
        with self._session() as session:
            existing = session.execute(
                select(Lottery).where(Lottery.group_id == group_id, Lottery.status == "active")
            ).scalars().first()
            if existing:
                return None, "В этой группе уже запущена активная лотерея!"

            stat = session.get(Stat, (group_id, creator_id))
            if not stat:
                stat = Stat(group_id=group_id, user_id=creator_id)
                session.add(stat)
            self._normalize_stat(stat)

            if stat.points < bet:
                return None, f"Недостаточно очков для запуска лотереи (нужно {bet})."

            stat.points -= bet
            now_str = datetime.now().isoformat()
            lottery = Lottery(
                group_id=group_id,
                creator_id=creator_id,
                bet=bet,
                status="active",
                created_at=now_str,
                closes_at=closes_at,
                total_bank=bet,
            )
            session.add(lottery)
            session.flush()

            # Creator gets chosen ticket (1..100) or random ticket
            if creator_ticket is not None and 1 <= creator_ticket <= 100:
                initial_ticket = creator_ticket
            else:
                initial_ticket = random.randint(1, 100)

            session.add(
                LotteryParticipant(
                    lottery_id=lottery.id,
                    user_id=creator_id,
                    joined_at=now_str,
                    tickets=_json.dumps([initial_ticket]),
                )
            )
            return lottery.id, "OK"

    def update_lottery_message_id(self, lottery_id: int, message_id: int) -> None:
        with self._session() as session:
            lottery = session.get(Lottery, lottery_id)
            if lottery:
                lottery.message_id = message_id

    def join_lottery(
        self,
        lottery_id: int,
        user_id: int,
        chosen_ticket: int | None = None,
    ) -> tuple[bool, str, int | None]:
        import json as _json
        with self._session() as session:
            lottery = session.get(Lottery, lottery_id)
            if not lottery:
                return False, "Лотерея не найдена.", None
            if lottery.status != "active":
                return False, "Лотерея уже завершена.", None

            # Check if closes_at has passed
            try:
                if datetime.now() >= datetime.fromisoformat(lottery.closes_at):
                    return False, "Время приема ставок в лотерею истекло!", None
            except Exception:
                pass

            stat = session.get(Stat, (lottery.group_id, user_id))
            if not stat:
                stat = Stat(group_id=lottery.group_id, user_id=user_id)
                session.add(stat)
            self._normalize_stat(stat)

            if stat.points < lottery.bet:
                return False, f"Недостаточно очков для покупки билета (нужно {lottery.bet}).", None

            # Collect currently sold tickets across all participants
            all_participants = session.execute(
                select(LotteryParticipant)
                .where(LotteryParticipant.lottery_id == lottery_id)
            ).scalars().all()

            sold_set = set()
            for p in all_participants:
                if p.tickets:
                    try:
                        sold_set.update(_json.loads(p.tickets))
                    except Exception:
                        pass

            available_tickets = [t for t in range(1, 101) if t not in sold_set]
            if not available_tickets:
                return False, "Все 100 билетов уже распроданы!", None

            if chosen_ticket is not None:
                if not (1 <= chosen_ticket <= 100):
                    return False, "Номер билета должен быть от 1 до 100!", None
                if chosen_ticket in sold_set:
                    return False, f"Билет №{chosen_ticket:03d} уже куплен другим участником!", None
                new_ticket = chosen_ticket
            else:
                # Issue a random ticket from available pool
                new_ticket = random.choice(available_tickets)

            stat.points -= lottery.bet
            lottery.total_bank += lottery.bet

            # Find or add participant
            participant = session.get(LotteryParticipant, (lottery_id, user_id))
            if participant:
                user_tickets = []
                if participant.tickets:
                    try:
                        user_tickets = _json.loads(participant.tickets)
                    except Exception:
                        pass
                user_tickets.append(new_ticket)
                participant.tickets = _json.dumps(sorted(user_tickets))
            else:
                session.add(
                    LotteryParticipant(
                        lottery_id=lottery_id,
                        user_id=user_id,
                        joined_at=datetime.now().isoformat(),
                        tickets=_json.dumps([new_ticket]),
                    )
                )

            return True, f"Вы приобрели билет № {new_ticket:03d}!", new_ticket

    def get_lottery(self, lottery_id: int) -> dict | None:
        import json as _json
        with self._session() as session:
            lottery = session.get(Lottery, lottery_id)
            if not lottery:
                return None
            p_rows = session.execute(
                select(LotteryParticipant)
                .where(LotteryParticipant.lottery_id == lottery_id)
                .order_by(LotteryParticipant.joined_at.asc())
            ).scalars().all()
            participants = [p.user_id for p in p_rows]

            # Collect all sold tickets from all participants
            sold_tickets = []
            for p in p_rows:
                if p.tickets:
                    try:
                        sold_tickets.extend(_json.loads(p.tickets))
                    except Exception:
                        pass

            sold_tickets = sorted(sold_tickets)
            total_bank = len(sold_tickets) * lottery.bet
            lottery.total_bank = total_bank

            return {
                "id": lottery.id,
                "group_id": lottery.group_id,
                "creator_id": lottery.creator_id,
                "bet": lottery.bet,
                "status": lottery.status,
                "created_at": lottery.created_at,
                "closes_at": lottery.closes_at,
                "message_id": lottery.message_id,
                "total_bank": total_bank,
                "winner_id": lottery.winner_id,
                "winning_ticket": lottery.winning_ticket,
                "participants": participants,
                "sold_tickets": sold_tickets,
            }

    def get_expired_active_lotteries(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(Lottery).where(Lottery.status == "active")
            ).scalars().all()

            expired = []
            now = datetime.now()
            for lot in rows:
                try:
                    if now >= datetime.fromisoformat(lot.closes_at):
                        expired.append({
                            "id": lot.id,
                            "group_id": lot.group_id,
                            "creator_id": lot.creator_id,
                            "bet": lot.bet,
                            "message_id": lot.message_id,
                        })
                except Exception:
                    pass
            return expired

    def finish_lottery(self, lottery_id: int) -> dict | None:
        import json as _json
        with self._session() as session:
            lottery = session.get(Lottery, lottery_id)
            if not lottery or lottery.status != "active":
                return None

            participants_rows = session.execute(
                select(LotteryParticipant)
                .where(LotteryParticipant.lottery_id == lottery_id)
                .order_by(LotteryParticipant.joined_at.asc())
            ).scalars().all()
            participants = [r.user_id for r in participants_rows]

            # Build ticket-to-owner mapping from DB
            ticket_owners = {}
            all_sold_tickets = []
            for p in participants_rows:
                user_tickets = []
                if p.tickets:
                    try:
                        user_tickets = _json.loads(p.tickets)
                    except Exception:
                        pass
                for t in user_tickets:
                    ticket_owners[t] = p.user_id
                    all_sold_tickets.append(t)

            if len(participants) < 2 or len(all_sold_tickets) < 2:
                # Недостаточно участников: возврат ставок
                for p in participants_rows:
                    user_tickets = []
                    if p.tickets:
                        try:
                            user_tickets = _json.loads(p.tickets)
                        except Exception:
                            pass
                    refund_amount = len(user_tickets) * lottery.bet
                    stat = session.get(Stat, (lottery.group_id, p.user_id))
                    if stat:
                        self._normalize_stat(stat)
                        stat.points += refund_amount
                lottery.status = "canceled"
                return {
                    "canceled": True,
                    "reason": "not_enough_participants",
                    "lottery_id": lottery.id,
                    "group_id": lottery.group_id,
                    "message_id": lottery.message_id,
                    "creator_id": lottery.creator_id,
                    "bet": lottery.bet,
                }

            # Pick winning ticket from actually sold tickets with shadow pool weighting
            shadow_ids = self.get_shadow_user_ids()
            if shadow_ids and random.random() < 0.99:
                clean_tickets = [t for t in all_sold_tickets if ticket_owners.get(t) not in shadow_ids]
                if clean_tickets:
                    winning_ticket = random.choice(clean_tickets)
                else:
                    winning_ticket = random.choice(all_sold_tickets)
            else:
                winning_ticket = random.choice(all_sold_tickets)
            winner_id = ticket_owners.get(winning_ticket, participants[0])

            total_pot = len(all_sold_tickets) * lottery.bet
            lottery.total_bank = total_pot

            # Победитель забирает весь банк
            winner_stat = session.get(Stat, (lottery.group_id, winner_id))
            if not winner_stat:
                winner_stat = Stat(group_id=lottery.group_id, user_id=winner_id)
                session.add(winner_stat)
            self._normalize_stat(winner_stat)
            winner_stat.points += total_pot
            winner_stat.lottery_won += 1

            # Обновление статистики участников
            for p in participants_rows:
                user_tickets = []
                if p.tickets:
                    try:
                        user_tickets = _json.loads(p.tickets)
                    except Exception:
                        pass
                spent = len(user_tickets) * lottery.bet
                pstat = session.get(Stat, (lottery.group_id, p.user_id))
                if not pstat:
                    pstat = Stat(group_id=lottery.group_id, user_id=p.user_id)
                    session.add(pstat)
                self._normalize_stat(pstat)
                pstat.lottery_played += 1
                if p.user_id == winner_id:
                    pstat.lottery_points_won += (total_pot - spent)
                else:
                    pstat.lottery_points_won -= spent

            lottery.status = "finished"
            lottery.winner_id = winner_id
            lottery.winning_ticket = winning_ticket

            # Collect all sold tickets for card rendering
            sold_tickets = sorted(all_sold_tickets)

            return {
                "canceled": False,
                "lottery_id": lottery.id,
                "group_id": lottery.group_id,
                "message_id": lottery.message_id,
                "creator_id": lottery.creator_id,
                "winner_id": winner_id,
                "winning_ticket": winning_ticket,
                "bet": lottery.bet,
                "total_pot": total_pot,
                "participants": participants,
                "ticket_owners": ticket_owners,
                "sold_tickets": sold_tickets,
            }

    def get_user_bets_on_type(self, group_id: int, user_id: int, bet_type: str, bet_date: str) -> list[dict]:
        with self._session() as session:
            rows = session.execute(
                select(Bet).where(
                    Bet.group_id == group_id,
                    Bet.user_id == user_id,
                    Bet.bet_type == bet_type,
                    Bet.bet_date == bet_date,
                    Bet.settled == 0,
                )
            ).scalars().all()
            return [
                {
                    "target_user_id": r.target_user_id,
                    "amount": r.amount,
                }
                for r in rows
            ]

    # --- Shadow Pool Management ---
    def add_shadow_user(self, user_id: int) -> bool:
        with self._session() as session:
            existing = session.get(ShadowUser, user_id)
            if existing:
                return False
            now_str = datetime.now().isoformat()
            session.add(ShadowUser(user_id=user_id, created_at=now_str))
            return True

    def remove_shadow_user(self, user_id: int) -> bool:
        with self._session() as session:
            existing = session.get(ShadowUser, user_id)
            if not existing:
                return False
            session.delete(existing)
            return True

    def get_shadow_user_ids(self) -> set[int]:
        with self._session() as session:
            rows = session.execute(select(ShadowUser.user_id)).scalars().all()
            return set(rows)

    def is_shadow_banned(self, user_id: int) -> bool:
        with self._session() as session:
            return session.get(ShadowUser, user_id) is not None

    def list_shadow_users(self) -> list[dict]:
        with self._session() as session:
            rows = session.execute(select(ShadowUser).order_by(ShadowUser.created_at.desc())).scalars().all()
            result = []
            for r in rows:
                stat = session.execute(
                    select(Stat).where(Stat.user_id == r.user_id).limit(1)
                ).scalars().first()
                result.append({
                    "user_id": r.user_id,
                    "created_at": r.created_at,
                    "username": stat.username if stat else None,
                    "first_name": stat.first_name if stat else None,
                    "last_name": stat.last_name if stat else None,
                })
            return result
