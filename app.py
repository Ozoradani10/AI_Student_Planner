import os
import streamlit as st
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ========== ENV SETUP ==========
st.set_page_config(page_title="Païrent — AI Student Planner", page_icon="📘", layout="centered")

st.title("📘 Païrent — AI Student Planner")
st.markdown("Generate sharp, structured daily/weekly/monthly study plans, and deliver them via beautiful HTML email with a calendar attachment.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_NAME = os.getenv("SMTP_NAME")

if not OPENAI_API_KEY:
    st.error("❌ Missing OpenAI API key in Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# ========== INPUTS ==========
email = st.text_input("📧 Your email address")
goal = st.text_input("🎯 What do you want to study or achieve?")
duration = st.selectbox("🕒 Choose your plan type", ["Daily", "Weekly", "Monthly"])

# ========== GENERATE PLAN ==========
if st.button("✨ Generate Study Plan"):
    if not goal.strip():
        st.warning("Please enter what you want to study.")
    elif not email.strip():
        st.warning("Please enter your email address.")
    else:
        with st.spinner("Generating your AI-powered study plan..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a smart AI study planner that builds clear and motivational plans for students."},
                        {"role": "user", "content": f"Create a {duration.lower()} study plan for: {goal}"}
                    ]
                )
                ai_plan = response.choices[0].message.content.strip()

                # Display in Streamlit
                st.success("✅ Plan generated successfully!")
                st.markdown(f"### 🧠 Your {duration} Plan\n{ai_plan}")

                # ========== SEND EMAIL ==========
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Your {duration} Study Plan – Païrent AI"
                msg["From"] = f"{SMTP_NAME} <{SMTP_EMAIL}>"
                msg["To"] = email

                # Format HTML email content
                plan_html = ai_plan.replace("\n", "<br>")
                html_content = f"""
                <html>
                  <body style="font-family:Arial,sans-serif;background-color:#f8f9fd;color:#333;padding:20px;">
                    <h2 style="color:#007bff;">Your {duration} AI Study Plan 📘</h2>
                    <p>Hey student, here’s your smartly generated {duration.lower()} study plan!</p>
                    <div style="background-color:white;padding:15px;border-radius:10px;border:1px solid #ddd;">
                      {plan_html}
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

                st.info(f"📩 Plan sent successfully to *{email}*!")

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
