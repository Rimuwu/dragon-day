import time
from typing import Optional


class CardCacheItem:
    __slots__ = ("card_bytes", "file_id", "expires_at")

    def __init__(self, card_bytes: bytes, file_id: Optional[str], expires_at: float):
        self.card_bytes = card_bytes
        self.file_id = file_id
        self.expires_at = expires_at


CACHE_TTL_SECONDS = 15 * 60  # 15 minutes

_CARD_CACHE: dict[tuple[int, int, str], CardCacheItem] = {}
_AVATAR_CACHE: dict[int, tuple[Optional[bytes], float]] = {}


def _cleanup_expired() -> None:
    now = time.time()
    expired_keys = [k for k, v in _CARD_CACHE.items() if now >= v.expires_at]
    for k in expired_keys:
        _CARD_CACHE.pop(k, None)

    expired_avatars = [k for k, v in _AVATAR_CACHE.items() if now >= v[1]]
    for k in expired_avatars:
        _AVATAR_CACHE.pop(k, None)


def get_cached_card(chat_id: int, user_id: int, page: str) -> Optional[tuple[bytes, Optional[str]]]:
    key = (chat_id, user_id, page)
    item = _CARD_CACHE.get(key)
    if not item:
        return None
    if time.time() >= item.expires_at:
        _CARD_CACHE.pop(key, None)
        return None
    return item.card_bytes, item.file_id


def set_cached_card(chat_id: int, user_id: int, page: str, card_bytes: bytes, file_id: Optional[str] = None) -> None:
    _cleanup_expired()
    key = (chat_id, user_id, page)
    expires_at = time.time() + CACHE_TTL_SECONDS
    _CARD_CACHE[key] = CardCacheItem(card_bytes, file_id, expires_at)


def update_cached_file_id(chat_id: int, user_id: int, page: str, file_id: str) -> None:
    key = (chat_id, user_id, page)
    item = _CARD_CACHE.get(key)
    if item and time.time() < item.expires_at:
        item.file_id = file_id


def get_cached_avatar(user_id: int) -> Optional[tuple[bool, Optional[bytes]]]:
    """
    Returns (True, bytes) if found in cache, or None if not cached / expired.
    Note: bytes can be None if user has no avatar.
    """
    item = _AVATAR_CACHE.get(user_id)
    if not item:
        return None
    data, expires_at = item
    if time.time() >= expires_at:
        _AVATAR_CACHE.pop(user_id, None)
        return None
    return True, data


AVATAR_CACHE_TTL_SECONDS = 24 * 3600  # 24 hours
GENERAL_CACHE_DEFAULT_TTL = 3600  # 1 hour


def set_cached_avatar(user_id: int, avatar_bytes: Optional[bytes], ttl: Optional[float] = None) -> None:
    duration = ttl if ttl is not None else AVATAR_CACHE_TTL_SECONDS
    expires_at = time.time() + duration
    _AVATAR_CACHE[user_id] = (avatar_bytes, expires_at)


def invalidate_user_cache(chat_id: int, user_id: int) -> None:
    keys = [k for k in _CARD_CACHE if k[0] == chat_id and k[1] == user_id]
    for k in keys:
        _CARD_CACHE.pop(k, None)


_GENERAL_CACHE: dict[str, CardCacheItem] = {}


def get_cached_general(key: str) -> Optional[tuple[bytes, Optional[str]]]:
    item = _GENERAL_CACHE.get(key)
    if not item:
        return None
    if time.time() >= item.expires_at:
        _GENERAL_CACHE.pop(key, None)
        return None
    return item.card_bytes, item.file_id


def set_cached_general(
    key: str,
    card_bytes: bytes,
    file_id: Optional[str] = None,
    ttl: Optional[float] = None,
) -> None:
    now = time.time()
    expired = [k for k, v in _GENERAL_CACHE.items() if now >= v.expires_at]
    for k in expired:
        _GENERAL_CACHE.pop(k, None)
    duration = ttl if ttl is not None else GENERAL_CACHE_DEFAULT_TTL
    _GENERAL_CACHE[key] = CardCacheItem(card_bytes, file_id, now + duration)


def update_cached_general_file_id(key: str, file_id: str) -> None:
    item = _GENERAL_CACHE.get(key)
    if item and time.time() < item.expires_at:
        item.file_id = file_id


def invalidate_general_cache(key: str) -> None:
    _GENERAL_CACHE.pop(key, None)


# Alias for backwards compatibility
_CACHE = _GENERAL_CACHE

