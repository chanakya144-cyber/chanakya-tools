from flask import Flask, render_template, request, redirect, flash
import sqlite3, os, json, requests
from datetime import datetime
from werkzeug.utils import secure_filename
from tool_utils import generate_tool_code
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sms_utils import log_sms, get_sms_logs, init_sms_db

app = Flask(__name__)
app.secret_key = "chanakya_nirman_secret_123"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

API_KEY = "qxqimzPJaf3dubFwzclrLDnEPUN5oA"
SENDER_ID = "CNIRMN"
API_URL = "https://api.aoc-portal.com/v1/sms"
HEADERS = {"apikey": API_KEY, "Content-Type": "application/json"}

DLT_TEMPLATES = {
    "ISSUED_USER": "1177178964041755626",
    "ISSUED_DIR": "1177179058639094372",
    "WEEKLY_REM": "1177179058667607210",
    "CONFIRM_DIR": "1177179058695523666",
    "MISSING_USER": "1177179058733710404",
    "MISSING_DIR": "1177179058763101113",
    "RETURNED_STORE": "1177179058785640474",
    "RETURNED_DIR": "1177179058813167740",
}
DIRECTOR_FILE = 'directors.json'
if not os.path.exists(DIRECTOR_FILE):
    with open(DIRECTOR_FILE, 'w') as f: json.dump(["7356898431"], f)

def get_directors():
    try:
        with open(DIRECTOR_FILE, 'r') as f: 
            dirs = json.load(f)
            # ഫയലിൽ ഉള്ള നമ്പറുകളിൽ നിന്ന് അവസാന 10 അക്കം മാത്രം ക്ലീൻ ചെയ്ത് എടുക്കുന്നു
            cleaned = []
            for d in dirs:
                digits = ''.join(filter(str.isdigit, str(d)))
                if len(digits) >= 10:
                    cleaned.append(digits[-10:])
            return cleaned
    except: return []
