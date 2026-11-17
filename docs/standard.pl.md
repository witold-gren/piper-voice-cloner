# Wspólny standard

Piper Voice Cloner jest jedną z kilku aplikacji domu, które wyglądają, instalują się i obsługuje się je
tak samo. Pozostałe to studio słów budzących, trener Assist Routera, Edytor Home Dashboard i Edytor
Assist Router. Wspólne zasady zebrane są w standardzie „gpu-studio”.

Ta strona zbiera wszystko, co w wersji 0.2.0 dostosowano do tego standardu. Kolejne części idą w
kolejności punktów standardu.

## W skrócie

| | Przed (0.1.0) | Teraz (0.2.0) |
|---|---|---|
| Panel | Gradio na Macu, maszyna sterowana przez SSH | Edytor w przeglądarce, działa na samej maszynie |
| Uruchomienie | Usługi systemd na maszynie, ręczne skrypty | Docker, startuje razem z maszyną |
| Instalacja i aktualizacja | Skrypty `scripts/*` | `make install`, `make deploy` |
| Wypróbowanie na Macu | Python, brew i zależności | Sam Docker Desktop: `make demo` |
| Wyłączanie po treningu | `sudo poweroff` z runnera | Przełącznik w Home Assistant, 120 s odliczania z Anuluj |
| Instrukcja | Dwa pliki Markdown | Strona PL/EN ze zrzutami, wbudowana w edytor |
| Testy | Testy logiki i panelu Gradio | 328 testów, 1 test obrazu demo, 45 testów w przeglądarce |

Usunięto ponad 13 tysięcy linii starego kodu (panel Gradio, sterowanie przez SSH, stare skrypty).

## 1. Zasada główna

- Jedna aplikacja na maszynie z kartą graficzną, w Dockerze. Po włączeniu maszyny edytor jest od razu
  dostępny.
- Mac służy tylko do wypróbowania (demo) i do pracy nad kodem.
- Usunięto:
  - panel Gradio (`webui/`);
  - polecenia `pvc ui` i `pvc remote`;
  - sterowanie maszyną z Maca przez SSH i listę kontrolną maszyny;
  - przycisk włączania maszyny (edytor działa tylko na włączonej maszynie);
  - stare usługi systemd (wyłącza je instalator).
- Wszystkie funkcje starego panelu są w edytorze. Kroki, które blokowały panel (przygotowanie nagrania,
  wybór zdań, „Użyj zestawu”), stały się zwykłymi zadaniami z postępem.

## 2. Polecenia make

Te same nazwy co w pozostałych aplikacjach, a `make help` po polsku albo po angielsku (z `$LANG`). Trzy
grupy:

- **1. Start:** `help`, `demo`, `demo-clean`, `docs`, `docs-serve`, `doctor`. Wystarczy Docker Desktop.
- **2. Maszyna z GPU:** `install`, `deploy`, `login`, `logs`, `status`, `docker-up`, `docker-down`,
  `docker-logs`, `docker-shell`. Wystarczą Docker oraz `ssh` i `rsync` z macOS.
- **3. Rozwój:** `setup`, `demo-local`, `test`, `test-browser`, `test-docker`, `test-all`, `lint`,
  `format`, `docs-build`, `screenshots`, `icons`, `clean`.

Co jeszcze dostosowano:

- Adres maszyny jest wspólny dla wszystkich aplikacji: `~/.config/gpu-studio/host.mk`. Wyjątki tej
  aplikacji trafiają do `Makefile.local`, który nie jest w gicie.
- `make doctor` sprawdza Dockera, Chrome, uv i połączenie z maszyną. Niczego nie instaluje.
- `make setup` tworzy `.venv` przez uv (Python 3.12). uv sam pobiera Pythona, brew nie jest potrzebny.
- `make test` nigdy nie buduje obrazów. Obraz demo sprawdza `make test-docker`, a `make test-all`
  uruchamia wszystko.
- Instrukcja buduje się w Dockerze: `make docs`, `make docs-build`, a `make docs-serve` daje podgląd na
  porcie 8861. Osobne środowisko `.venv-docs` zniknęło.
