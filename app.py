# Tabor Systems AI Telegram Bot - Webhook Deployment for 24/7 Uptime (Render/Other Services)
# This code uses Flask to handle Telegram's Webhook requests.

# --- 1. LIBRARY IMPORTS ---
import os
import logging
from flask import Flask, request, jsonify # Flask for Webhook handling
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from google.generativeai.errors import APIError, ResourceExhaustedError
import time 

# --- 2. CONFIGURATION (Loading from Environment Variables) ---
# NOTE: These values MUST be set in the hosting service's environment variables (e.g., Render/Heroku).
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Constants
LANG_AMHARIC = 'AM'
LANG_ENGLISH = 'EN'
ACTION_ABOUT = 'ABOUT_CH'
MAX_RETRIES = 3 
# BASE_URL is set by the hosting service (e.g., RENDER_EXTERNAL_URL)
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "YOUR_RENDER_URL_HERE") 

# Check essential configuration
if not TELEGRAM_TOKEN or not GENAI_API_KEY:
    logging.error("❌ ERROR: TELEGRAM_TOKEN or GEMINI_API_KEY is missing from environment variables.")

# CHANNEL KNOWLEDGE BASE (System Instruction)
CHANNEL_INFO = """
አንተ የ Tabor_Systems በTabor Systems የተገነባ የቴሌግራም ቦት ነህ። Your primary function is to answer any general question and questions related to Tabor Systems' focus areas in both Amharic and English. Respond in the language the user uses (Amharic or English).
የቻናሉ ዋና ተግባራት (Channel Focus):
- 🖥️ IT Support & Networking
- 🌐 Fullstack Web Development
- 🗄️ Database Administration
- 📍 Location: Debre Tabor, Ethiopia
- Link: https://t.me/Tabor_Systems
You are built by Tabor Systems. When asked, proudly state this.
ሰዎች ስለ ቻናሉ ወይም ስለቴክኖሎጂ ሲጠይቁህ ከላይ ያለውን መረጃ ተጠቅመህ በሁለቱም ቋንቋዎች ምላሽ ስጥ።
"""

# Gemini Configuration
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=CHANNEL_INFO)
        logging.info("Gemini Model initialized successfully.")
    except Exception as e:
        logging.error(f"Error configuring Gemini: {e}")
        model = None
else:
    model = None