def get_db(): return sqlite3.connect('chanakya_tools.db')

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tools (id INTEGER PRIMARY KEY AUTOINCREMENT, tool_name TEXT, brand_name TEXT, tool_group TEXT, tool_code TEXT UNIQUE, image_url TEXT, status TEXT DEFAULT 'In Store', current_person TEXT, current_site TEXT, item_type TEXT DEFAULT 'unique', total_qty INTEGER DEFAULT 1, available_qty INTEGER DEFAULT 1, is_confirmed INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, person_name TEXT, staff_phone TEXT, tool_id INTEGER, action_type TEXT, site_name TEXT, date TEXT, qty INTEGER DEFAULT 1, remarks TEXT)''')
    
    # ✅ നിലവിലുള്ള ടേബിളിൽ is_confirmed കോളം ഇല്ലെങ്കിൽ അത് ആഡ് ചെയ്യാൻ ഇത് ചേർക്കുക
    try:
        c.execute("ALTER TABLE tools ADD COLUMN is_confirmed INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        pass # കോളം നേരത്തെ തന്നെ ഉണ്ടെങ്കിൽ എറർ വരാതെ ഇത് ഒഴിവാക്കിക്കൊള്ളും

    conn.close()
    try:
        init_sms_db() # SMS Log Table Create ചെയ്യാൻ
    except Exception as e:
        print(f"SMS DB Init Error: {e}")

def send_vi_sms(mobile, template_id, full_message, tool_code=""):
    mob = ''.join(filter(str.isdigit, str(mobile)))[-10:]
    if len(mob)!=10: return False
    payload = {"sender": SENDER_ID, "to": "91"+mob, "text": full_message, "type": "TRANS", "templateId": template_id}
    try: 
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)
        status = "Success" if r.status_code == 200 else "Failed"
        log_sms(tool_code, mob, full_message, status) # <--- ലോഗ് ഡാറ്റാബേസിൽ സേവ് ചെയ്യുന്നു
        print(f"SMS OK to 91{mob} : {r.text}")
        return r.json()
    except Exception as e: 
        log_sms(tool_code, mob, full_message, "Failed")
        return {"error": str(e)}

def send_to_directors(template_key, full_message, tool_code=""):
    directors = get_directors()
    # എസ്എംഎസ് അയക്കുമ്പോൾ നമ്പറുകളുടെ മുന്നിൽ '91' ഓട്ടോമാറ്റിക് ആയി ചേർക്കുന്നു
    to_list = ",".join(["91" + d for d in directors if len(d) == 10])
    if not to_list:
        return {"error": "No valid director numbers found"}
    payload = {"sender": SENDER_ID, "to": to_list, "text": full_message, "type": "TRANS", "templateId": DLT_TEMPLATES[template_key]}
    try: 
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
        status = "Success" if r.status_code == 200 else "Failed"
        log_sms(tool_code, "Directors", full_message, status) # <--- ഡയറക്ടേഴ്സിനുള്ള ലോഗ് സേവ് ചെയ്യുന്നു
        print(f"SMS OK to Directors : {r.text}")
        return r.json()
    except Exception as e: 
        log_sms(tool_code, "Directors", full_message, "Failed")
        return {"error": str(e)}

# ===== 8 TEMPLATE SMS FUNCTIONS - 100% DLT MATCH =====
def sms_issue(person, tool, code, site, staff_phone):
    msg_dir = f"Info: Mr. {person} has taken {tool} with ID {code} for {site} site. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
    send_to_directors("ISSUED_DIR", msg_dir, code) # <--- ഇവിടെ code ചേർക്കുക
    if staff_phone:
        msg_user = f"Dear {person}, You have received {tool} with ID {code} for {site} site. Responsibility is yours till return to office. Inform office if moved to other site. Team Chanakya Nirman Pvt Ltd"
        send_vi_sms(staff_phone, DLT_TEMPLATES["ISSUED_USER"], msg_user, code) # <--- ഇവിടെയും code ചേർക്കുക
        
def sms_return(person, tool, code, site, date_str, staff_phone):
    # ഡയറക്ടർമാർക്ക് പോകുന്ന അപ്ഡേറ്റ് മെസ്സേജ്
    msg_dir = f"Update: Mr. {person} has successfully returned {tool} with ID {code} for {site} site to the office on {date_str}. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
    send_to_directors("RETURNED_DIR", msg_dir, code) # <--- ഇവിടെ code ചേർക്കുക
    
    # ടൂൾ തിരികെ കൊണ്ടുവന്ന സ്റ്റാഫിന്റെ നമ്പറിലേക്ക് പോകുന്ന കൺഫർമേഷൻ മെസ്സേജ്
    if staff_phone:
        msg_user = f"Dear {person}, {tool} with ID {code} issued for {site} site has been returned to office/store on {date_str}. Thank you. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
        send_vi_sms(staff_phone, DLT_TEMPLATES["RETURNED_STORE"], msg_user, code) # <--- ഇവിടെയും code ചേർക്കുക
# === WEEKLY REMINDER & SMS FUNCTIONS ===
def sms_weekly_reminder(person, tool, code, site, staff_phone, tool_id):
    if staff_phone:
        domain = "https://chanakya-tools.onrender.com"  # നിന്റെ site name
        link_yes = f"{domain}/confirm_tool/{tool_id}/yes"
        link_no = f"{domain}/confirm_tool/{tool_id}/no"
        msg_user = f"Dear {person}, Reminder: {tool} ({code}) at {site}? YES:{link_yes} NO:{link_no} -Team Chanakya Nirman"
        send_vi_sms(staff_phone, DLT_TEMPLATES["WEEKLY_REM"], msg_user, code)

def sms_confirm_director(person, date_str, tool, code, site):
    msg_dir = f"Mr. {person} has confirmed on {date_str} that {tool} with ID {code} taken for {site} site is available at {site} site. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
    send_to_directors("CONFIRM_DIR", msg_dir, code)

def sms_missing_flow(person, tool, code, site, staff_phone):
    if staff_phone:
        msg_user = f"Dear {person}, we noticed that you replied NO for {tool} with ID {code} issued for {site} site. If it is lost or misplaced, please inform the store manager immediately. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
        send_vi_sms(staff_phone, DLT_TEMPLATES["MISSING_USER"], msg_user, code) # <--- ഇവിടെ code ചേർക്കുക
    
    msg_dir = f"Alert: Mr. {person} has replied NO for {tool} with ID {code} issued for {site} site. Please verify regarding the missing tool. Team Chanakya Nirman Pvt Ltd -CHANAKYA NIRMAN PRIVATE LIMITED"
    send_to_directors("MISSING_DIR", msg_dir, code) # <--- ഇവിടെയും code ചേർക്കുക

# === BACKGROUND JOB: ഓരോ 10 മിനിറ്റിലും മറുപടി ലഭിക്കാത്തവർക്ക് റിമൈൻഡർ അയക്കുന്നു ===
def check_and_send_reminders():
    conn = get_db()
    c = conn.cursor()
    # സ്റ്റാറ്റസ് 'Issued' ആയതും ഇതുവരെ YES/NO മറുപടി നൽകാത്തതുമായ ടൂളുകൾ മാത്രം എടുക്കുന്നു
    c.execute("SELECT t.id, t.person_name, t.staff_phone, t.tool_id, t.site_name, tl.tool_name, tl.tool_code FROM transactions t JOIN tools tl ON tl.id=t.tool_id WHERE t.action_type='Issue Tool' AND tl.status='Issued' AND tl.is_confirmed=0")
    active_issues = c.fetchall()
    conn.close()

    for issue in active_issues:
        trans_id, person, phone, tool_id, site, tool_name, tool_code = issue
        if phone:
            # ഓരോ 10 മിനിറ്റ് കൂടുമ്പോൾ റിമൈൻഡർ എസ്എംഎസ് അയക്കുന്നു
            sms_weekly_reminder(person, tool_name, tool_code, site, phone, tool_id)

# ഷെഡ്യൂളർ സ്റ്റാർട്ട് ചെയ്യുന്നു (ഓരോ 10 മിനിറ്റിലും റൺ ചെയ്യാൻ)
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=check_and_send_reminders, 
    trigger=CronTrigger(day_of_week='sat', hour='10', minute='0')
)
scheduler.start()

@app.route('/sms_history')
def sms_history():
    tool_code = request.args.get('tool_code')
    logs = get_sms_logs(tool_code)
    return render_template('sms_history.html', logs=logs, selected_tool=tool_code)

@app.route('/')
def index():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT COUNT(*) FROM tools"); total=c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM tools WHERE status='Issued'"); issued=c.fetchone()[0] or 0
    
    # സ്റ്റാറ്റസ് 'In Store' ഉള്ള ടൂളുകളുടെ എണ്ണം അല്ലെങ്കിൽ available_qty-യുടെ കൃത്യമായ കണക്ക് എടുക്കുന്നു
    c.execute("SELECT SUM(CASE WHEN status='In Store' THEN available_qty ELSE 0 END) FROM tools")
    avail_res = c.fetchone()[0]
    avail = avail_res if avail_res is not None else 0
    
    c.execute("SELECT * FROM tools ORDER BY id DESC"); all_tools=c.fetchall()
    c.execute("SELECT t.id, tl.tool_name, t.qty, t.person_name, tl.tool_code, t.site_name, t.date, tl.id, t.staff_phone FROM transactions t JOIN tools tl ON tl.id=t.tool_id WHERE t.action_type='Issue Tool' ORDER BY t.id DESC LIMIT 100"); issued_tools=c.fetchall()
    conn.close()
    return render_template('index.html', active_page='dashboard', total_tools=total, tools_issued=issued, available_store=avail, all_tools=all_tools, all_tools_list=all_tools, available_tools=all_tools, issued_tools=issued_tools)
@app.route('/tools')
def tools_list():
    conn=get_db(); c=conn.cursor(); c.execute("SELECT * FROM tools ORDER BY id DESC"); all_tools=c.fetchall(); conn.close()
    return render_template('index.html', active_page='tools', all_tools=all_tools, all_tools_list=all_tools, available_tools=all_tools, issued_tools=[], total_tools=len(all_tools), tools_issued=0, available_store=0)

@app.route('/edit_tool/<int:tool_id>', methods=['GET', 'POST'])
def edit_tool(tool_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM tools WHERE id=?", (tool_id,)); tool = c.fetchone()
    if not tool: conn.close(); return redirect('/tools')
    if request.method == 'POST':
        tool_name = request.form.get('tool_name')
        brand_name = request.form.get('brand_name')
        tool_group = request.form.get('tool_group')
        tool_code = request.form.get('tool_code')
        total_qty = int(request.form.get('total_qty', 1) or 1)

        # total_qty യും available_qty യും ഒരുമിച്ച് Update ചെയ്യുന്നു - ഇതാണ് ശരി!
        c.execute("UPDATE tools SET tool_name=?, brand_name=?, tool_group=?, tool_code=?, total_qty=?, available_qty=? WHERE id=?",
          (tool_name, brand_name, tool_group, tool_code, total_qty, total_qty, tool_id))
        conn.commit(); conn.close(); return redirect('/tools')
    conn.close()
    try: return render_template('edit_tool.html', tool=tool, active_page='tools')
    except: return f"<h2>Edit Tool: {tool[1]} - {tool[4]}</h2><form method='POST'><input name='tool_name' value='{tool[1]}'><input name='tool_code' value='{tool[4]}'><button>Save</button></form><a href='/tools'>Back</a>"
@app.route('/add_tool', methods=['GET', 'POST'])
def add_tool():
    if request.method == 'POST':
        tool_name = request.form.get('tool_name')
        brand_name = request.form.get('brand_name')
        tool_group = request.form.get('tool_group')
        item_type = request.form.get('item_type', 'unique')
        total_qty = int(request.form.get('total_qty', 1) or 1)
        
        # ഇവിടെ യൂസർ നൽകിയ കോഡിന് പകരം ഓട്ടോമാറ്റിക് കോഡ് ജനറേറ്റ് ചെയ്യുന്നു
        # ഇവിടെ get_db() എന്നതിന് പകരം get_db എന്ന് മാത്രം നൽകുക
        tool_code = generate_tool_code(get_db, tool_name, tool_group)
        
        image_url = ""
        if 'tool_image' in request.files:
            file = request.files['tool_image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{tool_code}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f"/static/uploads/{filename}"
                
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO tools (tool_name, brand_name, tool_group, tool_code, image_url, item_type, total_qty, available_qty, status) VALUES (?,?,?,?,?,?,?,?,?)",
                      (tool_name, brand_name, tool_group, tool_code, image_url, item_type, total_qty, total_qty, 'In Store'))
            conn.commit()
        except Exception as e:
            print("Error inserting tool:", e)
        conn.close()
        return redirect('/')
    return render_template('add_tool.html', active_page='add_tool')

@app.route('/issue_tool', methods=['POST'])
def issue_tool():
    tool_id = request.form.get('tool_id')
    person_name = request.form.get('issued_to')
    site_name = request.form.get('site_name')
    staff_phone = request.form.get('staff_phone', '')
    issue_qty = int(request.form.get('issue_qty', 1) or 1)
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM tools WHERE id=?", (tool_id,)); tool = c.fetchone()
    if not tool: conn.close(); return redirect('/')
    tool_name_db = tool[1]; tool_code_db = tool[4]
    current_avail = tool[11] if len(tool) > 11 else 1
    new_avail = max(0, current_avail - issue_qty)
    c.execute("UPDATE tools SET status='Issued', current_person=?, current_site=?, available_qty=?, is_confirmed=0 WHERE id=?",
              (person_name, site_name, new_avail, tool_id))
    c.execute("INSERT INTO transactions (person_name, staff_phone, tool_id, action_type, site_name, date, qty) VALUES (?,?,?,?,?,?,?)",
              (person_name, staff_phone, tool_id, 'Issue Tool', site_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), issue_qty))
    conn.commit(); conn.close()
    sms_issue(person_name, tool_name_db, tool_code_db, site_name, staff_phone)
    return redirect('/')

@app.route('/return_tool', methods=['POST'])
def return_tool_post():
    issue_id = request.form.get('issue_id')
    if not issue_id:
        return redirect('/')
        
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id=?", (issue_id,))
    trans = c.fetchone()
    if not trans: 
        conn.close()
        return redirect('/')
    
    person_name = trans[1]
    staff_phone = trans[2]
    tool_id = trans[3]
    site_name = trans[5]
    issued_qty = trans[7] if len(trans) > 7 else 1
    
    c.execute("SELECT * FROM tools WHERE id=?", (tool_id,))
    tool = c.fetchone()
    if tool:
        tool_name_db = tool[1]
        tool_code_db = tool[4]
        current_avail = tool[11] if len(tool) > 11 else 1
        total_qty = tool[10] if len(tool) > 10 else 1
        
        # available_qty അപ്ഡേറ്റ് ചെയ്യുന്നു
        new_avail = min(total_qty, current_avail + issued_qty)
        c.execute("UPDATE tools SET status='In Store', current_person='', current_site='', available_qty=?, is_confirmed=0 WHERE id=?", (new_avail, tool_id))
    else:
        tool_name_db = "Tool"
        tool_code_db = ""
    
    # റിട്ടേൺ ട്രാൻസാക്ഷൻ സേവ് ചെയ്യുന്നു
    c.execute("INSERT INTO transactions (person_name, staff_phone, tool_id, action_type, site_name, date, qty) VALUES (?,?,?,?,?,?,?)",
              (person_name, staff_phone, tool_id, 'Return Tool', site_name, datetime.now().strftime('%d/%m/%Y %I:%M%p'), issued_qty))
    
    conn.commit(); conn.close()
    
    date_str = datetime.now().strftime('%d/%m/%Y %I:%M%p')
    sms_return(person_name, tool_name_db, tool_code_db, site_name, date_str, staff_phone)
    return redirect('/')

@app.route('/return_tool/<int:issue_id>')
def return_tool_get(issue_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id=?", (issue_id,))
    trans = c.fetchone()
    if not trans:
        conn.close(); return redirect('/')

    person_name = trans[1]
    staff_phone = trans[2]
    tool_id = trans[3]
    site_name = trans[5]
    issued_qty = trans[7] if len(trans) > 7 else 1

    c.execute("SELECT * FROM tools WHERE id=?", (tool_id,))
    tool = c.fetchone()
    if tool:
        tool_name_db = tool[1]
        tool_code_db = tool[4]
        current_avail = tool[11] if len(tool) > 11 else 1
        total_qty = tool[10] if len(tool) > 10 else 1
        new_avail = min(total_qty, current_avail + issued_qty)
        # ✅ ഇവിടെ is_confirmed=0 Add ചെയ്തു - ഇതാണ് Main Fix!
        c.execute("UPDATE tools SET status='In Store', current_person='', current_site='', available_qty=?, is_confirmed=0 WHERE id=?", (new_avail, tool_id))
    else:
        tool_name_db = "Tool"
        tool_code_db = ""

    c.execute("INSERT INTO transactions (person_name, staff_phone, tool_id, action_type, site_name, date, qty) VALUES (?,?,?,?,?,?,?)",
              (person_name, staff_phone, tool_id, 'Return Tool', site_name, datetime.now().strftime('%d/%m/%Y %I:%M%p'), issued_qty))

    conn.commit(); conn.close()

    date_str = datetime.now().strftime('%d/%m/%Y %I:%M%p')
    sms_return(person_name, tool_name_db, tool_code_db, site_name, date_str, staff_phone)
    return redirect('/')
@app.route('/sms_webhook', methods=['GET', 'POST'])
def sms_webhook():
    # ഗേറ്റ്‌വേ അയക്കുന്ന ഡാറ്റ (Query parameters അല്ലെങ്കിൽ Form data ആയി വരാം)
    incoming_phone = request.values.get('phone') or request.values.get('mobile') or request.values.get('sender')
    incoming_text = request.values.get('text') or request.values.get('message') or request.values.get('msg')
    
    if not incoming_phone or not incoming_text:
        return {"status": "error", "message": "Missing parameters"}, 400
    
    # ഫോൺ നമ്പർ ക്ലീൻ ചെയ്യുന്നു (അവസാന 10 അക്കം)
    mob = ''.join(filter(str.isdigit, str(incoming_phone)))[-10:]
    reply = incoming_text.strip().upper()
    
    conn = get_db()
    c = conn.cursor()
    # ഈ നമ്പറിൽ നിലവിൽ ഇഷ്യു ചെയ്തിരിക്കുന്ന ഏറ്റവും പുതിയ ടൂൾ കണ്ടെത്തുന്നു
    c.execute("SELECT t.id, t.person_name, t.staff_phone, t.tool_id, t.site_name, tl.tool_name, tl.tool_code FROM transactions t JOIN tools tl ON tl.id=t.tool_id WHERE t.staff_phone LIKE ? AND tl.status='Issued' ORDER BY t.id DESC LIMIT 1", (f"%{mob}%",))
    active_issue = c.fetchone()
    
    if not active_issue:
        conn.close() # ഇവിടെ കണക്ഷൻ ക്ലോസ് ചെയ്യുന്നു
        return {"status": "success", "message": "No active tool found for this number"}
    
    trans_id, person, phone, tool_id, site, tool_name, tool_code = active_issue
    date_str = datetime.now().strftime('%d/%m/%Y %I:%M%p')
    
    # --- പുതിയ മാറ്റം ഇവിടെ ചേർക്കുക ---
    # സ്റ്റാഫ് മറുപടി നൽകിയാൽ വീണ്ടും മെസ്സേജ് വരാതിരിക്കാൻ is_confirmed = 1 ആക്കുന്നു
    c.execute("UPDATE tools SET is_confirmed=1 WHERE id=?", (tool_id,))
    conn.commit()
    
    if "YES" in reply:
        # സ്റ്റാഫ് 'YES' എന്ന് മറുപടി നൽകിയാൽ
        sms_confirm_director(person, date_str, tool_name, tool_code, site)
    elif "NO" in reply:
        # സ്റ്റാഫ് 'NO' എന്ന് മറുപടി നൽകിയാൽ (മിസ്സിംഗ് അലേർട്ട്)
        sms_missing_flow(person, tool_name, tool_code, site, phone)
        
    conn.close() # എല്ലാ ജോലികളും കഴിഞ്ഞ ശേഷം ഇവിടെ കണക്ഷൻ ക്ലോസ് ചെയ്യുന്നു
    return {"status": "success", "message": "Webhook processed successfully"}

@app.route('/delete_tool/<int:tool_id>')
def delete_tool(tool_id):
    conn=get_db(); c=conn.cursor()
    c.execute("DELETE FROM tools WHERE id=?",(tool_id,))
    c.execute("DELETE FROM transactions WHERE tool_id=?",(tool_id,))
    conn.commit(); conn.close()
    return redirect('/tools')

# === SINGLE SETTINGS ROUTE - DUPLICATE FIXED ===
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    directors = get_directors()
    if request.method == 'POST':
        action = request.form.get('action')
        mobile = request.form.get('mobile', '').strip()
        mobile = ''.join(filter(str.isdigit, mobile))[-10:] # അവസാന 10 അക്കം മാത്രം എടുക്കുന്നു
        
        if action == 'add' and len(mobile) == 10:
            if mobile not in directors:
                directors.append(mobile)
                with open('directors.json', 'w') as f: 
                    json.dump(directors, f)
                flash("Director added successfully! ✅")
        elif action == 'remove':
            if mobile in directors:
                directors.remove(mobile)
                with open('directors.json', 'w') as f: 
                    json.dump(directors, f)
                flash("Director removed successfully! ❌")
        return redirect('/settings')
        
    return render_template('settings.html', directors=directors, active_page='settings')

@app.route('/settings/directors')
@app.route('/settings/directors/<path:dummy>')
def settings_directors_fix(dummy=None):
    return redirect('/settings')
@app.route('/confirm_tool/<int:tool_id>/<string:action>')
def confirm_tool(tool_id, action):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT t.id, t.person_name, t.staff_phone, t.site_name, tl.tool_name, tl.tool_code FROM transactions t JOIN tools tl ON tl.id=t.tool_id WHERE t.tool_id=? AND tl.status='Issued' ORDER BY t.id DESC LIMIT 1", (tool_id,))
    active_issue = c.fetchone()
    
    if not active_issue:
        conn.close()
        return "<h3>ഈ ടൂൾ നിലവിൽ ഇഷ്യു ചെയ്തിട്ടില്ല അല്ലെങ്കിൽ ലിങ്ക് എക്സ്പയർ ആയിരിക്കുന്നു.</h3>"
    
    trans_id, person, phone, site, tool_name, tool_code = active_issue
    date_str = datetime.now().strftime('%d/%m/%Y %I:%M%p')
    
    # സ്റ്റാഫ് മറുപടി നൽകിയ സ്ഥിതിക്ക് ടൂൾ കൺഫേം ചെയ്തതായി അപ്ഡേറ്റ് ചെയ്യുന്നു
    c.execute("UPDATE tools SET is_confirmed=1 WHERE id=?", (tool_id,))
    conn.commit()
    conn.close()
    
    action_upper = action.upper()
    if action_upper == "YES":
        sms_confirm_director(person, date_str, tool_name, tool_code, site)
        return "<h3>നന്ദി! ടൂൾ സൈറ്റിൽ ഉണ്ടെന്ന് വിജയകരമായി സ്ഥിരീകരിച്ചിരിക്കുന്നു. ✅</h3>"
    elif action_upper == "NO":
        sms_missing_flow(person, tool_name, tool_code, site, phone)
        return "<h3>മറുപടി സ്വീകരിച്ചിരിക്കുന്നു. ഓഫീസ് അധികൃതരെ വിവരം അറിയിച്ചിട്ടുണ്ട്. ⚠️</h3>"
    
    return "Invalid Request"
import os

if __name__ == '__main__':
    init_db()
    # Render തരുമ്പോൾ ആ PORT എ也将, അല്ലെങ്കിൽ ലോക്കലായി 5001 ഉപയോഗിക്കും
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
