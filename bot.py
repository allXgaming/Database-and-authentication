# ==================== সম্পূর্ণ বট (SQLite, ইমোজি বিহীন, বাংলা) ====================
import time
import threading
import math
import sqlite3
import json
import urllib.request
import urllib.error
import urllib.parse
from collections import deque, Counter

# ---------- কনফিগারেশন ----------
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?ts={}"
BOT_TOKEN = "7616902302:AAEp4VjUFX9mfBqYuc_ZY7pfuntVvQ8dpWE"   # আপনার টোকেন দিন
TELEGRAM_API = "https://api.telegram.org/bot{}/".format(BOT_TOKEN)

# ডাটাবেস ফাইল
DB_FILE = "predictions.db"

# ==================== অ্যাডমিন ও অথরাইজেশন ====================
ADMIN_USER_ID = 5824157133  # ← এখানে আপনার টেলিগ্রাম আইডি দিন

AUTHORIZED_USER_IDS = {
    7237785856,
    5824157133,
}

def is_authorized(user_id):
    if user_id is None:
        return False
    return user_id in AUTHORIZED_USER_IDS

def is_admin(user_id):
    if user_id is None:
        return False
    return user_id == ADMIN_USER_ID

# ==================== ডাটাবেস (SQLite) ====================
def init_db():
    """ডাটাবেস ও টেবিল তৈরি করে"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS rounds
                     (period TEXT PRIMARY KEY, 
                      number INTEGER, 
                      size TEXT,
                      prediction TEXT, 
                      result TEXT, 
                      range_pred TEXT, 
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        print("ডাটাবেস তৈরি হয়েছে:", DB_FILE)
        return True
    except Exception as e:
        print("ডাটাবেস তৈরি করতে সমস্যা:", e)
        return False

def save_round(period, number, size, prediction, result, range_pred):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO rounds (period, number, size, prediction, result, range_pred, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''', 
                     (period, number, size, prediction, result, range_pred))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("সেভ করতে সমস্যা:", e)
        return False

def load_recent_history(limit=300):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''SELECT period, number, size, prediction, result, range_pred FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("লোড করতে সমস্যা:", e)
        return []

def get_total_count():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM rounds")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print("কাউন্ট করতে সমস্যা:", e)
        return 0

# ==================== ইউটিলিটি ফাংশন ====================
def http_get_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print("HTTP GET সমস্যা:", e)
        return None

def http_post_json(url, payload, timeout=10):
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print("HTTP POST সমস্যা:", e)
        return None

# ==================== UI ফরম্যাটিং (বাংলা, ইমোজি বিহীন) ====================
def format_prediction_ui(pred_data, period):
    size = pred_data["size"]
    conf = pred_data["confidence"]
    num_range = pred_data["range"]
    ma_val = pred_data.get("ma", "বুলিশ")
    rsi_val = pred_data.get("rsi", 63.8)
    std_val = pred_data.get("std", "নিম্ন")
    pattern = pred_data.get("pattern", "একান্তর")
    cycle = pred_data.get("cycle", "স্থিতিশীল")
    big_pct = pred_data.get("big_pct", 78)
    small_pct = pred_data.get("small_pct", 22)
    
    # সংকেতের মাত্রা
    if conf >= 85:
        signal = "উচ্চ সংকেত"
        volatility = "নিম্ন"
        risk = "নিম্ন"
    else:
        signal = "মাঝারি সংকেত"
        volatility = "মাঝারি"
        risk = "মাঝারি"
    
    size_text = "বড়" if size == "BIG" else "ছোট"
    if conf >= 92:
        level = "স্তর ১"
    elif conf >= 85:
        level = "স্তর ২"
    else:
        level = "স্তর ৩"
    
    big_bar = "█" * int(big_pct / 10) + "░" * (10 - int(big_pct / 10))
    small_bar = "█" * int(small_pct / 10) + "░" * (10 - int(small_pct / 10))
    
    # বাংলা অনুবাদ
    ma_bn = {"বুলিশ": "বুলিশ", "বিয়ারিশ": "বিয়ারিশ", "নিরপেক্ষ": "নিরপেক্ষ",
             "STRONG BULLISH": "শক্তিশালী বুলিশ", "BEARISH": "বিয়ারিশ",
             "NEUTRAL": "নিরপেক্ষ", "BULLISH": "বুলিশ"}.get(ma_val, ma_val)
    
    pattern_bn = {"ALTERNATING": "একান্তর", "SPECIAL": "বিশেষ", "DRAGON": "ড্রাগন",
                  "4-STREAK": "৪-ধারা", "3-STREAK BREAK": "৩-ধারা ভাঙন",
                  "2-STREAK BREAK": "২-ধারা ভাঙন", "TRAP": "ফাঁদ", "RANDOM": "এলোমেলো",
                  "ALTERNATING 8": "একান্তর ৮", "ALTERNATING 6": "একান্তর ৬"}.get(pattern, pattern)
    
    cycle_bn = {"STABLE": "স্থিতিশীল", "UNSTABLE": "অস্থিতিশীল"}.get(cycle, cycle)
    std_bn = {"LOW": "নিম্ন", "MEDIUM": "মাঝারি", "HIGH": "উচ্চ"}.get(std_val, std_val)
    
    ui = """