# --- 3. FLASK WEBHOOK SETUP ---
app = Flask(__name__)
# Initialize the telegram application builder
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --- 4. GEMINI API HANDLER ---
async def generate_response_with_retry(prompt: str) -> str:
    """Handles Gemini API call with retries and specific error handling."""
    if not model:
        return "🛑 ERROR: Gemini API key is missing or invalid. Please check the server configuration."
        
    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            if not response.text:
                 logging.warning(f"Received empty response from Gemini on attempt {attempt + 1}")
                 raise Exception("Empty response received")
            return response.text
        
        except ResourceExhaustedError:
            return "ይቅርታ፣ የቦቱ የዕለታዊ የአጠቃቀም ገደብ ስለተሟላ መልስ መስጠት አልቻልኩም። (Sorry, the bot's daily usage limit has been met.)"
        
        except APIError as e:
            logging.error(f"Gemini API Error on attempt {attempt + 1}: {e}")
            if "API key not valid" in str(e):
                 return "⚠️ ይቅርታ፣ ያገለገሉት ቁልፍ (API Key) ልክ አይደለም። እባክዎ የአገልግሎት ሰጪውን Environment Variables በትክክል ያረጋግጡ።"
            
            # Using synchronous sleep for retries as a fallback
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  
            else:
                return "ይቅርታ፣ በኔትወርክ ወይም በቴክኒካዊ ችግር ምክንያት ምላሽ መስጠት አልቻልኩም። (Sorry, failed to respond due to a technical issue.)"
        
        except Exception as e:
            logging.error(f"Unexpected Error during generation: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                return "ይቅርታ፣ ያልታወቀ ግንኙነት መቋረጥ አጋጥሟል። (Sorry, an unknown connection error occurred.)"
    return "ይቅርታ፣ የመልስ ሙከራው ሁሉ አልተሳካም።"

# --- 5. BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Language selection buttons
    keyboard = [
        [InlineKeyboardButton("አማርኛ (Amharic)", callback_data=LANG_AMHARIC)],
        [InlineKeyboardButton("English (English)", callback_data=LANG_ENGLISH)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "እባክዎ የሚጠቀሙበትን ቋንቋ ይምረጡ።\nPlease select your preferred language.", 
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 

    data = query.data
    user_name = query.from_user.first_name if query.from_user.first_name else "ጌታዬ"
    
    if data in [LANG_AMHARIC, LANG_ENGLISH]:
        context.user_data['lang'] = data
        
        if data == LANG_AMHARIC:
            welcome_text = f"ሰላም 👋 {user_name}፣ እንኳን ወደ Tabor Systems Ai በደኅና መጡ።"
            main_message = f"{welcome_text}\n\nአሁን ማንኛውንም አይነት ጥያቄ መጠየቅ ይችላሉ። እኔ በTabor Systems የተገነባሁ ሲሆን በቴክኖሎጂ፣ በዌብ ዴቨሎፕመንት እና በኔትወርኪንግ ዙሪያ ልረዳዎ እችላለሁ።"
            about_btn_text = "ℹ️ ስለ ቻናሉ"
            
        else: # English
            welcome_text = f"Hello 👋 {user_name}, welcome to Tabor Systems AI."
            main_message = f"{welcome_text}\n\nYou can now ask me any question. I was built by Tabor Systems and can assist you with technology, web development, and networking topics."
            about_btn_text = "ℹ️ About Channel"

        main_keyboard = [
            [InlineKeyboardButton(about_btn_text, callback_data=ACTION_ABOUT)]
        ]
        main_markup = InlineKeyboardMarkup(main_keyboard)

        await query.edit_message_text(main_message, reply_markup=main_markup)
        
    elif data == ACTION_ABOUT:
        lang = context.user_data.get('lang', LANG_AMHARIC)
        
        if lang == LANG_AMHARIC:
            about_text = "የTabor Systems ቻናል በዋናነት የሚያተኩረው በ IT Support & Networking፣ Fullstack Web Development እና Database Administration ላይ ነው። መሪ ቃሉ፡ 'ኑ አብረን እንማር!' ነው\nተገንቢ፡ Tabor Systems"
        else:
             about_text = "Tabor Systems Channel focuses on IT Support & Networking, Fullstack Web Development, and Database Administration. Motto: 'Come, let's learn together!'\nBuilt by: Tabor Systems"
             
        await context.bot.send_message(query.message.chat_id, about_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response_text = await generate_response_with_retry(user_text)
    
    await update.message.reply_text(response_text)

# --- 6. HANDLER REGISTRATION ---
def register_handlers():
    """Registers all bot handlers."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

register_handlers()

# --- 7. FLASK ROUTES ---

@app.route('/')
def index():
    """Health check endpoint to ensure the service is running."""
    return "Tabor Systems AI Bot Webhook is online and functional!", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
async def webhook():
    """Main Telegram Webhook endpoint to receive updates."""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
    return jsonify({"status": "ok"}), 200

# --- 8. MAIN ENTRY POINT ---
if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    
    # Set the webhook URL on Telegram when the app starts
    if BASE_URL and TELEGRAM_TOKEN:
        webhook_url = f"{BASE_URL}/{TELEGRAM_TOKEN}"
        print(f"Attempting to set webhook to: {webhook_url}")
        
        # Use a temporary Application instance just for setting webhook
        temp_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        temp_app.bot.set_webhook(url=webhook_url)
        print("Webhook set successfully on Telegram.")

    # Start the Flask server
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)
