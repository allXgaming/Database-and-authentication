import time, threading, math, sqlite3, json, urllib.request, urllib.error, urllib.parse
from collections import deque, Counter
from datetime import datetime

# ==================== CONFIGURATION ====================
BOT_TOKEN = "7616902302:AAEp4VjUFX9mfBqYuc_ZY7pfuntVvQ8dpWE"               # 🔁 Replace
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json?ts={}"

# Google Sheet CSV export URL (publicly readable)
SHEET_ID = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRbulMlp7hQEM2zo0rNukTrjdD2MZh_KsaZvnZ4pHZX4WEaNv1ryofYSLQ1eHrAPHf940lnUSwWbkzQ/pub?output=csv"          # 🔁 Replace
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# Admins who can see SHOW DATA button (hardcoded for now)
ADMIN_USER_IDS = {5824157133}                   # 🔁 Replace

# ==================== GOOGLE SHEETS SYNC ====================
sheet_data_cache = []
sheet_last_fetch = 0
sheet_lock = threading.Lock()

def fetch_sheet_csv(url):
    """Download CSV from Google Sheets."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        print("Sheet fetch error:", e)
        return None

def parse_sheet(csv_text):
    """Parse CSV into list of dicts.
    Expected columns: Name, Username, Telegram ID, UID, Expired (Date and Time)
    """
    lines = csv_text.strip().split('\n')
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split(',')]
    users = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = [v.strip() for v in line.split(',')]
        user = {}
        for i, header in enumerate(headers):
            if i < len(values):
                user[header] = values[i]
            else:
                user[header] = ''
        # Ensure Telegram ID is integer
        try:
            user['telegram_id'] = int(user.get('Telegram ID', '0'))
        except:
            user['telegram_id'] = 0
        users.append(user)
    return users

def refresh_sheet_cache():
    """Refresh the local sheet cache every 60 seconds."""
    global sheet_data_cache, sheet_last_fetch
    while True:
        csv_text = fetch_sheet_csv(SHEET_CSV_URL)
        if csv_text:
            parsed = parse_sheet(csv_text)
            with sheet_lock:
                sheet_data_cache = parsed
                sheet_last_fetch = time.time()
        time.sleep(60)

# Start background sheet refresher
threading.Thread(target=refresh_sheet_cache, daemon=True).start()

def get_user_info(user_id):
    """Return user dict from sheet if ID exists and not expired, else None or deactivated flag.
    Returns: (status, info_dict)
        status: 'active', 'deactive', 'not_found'
    """
    with sheet_lock:
        for user in sheet_data_cache:
            if user.get('telegram_id') == user_id:
                # Check expiration
                expired_str = user.get('Expired (Date and Time)', '')
                if expired_str:
                    try:
                        expired_dt = datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
                        if datetime.now() > expired_dt:
                            return 'deactive', user
                    except:
                        pass
                return 'active', user
    return 'not_found', None

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rounds
                 (period TEXT PRIMARY KEY, number INTEGER, size TEXT,
                  prediction TEXT, result TEXT, range_pred TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    try: c.execute("ALTER TABLE rounds ADD COLUMN range_pred TEXT")
    except: pass
    try: c.execute("ALTER TABLE rounds ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except: pass
    conn.commit(); conn.close()

def save_round(period, number, size, prediction, result, range_pred):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO rounds VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
              (period, number, size, prediction, result, range_pred))
    conn.commit(); conn.close()

def load_recent_history(limit=300):
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    try:
        c.execute('''SELECT period, number, size, prediction, result, range_pred FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
    except:
        c.execute('''SELECT period, number, size, prediction, result FROM rounds
                     ORDER BY period DESC LIMIT ?''', (limit,))
        rows = [(r[0],r[1],r[2],r[3],r[4],None) for r in c.fetchall()]
    conn.close()
    return rows

def get_first_and_last():
    conn = sqlite3.connect('predictions.db')
    c = conn.cursor()
    c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period ASC LIMIT 2")
    first_two = c.fetchall()
    c.execute("SELECT period, number, size, prediction, result, range_pred FROM rounds ORDER BY period DESC LIMIT 2")
    last_two_raw = c.fetchall()
    conn.close()
    last_two = list(reversed(last_two_raw))
    return first_two, last_two

init_db()

# ==================== HTTP HELPERS ====================
def http_get_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except: return None

def http_post_json(url, payload, timeout=10):
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8')
    except: return None

# ==================== UI FORMATTERS ====================
def format_prediction_ui(pred_data, period):
    size = pred_data["size"]
    conf = pred_data["confidence"]
    rng = pred_data["range"]
    ma_val = pred_data.get("ma","BULLISH")
    rsi_val = pred_data.get("rsi",63.8)
    std_val = pred_data.get("std","LOW")
    pattern = pred_data.get("pattern","ALTERNATING")
    cycle = pred_data.get("cycle","STABLE")
    big_pct = pred_data.get("big_pct",78)
    small_pct = pred_data.get("small_pct",22)
    signal = "HIGH 🟢" if conf>=85 else "MEDIUM 🟡"
    vol = "LOW" if conf>=85 else "MEDIUM"
    risk = "LOW" if conf>=85 else "MEDIUM"
    size_emoji = "🐘" if size=="BIG" else "🐭"
    level = "🔥 LEVEL 1" if conf>=92 else "⚡ LEVEL 2" if conf>=85 else "⚠️ LEVEL 3"
    big_bar = "█"*int(big_pct/10)+"░"*(10-int(big_pct/10))
    small_bar = "█"*int(small_pct/10)+"░"*(10-int(small_pct/10))
    return f"""
