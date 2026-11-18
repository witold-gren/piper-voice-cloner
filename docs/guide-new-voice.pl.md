# Dodaj nowy głos

Tu tworzysz nowy, pusty głos. Na końcu będzie w drzewie z krokami swojej ścieżki, a Ty będziesz wiedzieć,
gdzie są jego ustawienia. Zanim zaczniesz, ustal, skąd wezmą się nagrania – od tego zależy ścieżka.

## 1. Wybierz ścieżkę {#way}

| Ścieżka | Wybierz ją, gdy | Kroki w drzewie |
|---|---|---|
| **A – klonowanie** | masz 10–60 s nagrania głosu **albo** głos jest na Twoim koncie ElevenLabs | Nagranie, Zdania, Odsłuch, Generowanie, Filtr, Trening, Eksport |
| **B – własne nagrania** | masz ok. 1500 klipów z tekstem (`metadata.csv`) | Import, Trening, Eksport |

Nie wiesz? Tysiące czystych klipów jednego mówcy są lepsze niż każdy klon – jeśli je masz, wybierz
ścieżkę B.

## 2. Otwórz okno „Nowy głos” {#open}

1. W drzewie kliknij **+** obok <span class="ui">Głosy</span>.
2. Okno <span class="ui">Nowy głos</span> pyta: <span class="ui">Jak chcesz go zrobić?</span>

![Nowy głos – ścieżka A, klonowanie](assets/screens/pl/guide-04-new-voice.png){ .shot }

3. Kliknij jedną z dwóch kart:
    - <span class="ui">Klonuję głos</span> – ścieżka A. Edytor dobierze zdania, zrobi ok. 1500–2000
      klipów tym głosem i je sprawdzi.
    - <span class="ui">Mam już nagrania</span> – ścieżka B. Klonowanie i zdania są pomijane: import,
      trening, eksport.

![Nowy głos – ścieżka B, własne nagrania](assets/screens/pl/guide-05-new-voice-import.png){ .shot }

Wybrana karta robi się niebieska.

## 3. Nadaj nazwę {#name}

1. **<span class="ui">Nazwa</span>** – wpisz ją tak, jak ją mówisz, np. `Kuba Bajka`. Edytor zrobi z niej
   bezpieczną nazwę: małe litery, cyfry i `_`, czyli `kuba_bajka`. To nazwa folderu i nazwa w drzewie.
2. **<span class="ui">Nazwa pliku Piper (opcjonalnie)</span>** – nazwa pliku, którą zobaczy Home Assistant,
   np. `pl_PL-kuba_bajka`. Puste pole da `pl_PL-<nazwa>`.
3. Kliknij <span class="ui">Utwórz</span>.

!!! tip "Nazwa, którą rozpoznasz w Home Assistant"
    Nazwę pliku Piper wybierzesz potem z listy głosów w Home Assistant. Czytelna nazwa
    (`pl_PL-kuba_bajka`, a nie `pl_PL-test3`) oszczędza zgadywania.

## 4. Co pojawi się w drzewie {#tree}

Nowy głos jest w drzewie pod <span class="ui">Głosy</span>, rozwinięty, z krokami:

- ścieżka A: <span class="ui">Nagranie</span>, <span class="ui">Zdania</span>,
  <span class="ui">Odsłuch</span>, <span class="ui">Generowanie</span>, <span class="ui">Filtr</span>,
  <span class="ui">Trening</span>, <span class="ui">Eksport</span>;
- ścieżka B: <span class="ui">Import</span>, <span class="ui">Trening</span>, <span class="ui">Eksport</span>;
- na końcu zawsze <span class="ui">Ustawienia głosu</span>.

Kliknięcie nazwy głosu pokazuje <span class="ui">Droga do głosu Piper</span>: każdy krok, jak daleko
jest i który jest następny. Zielony ✓ przy kroku oznacza, że jest zrobiony; liczba obok mówi, ile go jest
(klipów, epok), albo pokazuje nazwę wyeksportowanego pliku.

Przechodź kroki od góry. Jak: [Wytrenuj głos](guide-train.md).

## 5. Ustawienia głosu {#settings}

Każdy głos ma własny plik ustawień (`voice.yaml`). Nie musisz go ruszać – wartości domyślne są dobre.
Otwórz go, gdy chcesz ostrzejszego filtra, innej liczby epok albo mniejszego batcha.

![Ustawienia głosu](assets/screens/pl/guide-15-voice-settings.png){ .shot }

1. Kliknij <span class="ui">Ustawienia głosu</span> pod głosem.
2. Zmień pole na karcie <span class="ui">Formularz</span> (albo popraw tekst na karcie **YAML**).
   Sekcje:
    - <span class="ui">Ogólne</span> – <span class="ui">Ścieżka</span> i
      <span class="ui">Docelowa liczba klipów</span>;
    - <span class="ui">Generowanie</span> – <span class="ui">Generuj ×</span> (ścieżka A);
    - <span class="ui">Filtr</span> – <span class="ui">Maks. CER</span>, <span class="ui">Min. podobieństwo</span>,
      <span class="ui">Odrzuć najgorsze MOS</span>, <span class="ui">Min. s na znak</span>,
      <span class="ui">Maks. s na znak</span> (ścieżka A);
    - <span class="ui">Trening</span> – <span class="ui">Epoki</span>, <span class="ui">Batch</span>,
      <span class="ui">Procesy wczytujące dane</span>, <span class="ui">Część walidacyjna</span>;
    - <span class="ui">Nazwa i plik Piper</span> – <span class="ui">Zmień nazwę</span> głosu albo nazwę
      jego pliku Piper.
3. Każda zmiana od razu trafia do **szkicu**. Napis u góry zmienia się z <span class="ui">Bez zmian</span>
   na <span class="ui">Szkic zapisany</span>. Strzałki obok to <span class="ui">Cofnij</span> i
   <span class="ui">Ponów</span>.
4. <span class="ui">Zapisz</span> zapisuje `voice.yaml`. Najpierw pokazuje zmienione linie i pozwala dodać
   notatkę.
5. <span class="ui">Historia</span> trzyma 30 wcześniejszych wersji. <span class="ui">Przywróć</span>
   wstawia wersję do szkicu, a <span class="ui">Zapisz</span> ją zapisuje.

Co robi każde pole: [Trening → Parametry](training.md#parameters). Szkic dokładniej:
[Ekran](screen.md#draft).

!!! warning "Zmiana nazwy"
    Nie zmienisz nazwy głosu w czasie jego treningu. Wcześniej wyeksportowane pliki zachowują stare
    nazwy – po zmianie nazwy wyeksportuj głos jeszcze raz.

!!! note "Zaimportowany głos zostaje zaimportowany"
    Głos ze ścieżki B zostaje przy swoich nagraniach: nie wygeneruje nowych klipów. Na klony zrób nowy
    głos ścieżką A – może przeczytać dokładnie zdania zaimportowanego głosu (**Zestaw zdań** w kroku
    <span class="ui">Generowanie</span>).

Dalej: [Oceń nagrania](guide-rate.md) albo od razu [Wytrenuj głos](guide-train.md).
