import streamlit as st
import pandas as pd
from google import genai

# --- 1. SETTINGS & AI CONFIG ---
st.set_page_config(page_title="CreatorOS: ROI Dashboard", layout="wide")

# Custom CSS for a clean, dashboard-centric look
st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;} /* Hide Sidebar for a cleaner UI */
    .stButton>button {width: 100%; border-radius: 5px;}
    .creator-card {padding: 20px; border: 1px solid #ddd; border-radius: 10px; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)

try:
    client = genai.Client(api_key=st.secrets["GEMINI_KEY"])
    SHEET_URL = st.secrets["SHEET_URL"]
except:
    st.error("Please set up Secrets: GEMINI_KEY and SHEET_URL")
    st.stop()

CSV_URL = SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv")

# --- 2. DATA HANDLING (RESTACKING & CLEANING) ---
@st.cache_data(ttl=300)
def get_structured_data(url):
    df = pd.read_csv(url)
    
    # Fix the 'Followers' Error: Clean column names (removes hidden spaces/case issues)
    df.columns = df.columns.str.strip()
    
    def parse_num(val):
        if pd.isna(val): return 0
        val = str(val).lower().replace('$', '').replace(',', '').replace('%', '')
        if 'k' in val: return float(val.replace('k', '')) * 1000
        if 'm' in val: return float(val.replace('m', '')) * 1000000
        try: return float(val)
        except: return 0

    # Systematic Cleaning
    num_cols = ['Followers', 'Engagement_Rate_%', 'Avg_Views', 'Cost_Per_Post']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_num)
        else:
            df[col] = 0 # Create column if missing to prevent crashes
            
    return df

# Initialize State
if 'campaigns' not in st.session_state:
    st.session_state.campaigns = {} # Stores Campaign Code: {Details}
if 'classifications' not in st.session_state:
    st.session_state.classifications = {} # Stores Creator: Status

# --- 3. UI: CAMPAIGN HUB (TOP SECTION) ---
st.title("🚀 Creator Dashboard")

tab_new, tab_existing = st.tabs(["➕ Create New Campaign", "📂 Select Existing Campaign"])

with tab_new:
    c1, c2, c3 = st.columns([1, 1, 2])
    new_code = c1.text_input("Campaign Code*", placeholder="e.g. SUM24")
    new_name = c2.text_input("Campaign Name*", placeholder="Summer Launch")
    new_niches = c3.multiselect("Select Target Niches", ["Tech", "Fitness", "Fashion", "Lifestyle", "Gaming", "Travel"])
    if st.button("🚀 Initialize Campaign"):
        if new_code and new_name:
            st.session_state.campaigns[new_code] = {"name": new_name, "niches": new_niches}
            st.session_state.active_code = new_code
            st.success(f"Campaign {new_code} ready!")

with tab_existing:
    if st.session_state.campaigns:
        selected_code = st.selectbox("Switch to Campaign", options=list(st.session_state.campaigns.keys()))
        if st.button("Activate Selection"):
            st.session_state.active_code = selected_code
    else:
        st.info("No campaigns created yet.")

# --- 4. MAIN DASHBOARD AREA ---
if 'active_code' in st.session_state:
    active_code = st.session_state.active_code
    camp = st.session_state.campaigns[active_code]
    df = get_structured_data(CSV_URL)

    st.divider()
    st.subheader(f"Dashboard: {camp['name']} ({active_code})")
    
    # AI Feature: Ranking & Relevance
    def calculate_relevance(row, target_niches):
        score = 0
        if not target_niches: return 0
        for n in target_niches:
            if n.lower() in str(row['Primary_Niche']).lower(): score += 2
            if n.lower() in str(row['Secondary_Niche']).lower(): score += 1
        return score

    df['Relevance_Score'] = df.apply(lambda r: calculate_relevance(r, camp['niches']), axis=1)
    
    # AI Feature: Detect Incomplete Profiles
    df['Status_Flag'] = df.apply(lambda x: "⚠️ Incomplete" if pd.isna(x['Contact_Email']) or x['Avg_Views'] == 0 else "✅ Ready", axis=1)
    
    # Sort by Relevance
    display_df = df.sort_values(by='Relevance_Score', ascending=False)

    # UI Grid
    for _, row in display_df.iterrows():
        # Hide if not relevant at all to keep UI clean
        if len(camp['niches']) > 0 and row['Relevance_Score'] == 0:
            continue
            
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 3, 2])
            
            with col1:
                st.markdown(f"### {row['Name']}")
                st.caption(f"Handle: {row.get('Name', 'Unknown')} | {row['Status_Flag']}")
                st.write(f"**Relevance Rank:** {'⭐' * int(row['Relevance_Score'])}")
                st.write(f"📍 {row['City']} | {row['Language']}")

            with col2:
                m1, m2, m3 = st.columns(3)
                m1.metric("Followers", f"{int(row['Followers']):,}")
                m2.metric("Engagement", f"{row['Engagement_Rate_%']}%")
                m3.metric("Avg Views", f"{int(row['Avg_Views']):,}")
                st.markdown(f"💰 **Cost:** ${row['Cost_Per_Post']:,.2f}")
            
            with col3:
                # Creator Classification (Task #4)
                current_status = st.session_state.classifications.get(f"{active_code}_{row['Name']}", "Review")
                st.write(f"Current Status: **{current_status}**")
                
                # Classification Buttons
                b1, b2, b3 = st.columns(3)
                if b1.button("✅", key=f"s_{row['Name']}", help="Shortlist"):
                    st.session_state.classifications[f"{active_code}_{row['Name']}"] = "Shortlisted"
                    st.rerun()
                if b2.button("⏳", key=f"b_{row['Name']}", help="Backup"):
                    st.session_state.classifications[f"{active_code}_{row['Name']}"] = "Backup"
                    st.rerun()
                if b3.button("❌", key=f"r_{row['Name']}", help="Reject"):
                    st.session_state.classifications[f"{active_code}_{row['Name']}"] = "Rejected"
                    st.rerun()

    # AI Feature: Recommend Top Pick
    if not display_df.empty:
        st.divider()
        st.subheader("🤖 AI Smart Recommendation")
        top_pick = display_df.iloc[0]
        st.info(f"Based on your niches ({', '.join(camp['niches'])}), the best match is **{top_pick['Name']}** because they have the highest Relevance Score and {top_pick['Engagement_Rate_%']}% engagement.")

else:
    st.info("👋 Welcome! Start by creating a New Campaign above.")
