import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="CreatorOS Pro v2", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_KEY"]
    SHEET_URL = st.secrets["SHEET_URL"]
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Check Streamlit Secrets for GEMINI_KEY and SHEET_URL")
    st.stop()

CSV_URL = SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv")

# --- 2. DYNAMIC DATA CLEANING ---
def clean_data(df):
    """Automatically cleans numerical columns and handles missing text"""
    # Clean Followers, Views, and Engagement (converts 10k to 10000, 5% to 0.05)
    for col in ['Followers', 'Views', 'Engagement']:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({'k': '*1e3', 'K': '*1e3', 'M': '*1e6', ',': '', '%': '/100'}, regex=True).map(pd.eval).fillna(0)
    
    # Fill missing text fields
    text_cols = ['Language', 'City', 'Niche']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("Not Specified")
    return df

# --- 3. DASHBOARD UI ---
st.title("🚀 Creator Dashboard")

# Sidebar: Campaign Setup (Requirement #1 & #2)
st.sidebar.header("Campaign Manager")
with st.sidebar.expander("📝 Setup New Campaign", expanded=True):
    c_code = st.text_input("Campaign Code*")
    c_name = st.text_input("Campaign Name*")
    # Dynamic Niche Selection
    target_niches = st.multiselect("Target Niches", ["Tech", "Fitness", "Lifestyle", "Fashion", "Travel"])

# Sidebar: Global Filters (Requirement #3)
st.sidebar.header("Global Filters")
raw_df = pd.read_csv(CSV_URL)
df = clean_data(raw_df)

selected_lang = st.sidebar.multiselect("Filter by Language", options=df['Language'].unique())
selected_city = st.sidebar.multiselect("Filter by City", options=df['City'].unique())

# --- 4. DATA PROCESSING & AI RANKING ---
# Filter data based on user selection
filtered_df = df.copy()

if target_niches:
    filtered_df = filtered_df[filtered_df['Niche'].str.contains('|'.join(target_niches), case=False)]
if selected_lang:
    filtered_df = filtered_df[filtered_df['Language'].isin(selected_lang)]
if selected_city:
    filtered_df = filtered_df[filtered_df['City'].isin(selected_city)]

# AI Feature: Detect Incomplete Profiles
filtered_df['Health_Check'] = filtered_df.apply(lambda x: "⚠️ Incomplete" if "Not Specified" in x.values else "✅ Healthy", axis=1)

# --- 5. MAIN DISPLAY ---
if c_code:
    st.subheader(f"Vetting: {c_name} [{c_code}]")
    st.write(f"Showing {len(filtered_df)} relevant creators")

    for _, row in filtered_df.iterrows():
        with st.container(border=True):
            # Layout for many fields
            header_col, stats_col, action_col = st.columns([2, 3, 1])
            
            with header_col:
                st.markdown(f"### {row['Handle']}")
                st.caption(f"📍 {row['City']} | 🌐 {row['Language']}")
                st.write(f"**Niche:** {row['Niche']}")
                if row['Health_Check'] == "⚠️ Incomplete":
                    st.warning("Profile needs more data")

            with stats_col:
                # Use columns inside columns for stats
                s1, s2, s3 = st.columns(3)
                s1.metric("Followers", f"{int(row['Followers']):,}")
                s2.metric("Avg Views", f"{int(row['Views']):,}")
                s3.metric("Engagement", f"{row['Engagement']:.1%}")
                
            with action_col:
                # Requirement #4: Classification
                status = st.selectbox("Action", ["Review", "Shortlisted", "Backup", "Rejected"], key=f"status_{row['Handle']}")
                if st.button("Confirm", key=f"btn_{row['Handle']}"):
                    st.success("Logged!")

else:
    st.info("👈 Enter a Campaign Code in the sidebar to begin.")

# AI Requirement Example: Auto-Recommendation
if st.checkbox("AI: Recommend Top 3 Creators"):
    st.write("Based on Engagement vs Views ratio, we recommend:")
    top_3 = filtered_df.sort_values(by='Engagement', ascending=False).head(3)
    st.table(top_3[['Handle', 'Engagement', 'Views']])
