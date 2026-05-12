from typing import Optional

from pydantic import BaseModel


class UserIdentity(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class GroupSettingsSchema(BaseModel):
    group_id: int
    daily_time: str
    sleep_start: str
    sleep_end: str

    class Config:
        from_attributes = True


class StatsSchema(BaseModel):
    group_id: int
    user_id: int
    points: int
    wins_day: int
    wins_evil: int
    wins_sleepy: int
    bets_played: int
    bets_won: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True
