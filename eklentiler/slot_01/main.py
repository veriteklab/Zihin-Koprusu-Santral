"""
Slot 01 – Örnek Eklenti
Bu dosyayı kendi programınızla değiştirin.
Slot klasörüne main.py olarak kaydedin → Zihin Köprüsü otomatik çalıştırır.
"""
print("Merhaba! Bu bir örnek eklentidir.")
print("Kendi kodunuzu buraya yazın.")

# Örnek: bir işlem yap
import os
import datetime

zaman = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
print(f"Çalıştırma zamanı: {zaman}")
print(f"Çalışma dizini: {os.getcwd()}")
