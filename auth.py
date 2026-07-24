# auth.py

AUTHORIZED_USER_IDS = {
    7237785856,   # ← আপনার টেলিগ্রাম আইডি দিন (সুপার অ্যাডমিন)
}

def is_authorized(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in AUTHORIZED_USER_IDS

def add_authorized_user(user_id: int) -> None:
    AUTHORIZED_USER_IDS.add(user_id)

def remove_authorized_user(user_id: int) -> None:
    AUTHORIZED_USER_IDS.discard(user_id)