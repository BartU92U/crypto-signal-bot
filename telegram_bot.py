import logging
import json
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from config import TELEGRAM_BOT_TOKEN
from exchange_client import ExchangeClient

# Ustawienie logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ścieżka do pliku przechowującego symbole
SYMBOLS_FILE = 'monitored_symbols.json'

# Stany konwersacji
CHOOSING, AWAITING_SYMBOL_TO_ADD, AWAITING_SYMBOL_TO_REMOVE = range(3)

# --- Funkcje pomocnicze do zarządzania symbolami ---
def load_symbols():
    try:
        with open(SYMBOLS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('symbols', [])
    except FileNotFoundError:
        return []

def save_symbols(symbols):
    with open(SYMBOLS_FILE, 'w') as f:
        json.dump({'symbols': symbols}, f, indent=4)

# --- Główna logika bota ---
class TelegramBot:
    def __init__(self, exchange_client: ExchangeClient, chat_id: str):
        self.exchange_client = exchange_client
        self.chat_id = chat_id
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                CHOOSING: [
                    CallbackQueryHandler(self.handle_add_symbol_start, pattern='^add_symbol$'),
                    CallbackQueryHandler(self.handle_remove_symbol_start, pattern='^remove_symbol$'),
                    CallbackQueryHandler(self.list_symbols, pattern='^list_symbols$'),
                    CallbackQueryHandler(self.test_pairs, pattern='^test_pairs$'),
                ],
                AWAITING_SYMBOL_TO_ADD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_symbol_receive)
                ],
                AWAITING_SYMBOL_TO_REMOVE: [
                    CallbackQueryHandler(self.handle_remove_symbol_select, pattern='^remove_')
                ],
            },
            fallbacks=[CommandHandler('start', self.start)], # Powrót do menu po akcji
        )

        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler("status", self.status))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyboard = [
            [InlineKeyboardButton("📊 Monitorowane pary", callback_data='list_symbols')],
            [InlineKeyboardButton("➕ Dodaj parę", callback_data='add_symbol')],
            [InlineKeyboardButton("➖ Usuń parę", callback_data='remove_symbol')],
            [InlineKeyboardButton("🔬 Test", callback_data='test_pairs')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Jeśli to pierwsze wywołanie /start, wyślij nową wiadomość. Jeśli to powrót do menu, edytuj istniejącą.
        if update.callback_query:
            await update.callback_query.edit_message_text('🤖 Witaj! Co chcesz zrobić?', reply_markup=reply_markup)
        else:
            await update.message.reply_text('🤖 Witaj! Co chcesz zrobić?', reply_markup=reply_markup)
            
        return CHOOSING

    async def list_symbols(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        symbols = load_symbols()
        if not symbols:
            message = "Lista monitorowanych par jest pusta."
        else:
            monitored_pairs = "\n - ".join(symbols)
            message = f"<b>📊 Aktualnie monitorowane pary:</b>\n\n - {monitored_pairs}"
        
        await query.edit_message_text(message, parse_mode='HTML')
        await asyncio.sleep(3) # Czekaj 3 sekundy
        return await self.start(update, context) # Wróć do menu głównego

    async def test_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔬 Rozpoczynam testowanie par...")

        symbols = load_symbols()
        if not symbols:
            await query.edit_message_text("Lista monitorowanych par jest pusta. Nie ma czego testować.")
            await asyncio.sleep(3)
            return await self.start(update, context)

        results = []
        for symbol in symbols:
            df = self.exchange_client.fetch_ohlcv(symbol, '1m', limit=1)
            if not df.empty:
                results.append(f"✅ <b>{symbol}:</b> OK")
            else:
                results.append(f"❌ <b>{symbol}:</b> BŁĄD (Nie można pobrać danych. Sprawdź, czy para istnieje na Binance.)")
            await asyncio.sleep(1) # Unikaj zbyt szybkich zapytań

        report = "<b>🔬 Raport z testu:</b>\n\n" + "\n".join(results)
        await query.edit_message_text(report, parse_mode='HTML')
        await asyncio.sleep(5) # Zostaw raport na 5 sekund
        return await self.start(update, context)

    async def handle_add_symbol_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text="Podaj parę, którą chcesz dodać (np. ETH/USDC, SOL/USDC).")
        return AWAITING_SYMBOL_TO_ADD

    async def handle_add_symbol_receive(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        symbol_to_add = update.message.text.upper().strip()
        
        if not '/' in symbol_to_add:
            await update.message.reply_text("Nieprawidłowy format. Para musi zawierać '/', np. BTC/USDC.")
            return AWAITING_SYMBOL_TO_ADD

        await update.message.reply_text(f"Sprawdzam, czy para '{symbol_to_add}' istnieje na Binance...")
        
        if self.exchange_client.symbol_exists(symbol_to_add):
            symbols = load_symbols()
            if symbol_to_add not in symbols:
                symbols.append(symbol_to_add)
                save_symbols(symbols)
                await update.message.reply_text(f"✅ Para '{symbol_to_add}' została pomyślnie dodana.")
            else:
                await update.message.reply_text(f"⚠️ Para '{symbol_to_add}' już jest na liście.")
        else:
            await update.message.reply_text(f"❌ Niestety, para '{symbol_to_add}' nie została znaleziona na Binance.")
        
        await update.message.reply_text("Możesz dodać kolejną parę lub wrócić do menu, wpisując /start.")
        return AWAITING_SYMBOL_TO_ADD

    async def handle_remove_symbol_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        symbols = load_symbols()
        if not symbols:
            await query.edit_message_text('Lista monitorowanych par jest pusta.')
            await asyncio.sleep(2)
            return await self.start(update, context)
        
        keyboard = [[InlineKeyboardButton(s, callback_data='remove_' + s)] for s in symbols]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('Wybierz parę do usunięcia:', reply_markup=reply_markup)
        return AWAITING_SYMBOL_TO_REMOVE

    async def handle_remove_symbol_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        symbol_to_remove = query.data.split('_', 1)[1]
        
        symbols = load_symbols()
        if symbol_to_remove in symbols:
            symbols.remove(symbol_to_remove)
            save_symbols(symbols)
            await query.edit_message_text(f"✅ Para '{symbol_to_remove}' została usunięta.")
        else:
            await query.edit_message_text(f"⚠️ Nie znaleziono pary '{symbol_to_remove}' na liście.")
            
        await asyncio.sleep(2)
        return await self.start(update, context)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        monitored_pairs = "\n - ".join(load_symbols())
        message = f"<b>🤖 Status Bota 🤖</b>\n<b>Status:</b> Aktywny ✅\n<b>Monitorowane pary:</b>\n - {monitored_pairs}"
        await update.message.reply_text(message, parse_mode='HTML')

    async def send_signal(self, signal_data):
        message = self._format_signal_message(signal_data)
        await self.app.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
    
    def _format_signal_message(self, signal_data):
        signal_type, symbol = signal_data['type'], signal_data.get('symbol', 'N/A')
        price = signal_data['price']
        timestamp = signal_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        reason = signal_data['reason']
        emoji = '🟢 BUY SIGNAL 🟢' if signal_type == 'BUY' else '🔴 SELL SIGNAL 🔴'
        message = f"<b>{emoji}</b>\n\n<b>Symbol:</b> {symbol}\n<b>Cena:</b> {price:.4f} USDC\n<b>Czas:</b> {timestamp}\n<b>Powód:</b> {reason}\n\n<i>To nie jest porada finansowa.</i>"
        return message