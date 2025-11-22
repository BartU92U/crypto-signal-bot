import asyncio
import logging
from exchange_client import ExchangeClient
from strategy_analyzer import StrategyAnalyzer
from telegram_bot import TelegramBot
from utils import load_symbols
from config import TIMEFRAME_MACRO, TIMEFRAME_MICRO, TELEGRAM_CHAT_ID

# Ustawienia
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def analysis_loop(telegram_bot: TelegramBot):
    logging.info("Uruchamianie pętli analitycznej...")
    exchange_client = telegram_bot.exchange_client
    strategy_analyzer = StrategyAnalyzer()
    last_signals = {}

    while True:
        try:
            current_symbols = load_symbols()
            if not current_symbols:
                logging.warning("Brak symboli do monitorowania. Pętla analityczna czeka 60s.")
                await asyncio.sleep(60)
                continue

            for symbol in current_symbols:
                if symbol not in last_signals:
                    last_signals[symbol] = None

            for symbol in current_symbols:
                logging.info(f"Analizowanie symbolu: {symbol}")
                df_macro = exchange_client.fetch_ohlcv(symbol, TIMEFRAME_MACRO, limit=300)
                df_micro = exchange_client.fetch_ohlcv(symbol, TIMEFRAME_MICRO, limit=300)

                if df_macro.empty or df_micro.empty:
                    logging.warning(f"Brak danych dla {symbol}, pomijam.")
                    continue
                
                df_macro, df_micro = df_macro.sort_index(), df_micro.sort_index()
                signal = strategy_analyzer.analyze(df_macro, df_micro)

                if signal:
                    signal['symbol'] = symbol
                    if last_signals.get(symbol) != signal['type']:
                        await telegram_bot.send_signal(signal)
                        last_signals[symbol] = signal['type']
                else:
                    last_signals[symbol] = None
                
                await asyncio.sleep(5)

            # Prostsza logika oczekiwania - czekaj 1 minutę po pełnym cyklu
            logging.info(f"Pętla analityczna zakończona. Następne uruchomienie za 60 sekund.")
            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Wystąpił błąd w pętli analitycznej: {e}", exc_info=True)
            await asyncio.sleep(60)

async def main():
    exchange_client = ExchangeClient()
    telegram_bot = TelegramBot(exchange_client=exchange_client, chat_id=TELEGRAM_CHAT_ID)

    # Uruchomienie aplikacji bota i pętli analitycznej w jednej pętli zdarzeń
    async with telegram_bot.app:
        await telegram_bot.app.initialize()
        await telegram_bot.app.start()
        
        # Uruchomienie nasłuchiwania w tle
        if telegram_bot.app.updater:
            await telegram_bot.app.updater.start_polling()

        # Uruchomienie pętli analitycznej
        analysis_task = asyncio.create_task(analysis_loop(telegram_bot))

        # Oczekiwanie na zakończenie pętli analitycznej (nigdy się nie zakończy, chyba że wystąpi błąd)
        await analysis_task
        
        # Zatrzymanie nasłuchiwania
        if telegram_bot.app.updater:
            await telegram_bot.app.updater.stop()
        await telegram_bot.app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot zatrzymany przez użytkownika.")
    except Exception as e:
        logging.critical(f"Krytyczny błąd uniemożliwiający uruchomienie bota: {e}", exc_info=True)
