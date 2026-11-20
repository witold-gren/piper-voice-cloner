# FAQ i rozwiązywanie problemów

Każdy błąd, który się pojawił, ma tu wpis: dokładny komunikat, przyczynę i rozwiązanie. Log zadania
zobaczysz po prawej (<span class="ui">Powiększ</span>, <span class="ui">Kopiuj</span>), a starsze logi w
<span class="ui">Historia zadań</span>.

## Docker i maszyna

### `the editor does not answer`, a TensorBoard pokazuje `demo.py: error: unrecognized arguments`

Wersja 0.2.0 budowała na maszynie obraz demo. Zaktualizuj do 0.2.1 i uruchom `make deploy`.

### `NVIDIA driver 535.… is too old: the image needs 580 or newer`

torch w obrazie jest zbudowany dla CUDA 13.0, a ta wymaga sterownika 580. Zainstaluj go
(`sudo apt install -y nvidia-driver-580`), uruchom maszynę ponownie i powtórz `make install`. Kilka
sterowników w `dpkg -l` nie przeszkadza: liczy się wersja, którą pokazuje `nvidia-smi`.

### `nvidia-smi does not see the card` / `no nvidia-smi: install the NVIDIA driver first`

Sterownik nie jest zainstalowany albo nie jest załadowany (często zaraz po instalacji, przed
restartem). Zainstaluj go przez `sudo ubuntu-drivers install`, uruchom maszynę ponownie i przed
`make install` sprawdź `nvidia-smi`.

### `Docker is missing`, `docker compose is missing`, `no access to Docker`

Instalator niczego nie instaluje na samej maszynie, tylko wypisuje polecenie do wykonania:
`sudo apt install -y docker.io docker-compose-v2` albo `sudo usermod -aG docker <użytkownik>` (potem
wyloguj się i zaloguj ponownie). Wszystkie biblioteki potrzebne edytorowi instalują się w obrazie.

### `Weights only load failed` … `Unsupported global: GLOBAL pathlib.PosixPath`

Trening zatrzymał się od razu. Lightning 2.6 otwiera checkpointy w trybie bezpiecznym, a starsze
checkpointy (baza lessac pobrana z Hugging Face) mają w środku ścieżki folderów. Od wersji 0.2.1
edytor raz zmienia taki checkpoint przed treningiem. W 0.2.0: zaktualizuj i trenuj ponownie, nic więcej
nie trzeba robić.

### `could not select device driver "nvidia" with capabilities: [[gpu]]`

Docker nie widzi karty, bo brakuje `nvidia-container-toolkit` albo nie skonfigurowano go dla Dockera.
Wykonaj krok 1 z [instalacji](installation.md) (`nvidia-ctk runtime configure`, restart Dockera).
Sprawdzenie: `docker run --rm --gpus all ubuntu nvidia-smi`.

### Karta GPU pokazuje „brak karty NVIDIA”

Kontener działa bez GPU, na przykład po ręcznym `docker run` bez `--gpus`. Uruchamiaj edytor przez
`make deploy` albo `make docker-up`, bo compose sam rezerwuje kartę.

### `env file …/docker/config/env not found`

Edytor nie jest jeszcze zainstalowany: brakuje pliku z hasłem. Uruchom `make install` z Maca albo
`docker/install-ubuntu.sh` na maszynie. Potem już `make deploy`.

### Zapomniałem hasła do edytora

`make login` na Macu albo `docker/install-ubuntu.sh --show-login` na maszynie. Hasło jest w
`docker/config/env` (`PVC_UI_AUTH=admin:…`). Nowe hasło wpisz tam i uruchom
`docker compose -f docker/compose.yaml restart`. Zmiana hasła wylogowuje wszystkie przeglądarki.

### „Za dużo złych haseł: odczekaj minutę.”

Po 5 złych hasłach z jednego adresu edytor przez minutę nie przyjmuje kolejnych prób. Odczekaj chwilę.
Hasło pokaże `make login`.

### `Permission denied` przy zapisie w `/data`

Folder danych należy do innego użytkownika niż kontener. W `docker/.env` ustaw `UID` i `GID` na swoje
(`id -u`, `id -g`) albo popraw właściciela: `sudo chown -R $USER: <folder danych>`. Potem uruchom
`make deploy`.

