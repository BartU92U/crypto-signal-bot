# Telegramowy Bot Sygnałów Krypto

Bot do generowania sygnałów transakcyjnych dla rynku kryptowalut, który wysyła powiadomienia na Telegram. Projekt jest w pełni interaktywny i pozwala na zarządzanie listą monitorowanych par walutowych bezpośrednio z poziomu komunikatora.

## Jak to działa?

Bot działa w oparciu o dwa główne procesy:
1.  **Interaktywny Interfejs Telegram:** Po wysłaniu komendy `/start`, bot prezentuje menu, które pozwala na:
    - Dodawanie nowych par do monitorowania (z walidacją na giełdzie Binance).
    - Usuwanie istniejących par.
    - Wyświetlanie listy aktualnie śledzonych par.
    - Uruchamianie testu diagnostycznego, który sprawdza poprawność połączenia dla każdej pary.
2.  **Pętla Analityczna:** Proces działający w tle, który cyklicznie analizuje rynek dla skonfigurowanych par walutowych i wysyła sygnały, jeśli zostaną spełnione określone warunki strategiczne.

## Strategia Generowania Sygnałów

Bot wykorzystuje strategię **konfluencji (zbieżności) sygnałów**, aby filtrować transakcje o niskim prawdopodobieństwie sukcesu. Sygnał jest generowany tylko wtedy, gdy wszystkie poniższe warunki są spełnione jednocześnie:

### 1. Filtr Trendu (Interwał Makro, np. 4h)
- **Cel:** Upewnienie się, że handlujemy zgodnie z głównym trendem rynkowym.
- **Narzędzia:** Wykładnicze średnie kroczące (EMA 50 i EMA 200).
- **Warunek KUPNA:** Cena musi znajdować się powyżej EMA 50, a EMA 50 musi znajdować się powyżej EMA 200 (silny trend wzrostowy).
- **Warunek SPRZEDAŻY:** Cena musi znajdować się poniżej EMA 50, a EMA 50 musi znajdować się poniżej EMA 200 (silny trend spadkowy).
- **Brak sygnału:** Gdy cena znajduje się pomiędzy średnimi (rynek boczny), bot nie szuka okazji.

### 2. Wyzwalacz Wejścia (Interwał Mikro, np. 1h)
- **Cel:** Znalezienie optymalnego momentu na wejście w transakcję w ramach ustalonego trendu (np. na końcu lokalnej korekty).
- **Narzędzie:** Wskaźnik siły względnej (RSI).
- **Warunek KUPNA:** W trendzie wzrostowym, RSI musi najpierw wejść w strefę wyprzedania (poniżej 30), a następnie z niej wyjść.
- **Warunek SPRZEDAŻY:** W trendzie spadkowym, RSI musi najpierw wejść w strefę wykupienia (powyżej 70), a następnie z niej wyjść.

### 3. Potwierdzenie Wolumenem
- **Cel:** Upewnienie się, że za ruchem ceny stoi rzeczywiste zainteresowanie rynku.
- **Warunek:** Świeca, na której wystąpił sygnał RSI, musi mieć wolumen znacząco wyższy od średniej (np. 1.5x większy od średniej z ostatnich 20 świec).

## Instalacja i Konfiguracja

1.  Sklonuj repozytorium.
2.  Stwórz wirtualne środowisko: `python3 -m venv .venv`
3.  Aktywuj środowisko: `source .venv/bin/activate`
4.  Zainstaluj zależności: `pip install -r requirements.txt`
5.  Skopiuj plik `config.py.example` do `config.py`.
6.  Wypełnij `config.py` swoimi kluczami API Binance (tylko do odczytu) oraz danymi bota z Telegrama.
7.  Uruchom bota: `python3 main.py`
