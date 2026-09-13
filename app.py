import os, json, re, uuid, math
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from groq import Groq

st.set_page_config(page_title="PrimeFit AI", page_icon="🏋️", layout="wide", initial_sidebar_state="expanded")

# -------------------- CONFIG --------------------
def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return os.getenv(name, default)

SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_KEY = secret("SUPABASE_KEY")
GROQ_API_KEY = secret("GROQ_API_KEY")

@st.cache_resource(show_spinner=False)
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

@st.cache_resource(show_spinner=False)
def get_groq():
    if not GROQ_API_KEY: return None
    try: return Groq(api_key=GROQ_API_KEY)
    except Exception: return None

sb = get_supabase(); groq = get_groq()

# -------------------- STATE --------------------
if "theme" not in st.session_state: st.session_state.theme = "dark"
if "user" not in st.session_state: st.session_state.user = None
if "page" not in st.session_state: st.session_state.page = "Home"
if "workout_plan" not in st.session_state: st.session_state.workout_plan = None
if "meal_plan" not in st.session_state: st.session_state.meal_plan = None
if "demo_progress" not in st.session_state: st.session_state.demo_progress = []
if "messages" not in st.session_state: st.session_state.messages = []
if "admin_mode" not in st.session_state: st.session_state.admin_mode = False

