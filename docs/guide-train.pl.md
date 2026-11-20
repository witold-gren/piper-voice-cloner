# Wytrenuj głos

Tu prowadzisz głos od pustego folderu do wytrenowanego modelu Piper. Najpierw budujesz **dataset**
(ok. 1500 klipów z tekstem), potem **trenujesz**, słuchasz i wybierasz najlepszy moment. Ścieżka B
dostaje dataset z importu, ścieżka A z klonowania.

Najpierw potrzebny jest głos: [Dodaj nowy głos](guide-new-voice.md).

## 1. Dataset, ścieżka B: import {#import}

![Import](assets/screens/pl/guide-06-import.png){ .shot }

1. Przygotuj folder: `metadata.csv` (`id|tekst`, jedna linia na klip) i `wav/` z klipami. Format
   dokładnie: [Ścieżka B: własne nagrania](path-import.md).
2. Otwórz głos → <span class="ui">Import</span>.
3. W części **<span class="ui">Gdzie są nagrania</span>** wybierz jedną z trzech dróg:
    - <span class="ui">Folder w folderze importu</span> – najpierw skopiuj folder do
      `~/piper-voice-cloner/data/import/` na maszynie; pojawi się na liście;
    - <span class="ui">Albo ścieżka folderu</span> – ścieżka tak, jak widzi ją edytor (`/data/…`);
    - <span class="ui">Albo wyślij ZIP</span> – archiwum z Twojego komputera.
4. Opcjonalnie:
    - <span class="ui">Plik persony (opcjonalnie)</span> – gdy tekst jest zapisany jako numerowana lista;
    - <span class="ui">Sprawdź każdy klip Whisperem (wolne, używa GPU)</span> – odrzuca klipy, w których
      słowa różnią się od tekstu.
5. Kliknij <span class="ui">Importuj</span>.
6. Przeczytaj **<span class="ui">Wynik importu</span>** (tu 3796 z 3801 klipów) i posłuchaj kilku
   <span class="ui">Przyjęte klipy</span> i <span class="ui">Odrzucone klipy</span>. Linie z cyframi,
   skrótami albo symbolami zawsze odpadają – głos nauczyłby się czytać je źle.

