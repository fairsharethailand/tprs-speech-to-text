import streamlit as st
from gtts import gTTS
import base64
import os
import uuid
import random

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Talk to Me V.1.0", layout="wide")

# 2. Session State
if 'display_text' not in st.session_state:
    st.session_state.display_text = ""
if 'audio_key' not in st.session_state:
    st.session_state.audio_key = 0

# --- Grammar Logic ---
PAST_TO_INF = {
    "went": "go", "ate": "eat", "saw": "see", "bought": "buy", 
    "had": "have", "did": "do", "drank": "drink", "slept": "sleep", 
    "wrote": "write", "came": "come", "ran": "run", "met": "meet",
    "spoke": "speak", "took": "take", "found": "find", "gave": "give",
    "thought": "think", "brought": "bring", "told": "tell", "made": "make",
    "cut": "cut", "put": "put", "hit": "hit", "read": "read", "cost": "cost"
}

# เพิ่ม mice, teeth, feet, geese, oxen, data, media เพื่อความครอบคลุม
IRR_PL = ["children", "people", "men", "women", "mice", "teeth", "feet", "geese", "oxen", "data", "media"]

def is_present_perfect(predicate):
    words = predicate.lower().split()
    if len(words) >= 2 and words[0] in ['have', 'has', 'had']:
        v2 = words[1]
        if v2.endswith('ed') or v2 in PAST_TO_INF or v2 in ['been', 'done', 'gone', 'seen', 'eaten']:
            return True
    return False

def check_tense_type(predicate):
    words = predicate.split()
    if not words: return "unknown"
    v = words[0].lower().strip()
    if v.endswith("ed") or v in PAST_TO_INF:
        return "past"
    return "present"

def conjugate_singular(predicate):
    """ฟังก์ชันสำหรับ Who (คงเดิม): เติม s/es ให้กริยา"""
    words = predicate.split()
    if not words: return ""
    v = words[0].lower(); rest = " ".join(words[1:])
    if v.endswith(('ch', 'sh', 'x', 's', 'z', 'o')): v += "es"
    elif v.endswith('y') and len(v) > 1 and v[-2] not in 'aeiou': v = v[:-1] + "ies"
    else: v += "s"
    return f"{v} {rest}".strip()

def get_auxiliary(subject, pred_target, pred_other):
    if is_present_perfect(pred_target): return None 
    
    # 1. เช็ค Past Tense
    if check_tense_type(pred_target) == "past" or check_tense_type(pred_other) == "past":
        return "Did"
    
    # 2. เช็ค Subject (Present Tense)
    s_clean = subject.lower().strip()
    s_words = s_clean.split() # แยกคำ เช่น "the children" -> ["the", "children"]
    
    # Logic: ถ้ามีคำใดคำหนึ่งในประธาน ตรงกับ Irregular Plural List ให้ถือเป็นพหูพจน์
    found_irregular = any(word in IRR_PL for word in s_words)
    
    if (found_irregular or 
        'and' in s_clean or 
        s_clean in ['i', 'you', 'we', 'they'] or 
        (s_clean.endswith('s') and s_clean not in ['james', 'charles', 'boss'])):
        return "Do"
        
    return "Does"

def to_infinitive(predicate, other_predicate):
    words = predicate.split()
    if not words: return ""
    v = words[0].lower().strip(); rest = " ".join(words[1:])
    is_past = (check_tense_type(predicate) == "past" or check_tense_type(other_predicate) == "past")
    if is_past or v in ['had', 'has', 'have']:
        inf_v = "have" if v in ['had', 'has', 'have'] else PAST_TO_INF.get(v, v[:-2] if v.endswith("ed") else v)
    else:
        if v.endswith("es"): inf_v = v[:-2]
        elif v.endswith("s") and not v.endswith("ss"): inf_v = v[:-1]
        else: inf_v = v
    return f"{inf_v} {rest}".strip()

def has_be_verb(predicate):
    v_low = predicate.lower().split()
    be_modals = ['is', 'am', 'are', 'was', 'were', 'can', 'will', 'must', 'should', 'could', 'would']
    return v_low and v_low[0] in be_modals

