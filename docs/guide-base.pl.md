# Wytrenuj głos bazowy

Baza `bazowy-pl` to polski model Piper wytrenowany **od zera** na jednym mówcy z wieloma nagraniami.
Każdy nowy głos zaczyna potem od niej zamiast od angielskiego `lessac`: szybciej uczy się polskiego
i brzmi naturalniej. Bazę robisz raz. Na końcu tej strony `bazowy-pl` będzie gotowy i pojawi się w polu
<span class="ui">Start od</span> każdego treningu.

**Potrzebujesz:** jednego mówcy i tysięcy czystych klipów z tekstem – np. głosu zaimportowanego
[ścieżką B](guide-train.md#import) (głos `vision` na obrazkach ma 18 395 klipów). Nie masz takiego
zbioru? Trenuj głosy od `lessac` – to też działa.

**Kolejność** jest taka jak w drzewie pod <span class="ui">Model bazowy</span>:
<span class="ui">Przygotowanie danych</span> → <span class="ui">Ocena nagrań</span> →
<span class="ui">Trening</span> → <span class="ui">Porównanie rozmiarów</span> →
<span class="ui">Wybór i eksport</span>.

## 1. Przygotuj dane {#prepare}

![Przygotowanie danych](assets/screens/pl/guide-16-base-prepare.png){ .shot }

1. Otwórz <span class="ui">Model bazowy</span> → <span class="ui">Przygotowanie danych</span>.
2. **<span class="ui">Głos z datasetem</span>** – wybierz głos. Największy jest na górze.
   **<span class="ui">Folder datasetu</span>** wypełni się sam. Możesz tam też wpisać dowolny folder
   LJSpeech (`metadata.csv` + `wav/`).
3. **<span class="ui">Folder audio (zaawansowane, domyślnie wav)</span>** – zostaw puste.
4. Kliknij <span class="ui">Przygotuj dane bazy</span>. Po skończeniu krok pokaże
   <span class="ui">Dane bazy są przygotowane.</span>

## 2. Oceń nagrania {#score}

Krok opcjonalny, ale wart tych kilku minut: pokazuje **sufit**, czyli jak dobra może być baza.
Krok po kroku: [Oceń nagrania → Oceń nagrania bazy](guide-rate.md#score). Na obrazkach mediana wynosi
3,63.

## 3. Wytrenuj bazę {#train}

![Trening bazy](assets/screens/pl/guide-18-base-train.png){ .shot }

1. Otwórz <span class="ui">Model bazowy</span> → <span class="ui">Trening</span>.
2. **<span class="ui">Rozmiar modelu</span>**:
    - **medium** – standard Pipera: szybki trening i szybkie mówienie, także na Raspberry Pi i Jetsonie.
      Zacznij od niego.
    - **high** – 8× większy dekoder: czystszy dźwięk, ale 2–3× wolniejszy trening i mówienie.
3. **<span class="ui">Epoki</span>** – np. 3000. Przerwiesz wcześniej, gdy wykres się wypłaszczy.
4. **<span class="ui">Batch</span>** – zostaw puste: 32 dla medium, 16 dla high (mieści się w 24 GB).
   Zmniejsz dopiero po błędzie braku pamięci.
5. Jeśli chcesz, zaznacz <span class="ui">Wyłącz maszynę po zakończeniu</span>.
6. Kliknij <span class="ui">Trenuj bazę</span>.

Czego się spodziewać:

- **To trwa dni.** Baza od zera potrzebuje setek, a nawet tysięcy epok; na RTX 4090 przy 18 000 klipach
  to dni, nie godziny.
- **`val_mos` szybko rośnie, potem się wypłaszcza.** Na obrazku ma ok. 3,5 po mniej więcej stu epokach
  i potem prawie się nie zmienia: najlepszy był 3,77 w epoce 735, ostatnia epoka (1299) miała 3,57.
- **Sufit trzyma.** Przy medianie 3,63 z oceny nagrań wartości ok. 3,6–3,7 to koniec drogi. Więcej epok
  nie pomoże.
- Pod wykresem jest **<span class="ui">Odsłuch z treningu</span>** – działa jak przy głosie
  ([Wytrenuj głos](guide-train.md#listen)). Przy dwóch rozmiarach przełączasz model nad nim.

!!! warning "Karta jest zajęta"
    Gdy baza się trenuje, żadne inne zadanie na GPU nie ruszy (ocena nagrań tak – liczy się na CPU).
    <span class="ui">Zatrzymaj</span> przerywa trening w każdej chwili, a późniejsze
    <span class="ui">Trenuj bazę</span> wznawia od ostatniego checkpointu.

## 4. Porównaj rozmiary {#compare}

![Porównanie rozmiarów](assets/screens/pl/guide-19-base-compare.png){ .shot }

Trenujesz i medium, i high? <span class="ui">Porównanie rozmiarów</span> stawia je obok siebie:

- `val_mos` i `val_mel` jako średnia z ostatnich 10 epok, do których doszły oba – jedna epoka jest
  zaszumiona;
- <span class="ui">Najlepszy val_mos</span> i <span class="ui">Najniższy val_mel</span> z numerami epok;
- na dole sufit z nagrań (mediana UTMOS).

High opłaca się tylko wtedy, gdy jest wyraźnie lepszy **i** podoba Ci się jego brzmienie. W przeciwnym
razie zostań przy medium – mówi szybciej.

## 5. Wybierz i wyeksportuj {#select}

![Wybór i eksport](assets/screens/pl/guide-20-base-select.png){ .shot }

1. Otwórz <span class="ui">Model bazowy</span> → <span class="ui">Wybór i eksport</span>.
2. **<span class="ui">Checkpoint</span>** – wybierz checkpoint bazy. Weź taki z płaskiego odcinka,
   z dobrym `val_mos`, który do tego dobrze brzmi.
3. Opcjonalnie <span class="ui">Eksportuj jako głos</span> – robi z bazy zwykły głos Piper (pliki pojawią
   się w części **<span class="ui">Wyeksportowane pliki</span>**). Przydaje się, żeby posłuchać bazy
   w Home Assistant ([Eksport do Home Assistant](guide-export.md)).
4. Kliknij <span class="ui">Użyj jako bazowy-pl</span>.

Zielona linia u góry potwierdzi: „bazowy-pl jest gotowy (/data/bases). Nowe głosy zaczynają od niego.”

## 6. Korzystaj z bazy {#use}

- **Nowy głos:** w kroku <span class="ui">Trening</span> wybierz `bazowy-pl` w polu
  <span class="ui">Start od</span>. Przy ok. 1500 klipach wystarczy 500–1000 epok; barwa bazy zwykle
  zmienia się w nowy głos po 50–100 epokach.
- **Kilka głosów:** w <span class="ui">Kolejka treningów</span> wybierz `bazowy-pl` dla wszystkich.
- **Lepsza baza później:** dotrenuj, wybierz inny checkpoint i znowu kliknij
  <span class="ui">Użyj jako bazowy-pl</span>. Głosy wytrenowane wcześniej zostają przy swoich
  checkpointach, a poprzednia baza zostaje obok jako `bases/pl-scratch-1.ckpt` (`-2`…). Wrócisz do niej
  przez `ckpt:<ścieżka>` w <span class="ui">Start od</span>.

Więcej: [Model bazowy](base-model.md).

Dalej: [Eksport do Home Assistant](guide-export.md).