- Bez aliasów i starych nazw. Każdy cel ma opis w obu językach, co sprawdza test.

## 3. Docker

- `docker/Dockerfile` ma etapy ułożone od najrzadziej zmienianych:
  - `base`: Ubuntu 24.04, ffmpeg, espeak-ng, uv, Python 3.11;
  - `train`: trening piper1-gpl z przypiętym torch dla sterownika 580;
  - `docs`: instrukcja;
  - `deps`: środowisko edytora;
  - `app`: kod jako ostatnia warstwa, więc przebudowa po zmianie kodu trwa sekundy;
  - `demo`: osobny mały obraz bez torch i CUDA.
- Każdy etap kończy się samotestem importów.
- `docker/compose.yaml`:
  - usługi `studio` (edytor) i `tensorboard`;
  - `restart: unless-stopped`, karta graficzna przez nvidia-container-toolkit;
  - dane w folderze maszyny, sekrety w `docker/config/`.
- `docker/install-ubuntu.sh`:
  - sprawdza Dockera i kartę w kontenerze;
  - wyłącza stare usługi;
  - tworzy hasło;
  - przenosi istniejące połączenia z Home Assistant i ElevenLabs;
  - buduje i uruchamia edytor.
  - Opcje: `--show-login` i `--remove`.
- `GET /api/health` służy kontenerowi i `make status`.
- Restart kontenera nie zostawia zadania w stanie „trwa”: zadanie bez procesu dostaje stan „przerwane”.

## 4. Logowanie

- Jedno hasło, sesja na 30 dni w ciasteczku HttpOnly.
- Po pięciu złych hasłach trzeba odczekać minutę.
- Sekret sesji leży w pliku z prawami 600. Zmiana hasła wylogowuje wszystkich.
- `make login` pokazuje użytkownika i hasło.
- Wylogowanie jest w menu ☰.

## 5. Wygląd i obsługa

**Wygląd.** Ten sam wygląd co Edytor Home Dashboard i Edytor Assist Router:

- te same kolory (motyw jasny, ciemny i automatyczny), drzewo z wyszukiwarką, trzy kolumny z dzielnikami;
- ikony dołączone do aplikacji, więc działają bez internetu;
- wszystko po polsku i po angielsku.

**Pasek górny**, od lewej:

- menu ☰ (instrukcja, kto jest zalogowany, wylogowanie);
- chip zadania i chip maszyny (obciążenie karty, temperatura, pamięć, moc z gniazdka, ⏻);
- odliczanie przed wyłączeniem;
- motyw, „?” i ⚙.

**Pomoc.** Tylko „?” w pasku otwiera instrukcję. „?” przy krokach i kartach pokazuje małe okienko z
opisem. Zamykają je Esc, kliknięcie obok, ✕ albo ponowne „?”.

**Kolumny.** Boczne kolumny zwijają się przyciskiem albo skrótem Ctrl/⌘+B i Ctrl/⌘+Alt+B. Przeglądarka
pamięta ich stan, a w wąskim oknie prawa kolumna jest zwinięta od startu.

**Ustawienia głosu:**

- szkic zapisywany od razu na maszynie;
- zmiana pola zmienia dokładnie jedną linię `voice.yaml`, a komentarze zostają;
- cofnij i ponów;
- zapis z listą zmienionych linii, notatką i sprawdzeniem konfliktu;
- historia 30 wersji.

**Adresy.** Adres strony (`#voice/kasia/train`) prowadzi prosto do kroku.

## 6. Home Assistant i wyłączanie maszyny

- Maszynę wyłącza zawsze przełącznik w Home Assistant. Kontener nigdy nie woła `sudo poweroff`.
- Po zadaniu z zaznaczonym wyłączeniem edytor odlicza 120 s, a odliczanie można anulować.
- Wyłączenia nie ma nigdy po Zatrzymaj, także wtedy, gdy Zatrzymaj przyszło w czasie startu Pythona.
- Zadanie obok jest najpierw dokańczane. Nowe zadanie albo restart edytora kasuje odliczanie.
- ⏻ w pasku działa tylko wtedy, gdy nic nie trwa, a Home Assistant jest połączony.
- Gdy wyłączenie się nie uda, w pasku pojawia się czerwona pigułka z powodem.

