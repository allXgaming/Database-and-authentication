# authentication.py

# অনুমোদিত ইউজারনেমের তালিকা
AUTHORIZED_USERNAMES = [
    "your_username_1",   # এখানে নিজের ইউজারনেম বসাও
    "your_username_2"
]

def is_authorized(username: str) -> bool:
    """কোনো ইউজার অনুমোদিত কিনা তা যাচাই করে"""
    if not username:
        return False
    return username in AUTHORIZED_USERNAMES