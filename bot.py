import os
import threading
import datetime
from flask import Flask
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# Google Docs & Drive API Library
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# KONFIGURASI KUNCI RAHSIA
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

genai.configure(api_key=GEMINI_API_KEY)

# Konfigurasi Google Docs API (Pastikan fail credentials.json ada dalam folder projek)
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "credentials.json"

# Pelayan web Flask ringkas untuk kekal aktif di platform cloud (cth: Render)
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot Telegram OT PA (GDocs Integration) sedang aktif!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# System Prompt Profesional SOAP Note OT (Point Form)
OT_SYSTEM_INSTRUCTION = """
Anda adalah Pembantu Peribadi AI profesional yang bertugas khusus untuk membantu Occupational Therapist (OT) menghasilkan laporan klinikal format SOAP. 
Tugas anda adalah mengambil nota kasar / transkrip suara (rojak Bahasa Melayu/Inggeris) daripada terapis dan menyusunnya dengan teratur STRICTLY mengikut format senarai bernombor (point form) seperti berikut:

**S - Subjective**
1. [Maklumat aduan ibu bapa / guru]
2. [...]

**O - Objective**
1. **Participation / Behavior:** [...]
2. **Gross Motor / Sensory:** [...]
3. **Fine Motor / Tactile:** [...]
4. **Cognitive / Social:** [...]

**A - Assessment**
1. [...]
2. [...]

**P - Plan**
1. **In-Clinic Interventions:** [...]
2. **Home Program / Parent Notes:** [...]

PENTING: Gunakan format bernombor (1, 2, 3...) di bawah setiap tajuk SOAP. Nada bahasa profesional.
"""

# Fungsi untuk Auto-Create Google Docs
def create_google_doc_report(soap_text):
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        docs_service = build('docs', 'v1', credentials=creds)
        
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        doc_title = f"Laporan SOAP OT - {current_time_str}"
        
        body = {'title': doc_title}
        doc = docs_service.documents().create(body=body).execute()
        document_id = doc.get('documentId')

        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': f"LAPORAN KLINIKAL OCCUPATIONAL THERAPY (SOAP)\nTarikh: {current_time_str}\n\n{soap_text}"
                }
            }
        ]
        docs_service.documents().batchUpdate(
            documentId=document_id, body={'requests': requests}
        ).execute()

        file_url = f"https://docs.google.com/document/d/{document_id}/edit"
        return file_url

    except Exception as e:
        print(f"Ralat Google Docs API: {str(e)}")
        return None

# Fungsi Proses Gemini & Cipta Google Doc
async def process_and_create_doc(update: Update, prompt_text=None, audio_bytes=None):
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=OT_SYSTEM_INSTRUCTION
        )
        
        if audio_bytes:
            response = model.generate_content([
                {"mime_type": "audio/ogg", "data": audio_bytes},
                "Sila transkrip dan tukarkan audio sesi terapi ini kepada format laporan SOAP bernombor."
            ])
        else:
            response = model.generate_content(prompt_text)
            
        soap_report = response.text
        
        # Cipta fail Google Docs rasmi
        doc_url = create_google_doc_report(soap_report)
        
        reply_msg = f"📋 *SOAP Report (Point Form):*\n\n{soap_report}"
        if doc_url:
            reply_msg += f"\n\n📂 **Fail Google Docs Rasmi:**\n{doc_url}"
            
        await update.message.reply_text(reply_msg, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"Ralat berlaku: {str(e)}")

# Handle Mesej Teks
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await process_and_create_doc(update, prompt_text=user_text)

# Handle Mesej Suara (Voice Note)
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ Menerima suara... Sedang memproses laporan SOAP & menjana Google Docs...")
    
    voice_file = await update.message.voice.get_file()
    audio_path = "voice_note.oga"
    await voice_file.download_to_drive(audio_path)
    
    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        await process_and_create_doc(update, audio_bytes=audio_bytes)
        
    except Exception as e:
        await update.message.reply_text(f"Ralat memproses suara: {str(e)}")
    
    if os.path.exists(audio_path):
        os.remove(audio_path)

if __name__ == "__main__":
    # Jalankan Flask server dalam background thread
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    # Jalankan Bot Telegram
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("Bot Telegram OT PA (Dengan GDocs Auto-Create) sedang berjalan...")
    app.run_polling()