## 7. Backend

- FastAPI z REST. Standard dopuszcza zostawienie istniejącego REST.
- Zadania uruchamia odłączony proces. Stan zadania leży w pliku chronionym blokadą, więc dwa zapisy się
  nie nakładają.
- Drugie miejsce na zadanie poboczne (ocena nagrań) obok treningu.
- Szkic ustawień, historia wersji i kontrola konfliktu są po stronie serwera.

## 8. Dokumentacja

- Instrukcja MkDocs Material po polsku i po angielsku, ze zrzutami ekranu z demo (`make screenshots`).
- Rozdziały: instalacja, ekran, obie ścieżki, jak dobrze trenować, model bazowy, eksport, prawo i FAQ.
- Instrukcja jest na GitHub Pages i w edytorze pod `/docs/`, także bez internetu.
- Każdy błąd, który się pojawił, ma wpis w [FAQ](faq.md): dokładny komunikat, przyczynę i naprawę.
- Test pilnuje, że tabela parametrów treningu w instrukcji zgadza się z kodem.

## 8b. Wypróbuj na Macu

- `make demo` buduje mały obraz demo i uruchamia go pod http://localhost:7861 (`demo` / `demo`).
  Wystarczy sam Docker Desktop.
- W demo wszystko jest wymyślone: głosy, karta graficzna i zadania, które tylko udają pracę. Nic nie
  trafia do Home Assistant, ElevenLabs ani na maszynę.
- Ctrl+C usuwa kontener, a `make demo-clean` usuwa obraz.
- Ta sama sekcja jest w obu README i w [instalacji](installation.md#try-on-a-mac).

## 9. Testy i bezpieczeństwo

- Testy nie mogą wyłączyć prawdziwej maszyny: wyłączanie jest w nich podmienione. Wcześniej jeden test
  wyłączył serwer CI.
- Testy nie mogą wyjść do internetu: połączenia poza localhost są zablokowane.
- Demo i zrzuty mają własne, puste ustawienia, więc nie widzą prawdziwego połączenia z Home Assistant
  ani klucza ElevenLabs.
- 45 testów w Chrome przechodzi obie ścieżki, ustawienia, pasek górny, zwijanie kolumn, okienka pomocy
  i zapis szkicu.
- CI sprawdza Pythona 3.11 (wersja z obrazu) i 3.12.

## 9a. Wydajność

- Edytor pyta serwer o stan tylko raz naraz. Następne pytanie wychodzi dopiero po odpowiedzi.
- Karta przeglądarki w tle nie pyta wcale. Po powrocie pyta od razu.
- Każde zapytanie ma limit czasu (15 s), a brak odpowiedzi kończy się komunikatem zamiast zawieszenia.
- Widok przerysowuje się tylko wtedy, gdy stan się zmienił.
- Test na dużych danych (40 głosów, 1000 epok, 120 zadań w historii) sprawdza, że żaden widok nie
  blokuje strony dłużej niż 0,5 s.

## Świadome odstępstwa

- API zostaje REST, co standard dopuszcza.
- Obraz na maszynie używa Pythona 3.11, bo Chatterbox i piper1-gpl wymagają tej wersji torch. Pythona
  3.12 używa tylko programista.
- Przyciski YAML, Historia i Zapisz są w widoku „Ustawienia głosu”, a nie w pasku górnym, bo każdy głos
  ma własny plik ustawień.
- Nie ma poleceń `migrate` i `migrate-finish` (w standardzie są opcjonalne). Stare usługi wyłącza
  instalator, a dane zostają w dotychczasowym folderze.

## Co jeszcze czeka

Sprawdzenie na prawdziwej maszynie:

- `make install`;
- karta w kontenerze;
- próbny trening dwóch epok na kopii głosu;
- eksport;
- wyłączenie przez Home Assistant z odliczaniem.
