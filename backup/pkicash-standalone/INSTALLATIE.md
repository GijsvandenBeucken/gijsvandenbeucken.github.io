# PKI Cash - Installatie op een nieuwe machine

Dit document beschrijft stap voor stap hoe je PKI Cash installeert op een
nieuwe computer, inclusief LoRa-communicatie via een Heltec Wireless Stick V3.


## Vereisten

- Windows 10/11 (of Linux/macOS)
- Python 3.10 of hoger
- Een Heltec Wireless Stick V3 (ESP32-S3 + SX1262, 868 MHz) met LoRa-antenne
- USB-C kabel


## Stap 1: Python installeren

Download en installeer Python 3.10+ van https://python.org/downloads/

**Belangrijk:** vink bij installatie aan: "Add Python to PATH"

Controleer na installatie:
```
python --version
```


## Stap 2: Project dependencies installeren

Open een terminal (PowerShell of CMD) in de projectmap en voer uit:
```
pip install flask pynacl rns
```

Of via het requirements bestand:
```
pip install -r requirements.txt
```


## Stap 3: Silicon Labs USB driver installeren

De Heltec Wireless Stick V3 gebruikt een CP210x USB-naar-UART chip.

1. Download de driver van: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
2. Installeer de driver
3. Herstart de computer als daarom gevraagd wordt


## Stap 4: RNode firmware flashen op de Heltec stick

De LoRa-stick moet eerst de RNode firmware krijgen zodat Reticulum hem kan
aansturen. **Bevestig ALTIJD eerst de antenne voordat je het apparaat inschakelt!**

1. Sluit de Heltec Wireless Stick V3 aan via USB-C
2. Controleer in Apparaatbeheer (Device Manager) welke COM-poort is toegewezen
   (bijv. COM3, COM4, etc.) onder "Poorten (COM & LPT)"
3. Ga naar de web-based RNode flasher: https://liamcottle.github.io/rnode-flasher/
4. Kies:
   - Product: **Heltec LoRa32 v3**
   - Model: **868 MHz / 915 MHz / 923 MHz**
5. Download de firmware via de link op de pagina: `rnode_firmware_heltec32v3.zip`
6. Selecteer het gedownloade bestand bij "Select firmware (.zip)"
7. Klik **Flash Now** en wacht tot het klaar is
8. Klik **Provision** (stap 3 op de pagina)
9. Klik **Set Firmware Hash** (stap 4 op de pagina)

Controleer of het gelukt is (vervang COM3 door jouw poortnummer):
```
python -m RNS.Utilities.rnodeconf --info COM3
```

Je zou iets moeten zien als:
```
Device info:
    Product            : Heltec LoRa32 v3 850 - 950 MHz
    Modem chip         : SX1262
    Frequency range    : 850.0 MHz - 950.0 MHz
```


## Stap 5: Reticulum configureren voor LoRa

Maak het Reticulum config-bestand aan. Op Windows staat dit in:
```
C:\Users\<jouw_gebruikersnaam>\.reticulum\config
```

Start Reticulum eenmalig zodat het de standaard config aanmaakt:
```
python -c "import RNS; RNS.Reticulum()"
```

Open daarna het bestand `C:\Users\<jouw_gebruikersnaam>\.reticulum\config`
en voeg onderaan, in de `[interfaces]` sectie, het volgende toe
(vervang COM3 door jouw poortnummer):

```
  [[RNode LoRa Interface]]
    type = RNodeInterface
    interface_enabled = True
    port = COM3
    frequency = 868000000
    bandwidth = 125000
    txpower = 7
    spreadingfactor = 8
    codingrate = 5
```

**Let op:** de inspringing (2 spaties voor `[[` en 4 spaties voor de opties)
is belangrijk!


## Stap 6: Testen of LoRa werkt

Voer uit:
```
python -c "import RNS; r = RNS.Reticulum(); import time; time.sleep(3); print('OK')"
```

In de terminal output zou je moeten zien:
```
RNodeInterface[RNode LoRa Interface] is configured and powered up
OK
```


## Stap 7: PKI Cash starten

Je kunt elke rol starten. Kies wat past bij deze machine:

**Wallet starten:**
```
python run.py --role wallet --id mijn_wallet --port 5000
```

**Bank starten:**
```
python run.py --role bank --port 5000
```

**State Engine starten:**
```
python run.py --role engine --port 5000
```

Open daarna je browser op http://localhost:5000

De naam van je actor (bijv. "Wallet Jan" of "Dorpsbank") kun je aanpassen
via Menu > Mijn contactgegevens.


## Stap 8: Verbinding maken met andere machines

1. Klik op het antenne-icoon naast de titel (of via Menu > Netwerk)
2. Klik **Announce op netwerk**
3. Doe hetzelfde op de andere machine(s)
4. Na enkele seconden verschijnen de andere actoren onder "Ontdekte actoren"
5. Klik **Opslaan als contact** om een actor aan je adresboek toe te voegen


## Overzicht typische opzet met 4 machines

| Machine   | Rol          | Commando                                        |
| --------- | ------------ | ----------------------------------------------- |
| Laptop 1  | State Engine | `python run.py --role engine --port 5000`       |
| Laptop 2  | Bank         | `python run.py --role bank --port 5000`         |
| Laptop 3  | Wallet A     | `python run.py --role wallet --id a --port 5000`|
| Laptop 4  | Wallet B     | `python run.py --role wallet --id b --port 5000`|

Elke machine heeft een eigen Heltec stick met RNode firmware en dezelfde
Reticulum LoRa-instellingen (frequentie, bandwidth, spreadingfactor).


## Belangrijke LoRa-instellingen

Alle machines moeten **exact dezelfde** LoRa-parameters gebruiken, anders
kunnen ze elkaar niet horen:

| Parameter       | Waarde    | Toelichting                         |
| --------------- | --------- | ----------------------------------- |
| frequency       | 868000000 | 868 MHz (EU ISM band)               |
| bandwidth       | 125000    | 125 kHz (standaard LoRa)            |
| txpower         | 7         | Zendvermogen in dBm (7 = veilig)    |
| spreadingfactor | 8         | Hogere SF = meer bereik, lagere snelheid |
| codingrate      | 5         | Forward error correction 4/5        |


## Probleemoplossing

**"COM-poort niet gevonden"**
- Controleer of de USB-kabel goed is aangesloten
- Controleer of de CP210x driver is geinstalleerd
- Probeer een andere USB-poort

**"RNodeInterface failed to open"**
- Controleer of het juiste COM-poortnummer in de config staat
- Controleer of geen ander programma de COM-poort gebruikt
- Sluit eventueel de Meshtastic app of andere serieel-software

**Actoren zien elkaar niet**
- Controleer of beide machines dezelfde LoRa-parameters hebben
- Klik op beide machines op "Announce op netwerk"
- Controleer of de antennes zijn aangesloten
- Probeer de machines dichter bij elkaar te zetten

**"Device signature validation failed"**
- Dit is een waarschuwing, geen fout. De web flasher maakt geen signing key
  aan. Voor testgebruik is dit geen probleem.
