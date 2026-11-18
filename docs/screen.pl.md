# Ekran

Edytor wygląda i działa jak pozostałe studia: Edytor Home Dashboard, Edytor Assist Routera, studio słów
budzących.

![Edytor](assets/screens/pl/01-overview.png){ .shot }

## Pasek górny {#top-bar}

Od lewej:

1. **☰ menu:** instrukcja, kto jest zalogowany, jak zmienić hasło, <span class="ui">Wyloguj</span>.
   Obok ikona i nazwa.
2. **Chip zadania:** co trwa, procent i pozostały czas. Kliknięcie otwiera <span class="ui">Bieżące
   zadanie</span>.
3. **Chip maszyny:** obciążenie karty, temperatura, pamięć i moc z gniazdka. ⏻ wyłącza maszynę (gdy
   Home Assistant jest połączony i nic nie trwa).
4. **Odliczanie** po zadaniu z zaznaczonym wyłączeniem: „Wyłączenie za 1:45” z <span class="ui">Anuluj</span>.
   Gdy wyłączenie się nie uda, w tym miejscu pojawi się czerwona pigułka z powodem.
5. **Motyw**, **?** (ta instrukcja; tylko ten „?” otwiera instrukcję, „?” przy krokach i kartach pokazują
   okienko z opisem) i **⚙**: okienko pod ikoną z motywem i językiem, które zmieniają się od razu. Zamykają je Esc,
   kliknięcie obok albo ponowne ⚙, a <span class="ui">Cały wygląd i język</span> otwiera pełny widok.

![Menu i odliczanie](assets/screens/pl/14-menu.png){ .shot }

![Odliczanie przed wyłączeniem](assets/screens/pl/15-countdown.png){ .shot }

## Drzewo {#tree}

- <span class="ui">Głosy</span>: każdy głos ma kroki swojej ścieżki. ✓ oznacza krok zrobiony, a liczba
  obok mówi, ile go jest (np. klipów). Na końcu jest <span class="ui">Ustawienia głosu</span>. Przycisk „+”
  tworzy nowy głos i najpierw pyta o ścieżkę.
- <span class="ui">Model bazowy</span>: wszystko o bazie `bazowy-pl`.
- <span class="ui">Zadania</span>: <span class="ui">Bieżące zadanie</span>,
  <span class="ui">Kolejka treningów</span> i <span class="ui">Historia zadań</span>.
- <span class="ui">Ustawienia</span>: ElevenLabs, Home Assistant i maszyna, wygląd i język.

Wyszukiwarka filtruje drzewo, a zwinięcia i szerokości kolumn zapamiętuje przeglądarka. Lewą i prawą kolumnę
zwiniesz przyciskiem ‹ / › na ich górze albo skrótem Ctrl/⌘+B (lewa) i Ctrl/⌘+Alt+B (prawa). Zostaje wtedy
wąski pasek z przyciskiem rozwinięcia, a środek robi się szerszy. W wąskim oknie (poniżej 900 px) prawa
kolumna jest zwinięta od startu. Adres strony
(`#voice/kasia/train`) prowadzi prosto do kroku, więc można go wysłać albo dodać do zakładek.

## Środek i prawa kolumna {#columns}

**Środek** to wybrany krok: **?** z krótkim opisem w okienku (i linkiem do właściwego rozdziału),
ustawienia, przycisk uruchomienia i wyniki.

**Prawa kolumna** to zadanie na żywo: etap, postęp, karta graficzna, kolejka, log
(<span class="ui">Powiększ</span>, <span class="ui">Kopiuj</span>), <span class="ui">Zatrzymaj</span> i
<span class="ui">Wyłącz maszynę po zakończeniu</span>.

## Ustawienia głosu: szkic, zapis, historia {#draft}

Każda zmiana w <span class="ui">Ustawienia głosu</span> trafia od razu do **szkicu na maszynie**. Szkic
przetrwa zamknięcie przeglądarki, a `voice.yaml` zmienia się dopiero po <span class="ui">Zapisz</span>.

- Formularz albo YAML. Zmiana pola zmienia dokładnie jedną linię pliku, a komentarze i układ zostają.
- <span class="ui">Cofnij</span> i <span class="ui">Ponów</span> (Ctrl/⌘+Z, Shift+Ctrl/⌘+Z).
  Pisanie w jednym polu przez 1,5 s to jeden krok.
- <span class="ui">Zapisz</span> (Ctrl/⌘+S) pokazuje zmienione linie i pole na notatkę.
- Gdy ktoś zmienił plik w międzyczasie, edytor zapyta o <span class="ui">Zapisz mimo to</span>.
- <span class="ui">Historia</span> trzyma 30 poprzednich wersji z notatkami.
  <span class="ui">Przywróć</span> wstawia wersję do szkicu.

![Zapis z listą zmian](assets/screens/pl/16-save.png){ .shot }
