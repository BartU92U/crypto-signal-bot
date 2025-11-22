import ccxt
import logging
import time
import pandas as pd
from config import EXCHANGE_ID, BINANCE_API_KEY, BINANCE_SECRET_KEY

# Ustawienie logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExchangeClient:
    def __init__(self):
        self.exchange = self._init_exchange()

    def _init_exchange(self):
        try:
            exchange_class = getattr(ccxt, EXCHANGE_ID)
            exchange = exchange_class({
                'apiKey': BINANCE_API_KEY,
                'secret': BINANCE_SECRET_KEY,
                'enableRateLimit': True, # Włączanie kontroli limitu zapytań
            })
            logging.info(f"Pomyślnie zainicjowano giełdę: {EXCHANGE_ID}")
            return exchange
        except Exception as e:
            logging.error(f"Błąd inicjalizacji giełdy {EXCHANGE_ID}: {e}")
            return None

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        if not self.exchange:
            logging.error("Giełda nie jest zainicjowana.")
            return pd.DataFrame()

        try:
            # Sprawdzanie, czy symbol i interwał są obsługiwane
            self.exchange.load_markets()
            if symbol not in self.exchange.symbols:
                logging.error(f"Symbol {symbol} nie jest obsługiwany przez giełdę {EXCHANGE_ID}.")
                return pd.DataFrame()
            if timeframe not in self.exchange.timeframes:
                logging.error(f"Interwał czasowy {timeframe} nie jest obsługiwany przez giełdę {EXCHANGE_ID}.")
                return pd.DataFrame()
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            logging.info(f"Pomyślnie pobrano {len(df)} świec dla {symbol} {timeframe}.")
            return df
        except ccxt.NetworkError as e:
            logging.error(f"Błąd sieci podczas pobierania danych: {e}")
            time.sleep(5) # Odczekaj przed ponowną próbą
            return pd.DataFrame()
        except ccxt.ExchangeError as e:
            logging.error(f"Błąd giełdy podczas pobierania danych: {e}")
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"Nieznany błąd podczas pobierania danych: {e}")
            return pd.DataFrame()

    def symbol_exists(self, symbol):
        if not self.exchange:
            return False
        try:
            # Używamy reload=True, aby upewnić się, że lista rynków jest aktualna
            self.exchange.load_markets(reload=True) 
            return symbol in self.exchange.markets
        except Exception as e:
            logging.error(f"Błąd podczas walidacji symbolu {symbol}: {e}")
            return False

# Przykład użycia (można usunąć po testach)
# if __name__ == "__main__":
#     client = ExchangeClient()
#     # Test walidacji symbolu
#     print(f"Czy BTC/USDC istnieje? {client.symbol_exists('BTC/USDC')}")
#     print(f"Czy FAKE/COIN istnieje? {client.symbol_exists('FAKE/COIN')}")
#     # Test pobierania danych
#     df = client.fetch_ohlcv('BTC/USDC', '1h', limit=10)
#     print(df)
