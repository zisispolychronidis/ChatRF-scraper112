# ChatRF-scraper112
Αυτό είναι ένα απλό Twitter/X scraper που χρησιμοποιεί το selenium για να λάβει τα νέα μηνύματα που ανεβάζει η υπηρεσία του 112 στην Ελλάδα. Είναι φτιαγμένο για χρήση με το AI-enhanced repeater project μου, το [ChatRF](https://github.com/zisispolychronidis/ChatRF).

Για τη πρώτη χρήση, τρέξ' το κανονικά με `python scraper112.py`
Θα ανοίξει το chrome και θα ζητήσει log in για το Twitter, μη φοβάσαι, όλα αποθηκεύονται ΜΟΝΟ τοπικά. Μόλις κάνεις log in πάτα το Enter στο console/terminal.

Μετά, για χρήση στο ChatRF, πρόσθεσε τη γραμμή:
```
from modules.scraper112 import run_loop # 112 Scraper Module
```
στο πάνω μέρος του repeater.py, το code block:
```
def handle_112_alert(msg):
    # msg είναι dict: {"id":..., "date":..., "core_message":...}
    logger.info(f"Νέο μήνυμα 112: {msg['core_message']}")
    
    # Αν ο repeater μιλάει, περίμενε να τελειώσει
    while repeater.talking:
        time.sleep(1)

    # Πες το μήνυμα
    repeater.speak_with_piper(f"Προειδοποίηση από το εκατόν δώδεκα. {msg['core_message']}")

def start_112_scraper():
    run_loop(handle_112_alert, interval=600)
```
ακριβώς πάνω από το def main(), αλλά χωρίς εσοχή για να μη μπει στο HamRepeater class, και τέλος, τις δύο σειρές:
```
# Ξεκινά ο thread του scraper
    scraper_thread = threading.Thread(target=start_112_scraper, daemon=True)
    scraper_thread.start()
```
μέσα στο main() πάνω από το `PTT via Raspberry Pi GPIO`.
