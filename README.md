# Telegramowy Bot Sygnałów Krypto

Wielofunkcyjny bot do analizy rynku kryptowalut, który wysyła powiadomienia o sygnałach transakcyjnych na Telegram. Projekt jest w pełni interaktywny i pozwala na zarządzanie listą monitorowanych par oraz na przeprowadzanie zaawansowanych analiz bezpośrednio z poziomu komunikatora.

## Główne Funkcje

- **Automatyczne Sygnały:** Bot samodzielnie analizuje rynek i wysyła sygnały KUPNA/SPRZEDAŻY, gdy wszystkie warunki strategii zostaną spełnione.
- **Interaktywne Menu:** Po wysłaniu komendy `/start`, bot oferuje menu do zarządzania parami, testowania strategii i przeprowadzania analiz.
- **Analiza Fibonacciego na Żądanie:** Możliwość wygenerowania szczegółowego raportu z poziomami zniesienia Fibonacciego dla dowolnej monitorowanej pary.

## Strategia Generowania Sygnałów

Bot wykorzystuje strategię **konfluencji (zbieżności) pięciu sygnałów**, aby filtrować transakcje o niskim prawdopodobieństwie sukcesu. Sygnał jest generowany tylko wtedy, gdy wszystkie poniższe warunki są spełnione jednocześnie:

### 1. Filtr Trendu (Interwał Makro, np. 4h)
- **Cel:** Upewnienie się, że transakcja jest zgodna z głównym trendem rynkowym.
- **Narzędzia:** Wykładnicze średnie kroczące (EMA 50 i EMA 200).
- **Logika:** Bot szuka sygnałów kupna tylko w silnym trendzie wzrostowym (cena > EMA50 > EMA200) i sygnałów sprzedaży tylko w silnym trendzie spadkowym. Unika handlu w niestabilnym rynku bocznym.

### 2. Wyzwalacz Wejścia (Interwał Mikro, np. 1h)
- **Cel:** Znalezienie optymalnego momentu na wejście w transakcję, np. na końcu lokalnej korekty.
- **Narzędzie:** Wskaźnik siły względnej (RSI).
- **Logika:** W trendzie wzrostowym, bot czeka, aż RSI wejdzie w strefę wyprzedania (<30), a następnie z niej wyjdzie. W trendzie spadkowym, czeka na wyjście ze strefy wykupienia (>70).

### 3. Potwierdzenie Wstęgami Bollingera
- **Cel:** Potwierdzenie, że cena osiągnęła statystycznie istotny poziom, z którego może nastąpić odbicie.
- **Narzędzie:** Wstęgi Bollingera (Bollinger Bands).
- **Logika:** Sygnał kupna jest potwierdzony, jeśli cena dotyka lub przebija dolną wstęgę. Sygnał sprzedaży jest potwierdzony, jeśli cena dotyka lub przebija górną wstęgę.

### 4. Potwierdzenie Wolumenem
- **Cel:** Upewnienie się, że za ruchem ceny stoi rzeczywiste zainteresowanie rynku, a nie przypadkowy szum.
- **Logika:** Świeca, na której wystąpił sygnał, musi mieć wolumen znacząco wyższy od średniej.

### 5. Analiza Fibonacciego (Funkcja na żądanie)
- **Cel:** Identyfikacja kluczowych, psychologicznych poziomów wsparcia i oporu.
- **Narzędzie:** Poziomy zniesienia Fibonacciego (Fibonacci Retracement).
- **Logika:** Bot automatycznie identyfikuje ostatni znaczący ruch cenowy (impuls), a następnie oblicza poziomy zniesienia. Szczególną uwagę zwraca na **"Złotą Strefę" (między 50% a 61.8%)**, która jest uważana za obszar o najwyższym prawdopodobieństwie zakończenia korekty i kontynuacji trendu. Funkcja ta pozwala na ręczną, głębszą analizę rynku.

## Instalacja i Uruchomienie

1.  Sklonuj repozytorium.
2.  Stwórz i aktywuj wirtualne środowisko Pythona.
3.  Zainstaluj zależności: `pip install -r requirements.txt`
4.  Skopiuj plik `config.py.example` do `config.py` i wypełnij go swoimi kluczami API oraz danymi bota z Telegrama.
5.  Uruchom bota: `python3 main.py`