# auth.py

from typing import Optional, Set

AUTHORIZED_USER_IDS: Set[int] = {
    7237785856,   # ← আপনার টেলিগ্রাম আইডি (সুপার অ্যাডমিন) দিন
}

def is_authorized(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return user_id in AUTHORIZED_USER_IDS

def add_authorized_user(user_id: int) -> None:
    AUTHORIZED_USER_IDS.add(user_id)

def remove_authorized_user(user_id: int) -> None:
    AUTHORIZED_USER_IDS.discard(user_id)