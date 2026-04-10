import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. SETTINGS & AI CONFIG ---
st.set_page_config(page_title="CreatorOS: ROI Dashboard", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_KEY"]
    SHEET_URL = st.secrets["SHEET_URL"]
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Setup Secrets: GEMINI_KEY and SHEET_URL")
    st.stop()

# Convert Google Sheet URL to direct CSV link
CSV_URL = SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv")

# --- 2. ADVANCED DATA ENGINE ---
@st.cache_data(ttl=600) # Refreshes every 10 mins
def load_and_clean_data(url):
    df = pd.read_csv(url)
    
    # Clean Numeric Columns
    def parse_num(val):
        if pd.isna(val): return 0
        val = str(val).lower().replace('$', '').replace(',', '').replace('%', '')
        if 'k' in val: return float(val.replace('k', '')) * 1000
        if 'm' in val: return float(val.replace('m', '')) * 1000000
        try: return float(val)
        except: return 0

    df['Followers'] = df['Followers'].apply(parse_num)
    df['Engagement_Rate_%'] = df['Engagement_Rate_%'].apply(parse_num)
    df['Avg_Views'] = df['Avg_Views'].apply(parse_num)
    df['Cost_Per_Post'] = df['Cost_Per_Post'].apply(parse_num)
    
    # AI Feature: Calculate Value Score (Views per Dollar)
    df['Value_Score'] = df.apply(lambda x: x['Avg_Views'] / x['Cost_Per_Post'] if x['Cost_Per_Post'] > 0 else 0, axis=1)
    
    return df

# --- 3. SIDEBAR: CAMPAIGN FLOW ---
st.sidebar.header("📁 Campaign Management")
mode = st.sidebar.radio("Flow", ["New Campaign", "Select Existing"])

if mode == "New Campaign":
    with st.sidebar.form("campaign_form"):
        c_code = st.text_input("Campaign Code (Mandatory)*")
        c_name = st.text_input("Campaign Name (Mandatory)*")
        # Combine niches for selection
        available_niches = ["Tech", "Fitness", "Fashion", "Travel", "Lifestyle", "Gaming", "Food"]
        c_niches = st.multiselect("Target Niches*", available_niches)
        submit = st.form_submit_button("Create")
        if submit and c_code and c_name:
            st.session_state['active_camp'] = {"code": c_code, "name": c_name, "niches": c_niches}
else:
    # Simulated existing campaigns
    st.session_state['active_camp'] = {"code": "SUMMER24", "name": "Summer Launch", "niches": ["Travel", "Lifestyle"]}

# --- 4. MAIN DASHBOARD ---
st.title("🚀 Creator Dashboard")

try:
    df = load_and_clean_data(CSV_URL)
    
    if 'active_camp' in st.session_state:
        camp = st.session_state['active_camp']
        st.subheader(f"Vetting for: {camp['name']} ({camp['code']})")
        
        # Filtering logic: Checks BOTH Primary and Secondary Niches
        if camp['niches']:
            mask = df['Primary_Niche'].isin(camp['niches']) | df['Secondary_Niche'].isin(camp['niches'])
            filtered_df = df[mask]
        else:
            filtered_df = df

        # AI Recommendations Top Bar
        top_val = filtered_df.sort_values('Value_Score', ascending=False).head(1)
        if not top_val.empty:
            st.info(f"💡 AI Suggestion: **{top_val.iloc[0]['Name']}** offers the best 'Views-per-Dollar' in this niche.")

        # --- CREATOR GRID ---
        for _, row in filtered_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 3, 1])
                
                with col1:
                    st.markdown(f"### {row['Name']}")
                    st.caption(f"🆔 ID: {row['Creator_ID']} | 📍 {row['City']}")
                    st.write(f"**Niches:** {row['Primary_Niche']} / {row['Secondary_Niche']}")
                    st.write(f"**Platform:** {row['Platform']}")

                with col2:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Followers", f"{int(row['Followers']):,}")
                    m2.metric("Engagement", f"{row['Engagement_Rate_%']}%")
                    m3.metric("Avg Views", f"{int(row['Avg_Views']):,}")
                    
                    # Cost Highlight
                    st.markdown(f"💰 **Cost per Post:** ${row['Cost_Per_Post']:,.2f}")
                    # Email/Contact Expander (Saves space)
                    with st.expander("📞 View Contact Details"):
                        st.write(f"📧 {row['Contact_Email']}")
                        st.write(f"📱 {row['Contact_Number']}")

                with col3:
                    # Requirement: Classification
                    status = st.selectbox("Classification", ["Review", "Shortlisted", "Backup", "Rejected"], key=f"stat_{row['Creator_ID']}")
                    if st.button("Save", key=f"save_{row['Creator_ID']}"):
                        st.success("Updated")

    else:
        st.warning("Please set up a Campaign in the sidebar to view relevant creators.")

except Exception as e:
    st.error(f"Error: Ensure your Google Sheet is shared 'Anyone with the Link'. Details: {e}")
