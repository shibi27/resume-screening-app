import streamlit as st
import google.generativeai as genai
import pdfplumber
import pandas as pd
import matplotlib.pyplot as plt
import re
import json
import os
from io import StringIO


genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

st.set_page_config(page_title="Resume Screener & Ranking System", layout="wide", page_icon="🤖")

st.markdown("""
<style>
    body {background-color: #f5f7fa; font-family: 'Segoe UI', sans-serif;}
    .main-header {background: linear-gradient(90deg, #3b82f6 0%, #06b6d4 100%);
        color: white; padding: 30px; border-radius: 12px; text-align: center;
        margin-bottom: 25px; box-shadow: 0px 3px 10px rgba(0,0,0,0.15);}
    .result-card {background-color: #ffffff; padding: 20px; border-radius: 12px;
        margin-bottom: 18px; transition: all 0.2s ease-in-out;
        box-shadow: 0px 2px 8px rgba(0,0,0,0.05); color: #000000 !important;}
    .result-card:hover {transform: scale(1.01);
        box-shadow: 0px 4px 14px rgba(0,0,0,0.12);}
    .candidate-name {font-size: 22px; font-weight: 600; color: #0d47a1;}
    .stat-green {color: #16a34a !important;}
    .stat-orange {color: #f59e0b !important;}
    .stat-red {color: #dc2626 !important;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class='main-header'>
    <h1>🤖 Resume Screener, Skill Analyzer & Ranking System</h1>
    <p style='font-size:18px;'>Analyze resumes, rank candidates, and visualize their performance</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("⚙️ Filters & Options")
mode = st.sidebar.radio("Select Mode", ["AI Resume Screening", "CSV Resume Ranking"])
st.sidebar.markdown("---")

def color_for_match(pct):
    if pct >= 80: return "stat-green"
    elif pct >= 50: return "stat-orange"
    return "stat-red"

if mode == "AI Resume Screening":
    min_score = st.sidebar.slider("Minimum Score to Display", 0, 100, 0)
    job_description = st.text_area("📋 Enter Job Description:", height=180)
    uploaded_files = st.file_uploader("📄 Upload Candidate Resumes (PDF or TXT):", type=["pdf", "txt"], accept_multiple_files=True)
    if st.button("🔍 Analyze Resumes"):
        if not job_description or not uploaded_files:
            st.warning("⚠️ Please provide both job description and resumes.")
        else:
            results = []
            pattern = re.compile(
                r"\b(Python|Java|C\+\+|C|HTML|CSS|JavaScript|SQL|React|Node\.js|Django|Flask|AI|ML|Deep Learning|Data Science|TensorFlow|Pandas|NumPy|Angular|Communication|Leadership|Teamwork|Problem-solving)\b",
                re.IGNORECASE
            )
            job_skills = set(re.findall(pattern, job_description))
            for file in uploaded_files:
                if file.name.endswith(".pdf"):
                    with pdfplumber.open(file) as pdf:
                        resume_text = "".join(page.extract_text() or "" for page in pdf.pages)
                else:
                    resume_text = file.read().decode("utf-8")
                prompt = f"""
                You are an AI Resume Screening Assistant.
                Compare this resume with the job description below.

                ### Job Description:
                {job_description}

                ### Resume:
                {resume_text}

                Return structured JSON only:
                {{
                  "Score": "<numeric score 0-100>",
                  "AI Feedback": "<2-3 lines of feedback>",
                  "Summary": "<short summary>",
                  "Skills": ["list","of","skills"]
                }}
                """
                try:
                    model = genai.GenerativeModel("models/gemini-2.5-flash")
                    response = model.generate_content(prompt)
                    raw = re.sub(r"```(json)?", "", response.text.strip()).strip()
                    data = json.loads(raw)
                    extracted = set(map(str.lower, data.get("Skills", [])))
                    matched = [s for s in job_skills if s.lower() in extracted]
                    match_pct = round(len(matched) / len(job_skills) * 100, 2) if job_skills else 0
                    miss_pct = 100 - match_pct
                    results.append({
                        "Candidate": file.name,
                        "Score": float(data.get("Score", 0)),
                        "Matched %": match_pct,
                        "Missing %": miss_pct,
                        "Matched Skills": ", ".join(matched) or "None",
                        "Skills": ", ".join(extracted),
                        "Feedback": data.get("AI Feedback", "N/A"),
                        "Summary": data.get("Summary", "N/A")
                    })
                except Exception as e:
                    results.append({
                        "Candidate": file.name,
                        "Score": 0,
                        "Matched %": 0,
                        "Missing %": 100,
                        "Matched Skills": "None",
                        "Skills": "N/A",
                        "Feedback": f"Error: {e}",
                        "Summary": "N/A"
                    })
            df = pd.DataFrame(results).sort_values(by="Score", ascending=False)
            df["Selection Status"] = df["Score"].apply(lambda x: "✅ Selected" if x >= 75 else "❌ Not Selected")
            filtered_df = df[df["Score"] >= min_score]
            st.markdown("### 📊 Summary Overview")
            st.dataframe(filtered_df[["Candidate", "Score", "Matched %", "Missing %", "Selection Status"]], use_container_width=True)
            st.markdown("### 📈 Candidate Score Comparison")
            fig, ax = plt.subplots(figsize=(4, 1.5))   # reduces graph width & height
            ax.barh(
                filtered_df["Candidate"],
                filtered_df["Score"],
                height=0.15                             # reduces bar thickness
            )   
            ax.set_xlabel("AI Score")
            ax.set_title("Resume Ranking")
            plt.gca().invert_yaxis()
            st.pyplot(fig)
            csv = filtered_df.to_csv(index=False)
            st.download_button("📥 Download Results as CSV", data=csv, file_name="ai_resume_results.csv", mime="text/csv")
            st.markdown("### 🧾 Detailed Candidate Insights")
            for _, row in filtered_df.iterrows():
                match_class = color_for_match(row["Matched %"])
                st.markdown(f"""
                <div class='result-card'>
                    <div class='candidate-name'>👤 {row['Candidate']}</div>
                    <div style='margin-top:8px; color:#000000;'>
                        <b>💯 Score:</b> {row['Score']} / 100<br>
                        <b>🏁 Status:</b> {row['Selection Status']}<br>
                        <b class='{match_class}'>✅ Matched Skills:</b> {row['Matched %']}%<br>
                        <b>❌ Missing Skills:</b> {row['Missing %']}%<br><br>
                        <b>🧠 Feedback:</b> {row['Feedback']}<br>
                        <b>📄 Summary:</b> {row['Summary']}<br>
                        <b>🧩 Identified Skills:</b> {row['Skills']}<br>
                        <b>🏆 Matched Skills:</b> {row['Matched Skills']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

else:
    uploaded_file = st.file_uploader("📁 Upload CSV File", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()
        if "Candidate" not in df.columns or "Score" not in df.columns:
            st.error("CSV must contain 'Candidate' and 'Score' columns.")
        else:
            df["Selection_Status"] = df["Score"].apply(lambda x: "✅ Selected" if x >= 70 else "❌ Not Selected")
            st.markdown("### 📄 Candidate Data")
            st.dataframe(df)
            st.markdown("### 🔍 Filter by Score")
            min_score, max_score = st.slider("Select score range", float(df["Score"].min()), float(df["Score"].max()), (float(df["Score"].min()), float(df["Score"].max())))
            filtered_df = df[(df["Score"] >= min_score) & (df["Score"] <= max_score)]
            st.markdown("### 📈 Candidate Score Comparison")
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.barh(filtered_df["Candidate"], filtered_df["Score"], color="#60a5fa", height=0.4)
            ax.set_xlabel("AI Score")
            ax.set_title("Resume Ranking")
            plt.gca().invert_yaxis()
            st.pyplot(fig)
            st.markdown("### 🏆 Selection Results")
            for _, row in df.iterrows():
                st.write(f"{row['Candidate']}: {row['Selection_Status']}")
    else:
        st.info("Please upload a CSV file to proceed.")


