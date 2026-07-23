# 🛰️ Django Network Monitoring & Inventory

## 📌 Deskripsi
Aplikasi berbasis **Django** untuk:
- Login & autentikasi user.
- Dashboard monitoring jaringan.
- Network inventory hasil scan (IP, device, OS, brand, gateway, router, DNS).
- Peta jaringan interaktif (network mapping) seperti IP scanner.

## ⚙️ Fitur Utama
- **Autentikasi & Role Management**
  - Login dengan `django.contrib.auth`.
  - Role: Admin, Operator.
- **Network Scan**
  - Integrasi dengan `python-nmap` atau `scapy`.
  - Simpan hasil ke tabel `scan`.
- **Inventory Management**
  - Tabel `scan(id, ip, device, os, brand, gateway, router, dns, scanned_at)`.
  - CRUD untuk data hasil scan.
- **Dashboard Monitoring**
  - Tabel hasil scan.
  - Statistik perangkat & OS.
- **Network Mapping**
  - Visualisasi topologi jaringan.
  - Node: IP/device.
  - Edge: hubungan gateway, router, DNS.
  - Frontend: D3.js / vis.js.

## 🛠️ Instalasi
```bash
git clone <repo>
cd django-network-monitoring
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

project/
├── apps/
│   ├── scan/        # Model & view untuk hasil scan
│   ├── dashboard/   # Dashboard & visualisasi
├── templates/
│   ├── dashboard.html
│   ├── network_map.html
└── manage.py

🚀 Workflow
1. User login → masuk dashboard.
2. Jalankan scan jaringan → hasil tersimpan di tabel scan.
3. Dashboard menampilkan inventory & statistik.
4. Peta jaringan divisualisasikan secara interaktif.
🔮 Fitur Tambahan
• Alert & Notifikasi
	◦ Kirim email/telegram jika ada device baru atau perubahan OS.
• Scheduled Scan
	◦ Gunakan Celery atau django-crontab untuk scan otomatis.
• Export Data
	◦ Export hasil scan ke CSV/Excel.
• Integrasi SNMP
	◦ Ambil informasi device lebih detail (CPU, memory, interface).
• User Activity Log
	◦ Audit trail untuk login & aksi user.
• API Endpoint
	◦ Django Rest Framework untuk integrasi dengan aplikasi lain.
• Security Check
	◦ Tambahkan port scan & vulnerability check dasar.
• Multi-subnet Support
	◦ Scan lebih dari satu range IP sekaligus.
• Historical Trends
	◦ Grafik perubahan jumlah device/OS dari waktu ke waktu.


    Theme Hacker
• Warna dominan: hitam, abu-abu gelap, neon hijau (#00ff00), merah (#ff0033), atau biru elektrik.
• Font: monospace (misalnya Courier New, Fira Code, Hack).
• Background: efek grid, matrix-style, atau animasi ASCII.
• UI style: minimalis, mirip terminal, dengan highlight neon.
• Chart/Graph: gunakan tema dark dengan warna neon untuk node & edge.

🔮 Fitur Tambahan
• Alert & Notifikasi → email/telegram jika ada device baru atau perubahan OS.
• Scheduled Scan → gunakan Celery atau django-crontab untuk scan otomatis.
• Export Data → hasil scan ke CSV/Excel.
• Integrasi SNMP → ambil informasi device lebih detail (CPU, memory, interface).
• User Activity Log → audit trail login & aksi user.
• API Endpoint → Django Rest Framework untuk integrasi aplikasi lain.
• Security Check → port scan & vulnerability check dasar.
• Multi-subnet Support → scan lebih dari satu range IP.
• Historical Trends → grafik perubahan jumlah device/OS dari waktu ke waktu.
---
🎨 Theme Hacker
Untuk nuansa hacker dashboard:
• Warna dominan: hitam, abu-abu gelap, neon hijau (#00ff00), merah (#ff0033), biru elektrik.
• Font: monospace (Courier New, Fira Code, Hack).
• Background: efek grid, matrix-style, atau animasi ASCII.
• UI style: minimalis, mirip terminal, dengan highlight neon.
• Chart/Graph: tema dark dengan warna neon untuk node & edge.

# settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'network',          # ganti dengan nama database yang kamu buat
        'USER': 'postgres',
        'PASSWORD': 'Password09!',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

build run.sh and push.sh

git remote add origin https://github.com/harys-rifai/Network.git
git branch -M main
git push -u origin main