━━━━━━━━━━━━━━━━━━━━━━
এআই বিশ্লেষণ
━━━━━━━━━━━━━━━━━━━━━━
গড় মূল্য (MA)      : {ma}
আরএসআই (RSI)       : {rsi:.1f}
মানক বিচ্যুতি (STD): {std}
প্যাটার্ন           : {pattern}
সাইকেল              : {cycle}

━━━━━━━━━━━━━━━━━━━━━━
এআই ভোটিং
━━━━━━━━━━━━━━━━━━━━━━
বড়          {big_bar} {big_pct}%
ছোট        {small_bar} {small_pct}%

চূড়ান্ত পূর্বাভাস : {size_text}

━━━━━━━━━━━━━━━━━━━━━━
এআই মেট্রিক্স
━━━━━━━━━━━━━━━━━━━━━━
আত্মবিশ্বাস    : {conf}%
সংকেত          : {signal}
অস্থিরতা       : {volatility}
ঝুঁকি           : {risk}

━━━━━━━━━━━━━━━━━━━━━━
পর্যায়          : {period}
পরিসর           : {num_range}
স্তর             : {level}
━━━━━━━━━━━━━━━━━━━━━━
এআই অবস্থা : সক্রিয়
ইঞ্জিন      : শুভ এআই
মোড         : লাইভ
━━━━━━━━━━━━━━━━━━━━━━
""".format(ma=ma_bn, rsi=rsi_val, std=std_bn, pattern=pattern_bn, cycle=cycle_bn,
           big_bar=big_bar, big_pct=big_pct, small_bar=small_bar, small_pct=small_pct,
           size_text=size_text, conf=conf, signal=signal, volatility=volatility,
           risk=risk, period=period, num_range=num_range, level=level)
    return ui

def format_result_ui(period, number, actual_size, result, pred, range_pred):
    if result == "WIN":
        status_text = "জয়"
    else:
        status_text = "পরাজয়"
    actual_text = "বড়" if actual_size == "BIG" else "ছোট"
    ui = """
{status_text}
━━━━━━━━━━━━━━━━━━━━━━
ফলাফল
━━━━━━━━━━━━━━━━━━━━━━
পর্যায়    : {period}
পূর্বাভাস : {pred}
প্রকৃত     : {actual_text} [{number}]
পরিসর      : {range_pred}
━━━━━━━━━━━━━━━━━━━━━━
""".format(status_text=status_text, period=period, pred=pred,
           actual_text=actual_text, number=number, range_pred=range_pred)
    return ui

def format_data_first_last(first_two, last_two, total_count):
    """প্রথম ২ ও শেষ ২ রেকর্ড দেখানোর ফরম্যাট (শো ডাটা)"""
    text = "অ্যাডমিন আইডি: `{}`\n\n".format(ADMIN_USER_ID)
    text += "প্রথম ২ ও শেষ ২ রেকর্ড:\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "`{:<14} {:<4} {:<7} {:<7} {:<6} {:<10}`\n".format("পর্যায়", "সংখ্যা", "আকার", "পূর্বাভাস", "ফল", "পরিসর")
    for row in first_two:
        period_short = str(row[0])[-8:]   # শেষ ৮ ডিজিট
        num = str(row[1]) if row[1] is not None else "-"
        size = str(row[2]) if row[2] else "-"
        pred = str(row[3]) if row[3] else "-"
        res = str(row[4]) if row[4] else "-"
        rng = str(row[5]) if row[5] else "-"
        text += "`{:<14} {:<4} {:<7} {:<7} {:<6} {:<10}`\n".format(period_short, num, size, pred, res, rng)
    if len(first_two) == 2 and len(last_two) >= 2:
        text += "         ...\n"
    for row in last_two:
        period_short = str(row[0])[-8:]
        num = str(row[1]) if row[1] is not None else "-"
        size = str(row[2]) if row[2] else "-"
        pred = str(row[3]) if row[3] else "-"
        res = str(row[4]) if row[4] else "-"
        rng = str(row[5]) if row[5] else "-"
        text += "`{:<14} {:<4} {:<7} {:<7} {:<6} {:<10}`\n".format(period_short, num, size, pred, res, rng)
    text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "মোট রেকর্ড: {}".format(total_count)
    return text

# ==================== প্রেডিক্টর ক্লাস ====================
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
        rows = load_recent_history(300)
        for _, num, _, _, _, _ in rows:
            if num is not None:
                self.history.append(num)
        print("হিস্ট্রি লোড:", len(self.history), "টি সংখ্যা")

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

    def predict_size(self):
        hist = list(self.history)
        if len(hist) < 20:
            return "BIG", 60, "৫ • ৯", "বুলিশ", 50, "নিম্ন", "নিরপেক্ষ", "স্থিতিশীল", 50, 50

        last = hist[-1]
        last_size = "BIG" if last >= 5 else "SMALL"

        # বিশেষ সংখ্যা
        specials = {0: ("BIG", 99, "০ • ২"), 4: ("BIG", 99, "৩ • ৫"), 5: ("SMALL", 99, "৫ • ৭"), 9: ("SMALL", 99, "৭ • ৯")}
        if last in specials:
            s = specials[last]
            return s[0], s[1], s[2], "বুলিশ", 70, "নিম্ন", "বিশেষ", "স্থিতিশীল", 90, 10

        # ধারাবাহিকতা গণনা
        streak = 1
        for i in range(len(hist)-2, -1, -1):
            if (hist[i] >= 5) == (last >= 5):
                streak += 1
            else:
                break

        # শক্তিশালী ধারা (৫ বা তার বেশি)
        if streak >= 5:
            pred = last_size
            conf = 99
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "শক্তিশালী বুলিশ", 72, "নিম্ন", "ড্রাগন", "স্থিতিশীল", 95, 5

        if streak == 4:
            pred = last_size
            conf = 97
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "বুলিশ", 68, "নিম্ন", "৪-ধারা", "স্থিতিশীল", 90, 10

        if streak == 3:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 90
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "বিয়ারিশ", 55, "মাঝারি", "৩-ধারা ভাঙন", "অস্থিতিশীল", 75, 25

        if streak == 2:
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 85
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "নিরপেক্ষ", 52, "মাঝারি", "২-ধারা ভাঙন", "স্থিতিশীল", 70, 30

        # একান্তর প্যাটার্ন
        def is_alt(l):
            if len(hist) < l:
                return False
            for i in range(1, l):
                if (hist[-i] >= 5) == (hist[-i-1] >= 5):
                    return False
            return True

        if is_alt(8):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 92
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "বুলিশ", 65, "নিম্ন", "একান্তর ৮", "স্থিতিশীল", 85, 15

        if is_alt(6):
            pred = "SMALL" if last_size == "BIG" else "BIG"
            conf = 88
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "বুলিশ", 60, "নিম্ন", "একান্তর ৬", "স্থিতিশীল", 80, 20

        if is_alt(5):
            pred = last_size
            conf = 85
            recent = hist[-20:]
            nums = [x for x in recent if (x >= 5) == (pred == "BIG")]
            if len(nums) >= 2:
                cnt = Counter(nums)
                top = cnt.most_common(2)
                rng = str(top[0][0]) + " • " + str(top[1][0])
            else:
                rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"
            return pred, conf, rng, "নিরপেক্ষ", 55, "মাঝারি", "ফাঁদ", "স্থিতিশীল", 72, 28

        # এমএ, আরএসআই, ভারসাম্য বিশ্লেষণ
        ma5 = self.ma(hist, 5)
        ma10 = self.ma(hist, 10)
        ma20 = self.ma(hist, 20)
        if ma5 > ma10 and ma10 > ma20:
            ma_trend = "বুলিশ"
        elif ma5 < ma10 and ma10 < ma20:
            ma_trend = "বিয়ারিশ"
        else:
            ma_trend = "নিরপেক্ষ"

        rsi_val = self.rsi(hist, 14)
        if rsi_val < 30:
            rsi_trend = "বুলিশ"
        elif rsi_val > 70:
            rsi_trend = "বিয়ারিশ"
        else:
            rsi_trend = "নিরপেক্ষ"

        recent_30 = hist[-30:] if len(hist) >= 30 else hist
        big_c = sum(1 for x in recent_30 if x >= 5)
        small_c = len(recent_30) - big_c

        std = self.std_dev(hist, 20)
        if std < 1.5:
            std_text = "নিম্ন"
        elif std < 2.5:
            std_text = "মাঝারি"
        else:
            std_text = "উচ্চ"

        # ভোটিং
        votes = {"BIG": 0, "SMALL": 0}
        votes["SMALL" if last_size == "BIG" else "BIG"] += 1

        if ma_trend == "বুলিশ":
            votes["BIG"] += 3
        elif ma_trend == "বিয়ারিশ":
            votes["SMALL"] += 3

        if rsi_trend == "বুলিশ":
            votes["BIG"] += 2
        elif rsi_trend == "বিয়ারিশ":
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

        # প্যাটার্ন ও সাইকেল
        if is_alt(4):
            pattern_text = "একান্তর"
        else:
            pattern_text = "এলোমেলো"
        cycle_text = "স্থিতিশীল" if std < 1.5 else "অস্থিতিশীল"

        # পরিসর
        recent = hist[-20:] if len(hist) >= 20 else hist
        if pred == "BIG":
            nums = [x for x in recent if x >= 5]
        else:
            nums = [x for x in recent if x < 5]
        if len(nums) >= 2:
            cnt = Counter(nums)
            top = cnt.most_common(2)
            rng = str(top[0][0]) + " • " + str(top[1][0])
        else:
            rng = "৫ • ৯" if pred == "BIG" else "০ • ৪"

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

    def send_message(self, text, chat_id=None):
        target_chat = chat_id if chat_id is not None else self.chat_id
        if target_chat:
            try:
                url = TELEGRAM_API + "sendMessage"
                payload = {"chat_id": target_chat, "text": text, "parse_mode": "Markdown"}
                http_post_json(url, payload, timeout=10)
            except:
                pass

    def start(self, chat_id):
        if self.running:
            self.send_message("ইতিমধ্যে চলছে...", chat_id=chat_id)
            return
        self.running = True
        self.chat_id = chat_id
        self.send_message("পূর্বাভাস শুরু! (শুধু আত্মবিশ্বাস >= ৮৫%)", chat_id=chat_id)
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self, chat_id=None):
        self.running = False
        self.send_message("বন্ধ করা হয়েছে।", chat_id=chat_id)

    def _loop(self):
        seen = set()
        predictions_sent = set()
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
                        predictions_sent.add(next_period)

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
                print("লুপ সমস্যা:", e)
                time.sleep(2)

# ==================== টেলিগ্রাম হ্যান্ডলার ====================
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
    print("=" * 50)
    print("বট চালু হচ্ছে... (SQLite, বাংলা)")
    print("ডাটাবেস ফাইল:", DB_FILE)
    print("অ্যাডমিন আইডি:", ADMIN_USER_ID)
    print("=" * 50)

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

                    print("ইউজার:", user_id, "চ্যাট:", chat_id, "টেক্সট:", text)

                    if not is_authorized(user_id):
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": "আপনি অনুমোদিত নন।",
                            "parse_mode": "Markdown"
                        }, timeout=10)
                        continue

                    if text == "/start":
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "শুরু", "callback_data": "start"}],
                                [{"text": "বন্ধ", "callback_data": "stop"}],
                                [{"text": "পরিসংখ্যান", "callback_data": "status"}],
                            ]
                        }
                        if is_admin(user_id):
                            keyboard["inline_keyboard"].append([{"text": "ডেটা দেখুন", "callback_data": "show_data"}])
                        
                        keyboard["inline_keyboard"].append([{"text": "যোগাযোগ", "url": "https://t.me/your_username"}])
                        
                        start_text = "শুভ এআই সংস্করণ ৪.০ (SQLite)\n\n"
                        start_text += "প্রতি পর্বে পূর্বাভাস প্রদান করে\n"
                        start_text += "সকল ডেটা SQLite ডাটাবেসে সংরক্ষিত হয়\n"
                        start_text += "আপনার আইডি: `{}`\n".format(user_id)
                        if is_admin(user_id):
                            start_text += "আপনি অ্যাডমিন\n"
                            start_text += "/show_data - ডেটা দেখতে ব্যবহার করুন\n"
                        else:
                            start_text += "শুধু অ্যাডমিন ডেটা দেখতে পারবেন\n"
                        
                        http_post_json(TELEGRAM_API + "sendMessage", {
                            "chat_id": chat_id,
                            "text": start_text,
                            "reply_markup": keyboard,
                            "parse_mode": "Markdown"
                        }, timeout=10)

                    elif text == "/show_data":
                        if not is_admin(user_id):
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "অনুমতি নেই। শুধুমাত্র অ্যাডমিন দেখতে পারবেন।",
                                "parse_mode": "Markdown"
                            }, timeout=10)
                            continue
                        # প্রথম ২ ও শেষ ২ রেকর্ড আনা
                        try:
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period ASC LIMIT 2")
                            first_two = c.fetchall()
                            c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period DESC LIMIT 2")
                            last_two = c.fetchall()
                            conn.close()
                            # শেষ দুটোকে ক্রমানুসারে সাজানো (পুরোনো -> নতুন)
                            last_two_sorted = sorted(last_two, key=lambda x: x[0])
                            response = format_data_first_last(first_two, last_two_sorted, get_total_count())
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": response,
                                "parse_mode": "Markdown"
                            }, timeout=10)
                        except Exception as e:
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "ডেটা দেখাতে সমস্যা: {}".format(str(e))
                            }, timeout=10)

                cb = update.get("callback_query")
                if cb:
                    chat_id = cb["message"]["chat"]["id"]
                    user_id = cb["from"]["id"]
                    data = cb["data"]
                    cb_id = cb["id"]
                    http_post_json(TELEGRAM_API + "answerCallbackQuery", {"callback_query_id": cb_id}, timeout=5)

                    print("ক্লিক - ইউজার:", user_id, "চ্যাট:", chat_id, "ডেটা:", data)

                    if not is_authorized(user_id):
                        continue

                    if data == "start":
                        predictor.start(chat_id)
                    elif data == "stop":
                        predictor.stop(chat_id)
                    elif data == "status":
                        stats = "পরিসংখ্যান\n"
                        stats += "জয়: {}\n".format(predictor.wins)
                        stats += "পরাজয়: {}\n".format(predictor.losses)
                        stats += "বর্তমান ধারা: {}\n".format(predictor.streak)
                        stats += "সর্বোচ্চ ধারা: {}\n".format(predictor.best_streak)
                        stats += "মোট পূর্বাভাস: {}".format(predictor.total_predictions)
                        predictor.send_message(stats, chat_id=chat_id)
                    elif data == "show_data":
                        if not is_admin(user_id):
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "অনুমতি নেই।",
                                "parse_mode": "Markdown"
                            }, timeout=10)
                            continue
                        try:
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period ASC LIMIT 2")
                            first_two = c.fetchall()
                            c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period DESC LIMIT 2")
                            last_two = c.fetchall()
                            conn.close()
                            last_two_sorted = sorted(last_two, key=lambda x: x[0])
                            response = format_data_first_last(first_two, last_two_sorted, get_total_count())
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": response,
                                "parse_mode": "Markdown"
                            }, timeout=10)
                        except Exception as e:
                            http_post_json(TELEGRAM_API + "sendMessage", {
                                "chat_id": chat_id,
                                "text": "ডেটা দেখাতে সমস্যা: {}".format(str(e))
                            }, timeout=10)

            time.sleep(1)
        except Exception as e:
            print("মূল সমস্যা:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()