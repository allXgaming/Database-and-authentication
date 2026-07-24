# ==================== Complete Code (Python 3.6+ compatible) ====================
# auth.py + db.py (SQLite) + bot.py (using urllib) + Data View (Admin only)

import time
import threading
import math
import sqlite3
import json
import urllib.request
import urllib.error
import urllib.parse
from collections import deque, Counter
from typing import Optional, List, Dict, Any

# ---------- Configuration ----------
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?ts={}"
BOT_TOKEN = "7616902302:AAEp4VjUFX9mfBqYuc_ZY7pfuntVvQ8dpWE"   # Replace with your bot token
TELEGRAM_API = "https://api.telegram.org/bot{}/".format(BOT_TOKEN)

# ==================== auth.py ====================
AUTHORIZED_USER_IDS = {
    5824157133,  # Replace with your Telegram IDs
    7237785856,
    7747517074,
}

# Admin users who can view data
ADMIN_USER_IDS = {
    5824157133,   # Only this ID(s) can use SHOW DATA
}

def is_authorized(user_id):
    if user_id is None:
        return False
    return user_id in AUTHORIZED_USER_IDS

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS

# ==================== db.py (SQLite - built-in) ====================
def init_db():
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rounds
                 (period TEXT PRIMARY KEY, number INTEGER, size TEXT,
                  prediction TEXT, result TEXT, range_pred TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    try:
        c.execute("ALTER TABLE rounds ADD COLUMN range_pred TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE rounds ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def save_round(period, number, size, prediction, result, range_pred):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO rounds (period, number, size, prediction, result, range_pred, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
              (period, number, size, prediction, result, range_pred))
    conn.commit()
    conn.close()

def load_recent_history(limit=300):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    try:
        c.execute('''SELECT period, number, size, prediction, result, range_pred FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
    except sqlite3.OperationalError:
        c.execute('''SELECT period, number, size, prediction, result FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = [(r[0], r[1], r[2], r[3], r[4], None) for r in c.fetchall()]
    conn.close()
    return rows

def get_first_and_last():
    """Returns first 2 and last 2 records from the database."""
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    # First two (earliest)
    c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period ASC LIMIT 2")
    first_two = c.fetchall()
    # Last two (most recent)
    c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period DESC LIMIT 2")
    last_two_raw = c.fetchall()
    conn.close()
    # Reverse last_two so they appear in chronological order (older first)
    last_two = list(reversed(last_two_raw))
    return first_two, last_two

def get_total_count():
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM rounds")
    count = c.fetchone()[0]
    conn.close()
    return count

init_db()

# ==================== Utility Functions (HTTP calls) ====================
def http_get_json(url, timeout=10):
    """GET request and return JSON."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print("HTTP GET Error:", e)
        return None

def http_post_json(url, payload, timeout=10):
    """POST JSON payload."""
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print("HTTP POST Error:", e)
        return None

# ==================== UI Formatting ====================
def format_prediction_ui(pred_data, period):
    size = pred_data["size"]
    conf = pred_data["confidence"]
    num_range = pred_data["range"]
    ma_val = pred_data.get("ma", "BULLISH")
    rsi_val = pred_data.get("rsi", 63.8)
    std_val = pred_data.get("std", "LOW")
    pattern = pred_data.get("pattern", "ALTERNATING")
    cycle = pred_data.get("cycle", "STABLE")
    big_pct = pred_data.get("big_pct", 78)
    small_pct = pred_data.get("small_pct", 22)
    signal = "HIGH 🟢" if conf >= 85 else "MEDIUM 🟡"
    volatility = "LOW" if conf >= 85 else "MEDIUM"
    risk = "LOW" if conf >= 85 else "MEDIUM"

    size_emoji = "🐘" if size == "BIG" else "🐭"
    level = "🔥 LEVEL 1" if conf >= 92 else "⚡ LEVEL 2" if conf >= 85 else "⚠️ LEVEL 3"

    big_bar = "█" * int(big_pct / 10) + "░" * (10 - int(big_pct / 10))
    small_bar = "█" * int(small_pct / 10) + "░" * (10 - int(small_pct / 10))

    ui = """
━━━━━━━━━━━━━━━━━━━━━━
🧠 AI ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━
📈 MA           : {ma}
📊 RSI          : {rsi:.1f}
📉 STD DEV      : {std}
🔄 PATTERN      : {pattern}
🎯 CYCLE        : {cycle}

━━━━━━━━━━━━━━━━━━━━━━
🗳️ AI VOTING
━━━━━━━━━━━━━━━━━━━━━━
🐘 BIG          {big_bar} {big_pct}%
🐭 SMALL        {small_bar} {small_pct}%

🏆 FINAL EDGE   : {size_emoji} {size}

━━━━━━━━━━━━━━━━━━━━━━
📡 AI METRICS
━━━━━━━━━━━━━━━━━━━━━━
🎯 CONFIDENCE   : {conf}%
📶 SIGNAL       : {signal}
🎲 VOLATILITY   : {volatility}
⚖️ RISK         : {risk}

━━━━━━━━━━━━━━━━━━━━━━
🆔 PERIOD       : {period}
🎯 RANGE        : {num_range}
📊 LEVEL        : {level}
━━━━━━━━━━━━━━━━━━━━━━
⚡ AI STATUS : ACTIVE
🧠 ENGINE    : SUBHA AI
🔥 MODE      : LIVE
━━━━━━━━━━━━━━━━━━━━━━
""".format(ma=ma_val, rsi=rsi_val, std=std_val, pattern=pattern, cycle=cycle,
           big_bar=big_bar, big_pct=big_pct, small_bar=small_bar, small_pct=small_pct,
           size_emoji=size_emoji, size=size, conf=conf, signal=signal, volatility=volatility,
           risk=risk, period=period, num_range=num_range, level=level)
    return ui

def format_result_ui(period, number, actual_size, result, pred, range_pred):
    if result == "WIN":
        status_emoji, status_text, bg = "✅", "WIN 🎉", "🟢"
    else:
        status_emoji, status_text, bg = "❌", "LOSS 😞", "🔴"
    actual_emoji = "🐘" if actual_size == "BIG" else "🐭"
    ui = """
{status_emoji} {status_text}  {bg}
━━━━━━━━━━━━━━━━━━━━━━
📊 RESULT
━━━━━━━━━━━━━━━━━━━━━━
📅 PERIOD    : {period}
🎯 PREDICT   : {pred}
✅ ACTUAL    : {actual_emoji} {actual_size} [{number}]
📊 RANGE     : {range_pred}
━━━━━━━━━━━━━━━━━━━━━━
""".format(status_emoji=status_emoji, status_text=status_text, bg=bg,
           period=period, pred=pred, actual_emoji=actual_emoji,
           actual_size=actual_size, number=number, range_pred=range_pred)
    return ui

def format_first_last_ui(first_two, last_two):
    """Format first 2 and last 2 records + admin IDs."""
    text = "📋 *Database Records (First 2 & Last 2)*\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "🔹 *First 2 entries:*\n"
    for row in first_two:
        period, num, size, pred, result, range_pred = row
        text += f"📅 `{period}` | 🎯 {num} | 📊 {size} | 🧠 {pred} | 🏁 {result} | 🎚 {range_pred}\n"
    text += "\n🔸 *Last 2 entries:*\n"
    for row in last_two:
        period, num, size, pred, result, range_pred = row
        text += f"📅 `{period}` | 🎯 {num} | 📊 {size} | 🧠 {pred} | 🏁 {result} | 🎚 {range_pred}\n"
    text += "\n👑 *Admin User IDs:*\n"
    text += ", ".join(str(uid) for uid in ADMIN_USER_IDS)
    text += "\n━━━━━━━━━━━━━━━━━━━━━━"
    return text

# ==================== Predictor Class ====================
class Predictor:
    def __init__(self):
        self.history = deque(maxlen=300)
        self.wins = 0
        self.losses = 0
        self.streak = 0
        self.best_streak = 0
        self.total_predictions = 0
        self.running = False
        self.chat_id = None
        self.load_from_db()

    def load_from_db(self):
        for _, num, _, _, _, _ in load_recent_history(300):
            if num is not None:
                self.history.append(num)

    def update(self, num, period, prediction=None, result=None, range_pred=None):
        size = "BIG" if num >= 5 else "SMALL"
        self.history.append(num)
        save_round(period, num, size, prediction, result, range_pred)

    def fetch_data(self):
        try:
            ts = int(time.time() * 1000)
            data = http_get_json(API_URL.format(ts), timeout=10)
            if data:
                return data.get("data", {}).get("list", [])
        except:
            pass
        return []

    # ---------- Indicators ----------
    def ma(self, data, w):
        if len(data) >= w:
            return sum(data[-w:]) / w
        elif data:
            return sum(data) / len(data)
        return 0

    def rsi(self, data, w=14):
        if len(data) < w + 1:
            return 50
        g = 0
        l = 0
        for i in range(1, w + 1):
            d = data[-i] - data[-i-1]
            if d > 0:
                g += d
            else:
                l += abs(d)
        if l == 0:
            return 100
        return 100 - (100 / (1 + (g / l)))

    def std_dev(self, data, w=20):
        if len(data) < w:
            return 0
        recent = data[-w:]
        mean = sum(recent) / w
        return math.sqrt(sum((x - mean) ** 2 for x in recent) / w)

    # ---------- Prediction ----------
    def predict_size(self):
        hist = list(self.history)
        if len(hist) < 20:
            return "BIG", 60, "5 • 9", "BULLISH", 50, "LOW", "NEUTRAL", "STABLE", 50, 50

        last = hist[-1]
        last_size = "BIG" if last >= 5 else "SMALL"

        # Fixed special numbers (0-4 = SMALL, 5-9 = BIG)
        specials = {
            0: ("SMALL", 99, "0 • 2"),
            4: ("SMALL", 99, "3 • 5"),
            5: ("BIG", 99, "5 • 7"),
            9: ("SMALL", 99, "7 • 9")
        }
        if last in specials:
            s = specials[last]
            return s[0], s[1], s[2], "BULLISH", 70, "LOW", "SPECIAL", "STABLE", 90, 10

        streak = 1
        for i in range(len(hist)-2, -1, -1):
            if (hist[i] >= 5) == (last >= 5):
                streak += 1
            else:
                break

        def is_alt(l):
            if len(hist) < l:
                return False
            for i in range(1, l):
                if (hist[-i] >= 5) == (hist[-i-1] >= 5):
                    return False
            return True

        # Helper to get top 2 numbers for range
        def get_range(pred_type):
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred_type == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                return str(top[0][0]) + " • " + str(top[1][0])
            return "5 • 9" if pred_type == "BIG" else "0 • 4"

        if streak >= 5:
            pred = last_size
            conf = 99
            rng = get_range(pred)
            return pred, conf, rng, "STRONG BULLISH", 72, "LOW", "DRAGON", "STABLE", 95, 5

        if streak == 4:
            pred = last_size
            conf = 97
            rng = get_range(pred)
            return pred, conf, rng, "BULLISH", 68, "LOW", "4-STREAK", "STABLE", 90, 10

        if streak == 3:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 90
            rng = get_range(pred)
            return pred, conf, rng, "BEARISH", 55, "MEDIUM", "3-STREAK BREAK", "UNSTABLE", 75, 25

        if streak == 2:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 85
            rng = get_range(pred)
            return pred, conf, rng, "NEUTRAL", 52, "MEDIUM", "2-STREAK BREAK", "STABLE", 70, 30

        if is_alt(8):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 92
            rng = get_range(pred)
            return pred, conf, rng, "BULLISH", 65, "LOW", "ALTERNATING 8", "STABLE", 85, 15

        if is_alt(6):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 88
            rng = get_range(pred)
            return pred, conf, rng, "BULLISH", 60, "LOW", "ALTERNATING 6", "STABLE", 80, 20

        if is_alt(5):
            pred = last_size
            conf = 85
            rng = get_range(pred)
            return pred, conf, rng, "NEUTRAL", 55, "MEDIUM", "TRAP", "STABLE", 72, 28

        # Default analysis using moving averages and RSI
        ma5 = self.ma(hist, 5)
        ma10 = self.ma(hist, 10)
        ma20 = self.ma(hist, 20)
        ma_trend = "BULLISH" if ma5 > ma10 and ma10 > ma20 else "BEARISH" if ma5 < ma10 and ma10 < ma20 else "NEUTRAL"

        rsi_val = self.rsi(hist, 14)
        rsi_trend = "BULLISH" if rsi_val < 30 else "BEARISH" if rsi_val > 70 else "NEUTRAL"

        recent_30 = hist[-30:] if len(hist) >= 30 else hist
        big_c = sum(1 for x in recent_30 if x >= 5)
        small_c = len(recent_30) - big_c

        std = self.std_dev(hist, 20)
        std_text = "LOW" if std < 1.5 else "MEDIUM" if std < 2.5 else "HIGH"

        votes = {"BIG": 0, "SMALL": 0}
        votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        if ma_trend == "BULLISH":
            votes["BIG"] += 3
        elif ma_trend == "BEARISH":
            votes["SMALL"] += 3

        if rsi_trend == "BULLISH":
            votes["BIG"] += 2
        elif rsi_trend == "BEARISH":
            votes["SMALL"] += 2

        if big_c > small_c + 3:
            votes["SMALL"] += 2
        elif small_c > big_c + 3:
            votes["BIG"] += 2

        pred = max(votes, key=votes.get)
        total = sum(votes.values())
        diff = votes[pred] - (total - votes[pred])

        if diff >= 4:
            conf = 92
        elif diff >= 2:
            conf = 85
        else:
            conf = 70

        big_pct = int((votes["BIG"] / total) * 100) if total > 0 else 50
        small_pct = int((votes["SMALL"] / total) * 100) if total > 0 else 50
        pattern_text = "ALTERNATING" if is_alt(4) else "RANDOM"
        cycle_text = "STABLE" if std < 1.5 else "UNSTABLE"

        rng = get_range(pred)

        return pred, conf, rng, ma_trend, rsi_val, std_text, pattern_text, cycle_text, big_pct, small_pct

    def get_next_prediction(self):
        size, conf, rng, ma, rsi, std, pattern, cycle, big_pct, small_pct = self.predict_size()
        return {
            "size": size,
            "confidence": conf,
            "range": rng,
            "ma": ma,
            "rsi": rsi,
            "std": std,
            "pattern": pattern,
            "cycle": cycle,
            "big_pct": big_pct,
            "small_pct": small_pct
        }

    def update_result(self, won):
        if won:
            self.wins += 1
            self.streak += 1
            if self.streak > self.best_streak:
                self.best_streak = self.streak
        else:
            self.losses += 1
            self.streak = 0
        self.total_predictions += 1

    def send_message(self, text):
        if self.chat_id:
            try:
                url = TELEGRAM_API + "sendMessage"
                payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
                http_post_json(url, payload, timeout=10)
            except:
                pass

    def start(self, chat_id):
        if self.running:
            return
        self.running = True
        self.chat_id = chat_id
        self.send_message("✅ Prediction started! (LEVEL 1-2: >=85%)")
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.send_message("⏹ Stopped.")

    def _loop(self):
        seen = set()
        current_prediction = None

        while self.running:
            try:
                data = self.fetch_data()
                if not data:
                    time.sleep(1)
                    continue

                latest = data[0]
                period = latest.get("issueNumber", "")
                num_str = latest.get("number", "")
                try:
                    number = int(num_str)
                except:
                    number = None

                if not period or not period.isdigit():
                    time.sleep(1)
                    continue

                if period not in seen:
                    if number is not None:
                        self.update(number, period)
                    seen.add(period)

                    next_period = str(int(period) + 1)
                    pred_data = self.get_next_prediction()

                    if pred_data["confidence"] >= 85:
                        current_prediction = {
                            "period": next_period,
                            "size": pred_data["size"],
                            "range": pred_data["range"]
                        }
                        self.send_message(format_prediction_ui(pred_data, next_period))

                if current_prediction and current_prediction["period"] == period and number is not None:
                    actual_size = "BIG" if number >= 5 else "SMALL"
                    won = (actual_size == current_prediction["size"])
                    res = "WIN" if won else "LOSS"
                    self.update_result(won)
                    self.update(number, period,
                               prediction=current_prediction["size"],
                               result=res,
                               range_pred=current_prediction["range"])
                    self.send_message(format_result_ui(period, number, actual_size, res,
                                                       current_prediction["size"],
                                                       current_prediction["range"]))
                    current_prediction = None

                time.sleep(1)
            except Exception as e:
                print("Loop error:", e)
                time.sleep(2)

# ==================== Telegram Handler ====================
predictor = Predictor()
last_update_id = 0

def get_updates(offset=None):
    url = TELEGRAM_API + "getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        query_string = urllib.parse.urlencode(params)
        full_url = url + "?" + query_string
        data = http_get_json(full_url, timeout=35)
        if data:
            return data.get("result", [])
    except:
        pass
    return []

def main():
    global last_update_id
    print("Bot started... (Pure Standard Library + Admin Data View)")
    print("LEVEL 1 (>=92%) | LEVEL 2 (>=85%)")
    print("Database: predictions.db (SQLite)")
    print("Authorization active. Admin can view data.")

    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message")
                if msg:
                    chat_id = msg["chat"]["id"]
                    user_id = msg["from"]["id"]
                    text = msg.get("text", "")

                    # Authorization check
                    if not is_authorized(user_id):
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": "⛔ *You are not authorized!* Contact admin.",
                            "parse_mode": "Markdown"
                        }, timeout=10)
                        continue

                    # /start command
                    if text == "/start":
                        keyboard_buttons = [
                            [{"text": "▶️ START", "callback_data": "start"}],
                            [{"text": "⏹ STOP", "callback_data": "stop"}],
                            [{"text": "📊 STATUS", "callback_data": "status"}],
                        ]
                        # Only admin sees SHOW DATA button
                        if is_admin(user_id):
                            keyboard_buttons.append([{"text": "📊 SHOW DATA", "callback_data": "show_data"}])

                        keyboard_buttons.append([{"text": "📞 CONTACT", "url": "https://t.me/your_username"}])

                        keyboard = {"inline_keyboard": keyboard_buttons}
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": "🤖 *SUBHA v3.0 (Pure Python)*\n\n✅ Predictions every period\n✅ LEVEL 1 (>=92%) | LEVEL 2 (>=85%)\n✅ Data stored in SQLite\n✅ Admin can view first & last 2 records\n\nUse buttons below.",
                            "reply_markup": keyboard,
                            "parse_mode": "Markdown"
                        }, timeout=10)

                    # /show_data command (admin only)
                    elif text == "/show_data":
                        if not is_admin(user_id):
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "⛔ *This feature is for admins only!*",
                                "parse_mode": "Markdown"
                            }, timeout=10)
                            continue
                        first_two, last_two = get_first_and_last()
                        if not first_two and not last_two:
                            response = "⚠️ No data collected yet."
                        else:
                            response = format_first_last_ui(first_two, last_two)
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": response,
                            "parse_mode": "Markdown"
                        }, timeout=10)

                cb = update.get("callback_query")
                if cb:
                    chat_id = cb["message"]["chat"]["id"]
                    user_id = cb["from"]["id"]
                    data = cb["data"]
                    cb_id = cb["id"]
                    http_post_json(TELEGRAM_API + "answerCallbackQuery", {"callback_query_id": cb_id}, timeout=5)

                    if not is_authorized(user_id):
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": "⛔ You are not authorized.",
                        }, timeout=10)
                        continue

                    if data == "start":
                        if not predictor.running:
                            predictor.start(chat_id)
                        else:
                            predictor.send_message("⏳ Already running...")
                    elif data == "stop":
                        predictor.stop()
                    elif data == "status":
                        stats = "📊 *Statistics*\n✅ Wins: {wins}\n❌ Losses: {losses}\n🔥 Streak: {streak}\n🏆 Best Streak: {best}\n📈 Total: {total}".format(
                            wins=predictor.wins, losses=predictor.losses, streak=predictor.streak,
                            best=predictor.best_streak, total=predictor.total_predictions)
                        predictor.send_message(stats)
                    elif data == "show_data":
                        if not is_admin(user_id):
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "⛔ *This feature is for admins only!*",
                                "parse_mode": "Markdown"
                            }, timeout=10)
                            continue
                        first_two, last_two = get_first_and_last()
                        if not first_two and not last_two:
                            response = "⚠️ No data collected yet."
                        else:
                            response = format_first_last_ui(first_two, last_two)
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": response,
                            "parse_mode": "Markdown"
                        }, timeout=10)

            time.sleep(1)
        except Exception as e:
            print("Main error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()