### Zadanie ma stan „Przerwane (edytor został uruchomiony ponownie)”

Kontener zrestartował się w trakcie zadania (aktualizacja, wyłączenie maszyny, awaria), więc proces
zadania zniknął. Uruchom zadanie jeszcze raz. Trening wznowi się od ostatniego checkpointu, a
generowanie pominie gotowe klipy.

### Edytor nie odpowiada po włączeniu maszyny

Docker uruchamia edytor kilkadziesiąt sekund po starcie systemu. Gdy nadal nie działa:
`make status` i `make logs`. Sprawdź też, czy Docker startuje z systemem
(`sudo systemctl enable docker`).

## Trening

### Wznowienie trenuje tylko kilka epok

Plan poprzedniego treningu nie był skończony, a wznowienie tylko go dokańcza (zob.
[Wznawianie](training.md#resume)). Edytor pisze to nad przyciskiem. Wpisz więcej epok.

### `torch.OutOfMemoryError: CUDA out of memory`

Zabrakło pamięci karty. Rzadki batch z kilkoma długimi klipami (15–20 s) potrafi przekroczyć 24 GB, czasem
dopiero po setkach epok. Nic nie przepada: uruchom trening ponownie, wznowi się od ostatniego checkpointu.
Gdy błąd wraca, zmniejsz **Batch** w <span class="ui">Ustawienia głosu</span> (np. 24) albo przy bazie.
Upewnij się też, że kartą nie dzieli się nic innego, np. Ollama.

### `You restored a checkpoint with current_epoch=…, but you have set Trainer(max_epochs=…)`

Dawne wersje liczyły epoki od początku pierwszego biegu. Edytor liczy je od ostatniego checkpointu, gdy plan
był skończony (w logu `The planned … epochs are done …; training … more`). Uruchom trening ponownie.

### `ModelCheckpoint(monitor='val_mos') could not find the monitored key`

W środowisku treningu brakuje `torchaudio`. W obrazie Dockera jest instalowany, więc ten błąd oznacza stary
obraz. Zaktualizuj edytor (`git pull && make docker-up`).

### Gotowy głos szumi albo „rwie”

To problem danych, nie treningu. Zob. [Dane decydują o wszystkim](training.md#data): szum w pauzach
nagrań, ucięte klipy, różne pomieszczenia.

## Klonowanie i ElevenLabs

### Filtr odrzuca prawie wszystko jako `too_fast_or_cut`

Chatterbox urywał klipy po kilku słowach (w logu `forcing EOS token`). Edytor sprawdza powtórzenia dopiero
po wypowiedzeniu całego tekstu, więc to już nie powinno się zdarzać. Klipy wygenerowane starszą wersją
usuń (folder `raw/` głosu) i wygeneruj ponownie.

### `TypeError: 'NoneType' object is not callable` (`perth.PerthImplicitWatermarker()`)

Znak wodny Chatterbox nie załadował się, bo nowe `setuptools` nie ma już `pkg_resources`. Obraz przypina
`setuptools<81` i sprawdza to przy budowie. Ten błąd oznacza stary obraz, więc zaktualizuj edytor.

### `Stopped: HTTP 401: …` (`quota_exceeded`, `invalid_api_key`)

Zły klucz ElevenLabs albo brak kredytów: treść odpowiedzi mówi, które z nich. Zapisz nowy klucz w
<span class="ui">Ustawienia</span> → <span class="ui">ElevenLabs</span> albo dokup kredyty i uruchom
generowanie ponownie. Gotowe klipy zostają.

### `HTTP 401: … missing_permissions` przy <span class="ui">Wczytaj głosy</span>

Klucz z ograniczeniami nie ma dostępu do głosów. W ElevenLabs włącz to uprawnienie dla klucza albo utwórz
nowy. Brak samego `user_read` nie przeszkadza: głosy się wczytają, tylko bez kredytów.

### `Stopped: raw/ holds clips of another voice (…)`

W `raw/` są klipy innego modelu albo innego głosu ElevenLabs. Utwórz nowy głos albo przenieś `raw/` poza
folder głosu.

### `raw/ already holds … clips of other sentences` przy <span class="ui">Użyj zestawu</span>

Głos ma już klipy innych zdań, a filtr użyłby ich razem z nowymi. Utwórz nowy głos.

### `'…' is an imported voice: create a new voice to generate clips`

Zaimportowany głos to gotowy zestaw nagrań, który nie generuje nowych klipów. Utwórz nowy głos
(ścieżka A). Zdania zaimportowanego głosu możesz w nim użyć jako **Zestawu zdań**.

## Home Assistant

### „Home Assistant odrzucił token – zapisz nowy”

Home Assistant odpowiedział 401 (token zły, wygasły albo usunięty). Każda taka odpowiedź to dla HA nieudane
logowanie, a przy włączonym `ip_ban` po kilku z nich HA blokuje adres. Dlatego edytor po pierwszym
odrzuceniu przestaje pytać HA. Wklej nowy token i kliknij <span class="ui">Zapisz połączenie</span>.

### `Home Assistant 403: the token belongs to a user who is not an administrator`

Przełączanie maszyny wymaga konta administratora. Utwórz token na koncie administratora.

### `this does not look like a Home Assistant long-lived token`

Wklejony token ma spacje, cudzysłowy albo jest ucięty. Skopiuj go jeszcze raz w całości. Adres wpisz jako
`http://<host>:8123`, bez niczego po porcie.

### „Trwa zadanie (…): najpierw je zatrzymaj albo zaznacz „Wyłącz maszynę po zakończeniu””

<span class="ui">Wyłącz maszynę</span> nie przerywa trwającego zadania. Zatrzymaj je albo zaznacz
<span class="ui">Wyłącz maszynę po zakończeniu</span> na karcie zadania.

### Maszyna nie wyłączyła się po treningu

W logu zadania jest `Powering off failed: …`. Najczęściej brakuje połączenia z HA albo przełącznika
w <span class="ui">Home Assistant i maszyna</span>, albo HA odrzucił token. Po <span class="ui">Zatrzymaj</span>
maszyna celowo się nie wyłącza.

## Przewodnik i samouczki {#tour}

### Przewodnik po edytorze się nie pokazuje

Startuje sam tylko za pierwszym razem w danej przeglądarce. Po „Pomiń”, Esc albo „Gotowe” edytor zapamiętuje,
że został obejrzany. W oknie prywatnym przeglądarka nie pozwala niczego zapamiętać, więc edytor uznaje
przewodnik za obejrzany, żeby nie wracał za każdym razem. Otworzysz go zawsze z ⚙ →
<span class="ui">Przewodnik po edytorze</span>.

### Samouczek nie idzie dalej

Dymek z napisem „Kliknij to, co jest w ramce, aby przejść dalej” czeka na kliknięcie przycisku w ramce. Kliknij
go albo <span class="ui">Dalej</span> w dymku. Reszta ekranu jest wtedy zablokowana, a Esc kończy samouczek.
Przycisk na liście samouczków jest wyszarzony, gdy brakuje głosu danego rodzaju. Najpierw utwórz taki głos.

## make na Macu {#make}

### `Docker not found: install and start Docker Desktop` / `Docker is not running: start Docker Desktop`

`make demo`, `make docs`, `make docs-serve` i `make docs-build` działają w Dockerze. Zainstaluj Docker
Desktop, uruchom go (wieloryb na pasku menu przestaje się ruszać) i powtórz polecenie. `make doctor`
pokazuje, co jest, a czego brakuje.

### `uv not found | brak uv: curl -LsSf https://astral.sh/uv/install.sh | sh`

uv jest potrzebny tylko do poleceń programisty (`make setup`, `test`, `test-browser`, `lint`,
`screenshots`). Zainstaluj go poleceniem z komunikatu. uv sam pobiera Pythona (`PYTHON_VERSION` w
`Makefile`), brew nie jest potrzebny. Stara `.venv` z inną wersją Pythona powstaje od nowa.

### `make doctor`: `missing | brak  ssh użytkownik@host`

Maszyna jest wyłączona albo nie ma na niej Twojego klucza SSH. Włącz maszynę w Home Assistant albo raz
wykonaj `ssh-copy-id użytkownik@host`. Demo i instrukcja maszyny nie potrzebują.
