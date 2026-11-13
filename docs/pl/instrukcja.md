# Piper Voice Cloner – instrukcja

[English](../en/guide.md) · [HTML](instrukcja.html)

Z krótkiego nagrania (10–60 s) powstaje własny, szybki głos Piper. Przykład: postać z bajki do
pokoju dziecka w Home Assistant.

- [O co chodzi](#o-co-chodzi)
- [Instalacja](#instalacja)
- [Interfejs w przeglądarce](#interfejs-w-przeglądarce)
- [Gdzie są dane](#gdzie-są-dane)
- [1. Nagranie referencyjne](#1-nagranie-referencyjne)
- [2. Zdania](#2-zdania)
- [3. Odsłuch ustawień](#3-odsłuch-ustawień)
- [4. Generowanie i filtr](#4-generowanie-i-filtr)
- [5. Trening](#5-trening)
- [Jak długo trenować i na co patrzeć](#jak-długo-trenować-i-na-co-patrzeć)
- [6. Eksport i użycie](#6-eksport-i-użycie)
- [Nowy głos z krótkiego nagrania](#nowy-głos-z-krótkiego-nagrania)
- [Przetrenowanie istniejących głosów](#przetrenowanie-istniejących-głosów)
- [Dodanie języka](#dodanie-języka)
- [FAQ i rozwiązywanie problemów](#faq-i-rozwiązywanie-problemów)
- [Prywatność i prawo](#prywatność-i-prawo)

## O co chodzi

Piper działa szybko nawet na Raspberry Pi czy Jetsonie, ale mówi tylko głosami wytrenowanymi
specjalnie dla niego. Modele klonujące (Chatterbox, XTTS) naśladują głos z kilku sekund nagrania,
ale są za wolne dla asystenta głosowego. Narzędzie łączy jedno z drugim:

| Nagranie | Klonowanie | Filtr | Trening | Eksport |
|---|---|---|---|---|
| 10–60 s czystej mowy | ~2600 klipów (Chatterbox) | ~2000 klipów (Whisper, barwa, MOS) | głos medium (piper1-gpl) | `.onnx` + `.json` do Home Assistant |

Cały przebieg to kilka komend:

```bash
pvc init kuba_bajka --piper-name pl_PL-kuba_bajka
pvc reference kuba_bajka nagrania/*.m4a
pvc corpus kuba_bajka --source moje_zdania.txt
pvc audition kuba_bajka --apply-best
pvc synthesize kuba_bajka
pvc filter kuba_bajka
pvc train kuba_bajka --base lessac
pvc export kuba_bajka
```

## Instalacja

Potrzebne są:
- Ubuntu 24.04 z kartą NVIDIA GeForce RTX 4090 (24 GB). Skrypty są przygotowane tylko pod tę kartę;
  inne karty i maszyny nie są wspierane (można próbować, ale wsparcie trzeba zapewnić samemu).
- `ffmpeg`, `espeak-ng`, `build-essential cmake ninja-build` oraz [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/witold-gren/piper-voice-cloner.git
cd piper-voice-cloner
./scripts/setup.sh                         # .venv (klonowanie + kontrola) i .venv-train (piper1-gpl)
export PVC_HOME=$HOME/home-assistant/voices-private # prywatne dane POZA repozytorium
export PVC_TRAIN_PYTHON=$PWD/.venv-train/bin/python
source .venv/bin/activate
```

Skrypt tworzy dwa osobne środowiska, bo Chatterbox i trening Pipera wymagają różnych wersji
PyTorcha. Z `XTTS_ENV=1 ./scripts/setup.sh` powstaje też trzecie, dla XTTS-v2.

### Komputer z GPU przez SSH (praca z Maca lub laptopa)

Dane możesz przygotować na zwykłym komputerze (import, zdania), a kod, dane i instalację wysłać
na maszynę z kartą jednym kliknięciem: **⚒ Narzędzia → Serwer z GPU (SSH)**. To samo z terminala:

```bash
make remote-configure HOST=ubuntu.local SSH_USER=ja   # zapisuje server.json w folderze danych
make remote-status     # lista kontrolna: co maszyna ma, a co zostało do zrobienia
make remote-prepare    # zrób wszystko, co się da: pakiety, uv, kod i dane, środowiska, usługa
make remote-push       # rsync: kod -> ~/piper-voice-cloner/repo, dane -> ~/piper-voice-cloner/data
make remote-install    # setup.sh + usługa panelu; potem http://ubuntu.local:7860
make remote-pull       # gotowe voices/*/export/ z powrotem tutaj
```

- Logowanie musi działać bez hasła (klucz SSH, `ssh-copy-id`). Hasła nie są nigdzie zapisywane.
- **Przygotuj maszynę** najpierw sprawdza maszynę, a potem robi po kolei to, czego brakuje:
  pakiety systemowe (tylko gdy `sudo` na maszynie nie pyta o hasło), `uv`, wysyłkę kodu i danych,
  środowiska (`setup.sh`) i usługę panelu. Na końcu sprawdza maszynę jeszcze raz.
- Lista **Maszyna** pod przyciskami pokazuje stan: ✓ gotowe, → zrobi Przygotuj, ✋ musisz zrobić sam
  (np. `ssh -t … sudo apt install -y ffmpeg` w terminalu na Macu, bo wymaga hasła sudo; albo
  sterownik NVIDIA i restart), ! ostrzeżenie (mało miejsca, torch nie widzi karty). Tam jest też
  login do panelu na maszynie (**pokaż**).
- Gdy na maszynie trwa trening, Przygotuj wyśle kod i dane, ale nie przeinstaluje środowisk (zmieniłoby
  je pod działającym treningiem).
- Wysyłka przesyła tylko zmiany i niczego na serwerze nie usuwa: checkpointy, eksporty i bazy zostają.
- Trening uruchamiasz potem w panelu na serwerze; Mac może być wyłączony.

### Zasilanie maszyny przez Home Assistant

Maszyna z GPU nie musi być włączona cały czas. Jeśli stoi na inteligentnym gniazdku w Home
Assistant, panel może ją włączać i bezpiecznie wyłączać przyciskiem na górnym pasku (tak samo jak
panel treningu słów wybudzających, home-assistant-wakeword).

1. **W Home Assistant** potrzebny jest przełącznik maszyny, który sam robi całą pracę:
   włączenie = włączenie gniazdka (BIOS uruchamia komputer po powrocie zasilania; maszyna jest na
   Wi-Fi, więc Wake-on-LAN nie działa), wyłączenie = `sudo poweroff` przez SSH, czekanie aż
   gniazdko pokaże mniej niż 5 W (do 5 minut) i dopiero wtedy odcięcie gniazdka. Gotowy przykład:
   [`docs/home-assistant/maszyna_gpu.yaml`](../home-assistant/maszyna_gpu.yaml) (pakiet z
   `switch.maszyna_gpu` i skryptem; `shell_command.turn_off_ubuntu` i nazwy encji dopasuj do
   siebie). Nie wybieraj samego gniazdka: wyłączenie odcięłoby prąd działającemu systemowi.
2. **W panelu**: **⚒ Narzędzia → Home Assistant** – adres (np. `http://homeassistant.local:8123`)
   i token długoterminowy **administratora** (Home Assistant → Twój profil → Bezpieczeństwo →
   Tokeny długoterminowe → Utwórz) → **Zapisz połączenie**. Panel od razu pyta Home Assistant i
   mówi, czy odpowiada.
3. Niżej, w **Zasilanie maszyny z GPU**: **↻ Podpowiedzi z HA** wypełnia listy; wybierz
   przełącznik maszyny (`switch.maszyna_gpu`) i pomiar mocy gniazdka w W
   (np. `sensor.pokoj_kuby_komputer_moc_czynna`), próg wyłączenia zostaw 5 W → **Zapisz
   zasilanie**. Identyfikator encji można też wpisać ręcznie.

Na górnym pasku pojawia się przycisk ze stanem maszyny:

| Stan | Znaczy | Kliknięcie |
|---|---|---|
| Maszyna: wyłączona | przełącznik wyłączony, gniazdko poniżej progu | pyta i włącza |
| Maszyna: uruchamia się | przełącznik włączony, port SSH jeszcze nie odpowiada | pyta i wyłącza |
| Maszyna: włączona · 212 W | przełącznik włączony, SSH odpowiada; obok moc z gniazdka | pyta i wyłącza |
| Maszyna: wyłącza się | przełącznik wyłączony, a gniazdko wciąż pobiera więcej niż próg | nic (czekaj) |
| Maszyna: sprawdzam… | panel jeszcze nie dostał pierwszej odpowiedzi | nic |
| Maszyna: brak odczytu z HA | Home Assistant nie odpowiada albo odmawia; przyczyna w podpowiedzi po najechaniu | nic |
| Maszyna: token HA odrzucony | Home Assistant odrzucił token (401); panel przestał pytać HA, aż zapiszesz połączenie | **Zapisz połączenie** w ⚒ Narzędzia |

- Każde kliknięcie najpierw pyta o potwierdzenie.
- **Wyłączenie jest odrzucane, gdy na maszynie trwa zadanie** (trening, generowanie, filtr…):
  panel sprawdza to tuż przed, przez SSH (`<folder>/data/jobs/current.json` na maszynie). Zatrzymaj
  zadanie albo poczekaj, aż się skończy.
- Adres i token są tylko na tym komputerze, w `~/.config/piper-voice-cloner/home_assistant.json`
  (prawa 600), nie w folderze danych (ten jest kopiowany na maszynę i do kopii zapasowych). Token
  nigdy nie wraca na stronę; puste pole tokenu przy zapisie zostawia zapisany. Zmienne
  `PVC_HA_URL` i `PVC_HA_TOKEN` mają pierwszeństwo przed plikiem. W tym samym pliku, pod kluczem
  `"power"`, są ustawienia zasilania.
- Panel nie czeka na maszynę ani na Home Assistant: strona ładuje się od razu, a stan pojawia
  się po chwili (pytanie idzie w tle co ~10 s; wyłączona maszyna = 1,5 s próby połączenia z
  portem SSH zamiast 10 s czekania na SSH).

## Interfejs w przeglądarce

Każdy krok tej instrukcji jest dostępny także bez komend, w przeglądarce:

```bash
pvc ui --lang pl              # http://<komputer>:7860
./scripts/install-service.sh  # na stałe: usługa systemd użytkownika, startuje z systemem
```

- **Języki**: polski pod `/pl/`, angielski pod `/en/`; przełącznik EN | PL w górnym pasku
  zapamiętuje wybór. `--lang` ustawia tylko język przy pierwszej wizycie.
- **Panel na żywo**: bieżący etap, czas trwania i karta graficzna (obciążenie, pamięć, temperatura,
  moc), w tym samym układzie co panel treningu wake word.
- **Pasek kroków** u góry: kroki 1–7 oraz Ustawienia (`voice.yaml`) i Narzędzia (import, własna
  baza). Pokazuje postęp (✓ = zrobione, numer w obwódce = następny krok) i służy do nawigacji:
  kliknij krok, żeby go otworzyć. Każdy krok ma opis i znak „?”, który wyjaśnia, co robi.
- **Maszyna z GPU na górnym pasku**: przycisk zasilania (gdy jest ustawione połączenie z Home
  Assistant, patrz [Zasilanie maszyny przez Home Assistant](#zasilanie-maszyny-przez-home-assistant))
  i status. Gdy jest zapisany serwer z GPU, status pokazuje też zadanie trwające na maszynie
  („Na maszynie trwa Trening (kuba)…”), a zaraz po otwarciu strony „Sprawdzam maszynę…”.
- **Zadania w tle**: generowanie, filtr, trening, eksport i import działają w tle. Na górze strony
  widać ich log na żywo i przycisk „Zatrzymaj zadanie” (działa jak Ctrl+C). Naraz działa jedno
  zadanie, bo karta graficzna jest jedna. Zamknięcie przeglądarki ani restart usługi nie
  przerywają zadania.
- **Dostęp zdalny**: usługa nasłuchuje w sieci domowej (`0.0.0.0:7860`). Login i hasło są w
  `~/.config/piper-voice-cloner/env` (`PVC_UI_AUTH`); skrypt generuje je przy pierwszej
  instalacji. Spoza domu łącz się przez VPN, np. WireGuard. Nie wystawiaj portu do internetu.
- **Obsługa usługi**: logi przez `journalctl --user -u piper-voice-cloner -f`, restart przez
  `systemctl --user restart piper-voice-cloner`, usunięcie przez
  `./scripts/install-service.sh --remove`.

## Gdzie są dane

Wszystkie prywatne dane są w `$PVC_HOME` (`voices/<nazwa>/`, `bases/`, `models/`). Trzymaj ten
katalog poza repozytorium. Jeśli znajdzie się w repozytorium git, którego `.gitignore` nie
wyklucza `voices/`, `pvc` wypisze ostrzeżenie.

```
voices/<nazwa>/
  voice.yaml          ustawienia (tworzy `pvc init`)
  reference/          oczyszczone nagrania, embedding mówcy, skalibrowany próg
  prompts.tsv         wybrane zdania
  audition/           porównanie ustawień (audition.html)
  raw/                syntetyczne klipy + manifest.csv
  dataset/            zbiór treningowy: metadata.csv + wav/ (22 050 Hz, 16 bit) + raporty
  train/              trening Piper (lightning_logs/, config.json, run.json)
  export/             <locale>-<nazwa>-medium.onnx + .onnx.json
```

### Zmiana nazwy głosu

**⚙ Ustawienia** pozwalają zmienić nazwę głosu i nazwę pliku Piper. Nazwa głosu to nazwa folderu, więc
panel przenosi cały folder z klipami i ustawieniami. Nie zadziała to, gdy na tym głosie trwa zadanie.
Maszyna z GPU zachowuje stary folder i trening pod starą nazwą: po wysłaniu powstaje tam nowy folder
bez wyników treningu. Zmieniaj więc nazwę przed treningiem albo w panelu na maszynie. Wyeksportowane
pliki zachowują nazwy do następnego eksportu.

## 1. Nagranie referencyjne

- Wystarczy 10–60 sekund **czystej** mowy: bez muzyki, telewizora w tle i innych głosów.
- Blisko mikrofonu, w cichym pokoju, normalnym głosem. Notatka głosowa z telefonu wystarczy.
- Naturalna, zróżnicowana mowa jest lepsza niż czytanie listy. Dziecko niech opowie krótką
  historię albo odpowie na kilka pytań.
- Postać z bajki: wytnij fragmenty, w których mówi sama, bez muzyki i efektów. Muzyka w
  referencji przechodzi do każdego wygenerowanego klipu.

```bash
pvc init kuba_bajka --piper-name pl_PL-kuba_bajka
pvc reference kuba_bajka nagranie1.m4a nagranie2.wav
```

`pvc reference` przycina nagrania, wyrównuje głośność i tnie je na fragmenty 3–12 s. Liczy też
embedding mówcy i zapisuje w `voice.yaml` **skalibrowany próg podobieństwa**
(`quality.min_similarity`). Próg wynika z tego, jak bardzo różni się sama referencja. Głosy
dziecięce mają naturalnie niższe wyniki i kalibracja to uwzględnia.

## 2. Zdania

```bash
pvc corpus kuba_bajka --source ksiazki.txt --source kwestie_postaci.txt
```

- Źródła to pliki tekstowe z jednym zdaniem w linii albo TSV `id<TAB>tekst`.
- Pakiet językowy dokłada własne zdania: dla polskiego proste kwestie dla dzieci.
- Każde zdanie przechodzi przez reguły zwykłego tekstu. Linie z cyframi, godzinami, datami,
  numeracją list, symbolami, adresami albo skrótami są **odrzucane, a nie przerabiane**. Głos ma
  się uczyć tylko zwykłych słów; liczby poprawnie czyta normalizacja tekstu w czasie działania.
  Rozpisywanie ich w tekście treningowym daje niespójną wymowę.
- 3–20 słów w zdaniu, bez duplikatów.
- Wybór równomiernie pokrywa fonemy i difony. Domyślnie bierze `target_clips × overgenerate`
  (2000 × 1,3 = 2600) zdań.
- Co odrzucono i dlaczego, widać w `corpus_report.csv`.

## 3. Odsłuch ustawień

```bash
pvc audition kuba_bajka --apply-best
```

- Generuje 12 zdań dla każdej kombinacji ustawień backendu. Dla Chatterboxa siatka to
  `cfg_weight` 0 / 0,3 / 0,5 × `exaggeration` 0,5 / 0,7.
- Zapisuje `audition/audition.html`: odsłuchaj każdą kombinację i porównaj CER, podobieństwo i
  MOS.
- `--apply-best` zapisuje w `voice.yaml` ustawienia z najlepszym wynikiem. Ucho jest ważniejsze
  niż wynik.
- `cfg_weight` 0 zmniejsza akcent przeniesiony z referencji, co pomaga, gdy referencja jest w
  innym języku.
- Jeśli żadna kombinacja nie brzmi jak oryginał, popraw referencję (czystsza, dłuższa, bardziej
  zróżnicowana), zanim wygenerujesz 2600 klipów. Głosy małych dzieci to najtrudniejszy przypadek
  dla każdego modelu klonującego.

## 4. Generowanie i filtr

```bash
pvc synthesize kuba_bajka            # można wznawiać; referencje i seedy rotują co zdanie
pvc filter kuba_bajka                # Whisper large-v3 + CAM++ + UTMOS
```

Klip jest odrzucany, gdy:

| powód | reguła (`quality` w voice.yaml) |
|---|---|
| `too_fast_or_cut` / `too_slow_or_hallucinated` | sekundy na literę poza 0,035–0,16 |
| `asr_mismatch` | CER Whispera powyżej `max_cer` (0,04) |
| `speaker_mismatch` | podobieństwo poniżej `min_similarity` (skalibrowane) |
| `low_mos` | w najgorszych `mos_drop_fraction` (10%) według UTMOS |
| `surplus` | przeszło więcej niż `target_clips`; zostają najbardziej podobne |

`dataset/filter_report.csv` pokazuje każdy klip z wynikami. Jeśli przeszło za mało klipów,
wygeneruj więcej: zwiększ `overgenerate` i uruchom ponownie `pvc corpus` i `pvc synthesize`. Już
wygenerowane klipy zostaną użyte ponownie.

## Głos z ElevenLabs (bez nagrania i karty graficznej)

Gdy głos masz już na koncie ElevenLabs, nie trzeba go klonować lokalnie. ElevenLabs czyta zdania w
swojej chmurze, a klipy trafiają do `raw/` na komputerze, na którym działa panel. Do tego kroku
wystarczy Mac: karta potrzebna jest dopiero do treningu.

1. **⚙ Ustawienia:** zapisz klucz API raz, dla wszystkich głosów (plik
   `~/.config/piper-voice-cloner/elevenlabs.json`, poza folderem danych, nie trafia na maszynę z GPU
   ani do kopii). Klucz potrzebuje dostępu do głosów i tekstu na mowę. Uprawnienie `user_read` jest opcjonalne: pokazuje kredyty.
2. **Nowy głos:** podaj nazwę. Model klonujący wybierasz w Generowaniu, a start treningu w Treningu.
3. **Krok 4. Generowanie:** ustaw **Model klonujący** na `elevenlabs`, kliknij **Wczytaj głosy** i
   wybierz głos: Twoje głosy są na początku listy, którą można filtrować pisaniem. Panel pokaże kredyty, jeśli klucz ma `user_read`. Nie używaj głosu, który ma już klipy z Chatterboxa:
   generowanie odmówi mieszania dwóch źródeł.
4. Wybierz **Zestaw zdań**, np. `marek (1496)`, i kliknij **Użyj zestawu**. `marek`, `ewa` i
   `basia` mają te same zdania, więc każdy nowy głos czyta ten sam zestaw i ma te same
   identyfikatory klipów.
5. Zrób próbę: wpisz 20 zdań i odsłuchaj klipy w `raw/`. Potem ustaw 0 i wygeneruj resztę. Już
   zrobione klipy nie są generowane ani liczone ponownie.

To samo z terminala:

```bash
pvc init alicja --backend elevenlabs --base bazowy-pl
pvc elevenlabs voices                 # głosy z konta i pozostałe kredyty
pvc elevenlabs pick alicja <voice_id>
pvc sentences alicja marek           # zdania głosu marek
pvc synthesize alicja --limit 20     # próba
pvc synthesize alicja                # reszta
```

Koszt zestawu `marek` to około 78 000 znaków. Model `eleven_multilingual_v2` liczy około 1 kredytu
za znak; aktualny cennik sprawdź na koncie ElevenLabs.

Użycie zestawu ustawia `target_clips` na liczbę zdań, `overgenerate` na 1 i `mos_drop_fraction` na
0: filtr odrzuca tylko klipy, które nie przeszły kontroli, a nie najsłabsze 10%. Nie ma nagrania,
więc filtr pomija podobieństwo głosu i wypisuje `skipped check: similarity`.

Przy przeciążeniu albo zerwanym połączeniu każde zdanie jest ponawiane 5 razy. Błędny klucz, brak
kredytów i nieznany głos zatrzymują całe zadanie; gotowe klipy zostają.

## 5. Trening

Punkt startowy wybierasz w `voice.yaml` (`train.base`) albo przez `--base`:

| baza | co to jest | kiedy |
|---|---|---|
| `bazowy-pl` | własna baza, trenowana od losowych wag | głos bez żadnej wiedzy z angielskiego |
| `lessac` | angielski `en_US-lessac-medium` (pobierany raz, ~850 MB) | najszybszy dobry wynik |
| `ckpt:<ścieżka>` | dowolny checkpoint Piper **medium** | np. kontynuacja wcześniejszego głosu |

```bash
pvc train kuba_bajka                 # sam wznawia od ostatniego checkpointu
pvc train kuba_bajka --dry-run       # tylko wypisz komendę piper1-gpl
```

- `train.max_epochs` liczy się **ponad** checkpointem startowym. Lightning kontynuuje licznik
  epok z checkpointu (lessac zaczyna od epoki 2164), a `pvc` to uwzględnia.
- piper1-gpl sam zapisuje najlepsze checkpointy według `val_mel` i `val_mos` (UTMOS) oraz
  `last.ckpt`.
- Postęp śledzisz przez `tensorboard --logdir voices/<nazwa>/train/lightning_logs`. Ostateczny
  checkpoint wybierz na słuch; `val_mos` jest dobrą wskazówką.

### Własna baza bez angielskiego (`bazowy-pl`)

2000 klipów nie wystarczy do treningu od losowych wag; potrzeba około 13 000 nagrań lub więcej.
Dlatego bazę trenuje się **raz** na dużym zbiorze jednego mówcy, a potem każdy głos doszkala się
od niej.

Dobry darmowy wybór dla polskiego to **MC Speech**: CC0, jedna lektorka, około 22 000 nagrań
([Kaggle](https://www.kaggle.com/datasets/czyzi0/the-mc-speech-dataset)). Przerób go na katalog
LJSpeech (`metadata.csv` w formacie `plik|tekst` i folder z nagraniami), a potem:

```bash
pvc base prepare /dane/mc_speech --audio-dir /dane/mc_speech/wavs   # te same reguły tekstu
pvc base train --max-epochs 3000                                     # kilka dni na jednej karcie
pvc base select bases/pl-scratch/train/lightning_logs/version_0/checkpoints/<najlepszy>.ckpt
```

Po `base select` ustawienie `train.base: bazowy-pl` używa tej bazy dla każdego głosu.

#### Ocena nagrań: sufit jakości bazy

Model uczy się brzmieć jak jego nagrania, więc ocena samych nagrań to praktyczny sufit `val_mos`.
W panelu (Narzędzia, własna baza) kliknij **Oceń nagrania**. Ocena bierze losową próbkę (domyślnie
300 nagrań, `0` = wszystkie) i liczy ją tym samym UTMOS, który liczy `val_mos`. Panel pokazuje
medianę, granice 10% najsłabszych i najlepszych nagrań, odsetek ocen co najmniej 4,0 oraz po trzy
najsłabsze i najlepsze nagrania do odsłuchu. Gdy kartę zajmuje trening, ocena liczy się na CPU
(ok. 7 nagrań/s) i działa obok treningu, bez przerywania go. Wynik zostaje w
`bases/pl-scratch/dataset/utmos.json`.

```bash
pvc base score --sample 300      # z linii poleceń; --sample 0 ocenia wszystkie nagrania
```

Jeśli mediana nagrań to np. 3,67, a model ma już `val_mos` 3,55, dłuższy trening tej samej bazy
niewiele da. Wyraźnie lepszy dźwięk może dać większy model albo czystsze nagrania.

#### Wielkość modelu: medium czy high

- **medium** - standard Pipera: szybki trening (ok. 3 min na epokę przy 18 000 nagrań na RTX 4090)
  i szybkie mówienie.
- **high** - dekoder (część, która z widma robi dźwięk) jest ok. 8 razy większy: 14 zamiast 1,7 mln
  parametrów, tak jak w oficjalnych głosach Piper „high”. Dźwięk jest czystszy, ale trening trwa
  ok. 2-3 razy dłużej, a mówienie na Jetsonie jest wolniejsze. Domyślny batch to 16, żeby zmieścić
  się na karcie 24 GB.

Każda wielkość trenuje się we własnym folderze (`bases/pl-scratch/train` i
`bases/pl-scratch-high/train`) z **tych samych** nagrań i z tymi samymi zdaniami testowymi, więc
można je uczciwie porównać. Głos doszkalany od bazy dostaje jej wielkość automatycznie (odczytaną
z checkpointu), a eksport nazywa plik `…-medium.onnx` albo `…-high.onnx`.

```bash
pvc base train --quality high --max-epochs 3000          # batch 16; --batch-size zmienia
```

W panelu **Porównanie modeli bazowych** pokazuje dla każdej wielkości średni `val_mos` i `val_mel`
z ostatnich 10 epok do epoki, do której doszły oba modele (jedna epoka to tylko 5 zdań, więc jej
wynik skacze), oraz najlepsze wyniki. W **Odsłuchu z treningu** przełącznik **Model** pozwala
posłuchać tej samej epoki obu wielkości. Trening medium można w każdej chwili zatrzymać, a później
wznowić: zacznie od najnowszego checkpointu.

## Jak długo trenować i na co patrzeć

> **Szacunki dla:** RTX 4090 24 GB, Intel Core i9-14900K, 128 GB RAM DDR5. Nie są zmierzone
> narzędziem `pvc`. Opierają się na wcześniejszych głosach (około 10 h treningu na głos na tej
> karcie) i na założeniu 1,5–2 kroków na sekundę przy `batch_size` 32. Prawdziwą prędkość
> pokazuje pasek postępu Lightning (`it/s`) po kilku minutach treningu; przelicz tabelę według
> niej.

Rachunek: **kroki na epokę = klipy × 0,95 ÷ 32**, a **czas epoki = kroki ÷ (kroki na sekundę)**.
Lepiej myśleć w krokach niż w epokach: duży zbiór potrzebuje mniej epok.

| Zadanie | Klipy | Kroki na epokę | Czas epoki | Ile trenować | Łącznie |
|---|---|---|---|---|---|
| Nowy głos (od bazy) | 2 000 | ~60 | 30–40 s | 300–1000 epok (20–60 tys. kroków) | 3–11 h |
| Małe istniejące głosy | 1 500 | ~45 | 25–30 s | 400–1000 epok | 3–8 h |
| Średni głos | 3 800 | ~115 | 1–1,3 min | 300–600 epok | 5–13 h |
| Duży głos | 18 400 | ~550 | 5–6 min | 100–250 epok (55–140 tys. kroków) | 9 h – 1 doba |
| Baza od zera (MC Speech) | ~22 000 | ~650 | 6–7 min | 500–1000+ epok (300–600 tys. kroków) | 3–7 dni |

Uwagi do sprzętu:
- **Pierwsze uruchomienie** najpierw przygotowuje dane do `train/cache/`: głoski, przycięcie ciszy
  i spektrogramy. Przy małych głosach trwa to kilka minut, przy dużych zbiorach i bazie kilkadziesiąt.
  Kolejne uruchomienia korzystają z gotowego cache.
- **`train.num_workers`** to liczba procesów ładujących dane, domyślnie 8 (piper1-gpl sam ustawia
  1, przy którym GPU czeka na dane). i9-14900K ma 8 rdzeni wydajnych, więc 8–12 to rozsądny
  zakres. 128 GB RAM wystarcza z dużym zapasem.
- **`batch_size`**: zostaw 32. 24 GB VRAM wystarcza, a większy batch przyspiesza epokę, ale
  zmienia przebieg fine-tuningu. Przy bazie od zera można spróbować 48–64, pilnując VRAM w
  `nvidia-smi`.
- **Dysk**: checkpoint ma około 800 MB. piper1-gpl trzyma 5 najlepszych według `val_mel`, 5
  według `val_mos` i `last.ckpt`, czyli do około 9 GB na głos, plus cache (kilka GB przy dużych
  zbiorach).
- **Prąd i temperatura**: przy pełnym obciążeniu karta pobiera do około 450 W, a baza od zera
  trwa kilka dni. Zadbaj o chłodzenie; limit mocy (`nvidia-smi -pl 350`, wymaga uprawnień
  administratora) obniża pobór kosztem kilku procent prędkości.

### Postęp w panelu

Karta **Postęp** po prawej stronie pokazuje bieżące zadanie: jego nazwę, czas od startu i pasek.

- **Import, filtr, generowanie, przygotowanie bazy:** licznik plików (np. `950 / 18400`), procent
  i `zostało ok. …`. Czas do końca wynika z dotychczasowego tempa, więc w pierwszych minutach bywa
  niedokładny.
- **Trening (głos albo baza):** pasek obejmuje **cały trening**, a nie jedną epokę. Na przykład
  `Epoch 2464 · 25/50 · 300 / 1000 epok · zostało ok. 11:40:00 · 30%` znaczy:
  - `Epoch 2464` to numer epoki z licznika Lightning. Przy starcie od lessac lub innego checkpointu
    zaczyna się od jego numeru, nie od zera.
  - `25/50` to kroki w bieżącej epoce.
  - `300 / 1000 epok` to epoki zrobione w tym treningu z zaplanowanych (`train.max_epochs` w
    `voice.yaml`, domyślnie 1000; baza `--max-epochs`, domyślnie 3000).
  - **`zostało ok. …`** to długość jednej epoki z paska Lightning razem z pozostałymi epokami.
    Pojawia się po kilku sekundach pierwszej epoki. Walidacji po epokach nie liczy, więc
    rzeczywisty koniec bywa kilka procent później.
  - `30%` to postęp całego treningu.
- Pierwsze minuty treningu to przygotowanie `train/cache/`; pasek stoi wtedy na `0 / … epok`.
- Trening nie musi dochodzić do 100%. Gdy próbki w TensorBoard (niżej) brzmią dobrze, zatrzymaj go
  przyciskiem **Zatrzymaj** i wybierz najlepszy checkpoint. Po wznowieniu pasek liczy dalej od
  miejsca przerwania.
- Pod paskiem są pierścienie GPU (obciążenie, pamięć, temperatura, pobór mocy) odczytywane z
  `nvidia-smi`. Panel na Macu bez karty NVIDIA ich nie pokazuje.

### Na co patrzeć

**Odsłuch w panelu.** W karcie **Trening** (dla głosu) i w **⚒ Narzędzia → Własna baza** (dla bazy)
jest blok **Odsłuch z treningu**: wybierasz epokę i słuchasz zdań testowych, które trener czyta po
każdej epoce. Przy każdej epoce jest jej **jakość** (val_mos, UTMOS 1–5: ok. 2 surowy, ok. 3
zrozumiały, 3,5+ dobry; model rzadko przebija własne nagrania - zob. **Ocena nagrań**) i najlepsza
epoka do tej pory. Panel zachowuje próbki pierwszej epoki, co 10., 3 najnowszych, 5 z najlepszym
`val_mos` i **każdej epoki, która ma checkpoint** (na liście z dopiskiem `💾 checkpoint`). Plik
`epoch=1273-val_mel=0.3614.ckpt` w polu **Checkpoint bazy** to więc „epoka 1273 · 💾 checkpoint”
w odsłuchu: każdy checkpoint da się posłuchać przed wyborem. `last.ckpt` ma przed nazwą swój bieg
(`version_1/last.ckpt`), bo każde wznowienie ma własny; **↻ Odśwież** dociąga nowe próbki.

**Odsłuch na spokojnie u siebie.** **⬇ Pobierz próbki (ZIP)** pod odsłuchem (bazy albo głosu) pakuje
próbki wszystkich zachowanych epok do jednego pliku, który przeglądarka zapisze na Twoim
komputerze (przy bazie z gÅosu kasia około 85 MB). W środku jest folder na epokę z jakością w nazwie
(`epoch01273-mos3.71-checkpoint/00.wav`, w Finderze odsłuch spacją), `samples.csv` i
**`index.html`**: tabela z odtwarzaczami, sortowanie po `val_mos` i `val_mel` oraz filtr „only
epochs with a checkpoint”, czyli tylko epoki, które da się wybrać. To samo z terminala:
`pvc base samples --quality medium` albo `pvc samples <głos>` (plik `train/monitor/samples.zip`).

**Wykres w panelu.** Pod **Logiem** (prawa kolumna) jest wykres bieżącego treningu: górny pokazuje
jakość `val_mos`, dolny błąd `val_mel` i `train_mel`, ze wspólną osią epok. Najedź, aby zobaczyć
wartości; kliknij, aby otworzyć go na całym ekranie. Tam przeciągnięcie po wykresie powiększa ten
zakres epok (albo wpisz **Od epoki / do**), kliknięcie wybiera epokę i pokazuje jej wartości, a po
prawej jest opis trzech wartości i najlepsze epoki. Wykres pokazuje trening, który właśnie trwa
(albo ostatni), w przeciwnym razie wybrany głos lub bazę; odświeża się co 20 s.

- **val_mos** - przewidywana naturalność (UTMOS, 1–5) na zdaniach testowych: **im wyżej, tym lepiej**.
- **val_mel** - błąd brzmienia na zdaniach, których model nie widział: **im niżej, tym lepiej**.
- **train_mel** - ten sam błąd na zdaniach treningowych (średnia z epoki); spada powoli cały czas.
- **Najlepszy model:** `val_mos` nie rośnie od ok. 150–200 epok, `val_mel` nie rośnie, próbki brzmią
  dobrze - weź checkpoint z najwyższym `val_mos` z tego okresu.
- **Przetrenowanie:** `train_mel` dalej spada, a `val_mel` rośnie - weź checkpoint sprzed wzrostu.

**Wykresy w TensorBoard.** Na maszynie działa usługa TensorBoard (instaluje ją **Przygotuj maszynę**,
port 6006, ustawienie `PVC_TB_PORT` w `~/.config/piper-voice-cloner/env`). Link **Wykresy w
TensorBoard ↗** jest obok odsłuchu. TensorBoard nie ma logowania - jest dostępny tylko w sieci
lokalnej (z zewnątrz przez VPN). Ręcznie:

```bash
tensorboard --logdir voices/kuba_bajka/train/lightning_logs --bind_all   # http://<komputer>:6006
```

| Wskaźnik | Co znaczy | Czego się spodziewać |
|---|---|---|
| zakładka **AUDIO** | próbki zdań testowych po każdej epoce | **najważniejsze**: słuchaj, jak głos się zmienia |
| `val_mos` | przewidywana naturalność (UTMOS, skala 1–5) | rośnie i się stabilizuje; górną granicą jest MOS Twoich klipów treningowych (kolumna `mos` w `filter_report.csv`) |
| `val_mel` | błąd odtworzenia spektrogramu na zbiorze walidacyjnym | szybko spada i się wypłaszcza; wypłaszczenie **nie** oznacza końca, bo jakość dźwięku rośnie dalej |
| `loss_g`, `loss_d` | generator i dyskryminator (trening GAN) | wahają się i to normalne; źle, gdy `loss_d` spada w okolice zera, a `loss_g` gwałtownie rośnie |

Co słychać w próbkach:
- **Na początku fine-tuningu** słychać barwę bazy. Przy 2000 klipów głos zwykle przechodzi w nowy
  po 50–100 epokach.
- **Metaliczny, szumiący, „syczący” dźwięk**: za wcześnie, trenuj dalej.
- **Połykanie lub powtarzanie słów, zła wymowa konkretnych głosek**: to zwykle problem danych, nie
  czasu. Sprawdź `filter_report.csv`, zaostrz `max_cer` i przefiltruj ponownie.
- **`val_mel` zaczyna rosnąć, a próbki brzmią płasko albo gorzej**: przeuczenie. Wybierz
  wcześniejszy checkpoint.

Kiedy przerwać:
- `val_mos` nie rośnie od około 100 epok przy małych głosach albo około 30 epok przy dużych
  zbiorach i bazie, **i** próbki brzmią dobrze.
- Trening można przerwać w każdej chwili (Ctrl+C). `pvc train` wznawia od najnowszego
  checkpointu (`last.ckpt` albo nowszego „najlepszego”), więc powtarza najwyżej kilka epok.

Wybór checkpointu:
1. Weź plik z najlepszym `val_mos` (`epoch=…-val_mos=….ckpt` w `train/lightning_logs/version_*/checkpoints/`).
2. Porównaj go na słuch z `last.ckpt`.
3. Wyeksportuj wybrany: `pvc export kuba_bajka --checkpoint <plik>`.
4. Posłuchaj kilkunastu zdań spoza zbioru treningowego, także z liczbami i datami (czyta je
   normalizacja `pl_tts`).

### Kolejka treningów

W panelu na maszynie, w kroku **Trening**, ustaw **Start treningu** i liczbę epok. W polu **Kolejka
treningów** wybierz głosy w kolejności, w jakiej mają się trenować, i kliknij **Uruchom kolejkę**.
Wybrana kolejność jest widoczna w karcie **Etap**, która pokazuje też stan każdego głosu. Każdy głos dostaje te same ustawienia. Błąd jednego głosu nie zatrzymuje następnych, a **Zatrzymaj
zadanie** kończy całą kolejkę. Zaznaczone wyłączenie maszyny działa po ostatnim głosie. Filtr jest
potrzebny tylko dla głosów z wygenerowanymi klipami: zaimportowane mają gotowy `dataset/`.

Z terminala:

```bash
pvc train-queue alicja_nowa tomek marek --epochs 500 --base bazowy-pl
```

### Jak czytać postęp treningu

Przykład: `557 / 1000 epok · epoka modelu 1670 · krok 17/112`.

- `557 / 1000 epok`: ile epok głos ma od bazy i jaki jest limit z pola epok.
- `epoka modelu 1670`: licznik łącznie z epokami bazy. Tego numeru używają checkpointy i **Odsłuch**.
- `krok 17/112`: miejsce w bieżącej epoce.

Aby dotrenować gotowy głos, zwiększ limit, bo liczy się on od bazy. Głos po 500 epokach dostanie
około 500 kolejnych dopiero przy limicie 1000. Przy limicie 500 trening skończy się prawie od razu.

### Wyłączenie maszyny po treningu

W kroku **Trening** w panelu na maszynie zaznacz **Wyłącz maszynę po zakończeniu treningu**. Po
końcu treningu Ubuntu wyłącza się przez `sudo poweroff`, także gdy trening zakończył się błędem.
Przycisk **Zatrzymaj zadanie** nie wyłącza komputera. Gniazdko odcina automatyzacja z
`docs/home-assistant/maszyna_gpu.yaml`, gdy pobór spada poniżej 5 W, więc rano wystarczy włączyć
przełącznik maszyny w Home Assistant.

Decyzję możesz zmienić w trakcie zadania. Pod kartą **Etap** widać wtedy pole **Wyłącz maszynę po
zakończeniu tego zadania**. Zaznacz je albo odznacz, a trening nie zostanie przerwany. W kolejce
treningów pole dotyczy końca całej kolejki, a nie pojedynczego głosu.

## 6. Eksport i użycie

Eksport zamienia checkpoint w głos Pipera. Powstają dwa pliki i potrzebne są oba: `.onnx` to model, a
`.onnx.json` to jego ustawienia.

### Eksport wytrenowanego głosu

W panelu, w którym trwał trening, otwórz krok **7. Eksport**. Wybierz checkpoint, który najlepiej
brzmiał w odsłuchu, i uruchom eksport. Bez wyboru `pvc` użyje najnowszego:

```bash
pvc export kuba_bajka
```

Pliki trafiają do `voices/kuba_bajka/export/`, np. `pl_PL-kuba_bajka-medium.onnx`. Nazwę bierze z
pola **Nazwa pliku Piper**.

### Eksport głosu bazowego

Modele bazowe są na maszynie z GPU, więc użyj panelu na tej maszynie:

1. Otwórz **⚒ Narzędzia → Własna baza bez angielskiego (bazowy-pl)**.
2. W polu **Checkpoint bazy** wybierz checkpoint.
3. Kliknij **Eksportuj jako głos**.

Pliki trafiają do `bases/export/pl_PL-bazowy-medium.onnx` i `.onnx.json`. Ten sam eksport z terminala
na maszynie, z własną nazwą pliku:

```bash
cd ~/piper-voice-cloner/repo
PVC_TRAIN_PYTHON=$PWD/.venv-train/bin/python .venv/bin/pvc --root ~/piper-voice-cloner/data \
  base export --name pl_PL-moja_baza
```

Bez `--checkpoint` eksport bierze model ustawiony jako `bazowy-pl`.

### Wgranie głosu do Home Assistant

Przykłady dotyczą Wyoming Piper na osobnym serwerze. Podstaw swoje adresy i katalog z plikami
`*.onnx` Pipera.

1. **Pobierz pliki z maszyny z GPU.** Dla wytrenowanego głosu wystarczy `make remote-pull`. Głos
   bazowy pobierz tak (cudzysłów jest potrzebny w zsh):

   ```bash
   scp '<użytkownik>@<maszyna>:piper-voice-cloner/data/bases/export/pl_PL-bazowy-medium.onnx*' .
   ```

2. **Skopiuj oba pliki na serwer Pipera.** Użyj nowej nazwy głosu. Ta sama nazwa nadpisze działający
   głos, więc najpierw zrób jego kopię.

   ```bash
   scp pl_PL-bazowy-medium.onnx pl_PL-bazowy-medium.onnx.json <użytkownik>@<serwer>:/ścieżka/do/piper/models/
   ```

3. **Odśwież listę głosów w Home Assistant.** Otwórz **Ustawienia → Urządzenia i usługi → Wyoming
   Protocol**, przy wpisie Pipera wybierz **⋮ → Załaduj ponownie**. Starsze wersje Wyoming Piper
   mogą wymagać restartu kontenera Pipera.
4. **Wybierz głos.** Otwórz **Ustawienia → Asystenci głosowi**, wybierz asystenta, a w sekcji zamiany
   tekstu na mowę ustaw nowy głos. Ustawienie dotyczy tylko tego asystenta.
5. **Sprawdź go.** Zapisz asystenta i posłuchaj odpowiedzi albo użyj **Wypróbuj** przy głosie.

Żeby się wycofać, wybierz w asystencie poprzedni głos. Pliki na serwerze możesz wtedy usunąć.

## Nowy głos z krótkiego nagrania

Masz jedno nagranie, np. 15 s, i chcesz z niego zrobić głos Piper na około 1500 klipach. Da się,
ale wynik zależy bardziej od **jakości** nagrania niż od jego długości. Liczby w tym rozdziale
pochodzą z prawdziwej próby (postać filmowa, dwa nagrania) na MacBooku Pro M1 Max 64 GB.

### Czy 15 sekund wystarczy?

- **Do klonowania tak.** Chatterbox klonuje z około 10 s. `pvc reference` potnie 15 s na 1–2
  fragmenty i ostrzeże, że nagranie jest krótkie (poniżej 20 s albo tylko 1 fragment).
- **Dłuższe nagranie jest lepsze, nie konieczne.** 30–60 s różnorodnej mowy daje więcej
  fragmentów (synteza je rotuje, więc klipy są mniej monotonne) i pewniejszy próg podobieństwa w
  filtrze. Jeśli możesz dograć więcej, zrób to przed generowaniem 2000 klipów, nie po.
- **Język nagrania ma znaczenie.** Nagranie po polsku daje wyraźnie lepsze wyniki niż angielskie.
  W próbie 8,8 s polskiej mowy przebiło 33 s angielskiego oryginału (tabela niżej): przy obcym
  języku polskie klipy brzmią mniej jak oryginał i filtr odrzuca je jako `speaker_mismatch`.
- **Efekty dźwiękowe się nie przenoszą.** Pogłos, przetworzenie „robota” czy muzyka w tle albo
  zostaną zgubione, albo zabrudzą każdy klip. Najlepiej czysty głos.
- **Klon głosu syntetycznego** (np. z ElevenLabs) działa dobrze technicznie, ale kopiuje też jego
  płaskość: Piper wytrenowany na takim klonie będzie brzmiał jak klon klonu.
- **Głosy dzieci** są najtrudniejsze dla każdego modelu klonującego. Tu dłuższe nagranie (60 s)
  naprawdę się opłaca.

### Wynik próby

| | 33 s, oryginał po angielsku | 8,8 s po polsku (ElevenLabs) |
|---|---|---|
| fragmenty referencji | 3 | 1 |
| najlepsze ustawienia z odsłuchu | `cfg_weight` 0,3, `exaggeration` 0,7 | `cfg_weight` 0, `exaggeration` 0,7 |
| przeszło filtr (z 50) | **22 (44%)** | **38 (76%)** |
| odrzucone: inna barwa / błąd tekstu / słaba jakość | 17 / 8 / 3 | 0 / 7 / 5 |
| mediana podobieństwa, CER, UTMOS | 0,52 · 0,4% · 3,16 | 0,86 · 0,9% · 3,47 |
| zdań na 1500 klipów | ~3400 (`overgenerate` 2,3) | ~1950 (domyślne 1,3) |

Wniosek: z 76% przechodzących klipów wystarczy domyślny zapas zdań. Przy 44% trzeba podnieść
`overgenerate` albo, lepiej, poprawić nagranie.

### Krok po kroku (cel 1500 klipów)

1. **Nowy głos**: `pvc init <nazwa>` i w `voice.yaml` ustaw `target_clips: 1500` (panel: krok
   Nowy głos).
2. **Nagranie**: `pvc reference <nazwa> nagranie.wav`. Ostrzeżenie o krótkim nagraniu to
   informacja, nie błąd.
3. **Zdania**: `pvc corpus <nazwa>` wybiera `1500 × 1,3 ≈ 1950` zdań (około 2 min).
4. **Odsłuch ustawień**: `pvc audition <nazwa> --apply-best` (72 klipy). Posłuchaj
   `audition/audition.html`. Jeśli żadna kombinacja nie brzmi jak oryginał, popraw nagranie teraz.
5. **Próba**: `pvc synthesize <nazwa> --limit 50`, potem `pvc filter <nazwa>`. Na końcu
   generowania widać prędkość (np. `50 clips in 19.4 min on mps: 23.2 s per clip`), a filtr pokaże,
   jaki odsetek przechodzi. Z tego policzysz, ile zdań potrzeba.
6. **Całość**: `pvc synthesize <nazwa>` (można przerywać i wznawiać) i `pvc filter <nazwa>`.
7. **Trening** od `bazowy-pl` na maszynie z kartą NVIDIA, potem **eksport**.

### Mac czy Ubuntu?

Mac z Apple Silicon generuje i filtruje (`make setup-mac`, GPU Apple przez `mps`). Trening Pipera
wymaga karty NVIDIA, więc zostaje na Ubuntu.

| krok (1950 zdań) | Mac M1 Max, zmierzone | Ubuntu RTX 4090, szacunek |
|---|---|---|
| nagranie + zdania | ~2 min | ~2 min |
| odsłuch ustawień (72 klipy) | 50–110 min | ~15 min |
| generowanie | 23 s na klip → **~12,5 h** | ~3 s na klip → ~1,5–2 h |
| filtr (Whisper na CPU na Macu) | 7 s na klip → **~3,8 h** | ~1 s na klip → ~0,5 h |
| trening od `bazowy-pl` (1500 klipów) | nie da się | 3–8 h |

Kolumna Ubuntu to szacunek; zostanie zastąpiona pomiarem, gdy karta będzie wolna od treningu bazy.

- **Mac ma sens**, gdy karta trenuje coś innego (np. bazę przez kilka dni): generujesz na Macu w
  nocy, a gotowy zbiór wysyłasz na maszynę (`pvc remote push`) tylko do treningu.
- **Ubuntu jest kilka razy szybsze**, gdy karta jest wolna.
- Nie uruchamiaj dwóch modeli klonujących naraz na Macu: brakuje pamięci i system zabija proces
  (kod 137). Generowanie da się wtedy po prostu wznowić.

### Ile to trwa w sumie

- **Twoja praca**: przygotowanie nagrania i odsłuch to 30–60 min. Reszta idzie sama.
- **Mac + Ubuntu**: ~17 h generowania i filtra na Macu, potem 3–8 h treningu, czyli 1–1,5 doby.
- **Samo Ubuntu**: ~2–3 h generowania i filtra plus 3–8 h treningu, czyli około doby z zapasem
  na odsłuch i wybór checkpointu.

### Ograniczenia i prawo

- Każdy klip Chatterboxa ma niesłyszalny znak wodny Resemble Perth. Służy do rozpoznania, że mowa
  jest wygenerowana; nie zmienia brzmienia i nie przeszkadza w treningu.
- Głos prawdziwej osoby tylko za jej zgodą; głos dziecka za zgodą rodzica lub opiekuna.
- Postacie z filmów i bajek: tylko do prywatnego użytku w domu. Patrz
  [Prywatność i prawo](#prywatność-i-prawo).

## Przetrenowanie istniejących głosów

Stare datasety często mają linie z cyframi, datami albo numeracją list oraz audio MP3 zapisane
pod nazwą `.wav`. `pvc import` czyści je tymi samymi regułami:

```bash
pvc init kasia --piper-name pl_PL-kasia_glos     # ta sama nazwa pliku co wcześniej
pvc import kasia /stare/pl_PL-kasia_glos-medium \
  --metadata /stare/pl_PL-kasia_glos-medium/metadata.csv \
  --persona /stare/pl_PL-kasia_glos-medium/custom_metadata.csv  # numerowane listy: "1. ..."
pvc train kasia --base bazowy-pl
pvc export kasia
```

- W plikach `--persona` numeracja jest usuwana przed sprawdzeniem tekstu.
- Krótkie odpowiedzi („Usiądziesz?”) zostają; długie zdania ogranicza limit 20 s audio.
- `--verify` dodatkowo sprawdza każdy klip Whisperem (wolne).
- Przed podmianą zachowaj stare pliki `.onnx` jako kopię zapasową.

## Dodanie języka

Utwórz `piper_voice_cloner/languages/<kod>.py` z `PACK = LanguagePack(...)`:
- `espeak_voice`: głos espeak-ng dla Pipera (np. `cs`);
- `locale`: prefiks nazwy pliku (np. `cs_CZ`);
- `synth_language`: kod języka dla backendu klonującego i Whispera;
- `extra_letters`: litery poza a–z (np. `áčďéěíňóřšťúůýž`);
- `abbreviations`: skróty do odrzucenia;
- `focus_phonemes`: głoski do mocniejszego pokrycia;
- `prompt_files`: opcjonalne zdania w `languages/data/`.

Potem `pvc init <nazwa> --language <kod>`. Sprawdź, czy backend klonujący obsługuje dany język;
Chatterbox ma ich 23.

## FAQ i rozwiązywanie problemów

Szukaj po treści komunikatu (Ctrl+F). Pełny log zadania jest w panelu po prawej oraz w
`<dane>/jobs/*.log`.

### Filtr: `no generated clips in …/raw: nothing to filter`

Głos zaimportowany nie ma wygenerowanych klipów, a jego `dataset/` jest już gotowy do treningu. Pomiń
Filtr. Starsze wersje czyściły w tym miejscu `dataset/`. Jeśli tak się stało na maszynie, **⚒ Narzędzia
→ Przygotuj maszynę** przywróci zestaw z komputera, z którego go wysłano.

### Eksport: `No module named 'onnxscript'` albo `GuardOnDataDependentSymNode`

Środowisku treningu brakowało pakietów ONNX, a nowy eksporter PyTorch nie obsługuje tego modelu.
Kliknij **Przygotuj maszynę** i uruchom eksport ponownie: kloner używa starszego eksportera.

### Odsłuch: `ElevenLabsFatalError: no API key` w panelu na maszynie

Klucz ElevenLabs jest zapisany na komputerze, na którym go wpisano. Klipy generuj na Macu. Krok
**Odsłuch ustawień** pomiń: dla głosu z ElevenLabs zużywa kredyty i nie jest potrzebny do treningu.

### `'piotr' is an imported voice: create a new voice to generate clips`

Głos zaimportowany to gotowy zestaw nagrań i źródło zdań, więc nie generuje nowych klipów. Utwórz nowy
głos i tam wybierz model oraz zestaw zdań. Komunikat pod zestawem zawsze podaje nazwę wybranego głosu.

### Po restarcie `make ui`: `An event handler (run_export) didn't receive enough input values`

Karta otwarta przed aktualizacją panelu wysłała zdarzenia timerów według starego układu, a w nowym te
numery należą do innych funkcji. Błąd `Value: '…' is not in the list of choices: []` ma tę samą
przyczynę. Panel odrzuca takie zdarzenia, a zadanie się nie uruchamia. Odśwież kartę (Cmd+R). Po
aktualizacji kodu najlepiej zamknąć stare karty przed uruchomieniem panelu.

### Generowanie: `Stopped: HTTP 401: …` (`quota_exceeded`, `invalid_api_key`)

Kod 401 oznacza błędny klucz albo brak kredytów; treść odpowiedzi mówi który. Zapisz nowy klucz w
Ustawieniach albo dokup kredyty i uruchom generowanie ponownie. Gotowe klipy zostają.

### Wczytaj głosy: `HTTP 401: … missing_permissions`

Klucz z ograniczeniami nie ma dostępu do głosów. W ElevenLabs włącz to uprawnienie dla klucza albo
utwórz nowy. Sam brak `user_read` nie jest błędem: głosy się wczytają, tylko bez kredytów.

### Generowanie: `Stopped: raw/ holds clips of another voice (…)`

W `raw/` są klipy innego modelu albo innego głosu ElevenLabs. Utwórz nowy głos w panelu albo przenieś
`raw/` poza folder głosu.

### Użyj zestawu: `raw/ already holds … clips of other sentences`

Głos ma już klipy innych zdań, a filtr użyłby ich razem z nowymi. Utwórz nowy głos.

### `voice name: lowercase letters, digits and '_' only`

Nazwa głosu może mieć tylko małe litery, cyfry i `_`. Panel sam zamienia `Tomek` na `tomek`, a
`Kuba Bajka` na `kuba_bajka`; ten błąd zobaczysz tylko w starszej wersji albo w `pvc init`.
Wpisz nazwę małymi literami.

### `make ui`: `python3.11 not found`

Starszy Makefile po każdej zmianie `pyproject.toml` odtwarzał środowisko i wymagał
`python3.11`, nawet gdy `.venv` już było (np. na Pythonie 3.12). Poprawione: istniejące `.venv`
jest tylko odświeżane jego własnym Pythonem, a nowe powstaje z `python3.11` albo `python3.12`.
Gdy nie ma żadnego: `brew install python@3.12` (macOS) albo `uv python install 3.11` (Ubuntu).

### Nie widzę zakładek Narzędzia ani Ustawienia

Wszystkie kroki są w pasku u góry; kliknij **⚙ Ustawienia** albo **⚒ Narzędzia** na jego końcu.
W starszej wersji były schowane pod „⋯” po prawej stronie zakładek.

### Co wpisać w „Plik metadanych persony”?

Nazwę dodatkowego pliku z kwestiami zapisanymi jako lista numerowana („1. …”), który leży w tym
samym katalogu co `metadata.csv`, np. `custom_metadata.csv`. Jeśli takiego pliku nie ma, zostaw
pole puste. Plików z samymi godzinami albo datami (np. `ha_metadata.csv`) nie podawaj: filtr i tak
odrzuci każdą linię z cyframi.

### Import odrzucił część klipów

Powód każdego odrzucenia jest w `voices/<głos>/dataset/import_report.csv`. `duration` to klip
krótszy niż ~0,6 s albo za długi, `text:digits` / `text:abbreviation` / `text:foreign_characters`
to tekst, który psułby wymowę. Kilka odrzuceń na tysiąc jest normalne.

### Panel pokazuje „brak karty NVIDIA”

Na Macu albo komputerze bez karty NVIDIA to normalne: import, zdania i ustawienia działają, ale
generowanie, filtr Whisperem i trening wymagają karty. Użyj [serwera z GPU przez
SSH](#komputer-z-gpu-przez-ssh-praca-z-maca-lub-laptopa).

### Ctrl+C nie zatrzymuje `make ui`

W starszych wersjach serwer czekał, aż przeglądarka zamknie połączenie, czyli w nieskończoność.
Zaktualizuj kod; teraz kończy się po 2–4 s. Jeśli stara wersja wisi: zamknij kartę z panelem albo
`pkill -f "pvc.*ui"`. Zadania w tle (trening) to osobne procesy i nie giną razem z panelem.

### Nic się nie dzieje po kliknięciu, nie widać postępu

Długie kroki działają w tle. Postęp (pasek i licznik) i log są w karcie po prawej; przycisk
„Zatrzymaj zadanie” jest aktywny tylko wtedy, gdy coś działa. Po zakończeniu karta pokazuje
„Ostatnie zadanie … zakończone / błąd” i czas trwania. Naraz działa jedno zadanie.

### `Value: kasia is not in the list of choices: []` w terminalu `make ui`

Karta przeglądarki pamiętała wybrany głos z wcześniejszego uruchomienia panelu (np. sprzed restartu
`make ui` albo zmiany folderu danych), a nowa sesja nie miała go na liście. Nic się nie zepsuło: dane
są na dysku. Odśwież stronę (Cmd+R) albo kliknij **↻ Odśwież** przy liście głosów. Nowsze wersje
nie wypisują już tego błędu; głos, którego nie ma na dysku, panel traktuje jak niewybrany.

### „Trwa jeszcze zadanie: …” (dawniej `Inne zadanie jeszcze trwa: … is still running`)

Naraz działa jedno zadanie, a kliknięto następne, zanim poprzednie się skończyło. Na przykład
„Wyślij kod i dane” zaraz po „Sprawdź”. Poczekaj, aż karta **Postęp** pokaże „Ostatnie zadanie …”,
albo zatrzymaj zadanie, i kliknij ponownie. Starsze wersje wypisywały przy tym w terminalu
`make ui` długi `Traceback … JobBusy`; to nie był błąd programu, tylko ten komunikat.

### Sprawdź połączenie: `ssh: connect to host … port 22: Network is unreachable` albo `Operation timed out`

Maszyna z GPU jest wyłączona albo Mac nie ma do niej drogi. Gdy jesteś poza domem, sprawdź VPN
(WireGuard); w domu sprawdź, czy maszyna stoi (przycisk maszyny na górnym pasku, jeśli
skonfigurowałeś Home Assistant). Po włączeniu odczekaj 1–2 minuty i kliknij **Sprawdź** jeszcze raz.

Na górnym pasku ten błąd widać jako „Serwer: sprawdzanie połączenia nie powiodło się (kod 255)”. To
wynik ostatniego zadania, a nie bieżący stan. Gdy maszyna znów odpowie przez SSH (panel pyta ją co
około 10 s), pasek sam zmieni się na „Serwer znów odpowiada przez SSH”. Inne błędy, np. nieudana
instalacja (kod 1), zostają widoczne do następnego zadania.

### Trening staje po pierwszej epoce: `ModelCheckpoint(monitor='val_mos') could not find the monitored key`

W środowisku treningu brakuje `torchaudio`, więc piper nie liczy jakości (`val_mos`), a zapis
checkpointu na nią czeka. W logu wcześniej jest `Could not load MOS predictor 'utmos' (No module named
'torchaudio')`. Kliknij **Przygotuj maszynę** (lista kontrolna pokaże „Środowisko treningu” do
zrobienia) albo na maszynie: `uv pip install --python .venv-train/bin/python torchaudio`. Potem
uruchom trening ponownie - wznowi się od ostatniego checkpointu.

### Odsłuch albo generowanie: `TypeError: 'NoneType' object is not callable` (`perth.PerthImplicitWatermarker()`)

Chatterbox dodaje do każdego klipu niesłyszalny znak wodny z biblioteki `resemble-perth`. Ta
biblioteka importuje `pkg_resources`, którego nie ma już w `setuptools` od wersji 81. Przy błędzie
importu `perth` po cichu ustawia znak wodny na `None`, więc model wywraca się przy starcie. Od tej
wersji zależność `chatterbox` przypina `setuptools<81`, a instalacja sprawdza znak wodny. W starym
środowisku: `.venv/bin/pip install 'setuptools<81'` (na maszynie: kliknij **Przygotuj maszynę**,
gdy nic nie trenuje, albo `uv pip install --python .venv/bin/python 'setuptools<81'`).

### Filtr odrzuca prawie wszystko jako `too_fast_or_cut`, w logu `forcing EOS token, … token_repetition=True`

Klipy urywają się po kilku słowach (np. 2 s zamiast 11 s), a w logu generowania widać
`🚨 Detected 2x repetition of token …` i `forcing EOS token`. Chatterbox 0.1.7 kończy wypowiedź,
gdy dwa jednakowe tokeny mowy wystąpią po sobie w dowolnym miejscu. Niskie, przeciągane głosy
(np. postać z filmu) trafiają na to prawie zawsze, a odsłuch na 12 zdaniach może tego nie pokazać.
Od tej wersji aplikacja sprawdza powtórzenia dopiero po wypowiedzeniu całego tekstu, więc pętle na
końcu nadal są przerywane. Zła partia z wcześniejszej wersji: usuń `raw/` i `dataset/` głosu (albo
przenieś je obok) i wygeneruj klipy ponownie.

### Ponowny trening po zakończonym: `You restored a checkpoint with current_epoch=1273, but you have set Trainer(max_epochs=800)`

Trening bazy (albo głosu) skończył zaplanowane epoki, a potem kliknięto **Trenuj bazę** jeszcze
raz z mniejszą liczbą epok. Wznowienie startuje z najnowszego checkpointu (tu epoka 1273), a
wcześniejsze wersje liczyły epoki od początku pierwszego biegu (0 + 800 = 800). Lightning nie
pozwala zakończyć na epoce niższej niż ta w checkpoincie. Od tej wersji, gdy plan jest już
wykonany, pole **Epoki** oznacza „ile jeszcze”: 800 epok od 1273 do 2073 (w logu `The planned …
epochs are done …; training 800 more`). Przerwany, niedokończony trening nadal wznawia się do
pierwotnego końca.

Uwaga: piper zapisuje checkpoint tylko przy poprawie `val_mel`/`val_mos`, więc ostatnie epoki bez
poprawy (np. 1274–1299) nie mają checkpointu i wznowienie zaczyna od ostatniego zapisanego.
Wybierając wielkość: **medium** kontynuuje ten sam model, **high** zaczyna osobny trening w
`bases/pl-scratch-high`.

### Trening przerwany po wielu epokach: `torch.OutOfMemoryError: CUDA out of memory`

Zabrakło pamięci karty (24 GB). Batch jest dopełniany do najdłuższego klipu, więc zużycie pamięci
skacze od batcha do batcha. Rzadki batch z kilkoma długimi klipami (15–20 s) razem z pofragmentowaną
pamięcią podręczną CUDA przekracza limit, czasem dopiero po setkach epok. Nic nie przepada: kliknij
ponownie **Trenuj bazę** (albo **Trenuj**). Trening wznowi się od najnowszego checkpointu (`last.ckpt`
albo nowszego „najlepszego”), więc powtórzy najwyżej kilka epok. Od tej wersji trening działa z `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`,
co ogranicza fragmentację (po aktualizacji kliknij **Przygotuj maszynę**). Gdy błąd wraca, zmniejsz
batch: `pvc base train --batch-size 24`.

### Sprawdź połączenie: `Permission denied (publickey)` albo `Host key verification failed`

Logowanie do serwera musi działać bez hasła. Raz w terminalu:

```bash
ssh-copy-id uzytkownik@ubuntu.local   # kopiuje Twój klucz na serwer
ssh uzytkownik@ubuntu.local           # pierwsze połączenie: potwierdź klucz hosta (yes)
```

Jeśli używasz innego klucza niż domyślny, wybierz go w polu **Klucz SSH**.

### Sprawdź połączenie: `ffmpeg: MISSING` (albo inne narzędzie)

Pakiety systemowe instalujesz raz sam na serwerze (wymagają sudo). Na końcu wyniku jest gotowe
polecenie, np.:

```bash
ssh uzytkownik@ubuntu.local
sudo apt install ffmpeg
```

Brak `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### Instalacja: `ModuleNotFoundError: No module named 'Cython'` (`~/.local/bin/cythonize`)

Starszy `setup.sh` wywoływał `cythonize` z innego Pythona. Poprawione: kliknij **Wyślij kod i
dane**, potem **Zainstaluj / aktualizuj**. Drugie uruchomienie trwa kilka minut, bo pakiety są już
pobrane.

### Instalacja: `No module named 'skbuild'` albo `cannot import name 'espeakbridge'`

Brakowało kompilacji mostu espeak-ng w środowisku treningu. Poprawione w `setup.sh` jak wyżej:
**Wyślij kod i dane** → **Zainstaluj / aktualizuj**. Na końcu instalacja sama sprawdza, czy oba
moduły piper1-gpl się importują.

### Czerwony status „Serwer: instalacja nie powiodło się (kod 1)”

Status u góry pokazuje **ostatnie** zadanie, więc zostaje czerwony, dopóki nie uruchomisz
następnego. Przeczytaj koniec logu (po prawej albo `<dane>/jobs/*-remote-install.log`), znajdź
komunikat w tym FAQ, a po poprawce uruchom **Wyślij kod i dane** i **Zainstaluj / aktualizuj**
jeszcze raz. Instalację można powtarzać bez szkody.

### Zgubiłem login do panelu na serwerze

Jest w `~/.config/piper-voice-cloner/env` na serwerze (`PVC_UI_AUTH=admin:hasło`). Możesz go
zmienić i zrestartować usługę:

```bash
nano ~/.config/piper-voice-cloner/env
systemctl --user restart piper-voice-cloner
```

### „Maszyna: brak odczytu z HA”

**Objaw**: na górnym pasku czerwony przycisk „Maszyna: brak odczytu z HA”; po najechaniu
podpowiedź z przyczyną, np. `Home Assistant at http://homeassistant.local:8123 cannot be reached:
timed out` albo `Home Assistant 404: Entity not found.`

**Przyczyna**: panel nie dostał od Home Assistant stanu przełącznika maszyny: Home Assistant jest
wyłączony lub restartuje się, adres jest zły, token wygasł (401/403, niżej) albo encja z
ustawień nie istnieje (404, `unavailable`).

**Rozwiązanie**: sprawdź adres w **⚒ Narzędzia → Home Assistant** i kliknij **Zapisz połączenie**
(panel od razu mówi, czy Home Assistant odpowiada). Przy 404 kliknij **↻ Podpowiedzi z HA** i
wybierz istniejący przełącznik i czujnik. Stan odświeża się sam co ~10 s.

### „Maszyna: token HA odrzucony”

**Objaw**: na górnym pasku czerwony przycisk „Maszyna: token HA odrzucony”, a w polu tokenu w
**⚒ Narzędzia → Home Assistant** napis „Home Assistant odrzucił token…”.

**Przyczyna**: Home Assistant odpowiedział 401 (token zły, wygasły albo usunięty). Każda taka
odpowiedź to dla HA nieudane logowanie, a przy włączonym `ip_ban` po kilku z nich HA blokuje adres
(przez VPN może to być adres Jetsona). Dlatego panel **po pierwszym odrzuceniu przestaje pytać HA**:
stan maszyny, podpowiedzi encji i przełączanie maszyny.

**Rozwiązanie**: wklej nowy token długoterminowy (profil → Bezpieczeństwo) i kliknij **Zapisz
połączenie**. Jeśli token jest dobry, a HA np. się restartował, wystarczy samo **Zapisz
połączenie**: panel sprawdzi połączenie jednym zapytaniem.

### `Home Assistant 401: the token is wrong or expired` / `Home Assistant 403: the token belongs to a user who is not an administrator`

**Objaw**: komunikat po **Zapisz połączenie**, **↻ Podpowiedzi z HA** albo po kliknięciu
przycisku maszyny.

**Przyczyna**: 401 – token jest błędny, wygasł albo został usunięty w profilu. 403 – token należy
do użytkownika, który nie jest administratorem (włączanie przełączników wymaga uprawnień).

**Rozwiązanie**: w Home Assistant zaloguj się na konto administratora → profil → Bezpieczeństwo →
Tokeny długoterminowe → Utwórz; wklej nowy token w **⚒ Narzędzia → Home Assistant** i zapisz.

### `this does not look like a Home Assistant long-lived token` / `Home Assistant address: e.g. http://homeassistant.local:8123`

**Przyczyna**: wklejony token ma spacje, cudzysłowy albo jest ucięty (token to długi ciąg liter,
cyfr, `.`, `_`, `-`); adres nie zaczyna się od `http://` lub `https://` albo ma ścieżkę.

**Rozwiązanie**: skopiuj token jeszcze raz w całości; adres wpisz jako `http://<host>:8123` bez
niczego po porcie. Komunikat celowo nie pokazuje wpisanego tokenu.

### `a job is running on the machine: … - stop it first or wait until it ends`

**Objaw**: po kliknięciu „Maszyna: włączona” i potwierdzeniu wyłączenia pojawia się ten błąd i
maszyna zostaje włączona.

**Przyczyna**: na maszynie trwa zadanie panelu (np. `train (kuba)`) albo panel na tym komputerze
właśnie wysyła na nią kod lub instaluje (`remote-push`, `remote-install`). Wyłączenie
przerwałoby je.

**Rozwiązanie**: poczekaj, aż zadanie się skończy, albo zatrzymaj je przyciskiem **Zatrzymaj
zadanie** (w panelu na maszynie, jeśli zadanie działa tam) i spróbuj ponownie. Trening wznowi się
później od najnowszego checkpointu.

### Panel długo się ładuje albo długo pokazuje „Sprawdzam maszynę…”

**Objaw**: po otwarciu panelu status „Sprawdzam maszynę…” / „Maszyna: sprawdzam…” zostaje dłużej
niż kilka sekund.

**Przyczyna**: maszyna z GPU jest wyłączona albo nie odpowiada, a Home Assistant odpowiada wolno
lub wcale. Strona sama nie czeka na nie (pytanie idzie w tle): pierwszy stan pokazuje się po
około 1,5 s (próba połączenia z portem SSH), stan z Home Assistant najpóźniej po kilku sekundach
(limit 5 s na zapytanie). Wolne odpowiedzi `homeassistant.local` na Macu (5 s czekania na
odpowiedź IPv6 przy każdym zapytaniu) panel omija: nazwę sprawdza raz, najpierw IPv4, i pamięta
5 minut.

**Rozwiązanie**: zwykle nic – stan pojawi się sam. Jeśli „sprawdzam” nie znika, zrestartuj panel
i zobacz podpowiedź na statusie (najedź myszą). Gdy podpowiedź mówi `The GPU machine did not
answer over SSH: …`, maszyna jest włączona, ale logowanie SSH nie działa – patrz
[Sprawdź połączenie: Permission denied (publickey)](#sprawdź-połączenie-permission-denied-publickey-albo-host-key-verification-failed).

## Prywatność i prawo

- **Głosy dzieci**: nagrywaj i używaj ich tylko za zgodą rodzica lub opiekuna i trzymaj wszystko
  lokalnie. Domyślny backend działa w całości na Twoim komputerze. ElevenLabs wysyła tekst do
  chmury i narzędzie za każdym razem to zaznacza.
- **Postacie z bajek i filmów**: nagrania są chronione prawem autorskim, a aktor ma prawo do
  głosu i do wykonania. Takie głosy zostaw do prywatnego użytku. Nie publikuj modelu ani próbek
  i nigdy nie używaj ich komercyjnie.
- **Licencje modeli**: Chatterbox to MIT. XTTS-v2 ma licencję CPML, niekomercyjną, więc jego
  wyniki i wytrenowane na nich głosy też traktuj jako niekomercyjne. Chatterbox dodaje do
  wszystkiego niesłyszalny znak wodny (Resemble Perth).
- Jeśli kiedykolwiek publikujesz syntetyczną mowę, oznacz ją jako wygenerowaną przez AI
  (AI Act, art. 50).

To nie jest porada prawna.
