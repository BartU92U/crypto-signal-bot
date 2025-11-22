import pandas as pd
import pandas_ta as ta
import logging
from config import (
    EMA_FAST_PERIOD, EMA_SLOW_PERIOD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    VOLUME_MULTIPLIER
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StrategyAnalyzer:
    def __init__(self):
        self.last_signal = None

    def analyze(self, df_macro, df_micro):
        # 1. Obliczanie wskaźników dla filtra trendu (interwał MACRO)
        df_macro['EMA_FAST'] = ta.ema(df_macro['close'], length=EMA_FAST_PERIOD)
        df_macro['EMA_SLOW'] = ta.ema(df_macro['close'], length=EMA_SLOW_PERIOD)

        # 2. Obliczanie wskaźników dla wyzwalacza wejścia (interwał MICRO)
        df_micro['RSI'] = ta.rsi(df_micro['close'], length=RSI_PERIOD)
        # Obliczanie średniego wolumenu dla potwierdzenia
        df_micro['AVG_VOLUME'] = ta.sma(df_micro['volume'], length=20) # Średnia z 20 ostatnich wolumenów

        # Upewnij się, że mamy wystarczająco danych
        if df_macro['EMA_SLOW'].isnull().all() or df_micro['RSI'].isnull().all():
            logging.warning("Niewystarczająca ilość danych do obliczenia wskaźników.")
            return None

        # Pobierz najnowsze wartości
        latest_macro = df_macro.iloc[-1]
        latest_micro = df_micro.iloc[-1]
        previous_micro = df_micro.iloc[-2] if len(df_micro) > 1 else None

        current_price = latest_micro['close']

        # FILTR TRENDU (MACRO)
        is_bullish_trend = (latest_macro['close'] > latest_macro['EMA_FAST']) and \
                           (latest_macro['EMA_FAST'] > latest_macro['EMA_SLOW'])
        is_bearish_trend = (latest_macro['close'] < latest_macro['EMA_FAST']) and \
                           (latest_macro['EMA_FAST'] < latest_macro['EMA_SLOW'])

        # WYZWALACZ WEJŚCIA (MICRO)
        buy_signal_rsi = False
        sell_signal_rsi = False

        if previous_micro is not None:
            # RSI wychodzi ze strefy wyprzedania (dla sygnału kupna)
            if previous_micro['RSI'] <= RSI_OVERSOLD and latest_micro['RSI'] > RSI_OVERSOLD:
                buy_signal_rsi = True
                
            # RSI wychodzi ze strefy wykupienia (dla sygnału sprzedaży)
            if previous_micro['RSI'] >= RSI_OVERBOUGHT and latest_micro['RSI'] < RSI_OVERBOUGHT:
                sell_signal_rsi = True

        # POTWIERDZENIE WOLUMENEM
        volume_confirmed = latest_micro['volume'] > (latest_micro['AVG_VOLUME'] * VOLUME_MULTIPLIER)

        signal = None

        # Generowanie sygnału KUPNA
        if is_bullish_trend and buy_signal_rsi and volume_confirmed:
            if self.last_signal != 'BUY': # Zapobieganie powtarzającym się sygnałom
                signal = {
                    'type': 'BUY',
                    'price': current_price,
                    'timestamp': latest_micro.name,
                    'reason': f"Silny trend wzrostowy (MACRO {latest_macro['close']:.2f} > EMA50 {latest_macro['EMA_FAST']:.2f} > EMA200 {latest_macro['EMA_SLOW']:.2f}). RSI wychodzi ze strefy wyprzedania ({previous_micro['RSI']:.2f} -> {latest_micro['RSI']:.2f}). Wolumen potwierdzony ({latest_micro['volume']:.2f} > {latest_micro['AVG_VOLUME'] * VOLUME_MULTIPLIER:.2f})."
                }
                self.last_signal = 'BUY'
                logging.info(f"Generowanie sygnału KUPNA: {signal}")

        # Generowanie sygnału SPRZEDAŻY
        elif is_bearish_trend and sell_signal_rsi and volume_confirmed:
            if self.last_signal != 'SELL': # Zapobieganie powtarzającym się sygnałom
                signal = {
                    'type': 'SELL',
                    'price': current_price,
                    'timestamp': latest_micro.name,
                    'reason': f"Silny trend spadkowy (MACRO {latest_macro['close']:.2f} < EMA50 {latest_macro['EMA_FAST']:.2f} < EMA200 {latest_macro['EMA_SLOW']:.2f}). RSI wychodzi ze strefy wykupienia ({previous_micro['RSI']:.2f} -> {latest_micro['RSI']:.2f}). Wolumen potwierdzony ({latest_micro['volume']:.2f} > {latest_micro['AVG_VOLUME'] * VOLUME_MULTIPLIER:.2f})."
                }
                self.last_signal = 'SELL'
                logging.info(f"Generowanie sygnału SPRZEDAŻY: {signal}")

        return signal
