from contextlib import contextmanager

from sqlalchemy import delete, func, select, text

from models.db import Base, build_engine, build_session_factory
from models.model import (
    AllowedGroup,
    Bet,
    GroupSettings,
    GroupState,
    Participant,
    SleepEntry,
    SleepEvent,
    Stat,
)


class Database:
    def __init__(self, path: str) -> None:
        self.engine = build_engine(path)
        self.SessionLocal = build_session_factory(self.engine)

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
        self._ensure_group_state_columns()

    def _ensure_group_state_columns(self) -> None:
        with self.engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(group_state)")).fetchall()
            columns = {row[1] for row in rows}
            if "last_evil_date" not in columns:
                conn.execute(text("ALTER TABLE group_state ADD COLUMN last_evil_date TEXT"))

    def ensure_group(self, group_id: int, defaults: dict) -> None:
        with self._session() as session:
            settings = session.get(GroupSettings, group_id)
            if settings is None:
                settings = GroupSettings(
                    group_id=group_id,
                    daily_time=defaults["daily_time_default"],
                    sleep_start=defaults["sleep_start_default"],
                    sleep_end=defaults["sleep_end_default"],
                )
                session.add(settings)
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
                stat.username = username
                stat.first_name = first_name
                stat.last_name = last_name

    def sync_user(self, group_id: int, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is not None:
                stat.username = username
                stat.first_name = first_name
                stat.last_name = last_name
            participant = session.get(Participant, (group_id, user_id))
            if participant is not None:
                participant.username = username
                participant.first_name = first_name
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
            rows = (
                session.execute(
                    select(Participant)
                    .where(Participant.group_id == group_id)
                    .order_by(Participant.joined_at)
                )
                .scalars()
                .all()
            )
        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "first_name": row.first_name,
                "last_name": row.last_name,
            }
            for row in rows
        ]

    def get_user_stats(self, group_id: int, user_id: int) -> dict | None:
        with self._session() as session:
            row = session.get(Stat, (group_id, user_id))
        if row is None:
            return None
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
        }

    def get_user_identity(self, group_id: int, user_id: int) -> dict | None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat:
                return {
                    "user_id": stat.user_id,
                    "username": stat.username,
                    "first_name": stat.first_name,
                    "last_name": stat.last_name,
                }
            participant = session.get(Participant, (group_id, user_id))
            if participant:
                return {
                    "user_id": participant.user_id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                }
        return None

    def adjust_points(self, group_id: int, user_id: int, delta: int) -> None:
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)
            stat.points += delta

    def record_win(self, group_id: int, user_id: int, win_type: str, points_delta: int) -> None:
        column = {
            "day": "wins_day",
            "evil": "wins_evil",
            "sleepy": "wins_sleepy",
        }[win_type]
        with self._session() as session:
            stat = session.get(Stat, (group_id, user_id))
            if stat is None:
                stat = Stat(group_id=group_id, user_id=user_id)
                session.add(stat)
            setattr(stat, column, getattr(stat, column) + 1)
            stat.points += points_delta

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
                stat.points += int(total)
        return int(total)

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
                if winner_id is not None and bet.target_user_id == winner_id:
                    payout = int(bet.amount * coef)
                    stat.points += payout
                    stat.bets_played += 1
                    stat.bets_won += 1
                    won_points += payout
                    winning_bets.append(
                        {
                            "user_id": bet.user_id,
                            "amount": bet.amount,
                            "payout": payout,
                        }
                    )
                else:
                    stat.bets_played += 1
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

    def add_sleep_entry(self, group_id: int, user_id: int, sleep_date: str) -> None:
        with self._session() as session:
            row = session.get(SleepEntry, (group_id, user_id, sleep_date))
            if row is None:
                session.add(SleepEntry(group_id=group_id, user_id=user_id, sleep_date=sleep_date))

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