━━━━━━━━━━━━━━━━━━━━━━
🧠 AI ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━
📈 MA           : {ma_val}
📊 RSI          : {rsi_val:.1f}
📉 STD DEV      : {std_val}
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
🎲 VOLATILITY   : {vol}
⚖️ RISK         : {risk}

━━━━━━━━━━━━━━━━━━━━━━
🆔 PERIOD       : {period}
🎯 RANGE        : {rng}
📊 LEVEL        : {level}
━━━━━━━━━━━━━━━━━━━━━━
⚡ AI STATUS : ACTIVE
🧠 ENGINE    : SUBHA AI
🔥 MODE      : LIVE
━━━━━━━━━━━━━━━━━━━━━━
"""

def format_result_ui(period, number, actual_size, result, pred, range_pred):
    if result=="WIN":
        emoji,text,bg = "✅","WIN 🎉","🟢"
    else:
        emoji,text,bg = "❌","LOSS 😞","🔴"
    actual_emoji = "🐘" if actual_size=="BIG" else "🐭"
    return f"""
{emoji} {text}  {bg}
━━━━━━━━━━━━━━━━━━━━━━
📊 RESULT
━━━━━━━━━━━━━━━━━━━━━━
📅 PERIOD    : {period}
🎯 PREDICT   : {pred}
✅ ACTUAL    : {actual_emoji} {actual_size} [{number}]
📊 RANGE     : {range_pred}
━━━━━━━━━━━━━━━━━━━━━━
"""

def format_profile(user_info):
    return f"""
