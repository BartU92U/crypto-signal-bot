import logging
import json
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from config import TELEGRAM_BOT_TOKEN, TIMEFRAME_MACRO, TIMEFRAME_MICRO
from exchange_client import ExchangeClient
from strategy_analyzer import StrategyAnalyzer
from utils import load_symbols, save_symbols

# Ustawienie logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Stany konwersacji rozszerzone o Fibonacci
CHOOSING, AWAITING_SYMBOL_TO_ADD, AWAITING_SYMBOL_TO_REMOVE, CHOOSING_FIB_SYMBOL = range(4)

class TelegramBot:
    def __init__(self, exchange_client: ExchangeClient, chat_id: str):
        self.exchange_client = exchange_client
        self.chat_id = chat_id
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.strategy_analyzer = StrategyAnalyzer()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                CHOOSING: [
                    CallbackQueryHandler(self.start, pattern='^back_to_main$'),
                    CallbackQueryHandler(self.list_symbols, pattern='^list_symbols$'),
                    CallbackQueryHandler(self.handle_add_symbol_start, pattern='^add_symbol$'),
                    CallbackQueryHandler(self.handle_remove_symbol_start, pattern='^remove_symbol$'),
                    CallbackQueryHandler(self.test_pairs, pattern='^test_pairs$'),
                    CallbackQueryHandler(self.fib_start, pattern='^fibonacci$'),
                ],
                AWAITING_SYMBOL_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_add_symbol_receive)],
                AWAITING_SYMBOL_TO_REMOVE: [CallbackQueryHandler(self.handle_remove_symbol_select, pattern='^remove_')],
                CHOOSING_FIB_SYMBOL: [CallbackQueryHandler(self.fib_analyze, pattern='^fib_')]
            },
            fallbacks=[CommandHandler('start', self.start)],
        )
        self.app.add_handler(conv_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyboard = [
            [InlineKeyboardButton("📊 Monitorowane pary", callback_data='list_symbols')],
            [InlineKeyboardButton("🔬 Test strategii", callback_data='test_pairs')],
            [InlineKeyboardButton("〽️ Mierzenie Fibonacciego", callback_data='fibonacci')],
            [InlineKeyboardButton("➕ Dodaj parę", callback_data='add_symbol'),
             InlineKeyboardButton("➖ Usuń parę", callback_data='remove_symbol')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = '🤖 Witaj! Co chcesz zrobić?'
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
        return CHOOSING

    # ... (wszystkie inne funkcje, takie jak list_symbols, test_pairs, fib_start, etc. pozostają bez zmian)
    async def list_symbols(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        symbols = load_symbols()
        message = "Lista monitorowanych par jest pusta."
        if symbols:
            monitored_pairs = "\n - ".join(symbols)
            message = f"<b>📊 Aktualnie monitorowane pary:</b>\n\n - {monitored_pairs}"
        
        keyboard = [[InlineKeyboardButton("⬅️ Wróć do menu", callback_data='back_to_main')]]
        await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING

    async def test_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔬 Rozpoczynam szczegółowy test strategii...")

        symbols = load_symbols()
        if not symbols:
            await query.edit_message_text("Lista par jest pusta. Nie ma czego testować.")
            await asyncio.sleep(2)
            return await self.start(update, context)

        report_parts = ["<b>🔬 Raport z testu strategii:</b>\n"]
        for symbol in symbols:
            await query.edit_message_text(f"🔬 Testuję {symbol}...")
            df_macro = self.exchange_client.fetch_ohlcv(symbol, TIMEFRAME_MACRO, limit=300)
            df_micro = self.exchange_client.fetch_ohlcv(symbol, TIMEFRAME_MICRO, limit=300)

            part = f"\n--- <b>{symbol}</b> ---\\n"
            if df_macro.empty or df_micro.empty:
                part += "❌ BŁĄD: Nie można pobrać danych z giełdy."
                report_parts.append(part)
                continue

            status = self.strategy_analyzer.get_status(df_macro, df_micro)
            if status['error']:
                part += f"⚠️ Błąd analizy: {status['error']}"
            else:
                trend_emoji = "✅" if status['trend'] in ["WZROSTOWY", "SPADKOWY"] else "❌"
                rsi_emoji = "✅" if "Neutralny" in status['rsi'] else "⚠️"
                bb_emoji = "✅" if "wewnątrz" in status['bb_status'] else "⚠️"
                volume_emoji = "✅" if status['volume_confirmed'] else "❌"
                
                part += f"{trend_emoji} <b>Filtr Trendu ({TIMEFRAME_MACRO}):</b> {status['trend']}\n"
                part += f"{rsi_emoji} <b>Wyzwalacz RSI ({TIMEFRAME_MICRO}):</b> {status['rsi']}\n"
                part += f"{bb_emoji} <b>Wstęgi Bollingera:</b> {status['bb_status']}\n"
                part += f"{volume_emoji} <b>Potwierdzenie Wolumenem:</b> {'Tak' if status['volume_confirmed'] else 'Nie'}"
            
            report_parts.append(part)
            await asyncio.sleep(1)

        final_report = "".join(report_parts)
        keyboard = [[InlineKeyboardButton("⬅️ Wróć do menu", callback_data='back_to_main')]]
        await query.edit_message_text(final_report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING

    async def fib_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        symbols = load_symbols()
        if not symbols:
            await query.edit_message_text('Lista monitorowanych par jest pusta. Dodaj parę, aby ją analizować.')
            await asyncio.sleep(3)
            return await self.start(update, context)
        
        keyboard = [[InlineKeyboardButton(s, callback_data='fib_' + s)] for s in symbols]
        keyboard.append([InlineKeyboardButton("⬅️ Wróć do menu", callback_data='back_to_main')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('Wybierz parę do analizy Fibonacciego:', reply_markup=reply_markup)
        return CHOOSING_FIB_SYMBOL

    async def fib_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        symbol = query.data.split('_', 1)[1]
        
        await query.edit_message_text(f"Analizuję {symbol} używając poziomów Fibonacciego...")
        
        df = self.exchange_client.fetch_ohlcv(symbol, TIMEFRAME_MACRO, limit=500)
        
        if df.empty:
            await query.edit_message_text(f"Nie można pobrać danych dla {symbol}.")
            await asyncio.sleep(3)
            return await self.start(update, context)
            
        result = self.strategy_analyzer.analyze_fibonacci(df)
        
        if result.get('error'):
            message = f"<b>Błąd analizy Fibonacciego dla {symbol}:</b>\n\n{result['error']}"
        else:
            message = self.format_fib_report(symbol, result)
            
        keyboard = [[InlineKeyboardButton("⬅️ Wróć do menu", callback_data='back_to_main')]]
        await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING

    def format_fib_report(self, symbol, data):
        trend_emoji = "📈" if data['trend'] == "WZROSTOWY" else "📉"
        report = f"<b>〽️ Analiza Fibonacciego dla {symbol}</b> {trend_emoji}\n\n"
        report += f"<b>Główny trend:</b> {data['trend']}\n"
        report += f"<b>Analizowany ruch:</b>\n"
        report += f"  - Od: {data['swing_start_price']:.4f} ({data['swing_start_date']})\n"
        report += f"  - Do: {data['swing_end_price']:.4f} ({data['swing_end_date']})\n\n"
        report += f"<b>Aktualna cena:</b> {data['current_price']:.4f}\n\n"
        report += "<b>Kluczowe poziomy zniesienia:</b>\n"
        report += f"  - 38.2%: {data['levels']['0.382']:.4f}\n"
        report += f"  - 50.0%: {data['levels']['0.5']:.4f} 🟡\n"
        report += f"  - 61.8%: {data['levels']['0.618']:.4f} 🟡 (Złota Strefa)\n\n"
        report += f"<b>Wniosek:</b> {data['status']}"
        return report
    
    # ... (handle_add, handle_remove, send_signal, etc.)
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
        await query.edit_message_text('Wybierz parę do usunięcia:', reply_markup=InlineKeyboardMarkup(keyboard))
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

    async def send_signal(self, signal_data):
        message = self._format_signal_message(signal_data)
        await self.app.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')

    def _format_signal_message(self, signal_data):
        signal_type = signal_data['type']
        symbol = signal_data.get('symbol', 'N/A')
        price = signal_data['price']
        timestamp = signal_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        reason = signal_data['reason']
        emoji = '🟢 BUY SIGNAL 🟢' if signal_type == 'BUY' else '🔴 SELL SIGNAL 🔴'
        message = f"<b>{emoji}</b>\n\n<b>Symbol:</b> {symbol}\n<b>Cena:</b> {price:.4f} USDC\n<b>Czas:</b> {timestamp}\n<b>Powód:</b> {reason}\n\n<i>To nie jest porada finansowa.</i>"
        return message
