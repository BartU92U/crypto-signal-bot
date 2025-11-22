import pandas as pd
import pandas_ta as ta
import logging
from config import (
    EMA_FAST_PERIOD, EMA_SLOW_PERIOD, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    BB_LENGTH, BB_STD, VOLUME_MULTIPLIER, FIB_SWING_STRENGTH
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StrategyAnalyzer:
    def get_status(self, df_macro, df_micro):
        try:
            # Obliczenia wskaźników
            df_macro['EMA_FAST'] = ta.ema(df_macro['close'], length=EMA_FAST_PERIOD)
            df_macro['EMA_SLOW'] = ta.ema(df_macro['close'], length=EMA_SLOW_PERIOD)
            df_micro['RSI'] = ta.rsi(df_micro['close'], length=RSI_PERIOD)
            df_micro['AVG_VOLUME'] = ta.sma(df_micro['volume'], length=20)
            df_micro.ta.bbands(close=df_micro['close'], length=BB_LENGTH, std=BB_STD, append=True)
            
            # DYNAMICZNE WYSZUKIWANIE NAZW KOLUMN
            bb_lower_col = next((col for col in df_micro.columns if col.startswith('BBL')), None)
            bb_upper_col = next((col for col in df_micro.columns if col.startswith('BBU')), None)
            
            if not bb_lower_col or not bb_upper_col:
                return {'error': f'Nie można znaleźć kolumn BB. Dostępne: {", ".join(df_micro.columns)}'}

            if df_macro['EMA_SLOW'].isnull().all() or df_micro[bb_lower_col].isnull().all():
                return {'error': 'Niewystarczająca ilość danych po obliczeniu wskaźników.'}

            # Reszta logiki bez zmian...
            latest_macro, latest_micro, previous_micro = df_macro.iloc[-1], df_micro.iloc[-1], df_micro.iloc[-2]
            trend_status = "BOCZNY"
            if (latest_macro['close'] > latest_macro['EMA_FAST']) and (latest_macro['EMA_FAST'] > latest_macro['EMA_SLOW']):
                trend_status = "WZROSTOWY"
            elif (latest_macro['close'] < latest_macro['EMA_FAST']) and (latest_macro['EMA_FAST'] < latest_macro['EMA_SLOW']):
                trend_status = "SPADKOWY"
            
            rsi_value = latest_micro['RSI']
            rsi_status = f"Neutralny ({rsi_value:.2f})"
            if rsi_value <= RSI_OVERSOLD: rsi_status = f"Wyprzedany ({rsi_value:.2f})"
            elif rsi_value >= RSI_OVERBOUGHT: rsi_status = f"Wykupiony ({rsi_value:.2f})"
            
            price = latest_micro['close']
            lower_band, upper_band = latest_micro[bb_lower_col], latest_micro[bb_upper_col]
            bb_status = "Cena wewnątrz wstęg"
            if price <= lower_band: bb_status = "Cena dotyka dolnej wstęgi"
            elif price >= upper_band: bb_status = "Cena dotyka górnej wstęgi"

            return {
                'trend': trend_status, 'rsi': rsi_status, 'bb_status': bb_status,
                'volume_confirmed': latest_micro['volume'] > (latest_micro['AVG_VOLUME'] * VOLUME_MULTIPLIER),
                'rsi_buy_trigger': previous_micro['RSI'] <= RSI_OVERSOLD and rsi_value > RSI_OVERSOLD,
                'rsi_sell_trigger': previous_micro['RSI'] >= RSI_OVERBOUGHT and rsi_value < RSI_OVERBOUGHT,
                'bb_buy_trigger': price <= lower_band, 'bb_sell_trigger': price >= upper_band, 'error': None
            }
        except Exception as e:
            logging.error(f"Błąd w get_status: {e}", exc_info=True)
            return {'error': f'Wyjątek w analizie: {e}'}

    # ... reszta pliku (analyze, analyze_fibonacci) pozostaje bez zmian ...
    def __init__(self):
        self.last_signal = None

    def analyze(self, df_macro, df_micro):
        status = self.get_status(df_macro, df_micro)
        if status.get('error'):
            logging.warning(status['error'])
            return None

        current_price = df_micro.iloc[-1]['close']
        is_bullish_trend = status['trend'] == "WZROSTOWY"
        is_bearish_trend = status['trend'] == "SPADKOWY"
        buy_signal_rsi = status['rsi_buy_trigger']
        sell_signal_rsi = status['rsi_sell_trigger']
        buy_signal_bb = status['bb_buy_trigger']
        sell_signal_bb = status['bb_sell_trigger']
        volume_confirmed = status['volume_confirmed']
        signal = None

        if is_bullish_trend and buy_signal_rsi and buy_signal_bb and volume_confirmed:
            if self.last_signal != 'BUY':
                signal = {'type': 'BUY', 'price': current_price, 'timestamp': df_micro.index[-1], 'reason': 'Zgodność trendu, RSI, BB i wolumenu.'}
                self.last_signal = 'BUY'
        elif is_bearish_trend and sell_signal_rsi and sell_signal_bb and volume_confirmed:
            if self.last_signal != 'SELL':
                signal = {'type': 'SELL', 'price': current_price, 'timestamp': df_micro.index[-1], 'reason': 'Zgodność trendu, RSI, BB i wolumenu.'}
                self.last_signal = 'SELL'
        return signal

    def analyze_fibonacci(self, df):
        try:
            df['EMA_200'] = ta.ema(df['close'], length=200)
            if df['EMA_200'].isnull().all(): return {'error': 'Za mało danych dla EMA 200.'}
            
            trend = "WZROSTOWY" if df['close'].iloc[-1] > df['EMA_200'].iloc[-1] else "SPADKOWY"
            n = FIB_SWING_STRENGTH
            df['swing_high'] = df['high'].rolling(2 * n + 1, center=True).max() == df['high']
            df['swing_low'] = df['low'].rolling(2 * n + 1, center=True).min() == df['low']
            
            swing_highs, swing_lows = df[df['swing_high']], df[df['swing_low']]
            if swing_highs.empty or swing_lows.empty: return {'error': 'Nie znaleziono punktów zwrotnych.'}

            if trend == "WZROSTOWY":
                last_swing_high = swing_highs.iloc[-1]
                relevant_lows = swing_lows[swing_lows.index < last_swing_high.name]
                if relevant_lows.empty: return {'error': 'Nie znaleziono dołka dla swingu wzrostowego.'}
                start_point, end_point = relevant_lows.iloc[-1], last_swing_high
            else:
                last_swing_low = swing_lows.iloc[-1]
                relevant_highs = swing_highs[swing_highs.index < last_swing_low.name]
                if relevant_highs.empty: return {'error': 'Nie znaleziono szczytu dla swingu spadkowego.'}
                start_point, end_point = relevant_highs.iloc[-1], last_swing_low
            
            start_price = start_point['low'] if trend == "WZROSTOWY" else start_point['high']
            end_price = end_point['high'] if trend == "WZROSTOWY" else end_point['low']
            price_range = end_price - start_price
            levels = {f'{lvl:.3f}': end_price - price_range * lvl for lvl in [0.382, 0.5, 0.618]}
            
            status, latest_price = "", df['close'].iloc[-1]
            gz_top, gz_bottom = (levels['0.500'], levels['0.618']) if trend == "WZROSTOWY" else (levels['0.618'], levels['0.500'])
            
            if gz_bottom <= latest_price <= gz_top: status = "Cena w 'Złotej Strefie'."
            elif (trend == "WZROSTOWY" and latest_price > levels['0.382']) or (trend == "SPADKOWY" and latest_price < levels['0.382']):
                status = "Korekta jest płytka. Silny trend."
            elif (trend == "WZROSTOWY" and latest_price < gz_bottom) or (trend == "SPADKOWY" and latest_price > gz_bottom):
                status = "Cena przebiła 'Złotą Strefę'. Możliwa zmiana trendu."
            
            return {
                'trend': trend, 'swing_start_price': start_price, 'swing_start_date': start_point.name.strftime('%Y-%m-%d %H:%M'),
                'swing_end_price': end_price, 'swing_end_date': end_point.name.strftime('%Y-%m-%d %H:%M'),
                'levels': levels, 'current_price': latest_price, 'status': status, 'error': None
            }
        except Exception as e:
            logging.error(f"Błąd w analyze_fibonacci: {e}", exc_info=True)
            return {'error': f'Wyjątek: {e}'}