🧑‍💼 *Profile*
━━━━━━━━━━━━━━━━━━━━━━
👤 Name      : {user_info.get('Name','')}
📛 Username  : @{user_info.get('Username','')}
🆔 ID        : {user_info.get('Telegram ID','')}
🔢 UID       : {user_info.get('UID','')}
⏳ Expired   : {user_info.get('Expired (Date and Time)','')}
━━━━━━━━━━━━━━━━━━━━━━
"""

def format_first_last_ui(first_two, last_two):
    text = "📋 *Database Records (First 2 & Last 2)*\n"
    text += "━"*30 + "\n🔹 *First 2:*\n"
    for row in first_two:
        text += f"📅 `{row[0]}` | 🎯 {row[1]} | 📊 {row[2]} | 🧠 {row[3]} | 🏁 {row[4]} | 🎚 {row[5]}\n"
    text += "\n🔸 *Last 2:*\n"
    for row in last_two:
        text += f"📅 `{row[0]}` | 🎯 {row[1]} | 📊 {row[2]} | 🧠 {row[3]} | 🏁 {row[4]} | 🎚 {row[5]}\n"
    text += f"\n👑 *Admin IDs:* {', '.join(str(i) for i in ADMIN_USER_IDS)}\n" + "━"*30
    return text

# ==================== PREDICTOR CLASS ====================
class Predictor:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.history = deque(maxlen=300)
        self.wins = 0
        self.losses = 0
        self.streak = 0
        self.best_streak = 0
        self.total_predictions = 0
        self.running = False
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
            ts = int(time.time()*1000)
            data = http_get_json(API_URL.format(ts))
            return data.get("data",{}).get("list",[]) if data else []
        except: return []

    # ... indicators and predict_size() remain identical to previous code ...
    # (I'll include the full predict_size() for completeness)
    def ma(self, data, w):
        if len(data)>=w: return sum(data[-w:])/w
        return sum(data)/len(data) if data else 0

    def rsi(self, data, w=14):
        if len(data)<w+1: return 50
        g=l=0
        for i in range(1,w+1):
            d = data[-i]-data[-i-1]
            if d>0: g+=d
            else: l+=abs(d)
        if l==0: return 100
        return 100 - (100/(1+(g/l)))

    def std_dev(self, data, w=20):
        if len(data)<w: return 0
        recent=data[-w:]
        mean=sum(recent)/w
        return math.sqrt(sum((x-mean)**2 for x in recent)/w)

    def predict_size(self):
        hist=list(self.history)
        if len(hist)<20:
            return "BIG",60,"5 • 9","BULLISH",50,"LOW","NEUTRAL","STABLE",50,50

        last=hist[-1]; last_size="BIG" if last>=5 else "SMALL"

        # fixed specials (corrected)
        specials={0:("SMALL",99,"0 • 2"),4:("SMALL",99,"3 • 5"),
                  5:("BIG",99,"5 • 7"),9:("SMALL",99,"7 • 9")}
        if last in specials:
            s=specials[last]; return s[0],s[1],s[2],"BULLISH",70,"LOW","SPECIAL","STABLE",90,10

        streak=1
        for i in range(len(hist)-2,-1,-1):
            if (hist[i]>=5)==(last>=5): streak+=1
            else: break

        def is_alt(l):
            if len(hist)<l: return False
            for i in range(1,l):
                if (hist[-i]>=5)==(hist[-i-1]>=5): return False
            return True

        def get_range(pred_type):
            recent=hist[-20:]
            nums=[x for x in recent if (x>=5)==(pred_type=="BIG")]
            if len(nums)>=2:
                top=Counter(nums).most_common(2)
                return f"{top[0][0]} • {top[1][0]}"
            return "5 • 9" if pred_type=="BIG" else "0 • 4"

        if streak>=5:
            pred=last_size; conf=99; rng=get_range(pred)
            return pred,conf,rng,"STRONG BULLISH",72,"LOW","DRAGON","STABLE",95,5
        if streak==4:
            pred=last_size; conf=97; rng=get_range(pred)
            return pred,conf,rng,"BULLISH",68,"LOW","4-STREAK","STABLE",90,10
        if streak==3:
            pred="SMALL" if last_size=="BIG" else "BIG"; conf=90; rng=get_range(pred)
            return pred,conf,rng,"BEARISH",55,"MEDIUM","3-STREAK BREAK","UNSTABLE",75,25
        if streak==2:
            pred="SMALL" if last_size=="BIG" else "BIG"; conf=85; rng=get_range(pred)
            return pred,conf,rng,"NEUTRAL",52,"MEDIUM","2-STREAK BREAK","STABLE",70,30
        if is_alt(8):
            pred="SMALL" if last_size=="BIG" else "BIG"; conf=92; rng=get_range(pred)
            return pred,conf,rng,"BULLISH",65,"LOW","ALTERNATING 8","STABLE",85,15
        if is_alt(6):
            pred="SMALL" if last_size=="BIG" else "BIG"; conf=88; rng=get_range(pred)
            return pred,conf,rng,"BULLISH",60,"LOW","ALTERNATING 6","STABLE",80,20
        if is_alt(5):
            pred=last_size; conf=85; rng=get_range(pred)
            return pred,conf,rng,"NEUTRAL",55,"MEDIUM","TRAP","STABLE",72,28

        ma5=self.ma(hist,5); ma10=self.ma(hist,10); ma20=self.ma(hist,20)
        ma_trend="BULLISH" if ma5>ma10>ma20 else "BEARISH" if ma5<ma10<ma20 else "NEUTRAL"
        rsi_val=self.rsi(hist,14)
        rsi_trend="BULLISH" if rsi_val<30 else "BEARISH" if rsi_val>70 else "NEUTRAL"
        recent_30=hist[-30:] if len(hist)>=30 else hist
        big_c=sum(1 for x in recent_30 if x>=5)
        small_c=len(recent_30)-big_c
        std=self.std_dev(hist,20)
        std_text="LOW" if std<1.5 else "MEDIUM" if std<2.5 else "HIGH"
        votes={"BIG":0,"SMALL":0}
        votes["SMALL" if last_size=="BIG" else "BIG"]+=1
        if ma_trend=="BULLISH": votes["BIG"]+=3
        elif ma_trend=="BEARISH": votes["SMALL"]+=3
        if rsi_trend=="BULLISH": votes["BIG"]+=2
        elif rsi_trend=="BEARISH": votes["SMALL"]+=2
        if big_c>small_c+3: votes["SMALL"]+=2
        elif small_c>big_c+3: votes["BIG"]+=2
        pred=max(votes,key=votes.get)
        total=sum(votes.values()); diff=votes[pred]-(total-votes[pred])
        conf=92 if diff>=4 else 85 if diff>=2 else 70
        big_pct=int(votes["BIG"]/total*100) if total else 50
        small_pct=int(votes["SMALL"]/total*100) if total else 50
        pattern_text="ALTERNATING" if is_alt(4) else "RANDOM"
        cycle_text="STABLE" if std<1.5 else "UNSTABLE"
        rng=get_range(pred)
        return pred,conf,rng,ma_trend,rsi_val,std_text,pattern_text,cycle_text,big_pct,small_pct

    def get_next_prediction(self):
        size,conf,rng,ma,rsi,std,pattern,cycle,big_pct,small_pct=self.predict_size()
        return {"size":size,"confidence":conf,"range":rng,"ma":ma,"rsi":rsi,"std":std,
                "pattern":pattern,"cycle":cycle,"big_pct":big_pct,"small_pct":small_pct}

    def update_result(self, won):
        if won: self.wins+=1; self.streak+=1; self.best_streak=max(self.best_streak,self.streak)
        else: self.losses+=1; self.streak=0
        self.total_predictions+=1

    def send_message(self, text):
        if self.chat_id:
            try: http_post_json(TELEGRAM_API+"sendMessage",
                                {"chat_id":self.chat_id,"text":text,"parse_mode":"Markdown"})
            except: pass

    def start_loop(self):
        if self.running: return
        self.running=True
        threading.Thread(target=self._loop,daemon=True).start()

    def stop_loop(self):
        self.running=False

    def _loop(self):
        seen=set(); current_prediction=None
        while self.running:
            try:
                data=self.fetch_data()
                if not data: time.sleep(1); continue
                latest=data[0]; period=latest.get("issueNumber","")
                try: number=int(latest.get("number",""))
                except: number=None
                if not period or not period.isdigit(): time.sleep(1); continue
                if period not in seen:
                    if number is not None: self.update(number,period)
                    seen.add(period)
                    next_period=str(int(period)+1)
                    pred_data=self.get_next_prediction()
                    if pred_data["confidence"]>=85:
                        current_prediction={"period":next_period,"size":pred_data["size"],"range":pred_data["range"]}
                        self.send_message(format_prediction_ui(pred_data,next_period))
                if current_prediction and current_prediction["period"]==period and number is not None:
                    actual_size="BIG" if number>=5 else "SMALL"
                    won=(actual_size==current_prediction["size"])
                    res="WIN" if won else "LOSS"
                    self.update_result(won)
                    self.update(number,period,prediction=current_prediction["size"],
                                result=res,range_pred=current_prediction["range"])
                    self.send_message(format_result_ui(period,number,actual_size,res,
                                                       current_prediction["size"],current_prediction["range"]))
                    current_prediction=None
                time.sleep(1)
            except Exception as e:
                print("Loop error:",e); time.sleep(2)

# ==================== BOT HANDLER ====================
predictors = {}   # chat_id -> Predictor instance
last_update_id = 0

def get_updates(offset=None):
    url = TELEGRAM_API + "getUpdates"
    params = {"timeout":30}
    if offset: params["offset"]=offset
    try:
        full_url = url + "?" + urllib.parse.urlencode(params)
        data = http_get_json(full_url, timeout=35)
        return data.get("result",[]) if data else []
    except: return []

def process_message(chat_id, user_id, text=None):
    """Handle /start and /show_data commands."""
    if text == "/start":
        status, info = get_user_info(user_id)
        if status == "not_found":
            http_post_json(TELEGRAM_API+"sendMessage",
                           {"chat_id":chat_id,"text":"⛔ You are not authorized! Contact admin.","parse_mode":"Markdown"})
            return
        elif status == "deactive":
            http_post_json(TELEGRAM_API+"sendMessage",
                           {"chat_id":chat_id,"text":"🚫 Your account has been deactivated. Contact admin.","parse_mode":"Markdown"})
            return
        # Active user: show welcome with dynamic buttons
        name = info.get("Name","User")
        is_admin = user_id in ADMIN_USER_IDS
        buttons = [
            [{"text":"▶️ START","callback_data":"start"}],
            [{"text":"⏹ STOP","callback_data":"stop"}],
            [{"text":"📊 STATUS","callback_data":"status"}],
            [{"text":"👤 PROFILE","callback_data":"profile"}]
        ]
        if is_admin:
            buttons.append([{"text":"📊 SHOW DATA","callback_data":"show_data"}])
        else:
            buttons.append([{"text":"📞 CONTACT","url":"https://t.me/your_username"}])  # 🔁 update
        http_post_json(TELEGRAM_API+"sendMessage",{
            "chat_id":chat_id,
            "text":f"🤖 Predictor v1.0.0\nWelcome {name}\n\nUse buttons below.",
            "reply_markup":{"inline_keyboard":buttons},
            "parse_mode":"Markdown"
        })

    elif text == "/show_data":
        if user_id not in ADMIN_USER_IDS:
            http_post_json(TELEGRAM_API+"sendMessage",
                           {"chat_id":chat_id,"text":"⛔ This feature is for admins only.","parse_mode":"Markdown"})
            return
        first_two, last_two = get_first_and_last()
        if not first_two and not last_two:
            resp = "⚠️ No data collected yet."
        else:
            resp = format_first_last_ui(first_two, last_two)
        http_post_json(TELEGRAM_API+"sendMessage",{"chat_id":chat_id,"text":resp,"parse_mode":"Markdown"})

def process_callback(chat_id, user_id, data):
    """Handle inline button presses."""
    # First check user status from sheet
    status, info = get_user_info(user_id)
    if status == "not_found":
        http_post_json(TELEGRAM_API+"sendMessage",
                       {"chat_id":chat_id,"text":"⛔ You are not authorized! Contact admin.","parse_mode":"Markdown"})
        return
    elif status == "deactive":
        http_post_json(TELEGRAM_API+"sendMessage",
                       {"chat_id":chat_id,"text":"🚫 Your account has been deactivated. Contact admin.","parse_mode":"Markdown"})
        return

    # Get or create per-chat predictor
    if chat_id not in predictors:
        predictors[chat_id] = Predictor(chat_id)
    pred = predictors[chat_id]

    if data == "start":
        if not pred.running:
            pred.start_loop()
            pred.send_message("✅ Prediction started! (LEVEL 1-2: >=85%)")
        else:
            pred.send_message("⏳ Already running...")
    elif data == "stop":
        pred.stop_loop()
        pred.send_message("⏹ Stopped.")
    elif data == "status":
        stats = f"📊 *Statistics*\n✅ Wins: {pred.wins}\n❌ Losses: {pred.losses}\n🔥 Streak: {pred.streak}\n🏆 Best Streak: {pred.best_streak}\n📈 Total: {pred.total_predictions}"
        pred.send_message(stats)
    elif data == "profile":
        if info:
            pred.send_message(format_profile(info))
        else:
            pred.send_message("Profile not found.")
    elif data == "show_data":
        if user_id not in ADMIN_USER_IDS:
            pred.send_message("⛔ This feature is for admins only.")
            return
        first_two, last_two = get_first_and_last()
        if not first_two and not last_two:
            resp = "⚠️ No data collected yet."
        else:
            resp = format_first_last_ui(first_two, last_two)
        pred.send_message(resp)

def main():
    global last_update_id
    print("Bot started with Google Sheets authorization and per-user sessions.")
    while True:
        try:
            updates = get_updates(last_update_id+1 if last_update_id else None)
            for upd in updates:
                last_update_id = upd["update_id"]
                if "message" in upd:
                    msg = upd["message"]
                    chat_id = msg["chat"]["id"]
                    user_id = msg["from"]["id"]
                    text = msg.get("text","")
                    process_message(chat_id, user_id, text)
                elif "callback_query" in upd:
                    cb = upd["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    user_id = cb["from"]["id"]
                    data = cb["data"]
                    http_post_json(TELEGRAM_API+"answerCallbackQuery",{"callback_query_id":cb["id"]})
                    process_callback(chat_id, user_id, data)
            time.sleep(1)
        except Exception as e:
            print("Main error:",e)
            time.sleep(5)

if __name__ == "__main__":
    main()