# -------------------- THEME/UI --------------------
dark = st.session_state.theme == "dark"
bg = "#070B14" if dark else "#F5F7FB"; card = "#0F172A" if dark else "#FFFFFF"; text = "#F8FAFC" if dark else "#111827"; muted = "#94A3B8" if dark else "#64748B"; border = "rgba(148,163,184,.16)"; accent = "#38BDF8"; purple = "#8B5CF6"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{{font-family:Inter,sans-serif;background:{bg};color:{text}}}
.stApp{{background:{bg}}}.block-container{{max-width:1400px;padding-top:1rem}}
section[data-testid="stSidebar"]{{background:{'#0A1020' if dark else '#FFFFFF'};border-right:1px solid {border}}}
.pf-card{{background:{card};border:1px solid {border};border-radius:20px;padding:22px;box-shadow:0 12px 35px rgba(0,0,0,.10);transition:.2s}}
.pf-card:hover{{transform:translateY(-2px);box-shadow:0 18px 45px rgba(56,189,248,.08)}}
.hero{{padding:48px 20px;border-radius:28px;background:linear-gradient(135deg,rgba(56,189,248,.16),rgba(139,92,246,.13));border:1px solid {border};margin-bottom:20px}}
.grad{{background:linear-gradient(90deg,#38BDF8,#8B5CF6);-webkit-background-clip:text;background-clip:text;color:transparent}}
.small{{color:{muted};font-size:.9rem}}.kpi{{font-size:2rem;font-weight:800}}.pill{{display:inline-block;padding:6px 11px;border-radius:999px;background:rgba(56,189,248,.12);color:{accent};font-size:.78rem;font-weight:700}}
div.stButton>button{{border-radius:12px;border:1px solid {border};font-weight:700;transition:.2s}}
div.stButton>button:hover{{transform:translateY(-1px);border-color:{accent}}}
[data-testid="stMetricValue"]{{font-weight:800}}.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox div{{border-radius:12px}}
hr{{border-color:{border}}}
</style>
""", unsafe_allow_html=True)

def card(title, body="", icon=""):
    st.markdown(f'<div class="pf-card"><h3 style="margin:0 0 8px">{icon} {title}</h3><div class="small">{body}</div></div>', unsafe_allow_html=True)

def safe_page(name): st.session_state.page = name; st.rerun()

# -------------------- DB HELPERS --------------------
def db_select(table, filters=None, limit=100, order=None):
    if not sb: return []
    try:
        q = sb.table(table).select("*")
        for k,v in (filters or {}).items(): q = q.eq(k,v)
        if order: q=q.order(order, desc=True)
        r=q.limit(limit).execute(); return r.data or []
    except Exception: return []

def db_insert(table, payload):
    if not sb: return None
    try: return (sb.table(table).insert(payload).execute().data or [None])[0]
    except Exception: return None

def db_upsert(table, payload):
    if not sb: return None
    try: return (sb.table(table).upsert(payload).execute().data or [None])[0]
    except Exception: return None

def db_update(table, filters, payload):
    if not sb: return None
    try:
        q=sb.table(table).update(payload)
        for k,v in filters.items(): q=q.eq(k,v)
        return (q.execute().data or [None])[0]
    except Exception: return None

def db_delete(table, filters):
    if not sb: return False
    try:
        q=sb.table(table).delete()
        for k,v in filters.items(): q=q.eq(k,v)
        q.execute(); return True
    except Exception: return False

# -------------------- AI --------------------
def ai(prompt, system="You are PrimeFit AI, a practical fitness and nutrition assistant. Give safe general fitness guidance, avoid medical diagnosis and guaranteed results.", temperature=.35):
    if not groq: return "AI is not configured yet. Add GROQ_API_KEY in Streamlit Secrets."
    try:
        r=groq.chat.completions.create(model="llama-3.3-70b-versatile",messages=[{"role":"system","content":system},{"role":"user","content":prompt}],temperature=temperature,max_tokens=1800)
        return r.choices[0].message.content
    except Exception as e: return f"AI service temporarily unavailable: {e}"

def json_ai(prompt):
    raw=ai(prompt+"\nReturn ONLY valid JSON, no markdown fences.",temperature=.25)
    raw=re.sub(r"^```(?:json)?|```$","",raw.strip(),flags=re.I).strip()
    try:return json.loads(raw)
    except Exception:return None

# -------------------- AUTH --------------------
def current_user():
    return st.session_state.user

def sign_out():
    try:
        if sb: sb.auth.sign_out()
    except Exception: pass
    st.session_state.user=None; st.session_state.admin_mode=False; st.session_state.page="Home"; st.rerun()

def auth_box():
    tabs=st.tabs(["Login","Create account"])
    with tabs[0]:
        email=st.text_input("Email",key="li_email"); pw=st.text_input("Password",type="password",key="li_pw")
        if st.button("Login",type="primary",use_container_width=True):
            if not sb: st.error("Supabase is not configured."); return
            try:
                r=sb.auth.sign_in_with_password({"email":email,"password":pw}); st.session_state.user=r.user; safe_page("Dashboard")
            except Exception as e: st.error(f"Login failed: {e}")
    with tabs[1]:
        name=st.text_input("Name",key="su_name"); email=st.text_input("Email",key="su_email"); pw=st.text_input("Password (6+ chars)",type="password",key="su_pw")
        if st.button("Create account",type="primary",use_container_width=True):
            if not sb: st.error("Supabase is not configured."); return
            try:
                r=sb.auth.sign_up({"email":email,"password":pw,"options":{"data":{"name":name}}})
                if r.user:
                    st.session_state.user=r.user
                    uid=str(r.user.id)
                    db_upsert("profiles",{"id":uid,"name":name,"email":email})
                    st.success("Account created. You can continue to onboarding."); safe_page("Onboarding")
            except Exception as e: st.error(f"Signup failed: {e}")

# -------------------- LANDING --------------------
def landing():
    st.markdown('<div class="hero"> <span class="pill">AI FITNESS + NUTRITION</span><h1 style="font-size:3.3rem;margin:14px 0 8px">Your Body. Your Goal. <span class="grad">Your AI Coach.</span></h1><p style="font-size:1.15rem;max-width:780px">Personalized workouts and budget-based nutrition plans that adapt to your real progress — built for real people, real schedules and PKR budgets.</p></div>',unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    for c,title,txt,ico in [(c1,"Personalized AI Workouts","Goal, experience, equipment and schedule based plans.","🏋️"),(c2,"Budget-Based Nutrition","Daily, weekly or monthly PKR budget with practical local foods.","🥗"),(c3,"Real Progress Tracking","Workouts, strength, consistency, PRs and goal progress.","📈")]:
        with c: card(title,txt,ico)
    st.markdown("### How PrimeFit AI works")
    cols=st.columns(5)
    for c,n,t in zip(cols,["01","02","03","04","05"],["Assess","Plan","Train","Track","Adapt"]):
        with c: card(n,t,"⚡")
    st.markdown("### Built around your reality")
    a,b=st.columns(2)
    with a: card("Fitness That Fits Your Budget","Enter Rs. 300/day, Rs. 2,000/week or your own monthly budget. PrimeFit AI works within the number you provide.","🇵🇰")
    with b: card("Evidence, not magic","PrimeFit explains why a plan was selected and can point users toward trusted sources. It does not promise a dream physique or guaranteed results.","🔬")
    st.markdown("### Meet the team")
    team=db_select("team_members",{"is_visible":True},20,"display_order")
    if team:
        cs=st.columns(min(4,len(team)))
        for c,m in zip(cs,team):
            with c: card(m.get("name","Team member"),m.get("role","PrimeFit AI Team"),"👤")
    else:
        card("Our Team","Team profiles can be added and managed from the Admin → Team Management area after launch.","👥")
    st.markdown("---")
    if st.button("Start Your Free Journey →",type="primary",use_container_width=True): safe_page("Login")

# -------------------- ONBOARDING --------------------
def onboarding():
    st.title("Build your PrimeFit profile")
    st.caption("A few details help the AI make your plan more relevant. This is general fitness guidance, not medical treatment.")
    with st.form("onboard"):
        a,b=st.columns(2)
        with a:
            name=st.text_input("Name",value=(current_user().user_metadata.get("name","") if current_user() else "")); age=st.number_input("Age",16,80,20); gender=st.selectbox("Gender",["Prefer not to say","Male","Female"]); height=st.number_input("Height (cm)",100,230,165); weight=st.number_input("Weight (kg)",30.,250.,65.)
            experience=st.selectbox("Fitness experience",["Beginner","Intermediate","Advanced"]); activity=st.selectbox("Activity level",["Low","Moderate","High"])
        with b:
            goal=st.selectbox("Primary goal",["Muscle gain","Weight loss","Strength","General fitness","Lean / athletic physique"]); physique=st.text_input("Desired physique",placeholder="e.g. lean and athletic"); location=st.selectbox("Workout location",["Gym","Home"]); equipment=st.text_input("Available equipment",placeholder="e.g. dumbbells, resistance bands"); days=st.slider("Workout days/week",1,7,4); duration=st.slider("Approx. workout duration (minutes)",15,120,45); limitations=st.text_area("Exercise limitations / discomfort",placeholder="Optional")
        if st.form_submit_button("Save profile & create my plan",type="primary",use_container_width=True):
            payload={"id":str(current_user().id),"name":name,"age":age,"gender":gender,"height_cm":height,"weight_kg":weight,"experience":experience,"activity_level":activity,"goal":goal,"desired_physique":physique,"workout_location":location,"equipment":equipment,"workout_days":days,"workout_duration":duration,"limitations":limitations}
            ok=db_upsert("profiles",payload)
            st.session_state.profile=payload
            with st.spinner("PrimeFit AI is building your personalized plan..."): st.session_state.workout_plan=make_workout(payload)
            safe_page("My Plan")

def profile_data():
    if not current_user(): return {}
    rows=db_select("profiles",{"id":str(current_user().id)},1)
    return rows[0] if rows else st.session_state.get("profile",{})

def make_workout(p):
    prompt=f"""Create a safe, practical 7-day workout plan for this user: {json.dumps(p)}. Include rest days, warm-up, exercises, sets, reps, rest seconds, estimated duration, alternatives and progression. Respect equipment/location and limitations. Explain that adaptation depends on recovery and consistency. Also provide a short 'why_this_plan' explanation. Return JSON with keys: overview, why_this_plan, days. days must be a list of objects with day, focus, duration, exercises (list of objects name, sets, reps, rest, instructions, alternative)."""
    out=json_ai(prompt)
    if out:return out
    return {"overview":"Personalized starter plan","why_this_plan":"Based on your goal, schedule and available equipment.","days":[{"day":"Day 1","focus":"Full Body","duration":p.get("workout_duration",45),"exercises":[{"name":"Bodyweight Squat","sets":3,"reps":"8-12","rest":60,"instructions":"Keep chest tall and knees tracking over toes.","alternative":"Chair squat"},{"name":"Push-up","sets":3,"reps":"6-12","rest":60,"instructions":"Keep a straight body line.","alternative":"Incline push-up"}]}]}

def nutrition(p,basis,budget,preferences,meals):
    prompt=f"Create a practical general fitness nutrition structure for a Pakistani user. Profile: {json.dumps(p)}. Budget: Rs {budget} per {basis}. Preferences: {preferences}. Meals/day: {meals}. Use affordable local foods such as eggs, daal, rice, roti, chicken, dahi, milk, chana, vegetables and fruit where suitable. Do not prescribe medical diets or guarantee weight change. Return JSON with keys summary, budget_notes, meals (list: meal, foods, estimated_pkr, protein_focus), substitutions."
    out=json_ai(prompt)
    if out:return out
    return {"summary":"A practical budget-aware meal structure.","budget_notes":f"Target budget: Rs. {budget}/{basis}.","meals":[{"meal":"Breakfast","foods":"Eggs + roti + milk","estimated_pkr":120,"protein_focus":"Eggs and milk"},{"meal":"Lunch","foods":"Daal + rice/roti + vegetables","estimated_pkr":130,"protein_focus":"Daal"},{"meal":"Snack","foods":"Chana + fruit","estimated_pkr":70,"protein_focus":"Chana"},{"meal":"Dinner","foods":"Chicken/daal + roti + salad","estimated_pkr":160,"protein_focus":"Chicken or daal"}],"substitutions":["Chicken → daal/chana","Packaged snacks → fruit/chana"]}

# -------------------- USER PAGES --------------------
def dashboard():
    p=profile_data(); st.title("Dashboard"); st.caption(f"Welcome back, {p.get('name','there')} 👋")
    logs=db_select("workout_logs",{"user_id":str(current_user().id)},100,"created_at") if current_user() else []
    progress=db_select("progress_records",{"user_id":str(current_user().id)},100,"recorded_at") if current_user() else []
    done=len(logs); latest=progress[0].get("weight_kg") if progress else p.get("weight_kg","—")
    a,b,c,d=st.columns(4)
    for col,label,val in [(a,"Workouts completed",done),(b,"Current weight",f"{latest} kg"),(c,"Goal",p.get("goal","Set profile")),(d,"Streak","Keep building")]:
        with col: st.metric(label,val)
    st.markdown("### Quick actions")
    cols=st.columns(4)
    for c,label,page in zip(cols,["Start workout","My plan","Nutrition","AI Coach"],["Workout","My Plan","Nutrition","AI Coach"]):
        with c:
            if st.button(label,use_container_width=True):safe_page(page)
    if progress:
        vals=[x for x in reversed(progress) if x.get("weight_kg") is not None]
        if vals:
            fig=go.Figure(go.Scatter(x=[v.get("recorded_at","") for v in vals],y=[v["weight_kg"] for v in vals],mode="lines+markers")); fig.update_layout(title="Weight trend",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig,use_container_width=True)

def my_plan():
    st.title("My Plan")
    p=profile_data()
    if not p.get("goal"):
        st.info("Complete onboarding first.");
        if st.button("Go to onboarding"):safe_page("Onboarding")
        return
    if not st.session_state.workout_plan: st.session_state.workout_plan=make_workout(p)
    plan=st.session_state.workout_plan
    st.markdown(f"<div class='pf-card'><span class='pill'>PERSONALIZED</span><h2>{plan.get('overview','Your plan')}</h2><p class='small'>{plan.get('why_this_plan','')}</p></div>",unsafe_allow_html=True)
    for day in plan.get("days",[]):
        with st.expander(f"{day.get('day')} — {day.get('focus')} · {day.get('duration','')} min"):
            for ex in day.get("exercises",[]): st.markdown(f"**{ex.get('name')}** — {ex.get('sets')} × {ex.get('reps')} · rest {ex.get('rest')}s\n\n{ex.get('instructions','')}  \nAlternative: {ex.get('alternative','—')}")
    st.markdown("### Why this plan?")
    st.write(plan.get("why_this_plan","PrimeFit selected this structure from your goal, experience, equipment, schedule and available time."))
    st.caption("Evidence note: PrimeFit can explain training choices, but users should verify medical or condition-specific advice with a qualified professional.")

def workout():
    st.title("Today's Workout")
    p=profile_data(); plan=st.session_state.workout_plan or make_workout(p); st.session_state.workout_plan=plan
    day=plan.get("days",[])[0] if plan.get("days") else {}
    st.markdown(f"<div class='pf-card'><span class='pill'>{day.get('focus','WORKOUT')}</span><h2>{day.get('day','Today')}</h2><p class='small'>Complete each set with controlled form. Adjust or stop if something causes pain.</p></div>",unsafe_allow_html=True)
    completed=[]
    for i,ex in enumerate(day.get("exercises",[])):
        with st.container(border=True):
            st.subheader(f"{i+1}. {ex.get('name')}"); st.write(f"**{ex.get('sets')} sets × {ex.get('reps')} reps** · Rest {ex.get('rest')} sec"); st.caption(ex.get('instructions','')); done=st.checkbox("Exercise completed",key=f"exdone{i}");
            if done: completed.append(ex.get('name'))
    if st.button("Finish workout",type="primary",use_container_width=True):
        if current_user(): db_insert("workout_logs",{"user_id":str(current_user().id),"workout_date":str(date.today()),"duration_minutes":day.get("duration",0),"completed":True,"notes":json.dumps(completed)})
        st.success("Workout logged. Nice work! 🔥")

def nutrition_page():
    st.title("Budget-Based Nutrition")
    p=profile_data()
    a,b=st.columns(2)
    with a: basis=st.selectbox("Budget basis",["day","week","month"]); budget=st.number_input(f"Your budget (PKR per {basis})",100,1000000,300 if basis=="day" else (2000 if basis=="week" else 10000),step=100); meals=st.slider("Meals/day",2,6,4)
    with b: pref=st.text_area("Food preferences / allergies",placeholder="e.g. vegetarian, dislike fish, lactose sensitive");
    if st.button("Generate nutrition plan",type="primary",use_container_width=True):
        with st.spinner("Building a budget-aware plan..."): st.session_state.meal_plan=nutrition(p,basis,budget,pref,meals)
    if st.session_state.meal_plan:
        m=st.session_state.meal_plan; st.markdown(f"<div class='pf-card'><h3>{m.get('summary','')}</h3><p class='small'>{m.get('budget_notes','')}</p></div>",unsafe_allow_html=True)
        for meal in m.get("meals",[]): card(meal.get("meal","Meal"),f"{meal.get('foods','')} · Est. Rs. {meal.get('estimated_pkr','—')} · {meal.get('protein_focus','')}","🍽️")
        st.markdown("**Affordable substitutions**"); st.write(" • ".join(m.get("substitutions",[])))
        st.caption("Nutrition guidance is general and not a substitute for medical or dietetic care.")

def progress_page():
    st.title("Progress")
    uid=str(current_user().id); rows=db_select("progress_records",{"user_id":uid},200,"recorded_at")
    with st.form("progress"):
        a,b,c=st.columns(3); w=a.number_input("Weight (kg)",30.,250.,float(profile_data().get("weight_kg") or 65)); strength=b.text_input("Strength / PR note"); consistency=c.number_input("Workout consistency (%)",0.,100.,80.)
        if st.form_submit_button("Log progress",type="primary"):
            db_insert("progress_records",{"user_id":uid,"recorded_at":datetime.utcnow().isoformat(),"weight_kg":w,"strength_note":strength,"consistency":consistency}); st.success("Progress saved."); st.rerun()
    rows=db_select("progress_records",{"user_id":uid},200,"recorded_at")
    if rows:
        df=pd.DataFrame(rows); st.dataframe(df,use_container_width=True)
        if "weight_kg" in df.columns:
            df=df.dropna(subset=["weight_kg"]); fig=go.Figure(go.Scatter(x=df.get("recorded_at"),y=df["weight_kg"],mode="lines+markers")); fig.update_layout(title="Weight progression"); st.plotly_chart(fig,use_container_width=True)
        if st.button("Analyze my progress with AI"):
            st.write(ai(f"Analyze this fitness progress data and give 5 practical non-medical adjustments: {json.dumps(rows)}"))
    else: st.info("Log your first progress entry above.")

def coach():
    st.title("AI Coach")
    p=profile_data(); st.caption("Context-aware coaching based on your profile and logged data. Avoid medical emergencies; seek qualified care when needed.")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.write(m["content"])
    q=st.chat_input("Ask about your workout, progress, motivation or nutrition...")
    if q:
        st.session_state.messages.append({"role":"user","content":q})
        context={"profile":p,"recent_progress":db_select("progress_records",{"user_id":str(current_user().id)},20,"recorded_at") if current_user() else []}
        ans=ai(f"User context: {json.dumps(context)}\nQuestion: {q}\nGive concise practical advice. Do not diagnose or promise results.")
        st.session_state.messages.append({"role":"assistant","content":ans}); st.rerun()

def profile_page():
    st.title("Profile & Settings"); p=profile_data()
    st.json({k:v for k,v in p.items() if k not in ["id"]})
    if st.button("Regenerate my workout plan"): st.session_state.workout_plan=make_workout(p); st.success("Plan refreshed.")

# -------------------- ADMIN --------------------
def is_admin():
    if not current_user(): return False
    rows=db_select("admin_roles",{"user_id":str(current_user().id)},1)
    return bool(rows)

def admin():
    if not is_admin(): st.error("Admin access denied."); return
    st.title("PrimeFit AI Admin")
    tabs=st.tabs(["Overview","Users","Exercises","Nutrition","Moderation","Analytics","Team Management","Settings"])
    with tabs[0]:
        users=db_select("profiles",limit=1000); posts=db_select("community_posts",limit=1000); logs=db_select("workout_logs",limit=1000)
        a,b,c,d=st.columns(4)
        a.metric("Users",len(users)); b.metric("Community posts",len(posts)); c.metric("Workout logs",len(logs)); d.metric("Active data",len(logs)+len(posts))
    with tabs[1]:
        users=db_select("profiles",limit=500)
        if users: st.dataframe(pd.DataFrame(users),use_container_width=True)
        else: st.info("No users or RLS prevents admin read access.")
    with tabs[2]:
        st.subheader("Exercise management")
        with st.form("exercise_add"):
            n=st.text_input("Exercise name"); muscles=st.text_input("Target muscles"); eq=st.text_input("Equipment"); diff=st.selectbox("Difficulty",["Beginner","Intermediate","Advanced"]); ins=st.text_area("Instructions"); alt=st.text_input("Alternative")
            if st.form_submit_button("Add exercise"): db_insert("exercises",{"name":n,"target_muscles":muscles,"equipment":eq,"difficulty":diff,"instructions":ins,"alternative":alt}); st.success("Saved")
        ex=db_select("exercises",limit=500); st.dataframe(pd.DataFrame(ex),use_container_width=True) if ex else st.info("No exercises yet.")
    with tabs[3]:
        st.info("Nutrition content can be expanded here. User budget plans remain dynamically generated from the user's own PKR budget.")
    with tabs[4]:
        reports=db_select("reports","created_at",limit=500); st.dataframe(pd.DataFrame(reports),use_container_width=True) if reports else st.info("No reports.")
        posts=db_select("community_posts",limit=200,"created_at");
        if posts: st.dataframe(pd.DataFrame(posts),use_container_width=True)
    with tabs[5]:
        logs=db_select("workout_logs",limit=1000); prog=db_select("progress_records",limit=1000)
        st.metric("Workout logs",len(logs)); st.metric("Progress records",len(prog))
        if logs:
            df=pd.DataFrame(logs); st.bar_chart(df.groupby(df.get("workout_date",pd.Series(dtype=str))).size())
    with tabs[6]: team_management()
    with tabs[7]:
        st.text_input("Project name",value="PrimeFit AI",disabled=True); st.text_area("Project description",value="AI-powered fitness and budget-based nutrition platform.",disabled=True); st.caption("Team name can be configured through the project_settings table.")

def team_management():
    st.subheader("Team Management")
    st.caption("Add/edit/remove team credits without hard-coding them into the public website.")
    with st.form("team_add"):
        a,b=st.columns(2); name=a.text_input("Name"); role=b.text_input("Role"); bio=st.text_area("Short bio"); linkedin=a.text_input("LinkedIn URL"); instagram=b.text_input("Instagram URL"); xurl=a.text_input("X/Twitter URL"); portfolio=b.text_input("Portfolio URL"); other=a.text_input("Other social URL"); lead=b.checkbox("Project Lead & Idea Owner"); visible=a.checkbox("Visible on public site",True); order=b.number_input("Display order",0,100,0)
        if st.form_submit_button("Add team member",type="primary"):
            db_insert("team_members",{"team_member_id":str(uuid.uuid4()),"name":name,"role":role,"bio":bio,"linkedin_url":linkedin,"instagram_url":instagram,"x_url":xurl,"portfolio_url":portfolio,"other_social_url":other,"is_project_lead":lead,"is_visible":visible,"display_order":order}); st.success("Team member added.")
    team=db_select("team_members",limit=100,"display_order")
    if team:
        for m in team:
            with st.expander(f"{m.get('name','')} — {m.get('role','')}"):
                st.write(m.get("bio","")); st.caption(f"Lead: {m.get('is_project_lead',False)} · Visible: {m.get('is_visible',True)}")
                if st.button("Remove",key="rm_"+str(m.get("team_member_id",m.get("id",uuid.uuid4())))): db_delete("team_members",{"team_member_id":m.get("team_member_id")}); st.rerun()
    else: st.info("No team members yet. Add them above after launch.")

# -------------------- COMMUNITY --------------------
def community():
    st.title("Community")
    uid=str(current_user().id)
    with st.form("post"):
        txt=st.text_area("Share a fitness update",placeholder="Workout win, milestone, useful tip...")
        if st.form_submit_button("Post",type="primary"):
            # Basic contact-info guardrail
            if re.search(r"(?:\+?92|03)\d{9}|\b(?:gmail|yahoo|hotmail)\.com\b|https?://",txt,re.I): st.error("For safety, phone numbers, emails and external contact links are not allowed in community posts.")
            elif txt.strip(): db_insert("community_posts",{"user_id":uid,"content":txt.strip(),"created_at":datetime.utcnow().isoformat()}); st.success("Posted!")
    posts=db_select("community_posts",limit=100,"created_at")
    for p in posts:
        card("Community update",p.get("content",""),"💬")

# -------------------- NAV --------------------
def sidebar():
    with st.sidebar:
        st.markdown("# ⚡ <span class='grad'>PrimeFit AI</span>",unsafe_allow_html=True)
        st.caption("Your Body. Your Goal. Your AI Coach.")
        if st.button("☀️ Light mode" if dark else "🌙 Dark mode",use_container_width=True): st.session_state.theme="light" if dark else "dark"; st.rerun()
        st.divider()
        if current_user():
            nav=["Dashboard","My Plan","Workout","Nutrition","Progress","Community","AI Coach","Profile"]
            for n in nav:
                if st.button(n,use_container_width=True): safe_page(n)
            if is_admin():
                st.divider()
                if st.button("🛡️ Admin",use_container_width=True): st.session_state.page="Admin"; st.rerun()
            st.divider()
            if st.button("Logout",use_container_width=True): sign_out()
        else:
            for n in ["Home","Features","Login"]:
                if st.button(n,use_container_width=True): safe_page(n)
        st.divider(); st.caption("PrimeFit AI © 2026 — Built in Pakistan 🇵🇰 · A PrimeFit AI Project")

sidebar()
page=st.session_state.page
if page=="Home": landing()
elif page=="Features": landing()
elif page=="Login":
    st.title("Welcome to PrimeFit AI"); auth_box()
elif page=="Onboarding":
    if current_user(): onboarding()
    else: safe_page("Login")
elif page=="Dashboard" and current_user(): dashboard()
elif page=="My Plan" and current_user(): my_plan()
elif page=="Workout" and current_user(): workout()
elif page=="Nutrition" and current_user(): nutrition_page()
elif page=="Progress" and current_user(): progress_page()
elif page=="Community" and current_user(): community()
elif page=="AI Coach" and current_user(): coach()
elif page=="Profile" and current_user(): profile_page()
elif page=="Admin" and current_user(): admin()
else: landing()
