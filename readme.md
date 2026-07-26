# 🛰️ Django Network Monitoring & Inventory

## 📌 Deskripsi
Aplikasi monitoring jaringan berbasis Django untuk scan, inventaris, analytics, dan visualisasi topologi.

## ⚙️ Fitur
- **Dashboard** — ringkasan device, OS, brand, chart interaktif
- **Scan Results** — inventory lengkap (IP, MAC, gateway, router, DNS, port, latency, vendor)
- **Analytics** — top destinations, traffic by country, world map, OS/device breakdown
- **Network Map** — topologi interaktif (vis-network)
- **Connection Trace** — traceroute dengan geolokasi per-hop
- **Database Maintenance** — VACUUM, reindex, rebuild index per tabel

## 🚀 Instalasi Cepat

### Windows
```powershell
.\run.bat
```

### Linux / macOS
```bash
bash run.sh
```

Server berjalan di `http://127.0.0.1:8080/`  
Login: `admin` / `admin123`

### Manual
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8080
```

## ⚡ Performance & UX Improvements
- **Cached template loader** — menghilangkan template recompile tiap request di Windows
- **Analytics cached page** — hasil analytics di-cache 5 menit
- **Router clients cache** — avoid repeated router HTTP timeout when unreachable
- **Deferred map load** — jsvectormap dimuat hanya saat map terlihat (`IntersectionObserver`)
- **Chart animation off** — animasi Chart.js dimatikan agar render lebih cepat
- **Reduced dataset** — analytics awal dibatasi ke 100 trace terbaru

## 🎨 Theme
Dark green-navy theme (`#111827` / `#1a2332` / `#1e2a3a`) dengan aksen gold `#facc15` dan hijau `#22c55e`.

## 📁 Struktur
```
project/
├── apps/
│   ├── scan/           # scanner, models, views, URLs
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── scanner.py
│   │   └── templatetags/
│   └── dashboard/      # dashboard, analytics, map, trace
│       ├── views.py
│       └── models.py
├── project/
│   ├── settings.py
│   └── urls.py
├── templates/          # base, dashboard, analytics, map, trace, scan
├── static/css/style.css
├── manage.py
├── run.sh / run.bat
└── push.sh
```
