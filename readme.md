# 🛰️ Django Network Monitoring & Inventory

## 📌 Deskripsi
Aplikasi berbasis **Django** untuk:
- Login & autentikasi user.
- Dashboard monitoring jaringan.
- Network inventory hasil scan (IP, device, OS, brand, gateway, router, DNS).
- Peta jaringan interaktif (network mapping).

## ⚙️ Fitur Utama
- **Autentikasi & Role Management**
  - Login dengan `django.contrib.auth`.
- **Network Scan**
  - Scanner langsung berbasis socket + `ifconfig` tanpa perlu `nmap` atau `scapy`.
  - Deteksi interface aktif, gateway, dan DNS server secara otomatis.
  - Simpan hasil ke tabel `scan`.
- **Inventory Management**
  - Tabel `scan(id, ip, device, os, brand, gateway, router, dns, scanned_at)`.
  - CRUD untuk data hasil scan.
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
└── push.sh
```

## 🚀 Workflow
1. User login → masuk dashboard.
2. Buka **New Scan** → pilih subnet / gunakan auto-detect interface aktif.
3. Sistem melakukan live host discovery, live host dengan port terbentukkan disimpan.
4. Dashboard menampilkan inventory & statistik.
5. **Network Map** menampilkan topologi interaktif.

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

## 🚀 Push ke GitHub
bash push.sh  

