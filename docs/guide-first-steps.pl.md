# Pierwsze kroki

Ten przewodnik zaczyna się po [instalacji](installation.md). Na końcu będziesz umieć się zalogować,
poznasz każdą część ekranu, a edytor będzie połączony z Home Assistant (i z ElevenLabs, jeśli go używasz).

Kolejne strony prowadzą przez jedno zadanie naraz:

1. **Pierwsze kroki** – ta strona.
2. [Dodaj nowy głos](guide-new-voice.md)
3. [Oceń nagrania](guide-rate.md)
4. [Wytrenuj głos](guide-train.md)
5. [Wytrenuj głos bazowy](guide-base.md)
6. [Eksport do Home Assistant](guide-export.md)
7. [Przewodnik i samouczki w edytorze](guide-tour.md)

## 1. Zaloguj się {#login}

1. Otwórz `http://<maszyna>:7860` w przeglądarce na dowolnym komputerze, telefonie albo tablecie w domu.
2. Wpisz użytkownika i hasło. Nie znasz ich? Uruchom `make login` na Macu (albo
   `docker/install-ubuntu.sh --show-login` na maszynie).
3. Sesja trwa 30 dni, więc nie logujesz się codziennie.

## 2. Ekran w skrócie {#tour}

![Edytor z otwartym głosem jan](assets/screens/pl/guide-01-start.png){ .shot }

Ekran ma pasek górny i trzy kolumny.

**Pasek górny**, od lewej:

- **☰** otwiera menu (więcej niżej).
- **Edytor głosów** i nazwa otwartego głosu (tu `jan`).
- **Chip zadania** pojawia się, gdy coś działa: co trwa, procent i pozostały czas. Kliknięcie otwiera
  <span class="ui">Bieżące zadanie</span>.
- **Chip maszyny** (zielony, w prawym górnym rogu): obciążenie karty, temperatura, pamięć karty i moc
  pobierana z gniazdka (`0% · 39° · 0 GB · 86 W`). Czerwony ⏻ wyłącza maszynę – tylko z połączeniem
  z Home Assistant i gdy nic nie działa.
- **Słoneczko** przełącza motyw, **?** otwiera tę instrukcję, **⚙** otwiera okienko z wyglądem.

**Lewa kolumna** to drzewo:

- <span class="ui">Głosy</span> – każdy głos z krokami swojej ścieżki. Ikona mówi, jaka to ścieżka:
  folder z nutą to głos z własnych nagrań, mówiąca głowa to głos klonowany. Liczba po prawej (`3/3`,
  `6/6`) mówi, ile kroków jest zrobionych. Krok opcjonalny (<span class="ui">Odsłuch</span>) liczy się
  dopiero, gdy go zrobisz. **+** tworzy nowy głos.
- <span class="ui">Model bazowy</span> – pięć kroków polskiej bazy `bazowy-pl`.
- <span class="ui">Zadania</span> – <span class="ui">Bieżące zadanie</span>,
  <span class="ui">Kolejka treningów</span>, <span class="ui">Historia zadań</span>.
- <span class="ui">Ustawienia</span> – <span class="ui">ElevenLabs</span>,
  <span class="ui">Home Assistant i maszyna</span>, <span class="ui">Wygląd i język</span>.

Nad drzewem jest wyszukiwarka (<span class="ui">Szukaj głosu i kroku…</span>) oraz
<span class="ui">Zwiń</span> i <span class="ui">Rozwiń</span> (zwijają i rozwijają wszystko). Strzałka **‹** chowa całą
kolumnę.

**Środek** pokazuje to, co kliknięto. Kliknięcie głosu pokazuje
<span class="ui">Droga do głosu Piper</span>: wszystkie jego kroki z liczbami i słowem
<span class="ui">gotowe</span>. Kliknięcie kroku otwiera ten krok. Niebieski **?** w rogu każdego kroku
objaśnia go w małym okienku.

**Prawa kolumna** pokazuje zadanie:

- karta zadania – to, które działa teraz, albo ostatnie (tu: <span class="ui">Ostatnie zadanie</span>,
  Eksport · jan, <span class="ui">Zakończone</span>, <span class="ui">Trwało</span> 00:00:08);
- karta GPU – cztery kółka: <span class="ui">Obciążenie</span>, <span class="ui">Pamięć</span>,
  <span class="ui">Temperatura</span>, <span class="ui">Moc</span>, oraz link
  <span class="ui">TensorBoard</span> (szczegółowe wykresy treningu);
- log – ostatnie linie zadania. <span class="ui">Powiększ</span> otwiera go w dużym oknie,
  <span class="ui">Kopiuj</span> kopiuje (przydaje się, gdy prosisz kogoś o pomoc).

Gdy zadanie trwa, karta pokazuje też postęp, pozostały czas, <span class="ui">Zatrzymaj</span> i pole
<span class="ui">Wyłącz maszynę po zakończeniu</span>.

Więcej szczegółów: [Ekran](screen.md).

## 3. Menu ☰ {#menu}

![Menu](assets/screens/pl/guide-03-menu.png){ .shot }