Gotowe? Przejdź do [kroku 3: Trening](#train).

## 2. Dataset, ścieżka A: klonowanie {#clone}

Pięć kroków, każdy w drzewie pod głosem. Szczegóły każdego kroku: [Ścieżka A: klonowanie](path-clone.md).

### Nagranie {#recording}

![Nagranie](assets/screens/pl/guide-07-reference.png){ .shot }

1. Otwórz <span class="ui">Nagranie</span> i wyślij 10–60 s czystej mowy (wav, mp3, m4a). Bez muzyki,
   telewizora i innych osób.
2. Zostaw zaznaczone <span class="ui">Policz embedding mówcy (zalecane – filtr porównuje z nim każdy klip)</span>.
3. Kliknij <span class="ui">Przygotuj nagranie</span>.

Głos na obrazku (`optimus_prime`) czyta ElevenLabs, więc edytor pisze, że nagranie nie jest potrzebne –
krok liczy się jako zrobiony.

### Zdania {#sentences}

![Zdania](assets/screens/pl/guide-08-corpus.png){ .shot }

1. Otwórz <span class="ui">Zdania</span>.
2. Wyślij własne pliki tekstowe (jedno zdanie w linii) i/lub zostaw zaznaczone
   <span class="ui">Dodaj wbudowane zdania (proste, przyjazne dzieciom)</span>.
3. **<span class="ui">Ile zdań</span>** – puste pole to cel × 1,3 (filtr część odrzuci).
4. Kliknij <span class="ui">Wybierz zdania</span>. Poniżej widać pierwsze 50 wybranych zdań.

### Odsłuch {#audition}

Sprawdź ustawienia modelu klonującego na kilku zdaniach i wybierz najlepsze na ucho. Krok po kroku:
[Oceń nagrania → Odsłuch](guide-rate.md#audition). Przy ElevenLabs niepotrzebny.

### Generowanie {#generate}

![Generowanie](assets/screens/pl/guide-10-synthesize.png){ .shot }

1. Otwórz <span class="ui">Generowanie</span>.
2. Wybierz **<span class="ui">Model klonujący</span>**: <span class="ui">Chatterbox</span> (lokalnie,
   za darmo), <span class="ui">XTTS-v2</span> albo <span class="ui">ElevenLabs</span> (bez GPU, kosztuje
   kredyty).
3. Przy ElevenLabs: <span class="ui">Wczytaj głosy</span>, wybierz <span class="ui">Głos z konta</span>.
   Opcjonalnie wybierz <span class="ui">Zestaw zdań</span> zaimportowanego głosu i kliknij
   <span class="ui">Użyj zestawu</span>. Edytor pokazuje, ile znaków (kredytów) zostało do przeczytania.
4. **Najpierw próba:** wpisz 20 w <span class="ui">Tylko pierwsze</span> i kliknij
   <span class="ui">Generuj klipy</span>. Posłuchaj kilku klipów.
5. Potem wpisz 0 (wszystkie) i znowu <span class="ui">Generuj klipy</span>. Gotowe klipy zostają, więc
   możesz przerwać i wrócić, kiedy chcesz. Edytor pokazuje tempo ostatniego biegu i szacuje resztę.

### Filtr {#filter}

Sprawdź każdy klip i zostaw dobre. Krok po kroku: [Oceń nagrania → Filtr](guide-rate.md#filter).

Gdy w datasecie jest ok. 1500 klipów, idź dalej.

## 3. Trening {#train}

![Trening](assets/screens/pl/guide-12-train.png){ .shot }

1. Otwórz głos → <span class="ui">Trening</span>.
2. **<span class="ui">Start od</span>** – model, od którego zaczyna się trening:
    - `bazowy-pl` – Twoja polska baza. Najlepszy wybór, gdy już ją masz ([Wytrenuj głos bazowy](guide-base.md));
    - `lessac` – angielski głos Pipera. Działa bez bazy, wolniej uczy się polskiego;
    - `ckpt:…` – dowolny checkpoint (do eksperymentów).
3. **<span class="ui">Epoki</span>** – dla ok. 1500 klipów od `bazowy-pl`: 500–1000. Epoki liczą się od
   checkpointu startowego.
4. Przeczytaj szacunek pod polami: klipy → kroki na epokę → sekundy na epokę → czas całości na RTX 4090
   (np. „15–21 h”).
5. Zaznacz <span class="ui">Wyłącz maszynę po zakończeniu</span>, jeśli trenujesz w nocy. (Bez połączenia
   z Home Assistant edytor napisze, że to pole go wymaga).
6. Kliknij <span class="ui">Trenuj</span>. Głos, który już był trenowany, ma w tym miejscu
   <span class="ui">Wznów trening</span>.

Postęp widać w chipie zadania u góry i po prawej: epoki, pozostały czas, log. Pierwszy bieg przez kilka
minut przygotowuje cache, zanim ruszy epoka 1.

!!! warning "Wznawianie albo od nowa"
    <span class="ui">Wznów trening</span> kontynuuje od ostatniego checkpointu tego głosu – pole
    <span class="ui">Start od</span> nie ma wtedy znaczenia (mówi o tym podpowiedź pod polem). Żółta ramka
    mówi dokładnie, co się stanie. Tu: poprzedni trening doszedł do epoki 2111, a plan kończył się na
    2113, więc zostały tylko 2 epoki. Chcesz więcej? Wpisz więcej epok. Szczegóły:
    [Trening → Wznawianie](training.md#resume).

    Chcesz zacząć głos jeszcze raz, np. od nowej bazy `bazowy-pl`? Wybierz ją w
    <span class="ui">Start od</span> i kliknij <span class="ui">Zacznij od nowa</span>. Edytor zapyta
    o potwierdzenie. Wcześniejsze checkpointy zostają na dysku i na liście checkpointów.

### Od nowa bez utraty poprzedniego treningu {#start-over}

„Zacznij od nowa” niczego nie kasuje ani nie nadpisuje.

1. **Checkpointy zostają.** Nowy trening idzie do nowego folderu (`lightning_logs/version_1`, `_2`…).
   Stare checkpointy (`version_0`) są dalej na liście w Treningu i w Eksporcie.
2. **Wykres i próbki zostają.** Wykres i odsłuch starego treningu trafiają w całości do `train/runs/`
   i nikt ich już nie przycina. Nad wykresem pole <span class="ui">Trening</span> wybiera, który pokazać:
   <span class="ui">Obecny trening</span> albo wcześniejszy, z jego bazą, epokami i najlepszym `val_mos`.
   Działa nawet wtedy, gdy oba treningi mają te same numery epok (dwa starty od tej samej bazy).
3. **Eksport nigdy nie nadpisuje.** Gdy `pl_PL-meski-medium.onnx` już jest, kolejny eksport zapisze
   `pl_PL-meski_2-medium.onnx`, potem `_3`. Podpowiedź pod przyciskiem <span class="ui">Eksportuj</span>
   pokazuje nazwę, którą dostanie następny plik.
4. Wybierz bazę w <span class="ui">Start od</span> i epoki. Liczą się od bazy (lessac zaczyna od epoki
   ok. 2164).
5. Kliknij <span class="ui">Zacznij od nowa</span>. Od tej chwili <span class="ui">Wznów trening</span>
   kontynuuje tylko nowy trening, nawet jeśli nowy zatrzymał się przed pierwszym checkpointem.
6. Stary podobał się bardziej? Wyeksportuj jego checkpoint z listy (`version_0`). Nic nie trzeba trenować
   ponownie.

To samo pokazuje samouczek **Od nowa, z zachowaniem starego treningu** (⚙ → <span class="ui">Samouczki</span>).

<span class="ui">Zatrzymaj</span> (po prawej) przerywa trening w każdej chwili. Późniejsze wznowienie
traci najwyżej kilka epok.

## 4. Wykres {#chart}

Pod ustawieniami jest **wykres treningu**. Odświeża się co 20 s.

- **val_mos** (u góry, niebieski): przewidywana naturalność zdań testowych, 1–5. **Wyżej = lepiej.**
  Ok. 3 to głos zrozumiały, 3,5+ dobry.
- **val_mel** (na dole, pomarańczowy): jak bardzo dźwięk różni się od prawdziwego. **Niżej = lepiej.**
  Na początku szybko spada, potem prawie stoi.
- **train_mel** (przerywany): to samo na zdaniach treningowych.
- Zielone kółka zaznaczają najlepszy `val_mos` i najniższy `val_mel`.

Kliknij wykres, żeby otworzyć go w dużym oknie:

![Powiększony wykres](assets/screens/pl/guide-13-chart.png){ .shot }

- wpisz zakres w <span class="ui">Od epoki</span> i <span class="ui">do</span> albo przeciągnij po
  wykresie, żeby powiększyć te epoki; <span class="ui">Cały trening</span> wraca do całości;
- kliknij, żeby przypiąć jedną epokę i odczytać jej wartości;
- linia na dole podaje najlepsze momenty, np. „Najlepsza jakość: 3,93 (epoka 1828)”.

Jak czytać wykres dokładniej: [Trening](training.md).

## 5. Posłuchaj i wybierz checkpoint {#listen}

Pod wykresem jest **<span class="ui">Odsłuch z treningu</span>**.

1. Wybierz epokę z listy. Na początku słychać szum i „robota”, później coraz wyraźniejszy głos.
2. Epoki oznaczone <span class="ui">💾 checkpoint</span> mają zapisany model – tylko je da się
   wyeksportować.
3. <span class="ui">Próbki (ZIP)</span> zapisuje wszystkie próbki na Twoim komputerze, z tabelą do
   sortowania.
4. **<span class="ui">Checkpointy</span>** niżej mówią, dlaczego każdy plik został zachowany: najlepszy
   `val_mos`, najniższy `val_mel` albo <span class="ui">najnowszy</span>.

**Kiedy przerwać:**

- `val_mos` nie rośnie od ok. 150–200 epok, `val_mel` nie rośnie, a próbki brzmią dobrze;
- `train_mel` dalej spada, a `val_mel` rośnie – to przetrenowanie; weź checkpoint sprzed wzrostu.

!!! tip "Wybieraj uchem"
    Najlepszy `val_mos` nie zawsze brzmi najlepiej. Posłuchaj dwóch, trzech kandydatów na tych samych
    zdaniach i weź ten, który Ci się podoba. Możesz wyeksportować kilka i porównać je w Home Assistant.

## 6. Kilka głosów przez noc: kolejka {#queue}

![Kolejka treningów](assets/screens/pl/guide-22-queue.png){ .shot }

1. Otwórz <span class="ui">Zadania</span> → <span class="ui">Kolejka treningów</span>.
2. W części **<span class="ui">Głosy z datasetem</span>** zaznacz głosy w kolejności treningu.
3. Wybierz <span class="ui">Start od</span> i <span class="ui">Epoki</span> – te same dla każdego głosu.
4. Opcjonalnie zaznacz <span class="ui">Wyłącz maszynę po ostatnim głosie</span>.
5. Kliknij <span class="ui">Uruchom kolejkę</span>.

Błąd jednego głosu nie zatrzymuje następnego. <span class="ui">Zatrzymaj</span> kończy całą kolejkę.
Rano w <span class="ui">Historia zadań</span> jest log każdego głosu.

Dalej: [Eksport do Home Assistant](guide-export.md).
