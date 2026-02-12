import streamlit as st
from gtts import gTTS
import base64
import os
import uuid
import random
import json

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Speak V1.0", layout="wide")

# 2. Session State
if 'display_text' not in st.session_state:
    st.session_state.display_text = ""
if 'audio_key' not in st.session_state:
    st.session_state.audio_key = 0

# --- Grammar Logic ---

def load_irregular_verbs():
    try:
        if os.path.exists('verbs.json'):
            with open('verbs.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "went": "go", "ate": "eat", "saw": "see", "bought": "buy", 
                "had": "have", "did": "do", "drank": "drink", "slept": "sleep", 
                "wrote": "write", "came": "come", "ran": "run", "met": "meet",
                "spoke": "speak", "took": "take", "found": "find", "gave": "give",
                "thought": "think", "brought": "bring", "told": "tell", "made": "make"
            }
    except Exception:
        return {"went": "go", "ate": "eat"}

PAST_TO_INF = load_irregular_verbs()
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
    words = predicate.split()
    if not words: return ""
    v = words[0].lower(); rest = " ".join(words[1:])
    if v in ['have', 'has']:
        return f"has {rest}".strip()
    if v.endswith(('ch', 'sh', 'x', 's', 'z', 'o')): v += "es"
    elif v.endswith('y') and len(v) > 1 and v[-2] not in 'aeiou': v = v[:-1] + "ies"
    else: v += "s"
    return f"{v} {rest}".strip()

def get_auxiliary(subject, pred_target, pred_other):
    if is_present_perfect(pred_target): return None 
    if check_tense_type(pred_target) == "past" or check_tense_type(pred_other) == "past":
        return "Did"
    s_clean = subject.lower().strip()
    s_words = s_clean.split()
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
    
    # แก้ไข: ถ้าเป็น have/has/had ให้คืนค่าเป็น have เสมอเมื่อทำเป็น infinitive
    if v in ['have', 'has', 'had']:
        return f"have {rest}".strip()
        
    is_past = (check_tense_type(predicate) == "past" or check_tense_type(other_predicate) == "past")
    if is_past:
        inf_v = PAST_TO_INF.get(v, v[:-2] if v.endswith("ed") else v)
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
        words = pred_r.lower().split()
        # 1. เช็คโครงสร้าง be + V-ing
        if len(words) >= 2 and words[0] in ['is', 'am', 'are', 'was', 'were'] and words[1].endswith('ing'):
            return f"{q_type} {words[0]} {subj_r} {' '.join(words[1:])}?"
            
        # 2. เช็คโครงสร้าง Verb to have (ไม่ใช่ Present Perfect)
        if words[0] in ['have', 'has', 'had'] and not is_present_perfect(pred_r):
            aux = get_auxiliary(subj_r, pred_r, pred_t)
            return f"{q_type} {aux.lower()} {subj_r} {to_infinitive(pred_r, pred_t)}?"

        # 3. กรณีอื่นๆ (Modal หรือ Be ตัวเดียว)
        if has_be_verb(pred_r) or is_present_perfect(pred_r):
            return f"{q_type} {pred_r.split()[0]} {subj_r} {' '.join(pred_r.split()[1:])}?"
        
        # 4. กริยาทั่วไป
        aux = get_auxiliary(subj_r, pred_r, pred_t)
        return f"{q_type} {aux.lower()} {subj_r} {to_infinitive(pred_r, pred_t)}?"

    if q_type == "Either/Or":
        if s2 != "-" and s1.lower().strip() != s2.lower().strip():
            if has_be_verb(pred_r): return f"{pred_r.split()[0].capitalize()} {subj
