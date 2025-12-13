import streamlit as st
import requests
import time
import re
import uuid
from gtts import gTTS
from streamlit_js_eval import get_geolocation
import google.generativeai as genai

# ================= CONFIG =================
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

genai.configure(api_key=GEMINI_API_KEY)
ai = genai.GenerativeModel("gemini-flash-latest")

st.set_page_config(page_title="Bus Assistant for Blind", layout="centered")
st.title("🦯 Trợ lý xe bus cho người khiếm thị")

# ================= STATE =================
if "running" not in st.session_state:
    st.session_state.running = False

if "last_voice" not in st.session_state:
    st.session_state.last_voice = ""

# ================= UTILS =================
def speak(text):
    filename = f"voice_{uuid.uuid4()}.mp3"
    gTTS(text, lang="vi").save(filename)
    st.audio(filename, autoplay=True)

def clean_html(t):
    return re.sub("<[^<]+?>", "", t)

def normalize_direction(text):
    t = text.lower()
    if "trái" in t:
        return "Rẽ trái"
    if "phải" in t:
        return "Rẽ phải"
    return "Đi thẳng"

# ================= AI: PARSE USER INTENT =================
def ai_parse_input(user_text):
    prompt = f"""
    Người dùng khiếm thị nói: "{user_text}"

    Hãy trích xuất:
    - điểm đi
    - điểm đến
    - ưu tiên (ít đổi xe / ít đi bộ / nhanh nhất)

    Trả về dạng:
    origin=...
    destination=...
    priority=...
    """
    return ai.generate_content(prompt).text

# ================= UI =================
st.markdown("### 🎙️ Nhập bằng giọng nói (hoặc gõ chữ)")
user_input = st.text_input(
    "Ví dụ: Tôi đi từ Đại học Bách Khoa đến Chợ Bến Thành, ưu tiên ít đi bộ"
)

col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ Bắt đầu"):
        st.session_state.running = True
        st.session_state.last_voice = ""
with col2:
    if st.button("⏹️ Dừng chỉ đường"):
        st.session_state.running = False
        st.session_state.last_voice = ""

# ================= MAIN LOGIC =================
if st.session_state.running:
    if not user_input:
        speak("Vui lòng nói hoặc nhập điểm đi và điểm đến")
        st.stop()

    # ===== AI hiểu yêu cầu =====
    ai_result = ai_parse_input(user_input)

    # Parse đơn giản
    lines = ai_result.splitlines()
    origin = destination = ""
    for l in lines:
        if "origin" in l:
            origin = l.split("=")[1].strip()
        if "destination" in l:
            destination = l.split("=")[1].strip()

    # ===== GPS =====
    loc = get_geolocation()
    if loc is None:
        speak("Đang xác định vị trí của bạn")
        st.stop()

    lat = loc["coords"]["latitude"]
    lng = loc["coords"]["longitude"]

    # ===== WALK TO STOP =====
    walk_params = {
        "origin": f"{lat},{lng}",
        "destination": origin,
        "mode": "walking",
        "language": "vi",
        "key": GOOGLE_MAPS_API_KEY
    }

    walk = requests.get(
        "https://maps.googleapis.com/maps/api/directions/json",
        params=walk_params
    ).json()

    step = clean_html(walk["routes"][0]["legs"][0]["steps"][0]["html_instructions"])
    direction = normalize_direction(step)

    # ===== BUS ETA =====
    transit_params = {
        "origin": origin,
        "destination": destination,
        "mode": "transit",
        "transit_mode": "bus",
        "departure_time": "now",
        "language": "vi",
        "key": GOOGLE_MAPS_API_KEY
    }

    transit = requests.get(
        "https://maps.googleapis.com/maps/api/directions/json",
        params=transit_params
    ).json()

    bus_info = "Đang chờ xe bus"
    for s in transit["routes"][0]["legs"][0]["steps"]:
        if s["travel_mode"] == "TRANSIT":
            td = s["transit_details"]
            line = td["line"].get("short_name", "")
            time_txt = td["departure_time"]["text"]
            bus_info = f"Xe số {line} sẽ đến lúc {time_txt}"
            break

    # ===== FINAL VOICE =====
    voice = f"{direction}. {bus_info}"

    if voice != st.session_state.last_voice:
        speak(voice)
        st.session_state.last_voice = voice

    time.sleep(8)
    st.rerun()

else:
    st.info("Ứng dụng đang chờ. Nhấn Bắt đầu để sử dụng.")

