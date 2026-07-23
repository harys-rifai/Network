# 🛰️ Django Network Monitoring & Inventory

## 📌 Deskripsi
Aplikasi berbasis **Django** untuk:
- Login & autentikasi user.
- Dashboard monitoring jaringan.
- Network inventory hasil scan (IP, device, OS, brand, gateway, router, DNS, MAC, latency, open ports).
- Peta jaringan interaktif (network mapping).

## ⚙️ Fitur Utama
- **Autentikasi & Role Management**
  - Login dengan `django.contrib.auth`.
- **Live Host Discovery**
  - Ping sweep untuk menemukan semua host yang hidup di subnet.
  - Deteksi TTL untuk inferensi OS sederhana.
  - Deteksi interface aktif, gateway, dan DNS server secara otomatis.
- **Port & Service Detection**
  - Scan koneksi TCP pada port umum.
  - Pemetaan port ke layanan (HTTP, SSH, SMB, RDP, dll).
  - Pengukuran latency berbasis port terbuka.
- **Device Classification**
  - Inferensi device, OS, dan vendor dari hostname, MAC vendor, TTL, dan open ports.
  - Mendeteksi perangkat tanpa open port (phone, tablet, IoT, PC, server).
- **Inventory Management**
  - Tabel `scan(id, ip, device, os, brand, gateway, router, dns, mac_address, latency_ms, open_ports, services, scanned_at)`.
  - CRUD untuk data hasil scan.
  - Identifikasi duplikat IP dan MAC.
- **Dashboard Monitoring**
  - Ringkasan jumlah device, distribusi OS & brand.
  - Grafik interaktif dengan Chart.js.
- **Network Mapping**
  - Visualisasi topologi jaringan menggunakan vis.js.
  - Node: IP/device.
  - Edge: hubungan ke gateway.

## 🛠️ Instalasi
```bash
git clone <repo>
cd network
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka `http://127.0.0.1:8000/accounts/login/` dan login dengan akun superuser.

## 📁 Struktur Project
```
project/
├── apps/
│   ├── scan/           # Model, scanner, view untuk hasil scan
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── scanner.py
│   └── dashboard/      # Dashboard & visualisasi
│       ├── views.py
│       └── urls.py
├── project/
│   ├── settings.py
│   └── urls.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── network_map.html
│   ├── scan_list.html
│   ├── scan_detail.html
│   ├── scan_form.html
│   ├── scan_trigger.html
│   └── scan_confirm_delete.html
├── static/
│   └── css/
│       └── style.css
├── manage.py
├── push.sh
└── readme.md
```

## 🚀 Workflow
1. User login → masuk dashboard.
2. Buka **New Scan** → pilih subnet / gunakan auto-detect interface aktif.
3. Sistem melakukan ping sweep, live host discovery, dan port scan.
4. Host tanpa open port tetap terdeteksi menggunakan fallback inference (hostname, MAC vendor, TTL).
5. Dashboard menampilkan inventory & statistik.
6. **Network Map** menampilkan topologi interaktif.

## 🔮 Fitur Tambahan
- Alert & Notifikasi
  - Kirim email/telegram jika ada device baru atau perubahan OS.
- Scheduled Scan
  - Gunakan Celery atau django-crontab untuk scan otomatis.
- Export Data
  - Export hasil scan ke CSV/Excel.
- Integrasi SNMP
  - Ambil informasi device lebih detail (CPU, memory, interface).
- User Activity Log
  - Audit trail untuk login & aksi user.
- API Endpoint
  - Django Rest Framework untuk integrasi dengan aplikasi lain.
- Security Check
  - Tambahkan port scan & vulnerability check dasar.
- Multi-subnet Support
  - Scan lebih dari satu range IP sekaligus.
- Historical Trends
  - Grafik perubahan jumlah device/OS dari waktu ke waktu.

## ⚙️ Konfigurasi Database
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'network',
        'USER': 'postgres',
        'PASSWORD': 'Password09!',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 📸 Tampilan
- Tema gelap elegan dengan aksen cyan.
- Navbar sticky, card-based dashboard, tabel data yang rapi.
- Chart.js untuk statistik OS dan brand.
- vis.js untuk network topology.

### Screenshots
![Login](img/Screenshot%202026-07-24%20at%2002.26.35.png)
![Dashboard](img/Screenshot%202026-07-24%20at%2002.29.13.png)
![Scan List](img/Screenshot%202026-07-24%20at%2002.29.26.png)
![Scan Detail](img/Screenshot%202026-07-24%20at%2002.29.33.png)
![Scan Edit](img/Screenshot%202026-07-24%20at%2002.29.42.png)
![Scan Delete Confirmation](img/Screenshot%202026-07-24%20at%2002.29.55.png)
![Network Map](img/Screenshot%202026-07-24%20at%2002.31.14.png)
![Scan Trigger](img/Screenshot%202026-07-24%20at%2002.31.41.png)
![Scan Results Table](img/Screenshot%202026-07-24%20at%2003.25.50.png)
![Phones Detected](img/Screenshot%202026-07-24%20at%2003.25.59.png)
![PCs and Devices](img/Screenshot%202026-07-24%20at%2003.26.05.png)
![Full Inventory](img/Screenshot%202026-07-24%20at%2003.26.12.png)

## 🚀 Push ke GitHub
```bash
bash push.sh  
```