def build_logic(q_type, data):
    s1, p1, s2, p2 = data['s1'], data['p1'], data['s2'], data['p2']
    subj_r, pred_r = (s1 if s1 else "He"), (p1 if p1 else "is here")
    subj_t = s2 if s2 != "-" else s1
    pred_t = p2 if p2 != "-" else p1

    def swap(s, p):
        pts = p.split()
        return f"{pts[0].capitalize()} {s} {' '.join(pts[1:])}".strip()

    if q_type == "Statement": return data['main_sent']
    
    if q_type == "Negative":
        if has_be_verb(pred_t) or is_present_perfect(pred_t):
            return f"No, {subj_t} {pred_t.split()[0]} not {' '.join(pred_t.split()[1:])}."
        
        # แก้ไขให้ใช้ don't / doesn't / didn't
        aux = get_auxiliary(subj_t, pred_t, pred_r)
        neg_word = "don't" if aux == "Do" else ("doesn't" if aux == "Does" else "didn't")
        return f"No, {subj_t} {neg_word} {to_infinitive(pred_t, pred_r)}."

    if q_type == "Yes-Q":
        if has_be_verb(pred_r) or is_present_perfect(pred_r): return swap(subj_r, pred_r) + "?"
        return f"{get_auxiliary(subj_r, pred_r, pred_t)} {subj_r} {to_infinitive(pred_r, pred_t)}?"

    if q_type == "No-Q":
        if has_be_verb(pred_t) or is_present_perfect(pred_t): return swap(subj_t, pred_t) + "?"
        return f"{get_auxiliary(subj_t, pred_t, pred_r)} {subj_t} {to_infinitive(pred_t, pred_r)}?"

    if q_type == "Who":
        words = pred_r.split()
        if not words: return "Who?"
        v = words[0].lower(); rest = " ".join(words[1:])
        if v in ['am', 'are']: return f"Who is {rest}?"
        if v == 'were': return f"Who was {rest}?"
        if not has_be_verb(pred_r) and check_tense_type(pred_r) == "present":
            return f"Who {conjugate_singular(pred_r)}?"
        return f"Who {pred_r}?"

    if q_type in ["What", "Where", "When", "How", "Why"]:
        if has_be_verb(pred_r) or is_present_perfect(pred_r):
            return f"{q_type} {pred_r.split()[0]} {subj_r} {' '.join(pred_r.split()[1:])}?"
        aux = get_auxiliary(subj_r, pred_r, pred_t)
        return f"{q_type} {aux.lower()} {subj_r} {to_infinitive(pred_r, pred_t)}?"

    if q_type == "Either/Or":
        if s2 != "-" and s1.lower().strip() != s2.lower().strip():
            if has_be_verb(pred_r): return f"{pred_r.split()[0].capitalize()} {subj_r} or {subj_t} {' '.join(pred_r.split()[1:])}?"
            return f"{get_auxiliary(subj_r, pred_r, pred_t)} {subj_r} or {subj_t} {to_infinitive(pred_r, pred_t)}?"
        else:
            p_alt = p2 if p2 != "-" else "something else"
            if has_be_verb(pred_r): return f"{swap(subj_r, pred_r)} or {p_alt}?"
            return f"{get_auxiliary(subj_r, pred_r, p_alt)} {subj_r} {to_infinitive(pred_r, p_alt)} or {to_infinitive(p_alt, pred_r)}?"
    return data['main_sent']

def play_voice(text):
    if not text: return
    try:
        clean = text.split(":")[-1].strip().replace("🎯","")
        tts = gTTS(text=clean, lang='en')
        fn = f"v_{uuid.uuid4()}.mp3"
        tts.save(fn)
        with open(fn, "rb") as f: b64 = base64.b64encode(f.read()).decode()
        st.session_state.audio_key += 1
        st.markdown(f'<audio autoplay key="{st.session_state.audio_key}"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)
        os.remove(fn)
    except: pass

# --- UI ---
st.title("🎡 Talk to Me V.1.0")
m_in = st.text_input("📝 Main Sentence", "The children make a cake.")
c1, c2 = st.columns(2)
with c1: sr, pr = st.text_input("Subject (R):", "The children"), st.text_input("Predicate (R):", "make a cake")
with c2: st_subj, pt = st.text_input("Subject (T):", "-"), st.text_input("Predicate (T):", "make a bread")
data = {'s1':sr, 'p1':pr, 's2':st_subj, 'p2':pt, 'main_sent':m_in}

st.divider()
clicked = None
if st.button("🎰 RANDOM TRICK", use_container_width=True, type="primary"):
    clicked = random.choice(["Statement", "Yes-Q", "No-Q", "Negative", "Either/Or", "Who", "What", "Where", "When", "How", "Why"])

r1 = st.columns(5)
btns1 = [("📢 Statement", "Statement"), ("✅ Yes-Q", "Yes-Q"), ("❌ No-Q", "No-Q"), ("🚫 Negative", "Negative"), ("⚖️ Either/Or", "Either/Or")]
for i, (l, m) in enumerate(btns1):
    if r1[i].button(l, use_container_width=True): clicked = m

r2 = st.columns(6)
for i, wh in enumerate(["Who", "What", "Where", "When", "How", "Why"]):
    if r2[i].button(f"❓ {wh}", use_container_width=True): clicked = wh

if clicked:
    res = build_logic(clicked, data)
    st.session_state.display_text = f"🎯 {clicked}: {res}"
    play_voice(res)

if st.session_state.display_text: st.info(st.session_state.display_text)
