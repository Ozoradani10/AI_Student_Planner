import os
os.environ["WATCHFILES_FORCE_POLLING"] = "true"

import streamlit as st
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz

# =============== APP TITLE / STYLE ===============
st.markdown("""
    <style>
        .main {
            background-color: #f8f9fd;
            font-family: 'Inter', sans-serif;
        }
        .stButton>button {
            background: linear-gradient(90deg, #007bff, #00c6ff);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.6rem 1.2rem;
            font-weight: bold;
        }
        .stButton>button:hover {
            background: linear-gradient(90deg, #0066cc, #00aaff);
        }
        .title {
            background: linear-gradient(90deg, #007bff, #00c6ff);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            font-size: 1.6rem;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🧠 Paîrent — AI Student Planner</div>', unsafe_allow_html=True)
st.write("Generate sharp, structured study plans and receive them as elegant HTML emails.")

# =============== LOAD SECRETS ===============
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = os.getenv("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", SMTP_USER)
SMTP_NAME = os.getenv("SMTP_NAME", "Paîrent Planner")

if not OPENAI_API_KEY:
    st.error("❌ Missing OPENAI_API_KEY secret. Add it in Streamlit → Settings → Secrets.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# =============== FORM INPUTS ===============
email = st.text_input("📧 Your email address")
goal = st.text_input("🎯 What do you want to study or achieve?")
duration = st.selectbox("📅 Choose your plan type", ["Daily", "Weekly", "Monthly"])

# =============== AI PLAN GENERATION ===============
if st.button("⚡ Generate Study Plan"):
    if not goal.strip():
        st.warning("Please enter your study goal first.")
    elif not email.strip():
        st.warning("Please enter your email address.")
    else:
        with st.spinner("Generating your AI-powered study plan..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert academic planner. Generate a clear, motivational, and structured study plan with time blocks and tasks."},
                        {"role": "user", "content": f"Create a {duration.lower()} study plan to achieve: {goal}"}
                    ],
                )
                ai_plan = response.choices[0].message.content.strip()

                st.success("✅ Plan generated successfully!")
                st.markdown(f"### 📘 Your {duration} Plan\n{ai_plan}")

                # Send email
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Your {duration} Study Plan — Paîrent AI"
                msg["From"] = f"{SMTP_NAME} <{SMTP_EMAIL}>"
                msg["To"] = email

                html_content = f"""
                <html>
                    <body style="font-family:Arial,sans-serif;background-color:#f8f9fd;color:#333;padding:20px;">
                        <h2 style="color:#007bff;">Your {duration} AI Study Plan 📘</h2>
                        <p>Hey student, here’s your smartly generated {duration.lower()} study plan!</p>
                        <div style="background-color:white;padding:15px;border-radius:10px;border:1px solid #ddd;">
                            {ai_plan.replace('\n', '<br>')}
                        </div>
                        <p style="margin-top:15px;">Stay focused and achieve greatness 💪</p>
                        <p>— {SMTP_NAME}</p>
                    </body>
                </html>
                """

                msg.attach(MIMEText(html_content, "html"))

                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_EMAIL, email, msg.as_string())

                st.info(f"📩 Plan sent successfully to {email}")

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
