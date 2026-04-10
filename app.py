import streamlit as st
import pandas as pd
from google import genai

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="CreatorOS Pro", layout="wide")

# Custom CSS for a professional "SaaS" feel
st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;} 
    .stTabs [data-baseweb="tab-list"] {gap: 24px;}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; padding: 10px;}
    .stTabs [aria-selected="true"] {background-color: #4CAF50; color: white;}
    </style>
    """, unsafe_allow_html=True)

try:
    API_KEY = st.secrets["GEMINI_KEY"]
    SHEET_URL = st.secrets["SHEET_URL"]
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error("Secrets missing: GEMINI_KEY or SHEET_URL")
    st.stop()

# --- 2. THE DATA ENGINE (AUTO-NORMALIZING) ---
@st.cache_data(ttl=60)
def get_clean_data(url):
    csv_url = url.replace("/edit?usp=sharing", "/export?format=csv")
    df = pd.read_csv(csv_url)
    
    # CRITICAL: Normalize Column Names (Removes spaces, lowercase everything)
    # This fixes the KeyError: 'Primary_Niche'
    df.columns = df.columns.str.strip().str.replace(' ', '_').str.lower()
    
    def clean_num(val):
        if pd.isna(val): return 0
        val = str(val).lower().replace('$', '').replace(',', '').replace('%', '')
        if 'k' in val: return float(val.replace('k', '')) * 1000
        if 'm' in val: return float(val.replace('m', '')) * 1000000
        try: return float(val)
        except: return 0

    # Auto-clean known numeric columns
    for col in ['followers', 'engagement_rate_%', 'avg_views', 'cost_per_post']:
        if col in df.columns:
            df[col] = df[col].apply(clean_num)
        else:
            df[col] = 0
            
    return df

# Initialize Session State
if 'campaigns' not in st.session_state: st.session_state.campaigns = {}
if 'classification' not in st.session_state: st.session_state.classification = {}

# --- 3. CAMPAIGN HUB ---
st.title("🚀 CreatorOS Intelligence")

tab_new, tab_existing = st.tabs(["➕ Create New Campaign", "📂 Select Existing Campaign"])

with tab_new:
    c1, c2, c3 = st.columns([1,1,2])
    c_code = c1.text_input("Campaign Code*", placeholder="e.g. SUM25")
    c_name = c2.text_input("Campaign Name*", placeholder="Summer Launch")
    c_niches = c3.multiselect("Select Target Niches", ["Tech", "Fitness", "Fashion", "Travel", "Gaming", "Food"])
    
    if st.button("Initialize Campaign"):
        if c_code and c_name:
            st.session_state.campaigns[c_code] = {"name": c_name, "niches": [n.lower() for n in c_niches]}
            st.session_state.active_campaign = c_code
            st.success(f"Campaign {c_code} created!")
        else:
            st.error("Code and Name are mandatory.")

with tab_existing:
    if st.session_state.campaigns:
        choice = st.selectbox("Select Active Campaign", options=list(st.session_state.campaigns.keys()))
        if st.button("Activate"):
            st.session_state.active_campaign = choice
    else:
        st.info("No campaigns found.")

# --- 4. DASHBOARD (MAIN VETTING FLOW) ---
if 'active_campaign' in st.session_state:
    active_id = st.session_state.active_campaign
    camp = st.session_state.campaigns[active_id]
    df = get_clean_data(SHEET_URL)
    
    st.divider()
    st.subheader(f"Vetting for: {camp['name']} ({active_id})")

    # AI Feature: Relevance Ranking (Requirement #4)
    def score_relevance(row, target_niches):
        if not target_niches: return 0
        score = 0
        # Check normalized columns
        p_niche = str(row.get('primary_niche', '')).lower()
        s_niche = str(row.get('secondary_niche', '')).lower()
        for tn in target_niches:
            if tn in p_niche: score += 10
            if tn in s_niche: score += 5
        return score

    df['relevance'] = df.apply(lambda r: score_relevance(r, camp['niches']), axis=1)
    
    # Filter based on campaign niches if any selected
    if camp['niches']:
        display_df = df[df['relevance'] > 0].sort_values('relevance', ascending=False)
    else:
        display_df = df

    # --- GRID DISPLAY ---
    if display_df.empty:
        st.warning("No creators match the selected niches.")
    else:
        for _, row in display_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 3, 2])
                
                with col1:
                    st.markdown(f"### {row['name']}")
                    st.caption(f"ID: {row.get('creator_id', 'N/A')} | Platform: {row.get('platform', 'N/A')}")
                    st.write(f"**Niches:** {row.get('primary_niche')} / {row.get('secondary_niche')}")
                    # AI Detect Incomplete Profiles
                    if pd.isna(row.get('contact_email')) or row.get('avg_views', 0) == 0:
                        st.warning("⚠️ Profile Incomplete")

                with col2:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Followers", f"{int(row.get('followers', 0)):,}")
                    m2.metric("Engagement", f"{row.get('engagement_rate_%', 0)}%")
                    m3.metric("Avg Views", f"{int(row.get('avg_views', 0)):,}")
                    st.markdown(f"💰 **Cost:** ${row.get('cost_per_post', 0):,.2f}")

                with col3:
                    # Requirement #4: Creator Classification
                    key = f"{active_id}_{row['name']}"
                    current_status = st.session_state.classification.get(key, "Pending")
                    st.write(f"Status: **{current_status}**")
                    
                    b1, b2, b3 = st.columns(3)
                    if b1.button("✅", key=f"s_{key}", help="Shortlist"):
                        st.session_state.classification[key] = "Shortlisted"
                        st.rerun()
                    if b2.button("⏳", key=f"b_{key}", help="Backup"):
                        st.session_state.classification[key] = "Backup"
                        st.rerun()
                    if b3.button("❌", key=f"r_{key}", help="Reject"):
                        st.session_state.classification[key] = "Rejected"
                        st.rerun()

        # AI Recommendation Section
        st.divider()
        st.subheader("🤖 AI Smart Recommendation")
        top_pick = display_df.iloc[0]
        st.success(f"**Top Recommendation:** {top_pick['name']}. Based on your campaign goals, they have the highest relevance score and an engagement rate of {top_pick['engagement_rate_%']}%")
else:
    st.info("Start by creating a campaign above.")
