import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai

# Tetapan Logging Supaya Nampak Jelas di Render
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Ambil Token dan Kunci API dari Environment Variables Render
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inisialisasi Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    logger.error("GEMINI_API_KEY tidak dijumpai di environment variables!")

# Flask App untuk Pastikan Render Aktif 24/7
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot OT SOAP Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# Fungsi Penjanaan SOAP Menggunakan Gemini
async def generate_soap_report(clinical_notes: str) -> str:
    if not GEMINI_API_KEY:
        return "Ralat: API Key Gemini tidak dikonfikurasi."
    
    prompt = f"""
    Bertindak sebagai Pakar Terapi Carakerja (Occupational Therapist) pediatrik yang berpengalaman.
    Sila ambil nota kasar sesi pesakit di bawah dan susun menjadi laporan klinikal profesional berformat SOAP (Subjective, Objective, Assessment, Plan) dalam Bahasa Melayu.

    Nota Kasar Pesakit:
    {clinical_notes}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Ralat Gemini AI: {e}")
        return f"Gagal menjana laporan SOAP: {str(e)}"

# Handler Mesej Telegram
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    # Sapaan biasa
    sapaan_biasa = ["hi", "hello", "pagi", "selamat pagi", "assalamualaikum", "waalaikumsalam", "test", "salam"]
    if user_text.lower() in sapaan_biasa or len(user_text.split()) < 3:
        await update.message.reply_text(
            "Waalaikumsalam / Selamat pagi! ☀️\n"
            "Saya sedia membantu menyediakan laporan SOAP. "
            "Sila hantar nota kasar atau transkrip sesi pesakit bila-bila masa! 📋✨"
        )
        return

    # Proses nota klinikal
    msg = await update.message.reply_text("⏳ Sedang menyusun laporan SOAP...")
    
    soap_result = await generate_soap_report(user_text)
    
    await msg.edit_text(f"📋 *Laporan SOAP Klinikal:*\n\n{soap_result}", parse_mode="Markdown")

if __name__ == "__main__":
    print("[INFO] Memulakan Flask web server...")
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    print("[INFO] Menghubungkan Bot Telegram...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("[INFO] Bot sedang berjalan...")
    # drop_pending_updates=True elakkan konflik session lama
    app.run_polling(drop_pending_updates=True)