- <span class="ui">Instrukcja</span> otwiera tę instrukcję.
- **Zalogowany: admin** – i gdzie jest hasło (`docker/config/env` na maszynie). Żeby je zmienić,
  popraw ten plik i uruchom edytor ponownie.
- <span class="ui">Wyloguj</span> wylogowuje w tej przeglądarce.
- Na dole: wersja edytora.

## 4. Wygląd i język ⚙ {#look}

![Okienko wyglądu i języka](assets/screens/pl/guide-02-gear.png){ .shot }

1. Kliknij **⚙** w prawym górnym rogu.
2. **Motyw:** <span class="ui">Jak system</span>, <span class="ui">Jasny</span> albo <span class="ui">Ciemny</span>.
3. **Język:** **Polski** albo **English**.
4. Zmiana działa od razu. Esc albo kliknięcie obok zamyka okienko.

Przeglądarka zapamięta wybór. <span class="ui">Cały wygląd i język</span> otwiera te same ustawienia na
całej stronie.

## 5. Zadania: co działa i co działało {#jobs}

Naraz działa tylko jedno zadanie na GPU. Zadania działają dalej po zamknięciu przeglądarki.

![Bieżące zadanie](assets/screens/pl/guide-21-job.png){ .shot }

<span class="ui">Bieżące zadanie</span> pokazuje kartę zadania, kartę GPU i log na środku, szeroko.
Przydaje się do czytania długiego logu w czasie treningu.

![Historia zadań](assets/screens/pl/guide-23-history.png){ .shot }

<span class="ui">Historia zadań</span> to lista wszystkich zadań: kiedy ruszyło, co to było, dla jakiego
głosu (przy kolejce: dla jakich głosów), z jakim wynikiem i jak długo trwało. Nieudane zadanie widać od
razu: ma czerwony wynik „Błąd” z kodem. <span class="ui">Log</span> otwiera pod tabelą cały log – przydatne rano po nocnym treningu.

## 6. Połącz Home Assistant (raz) {#home-assistant}

Po połączeniu edytor pokazuje moc z gniazdka i potrafi wyłączyć maszynę po treningu. Najpierw potrzebny
jest przykładowy pakiet w Home Assistant (zob. [Instalacja](installation.md#home-assistant)).

![Home Assistant i maszyna](assets/screens/pl/guide-24-settings-ha.png){ .shot }

1. Otwórz <span class="ui">Ustawienia</span> → <span class="ui">Home Assistant i maszyna</span>.
2. **<span class="ui">Adres Home Assistant</span>**, np. `http://homeassistant.local:8123`.
3. **<span class="ui">Token długoterminowy</span>**: w Home Assistant otwórz swój profil →
   **Bezpieczeństwo** → **Tokeny długoterminowe**, utwórz token użytkownika z prawami administratora
   i wklej go tutaj.
4. <span class="ui">Zapisz połączenie</span>. Zapisany token widać jako „zapisany (wpisz, aby zmienić)”.
   <span class="ui">Usuń</span> kasuje adres i token.
5. W części **<span class="ui">Zasilanie maszyny</span>** kliknij
   <span class="ui">Podpowiedz z Home Assistant</span> i wybierz:
    - <span class="ui">Przełącznik maszyny</span> – przełącznik z przykładowego pakietu;
    - <span class="ui">Moc gniazdka (W)</span> – czujnik mocy gniazdka;
    - <span class="ui">Wyłączona poniżej (W)</span> – poniżej tej mocy maszyna uchodzi za wyłączoną (np. 5).
6. <span class="ui">Zapisz</span>.

Karta **<span class="ui">Maszyna</span>** pokazuje wtedy stan (`Maszyna: włączona · 67 W`) i przycisk
<span class="ui">Wyłącz maszynę</span>.

!!! warning "Wyłączenie maszyny wyłącza też edytor"
    <span class="ui">Wyłącz maszynę</span> zamyka system, a potem wyłącza gniazdko. Edytor przestaje
    odpowiadać, dopóki nie włączysz maszyny z Home Assistant. Gdy zadanie z zaznaczonym wyłączeniem się
    skończy, pasek górny najpierw odlicza dwie minuty („Wyłączenie za 1:45”) – kliknij tam
    <span class="ui">Anuluj</span>, jeśli maszyna jest jeszcze potrzebna. Po
    <span class="ui">Zatrzymaj</span> maszyna nigdy się nie wyłącza.

## 7. Zapisz klucz ElevenLabs (tylko dla ElevenLabs) {#elevenlabs}

To potrzebne tylko wtedy, gdy zdania ma czytać głos z ElevenLabs (ścieżka A).

![ElevenLabs](assets/screens/pl/guide-25-settings-elevenlabs.png){ .shot }

1. Na elevenlabs.io otwórz **Profil → API keys** i utwórz klucz.
2. W edytorze: <span class="ui">Ustawienia</span> → <span class="ui">ElevenLabs</span>.
3. Wklej klucz (`sk_…`) i kliknij <span class="ui">Zapisz</span>.

Klucz zapisuje się raz na maszynie i nie jest już nigdy pokazywany. Działa dla wszystkich głosów.

Dalej: [Dodaj nowy głos](guide-new-voice.md).
