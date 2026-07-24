import ipaddress
import json
import re
import socket
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from django.core.cache import cache
    from apps.scan.models import OuiVendor, PortService, IspInfo
    HAS_DB = True
except Exception:
    HAS_DB = False
    cache = None
    OuiVendor = None
    PortService = None
    IspInfo = None

CACHE_TIMEOUT = 600


def _load_port_services():
    if not HAS_DB:
        return {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 110: 'POP3', 139: 'NetBIOS', 143: 'IMAP', 443: 'HTTPS',
            445: 'SMB', 993: 'IMAPS', 995: 'POP3S', 3389: 'RDP', 5353: 'mDNS',
            5900: 'VNC', 631: 'IPP', 5000: 'UPnP', 7000: 'AirPlay', 548: 'AFP',
            3306: 'MySQL', 5432: 'PostgreSQL', 27017: 'MongoDB', 6379: 'Redis',
            11211: 'Memcached', 1433: 'MSSQL', 1521: 'Oracle', 2375: 'Docker',
            3000: 'Node/HTTP', 9200: 'Elasticsearch', 5601: 'Kibana',
        }
    key = 'scanner_port_services'
    data = cache.get(key)
    if data is None:
        data = {p.port: p.service for p in PortService.objects.all()}
        cache.set(key, data, CACHE_TIMEOUT)
    return data


def _load_oui_vendors():
    if not HAS_DB:
        return {}
    key = 'scanner_oui_vendors'
    data = cache.get(key)
    if data is None:
        data = {o.prefix.upper(): o.vendor for o in OuiVendor.objects.all()}
        cache.set(key, data, CACHE_TIMEOUT)
    return data


def get_port_services():
    return _load_port_services()


def mac_to_vendor(mac):
    if not mac:
        return 'Unknown'
    mac = mac.strip().upper().replace(':','').replace('-','')
    prefix = mac[:6]
    vendors = _load_oui_vendors()
    return vendors.get(prefix, 'Unknown')


PORT_SERVICES = _load_port_services()


# OUI_VENDORS kept as alias for backward compatibility
OUI_VENDORS = _load_oui_vendors()


def get_active_interface():
    try:
        import platform
        system = platform.system().lower()
        if system == 'windows':
            return _get_active_interface_windows()
        else:
            return _get_active_interface_unix()
    except Exception:
        return None, None, None


def _get_active_interface_unix():
    try:
        out = subprocess.check_output(['ifconfig'], text=True)
    except Exception:
        return None, None, None
    lines = out.splitlines()
    interfaces = {}
    current = None
    curr_lines = []
    for line in lines:
        if line and not line.startswith('\t') and ':' in line:
            if current:
                interfaces[current] = curr_lines
            current = line.split(':')[0].strip()
            curr_lines = [line]
        else:
            curr_lines.append(line)
    if current:
        interfaces[current] = curr_lines

    skip = {'lo0','gif0','stf0','utun0','utun1','utun2','utun3','awdl0','llw0','bridge0'}
    for name, block in interfaces.items():
        if name in skip:
            continue
        ip = None
        netmask = None
        for bline in block:
            bline = bline.strip()
            if bline.startswith('inet '):
                parts = bline.split()
                if len(parts) >= 4 and parts[0] == 'inet':
                    ip = parts[1]
                    mask_raw = parts[3]
                    if mask_raw.startswith('0x') or mask_raw.startswith('0X'):
                        mask_int = int(mask_raw, 16)
                        mask_bits = bin(mask_int).count('1')
                        netmask = str(ipaddress.IPv4Network(f'0.0.0.0/{mask_bits}').netmask)
                    else:
                        netmask = mask_raw
                    break
        if ip and netmask and not ip.startswith('127.'):
            return name, ip, netmask
    return None, None, None


def _get_active_interface_windows():
    try:
        out = subprocess.check_output(['ipconfig'], text=True)
    except Exception:
        return None, None, None

    lines = out.splitlines()
    interfaces = {}
    current = None
    curr_lines = []
    for line in lines:
        line = line.rstrip()
        if line and not line.startswith(' ') and not line.startswith('\t') and ':' in line:
            if current:
                interfaces[current] = curr_lines
            current = line.split(':')[0].strip()
            curr_lines = [line]
        else:
            curr_lines.append(line)
    if current:
        interfaces[current] = curr_lines

    skip = {'Loopback Pseudo-Interface 1'}
    for name, block in interfaces.items():
        if name in skip:
            continue
        ip = None
        netmask = None
        for bline in block:
            bline = bline.strip()
            if 'IPv4 Address' in bline or 'IPv4 Address' in bline:
                parts = bline.split(':')
                if len(parts) >= 2:
                    ip = parts[1].strip().replace('(Preferred)', '')
            if 'Subnet Mask' in bline:
                parts = bline.split(':')
                if len(parts) >= 2:
                    netmask = parts[1].strip()
        if ip and netmask and not ip.startswith('127.'):
            return name, ip, netmask
    return None, None, None


def get_gateway():
    import platform
    system = platform.system().lower()
    if system == 'windows':
        return _get_gateway_windows()
    return _get_gateway_unix()


def _get_gateway_unix():
    try:
        out = subprocess.check_output(['route', '-n', 'get', 'default'], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('gateway:'):
                return line.split(':', 1)[1].strip()
            if line.startswith('router:'):
                return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return None


def _get_gateway_windows():
    try:
        out = subprocess.check_output(['route', 'print', '0.0.0.0'], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('0.0.0.0'):
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
    except Exception:
        pass
    return None


def get_dns_servers():
    import platform
    system = platform.system().lower()
    if system == 'windows':
        return _get_dns_servers_windows()
    return _get_dns_servers_unix()


def _get_dns_servers_unix():
    try:
        out = subprocess.check_output(['scutil', '--dns'], text=True)
        servers = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('nameserver['):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    servers.append(parts[1].strip())
        return servers
    except Exception:
        return []


def _get_dns_servers_windows():
    try:
        out = subprocess.check_output(
            ['powershell', '-Command', 'Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses'],
            text=True,
        )
        servers = []
        for line in out.splitlines():
            line = line.strip()
            if line and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', line):
                servers.append(line)
        return servers
    except Exception:
        pass
    return []


def build_arp_cache():
    try:
        out = subprocess.check_output(['arp', '-a'], text=True)
        cache = {}
        for line in out.splitlines():
            line = line.strip()
            parts = line.split()
            if len(parts) >= 3:
                ip = None
                mac = None
                if parts[0].startswith('[') and parts[1].endswith(']'):
                    ip = parts[1].strip('[]')
                elif '(' in line and ')' in line:
                    m = re.search(r'\(([^)]+)\)', line)
                    if m:
                        ip = m.group(1)
                for p in parts:
                    p = p.strip()
                    if ':' in p and len(p) == 17:
                        mac = p.lower()
                        break
                if ip and mac:
                    cache[ip] = mac
        return cache
    except Exception:
        return {}


def get_mac_from_arp(ip, arp_cache=None):
    if arp_cache is not None:
        return arp_cache.get(str(ip))
    cache = build_arp_cache()
    return cache.get(str(ip))


def measure_latency(ip, ports):
    last = None
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            start = time.time()
            s.connect((str(ip), port))
            s.close()
            last = round((time.time() - start) * 1000, 2)
            break
        except Exception:
            pass
    return last


def ping_host(ip):
    import platform
    system = platform.system().lower()
    try:
        if system == 'windows':
            out = subprocess.check_output(
                ['ping', '-n', '1', '-w', '300', str(ip)],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            )
        else:
            out = subprocess.check_output(
                ['ping', '-c', '1', '-W', '1', str(ip)],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            )
        ttl = None
        m = re.search(r'ttl=(\d+)', out, re.IGNORECASE)
        if m:
            ttl = int(m.group(1))
        return True, ttl
    except Exception:
        return False, None


def _probe_port(ip, port, timeout=0.3):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((str(ip), port))
        s.close()
        return port
    except Exception:
        return None


def scan_host(ip, ports=(22, 80, 443, 445, 139, 3389, 53, 5353, 5900, 3306, 5432, 6379, 2375, 9200, 8080, 8443, 1883, 8883, 554, 8000, 9090), arp_cache=None):
    hostname = None
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except Exception:
        pass
    mac = get_mac_from_arp(str(ip), arp_cache)
    return {
        'ip': str(ip),
        'open_ports': [],
        'hostname': hostname,
        'latency_ms': None,
        'mac_address': mac,
        'services': [],
    }


def guess_device_from_hostname(hn, ports):
    if hn:
        h = hn.lower()
        if 'router' in h or 'gateway' in h or 'gw ' in h or h.endswith('.gw'):
            return 'Router'
        if 'switch' in h:
            return 'Switch'
        if 'server' in h or 'srv' in h:
            return 'Server'
        if 'pc-' in h or 'laptop' in h or 'macbook' in h or 'imac' in h or 'desktop' in h:
            return 'PC'
        if 'phone' in h or 'iphone' in h or 'android' in h or 'galaxy' in h:
            return 'Phone'
        if 'printer' in h:
            return 'Printer'
        if 'firewall' in h or 'fw' in h:
            return 'Firewall'
        if 'ap' in h or 'access-point' in h or 'wifi' in h:
            return 'Access Point'
        if 'nas' in h or 'storage' in h:
            return 'NAS'
        if 'iot' in h:
            return 'IoT'
    ports_set = set(ports)
    if 445 in ports_set and 139 in ports_set:
        return 'PC/Server'
    if 3389 in ports_set:
        return 'PC/Server'
    if 22 in ports_set and 80 not in ports_set and 443 not in ports_set:
        return 'Server/IoT'
    if 80 in ports_set or 443 in ports_set:
        return 'Web Device'
    if 53 in ports_set or 5353 in ports_set:
        return 'IoT/Embedded'
    if 631 in ports_set:
        return 'Printer'
    if 5900 in ports_set:
        return 'Workstation/IoT'
    return 'Unknown'


def guess_os_from_ports(open_ports, hostname):
    ports = set(open_ports)
    hn = (hostname or '').lower()
    if 'mac' in hn or 'apple' in hn or 'iphone' in hn or 'ipad' in hn:
        return 'macOS/iOS'
    if 'android' in hn or 'galaxy' in hn:
        return 'Android'
    if 445 in ports and 139 in ports:
        return 'Windows'
    if 3389 in ports:
        return 'Windows'
    if 1433 in ports or 3306 in ports:
        return 'Windows/Linux'
    if 22 in ports and 80 not in ports and 443 not in ports:
        return 'Linux'
    if 22 in ports and (80 in ports or 443 in ports):
        return 'Linux'
    if 80 in ports or 443 in ports:
        return 'Unknown'
    if 53 in ports or 5353 in ports:
        return 'Embedded'
    if 631 in ports:
        return 'Embedded'
    if 5900 in ports:
        return 'Unknown'
    return 'Unknown'


def guess_brand(hostname, mac, services):
    if mac:
        v = mac_to_vendor(mac)
        if v != 'Unknown':
            return v
    if hostname:
        h = hostname.lower()
        brands = {
            'cisco': ['cisco'], 'ubiquiti': ['ubiquiti', 'unifi', 'dream machine', 'udm', 'edge'],
            'mikrotik': ['mikrotik', 'routeros'], 'netgear': ['netgear'], 'tp-link': ['tp-link', 'tplink'],
            'asus': ['asus'], 'apple': ['apple', 'macbook', 'imac', 'iphone', 'ipad'],
            'juniper': ['juniper'], 'd-link': ['d-link', 'dlink'], 'lenovo': ['lenovo', 'thinkpad'],
            'dell': ['dell', 'optiplex', 'latitude'], 'hp': ['hp', 'proliant'], 'samsung': ['samsung', 'galaxy'],
            'huawei': ['huawei'], 'xiaomi': ['xiaomi', 'redmi'], 'oppo': ['oppo'],
            'realme': ['realme'], 'vivo': ['vivo'], 'nokia': ['nokia'],
            'sony': ['sony'], 'lg': ['lg'], 'motorola': ['motorola', 'moto']
        }
        for brand, keys in brands.items():
            for k in keys:
                if k in h:
                    return brand.title()
    if services:
        svc_set = set(services)
        if {'HTTP','HTTPS'} <= svc_set:
            return 'Web Server'
        if 'SSH' in svc_set:
            return 'Linux/Embedded'
        if {'SMB','NetBIOS'} <= svc_set:
            return 'Windows PC'
    return 'Unknown'


def guess_os_from_ttl(ttl):
    if ttl is None:
        return 'Unknown'
    if ttl <= 64:
        return 'Linux/Unix/Android'
    if ttl <= 128:
        return 'Windows'
    if ttl <= 255:
        return 'Network/Embedded'
    return 'Unknown'


def guess_device_from_fallback(hostname, mac, ttl, brand):
    hn = (hostname or '').lower()
    mac_vendor = mac_to_vendor(mac) if mac else 'Unknown'

    if hn:
        if 'router' in hn or 'gateway' in hn or 'gw ' in hn or hn.endswith('.gw'):
            return 'Router'
        if 'switch' in hn:
            return 'Switch'
        if 'server' in hn or 'srv' in hn:
            return 'Server'
        if 'pc-' in hn or 'laptop' in hn or 'macbook' in hn or 'imac' in hn or 'desktop' in hn:
            return 'PC'
        if 'phone' in hn or 'iphone' in hn or 'android' in hn or 'galaxy' in hn:
            return 'Phone'
        if 'printer' in hn:
            return 'Printer'
        if 'firewall' in hn or 'fw' in hn:
            return 'Firewall'
        if 'ap' in hn or 'access-point' in hn or 'wifi' in hn:
            return 'Access Point'
        if 'nas' in hn or 'storage' in hn:
            return 'NAS'
        if 'iot' in hn:
            return 'IoT'

    if brand and brand != 'Unknown':
        bl = brand.lower()
        if any(x in bl for x in ['cisco', 'ubiquiti', 'mikrotik', 'netgear', 'tp-link', 'asus', 'juniper']):
            return 'Network Device'
        if any(x in bl for x in ['apple', 'samsung', 'xiaomi', 'huawei', 'oppo', 'realme', 'vivo', 'nokia', 'sony', 'lg', 'motorola']):
            return 'Phone/Tablet'
        if any(x in bl for x in ['dell', 'hp', 'lenovo']):
            return 'PC'

    if mac_vendor and mac_vendor != 'Unknown':
        mv = mac_vendor.lower()
        if any(x in mv for x in ['cisco', 'ubiquiti', 'mikrotik', 'netgear', 'tp-link', 'asus']):
            return 'Network Device'
        if any(x in mv for x in ['apple', 'samsung', 'xiaomi', 'huawei', 'oppo', 'realme', 'vivo', 'nokia', 'sony', 'lg', 'motorola']):
            return 'Phone/Tablet'
        if any(x in mv for x in ['dell', 'hp', 'lenovo']):
            return 'PC'

    if ttl is not None:
        if ttl <= 64:
            return 'Linux/Android/iOS Device'
        if ttl <= 128:
            return 'Windows Device'
        if ttl <= 255:
            return 'Network/Embedded Device'

    return 'Active Host'


def scan_network(subnet=None, max_hosts=254, max_workers=60):
    iface_name, ip_addr, netmask = get_active_interface()
    if not ip_addr or not netmask:
        raise RuntimeError('Could not detect active network interface.')
    network = ipaddress.IPv4Network(f'{ip_addr}/{netmask}', strict=False)
    target_subnet = subnet or str(network)
    net = ipaddress.IPv4Network(target_subnet, strict=False)
    hosts = list(net.hosts())[:max_hosts]
    if not hosts and str(net.network_address) == target_subnet.replace('/32', ''):
        hosts = [ipaddress.IPv4Address(target_subnet)]

    gateway = get_gateway()
    dns_servers = get_dns_servers()
    gateway_ip = gateway or str(net.network_address + 1)

    alive_ips = set()
    alive_with_ttl = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(ping_host, ip): ip for ip in hosts}
            for future in as_completed(futures):
                ip = futures[future]
                is_alive, ttl = future.result()
                if is_alive:
                    alive_ips.add(str(ip))
                    alive_with_ttl[str(ip)] = ttl
    except RuntimeError as e:
        if 'cannot schedule new futures after interpreter shutdown' in str(e):
            for ip in hosts:
                is_alive, ttl = ping_host(ip)
                if is_alive:
                    alive_ips.add(str(ip))
                    alive_with_ttl[str(ip)] = ttl
        else:
            raise

    if not alive_ips:
        public_ip = get_public_ip()
        isp_info = get_isp_info(public_ip)
        return [], isp_info

    arp_cache = build_arp_cache()

    ports = (22, 80, 443, 445, 139, 3389, 53, 5353, 5900, 3306, 5432, 6379, 2375, 9200, 8080, 8443, 1883, 8883, 554, 8000, 9090)

    results_map = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            host_futures = {executor.submit(scan_host, ip, ports, arp_cache): ip for ip in hosts}
            for future in as_completed(host_futures):
                res = future.result()
                ip_str = res['ip']
                if ip_str not in alive_ips:
                    continue
                results_map[ip_str] = res

            port_futures = {}
            for ip_str in results_map:
                for port in ports:
                    port_futures[executor.submit(_probe_port, ip_str, port)] = (ip_str, port)

            for future in as_completed(port_futures):
                ip_str, port = port_futures[future]
                result = future.result()
                if result is not None:
                    results_map[ip_str]['open_ports'].append(port)
    except RuntimeError as e:
        if 'cannot schedule new futures after interpreter shutdown' in str(e):
            for ip in hosts:
                res = scan_host(ip, ports, arp_cache)
                ip_str = res['ip']
                if ip_str not in alive_ips:
                    continue
                results_map[ip_str] = res
                for port in ports:
                    if _probe_port(ip_str, port):
                        results_map[ip_str]['open_ports'].append(port)
        else:
            raise

    results = []
    for ip_str, res in results_map.items():
        hostname = res['hostname']
        mac = res['mac_address']
        ports_open = sorted(res['open_ports'])
        services = [PORT_SERVICES.get(p) for p in ports_open if p in PORT_SERVICES]
        latency_ms = measure_latency(ip_str, ports_open) if ports_open else None
        ttl = alive_with_ttl.get(ip_str)
        brand = guess_brand(hostname, mac, services)

        if ports_open:
            device = guess_device_from_hostname(hostname, ports_open)
            os_name = guess_os_from_ports(ports_open, hostname)
        else:
            device = guess_device_from_fallback(hostname, mac, ttl, brand)
            os_name = guess_os_from_ttl(ttl)

        results.append({
            'ip': ip_str,
            'device': device,
            'os': os_name,
            'brand': brand,
            'gateway': gateway_ip,
            'router': gateway_ip,
            'dns': dns_servers[0] if dns_servers else None,
            'mac_address': mac,
            'latency_ms': latency_ms,
            'open_ports': ports_open,
            'services': services,
            'server_info': detect_server_info(hostname, ports_open, services),
        })

    public_ip = get_public_ip()
    isp_info = get_isp_info(public_ip)
    for r in results:
        r['public_ip'] = public_ip
        r['isp_name'] = isp_info.get('isp')
        r['isp_org'] = isp_info.get('org')
    return results, isp_info


def get_public_ip():
    if HAS_DB:
        cached = cache.get('scanner_public_ip')
        if cached:
            return cached
    try:
        req = urllib.request.Request(
            'https://api.ipify.org',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ip = resp.read().decode().strip()
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            if HAS_DB:
                cache.set('scanner_public_ip', ip, 300)
            return ip
    except Exception:
        pass
    return None


def get_isp_info(public_ip=None):
    ip = public_ip or get_public_ip()
    if not ip:
        return {}
    if HAS_DB:
        cache_key = f'scanner_isp_info:{ip}'
        cached = cache.get(cache_key)
        if cached:
            return cached
    try:
        req = urllib.request.Request(
            f'https://ip-api.com/json/{ip}?fields=isp,org,as,country,regionName,city,status,message',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get('status') == 'success':
            result = {
                'isp': data.get('isp'),
                'org': data.get('org'),
                'as': data.get('as'),
                'country': data.get('country'),
                'region': data.get('regionName'),
                'city': data.get('city'),
            }
            if HAS_DB:
                cache.set(cache_key, result, 300)
                _save_isp_info(ip, result)
            return result
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            f'https://freeipapi.com/api/json/{ip}',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        result = {
            'isp': data.get('asnOrganization') or data.get('org') or data.get('isp'),
            'org': data.get('asnOrganization') or data.get('org') or data.get('isp'),
            'as': data.get('asn'),
            'country': data.get('countryName'),
            'region': data.get('regionName'),
            'city': data.get('cityName'),
        }
        if HAS_DB:
            cache.set(cache_key, result, 300)
            _save_isp_info(ip, result)
        return result
    except Exception:
        pass
    return {}


def _save_isp_info(ip, info):
    if not HAS_DB or not IspInfo or not ip:
        return
    try:
        defaults = {
            'isp': info.get('isp') or info.get('org'),
            'org': info.get('org'),
            'as_number': info.get('as'),
            'country': info.get('country'),
            'region': info.get('region'),
            'city': info.get('city'),
        }
        IspInfo.objects.update_or_create(ip=ip, defaults=defaults)
    except Exception:
        pass


def detect_server_info(hostname, ports, services):
    ports_set = set(ports)
    svc_set = set(services)
    server_types = []
    if 22 in ports_set:
        server_types.append('SSH')
    if 80 in ports_set or 443 in ports_set:
        server_types.append('Web')
    if 3306 in ports_set:
        server_types.append('MySQL')
    if 5432 in ports_set:
        server_types.append('PostgreSQL')
    if 6379 in ports_set:
        server_types.append('Redis')
    if 27017 in ports_set:
        server_types.append('MongoDB')
    if 1433 in ports_set:
        server_types.append('MSSQL')
    if 1521 in ports_set:
        server_types.append('Oracle')
    if 2375 in ports_set:
        server_types.append('Docker')
    if 9200 in ports_set or 5601 in ports_set:
        server_types.append('Elasticsearch')
    if 21 in ports_set:
        server_types.append('FTP')
    if 25 in ports_set:
        server_types.append('SMTP')
    if 53 in ports_set:
        server_types.append('DNS')
    if 3000 in ports_set:
        server_types.append('Node.js')
    if 5000 in ports_set:
        server_types.append('UPnP/Media')
    if 631 in ports_set:
        server_types.append('Print Server')
    if 5900 in ports_set:
        server_types.append('VNC')
    if 7000 in ports_set:
        server_types.append('AirPlay')
    if 548 in ports_set:
        server_types.append('AFP')
    if 11211 in ports_set:
        server_types.append('Memcached')
    if 445 in ports_set or 139 in ports_set:
        server_types.append('SMB/File')
    if 5353 in ports_set:
        server_types.append('mDNS/Bonjour')
    if hostname and ('server' in hostname.lower() or 'srv' in hostname.lower()):
        server_types.append('Hostname')
    return ', '.join(server_types) if server_types else None


def get_wan_interface_info():
    try:
        import platform
        system = platform.system().lower()
        if system == 'windows':
            return _get_wan_interface_info_windows()
        return _get_wan_interface_info_unix()
    except Exception:
        pass
    return {}


def _get_wan_interface_info_unix():
    try:
        out = subprocess.check_output(['ifconfig'], text=True)
        lines = out.splitlines()
        interfaces = {}
        current = None
        curr_lines = []
        for line in lines:
            if line and not line.startswith('\t') and ':' in line:
                if current:
                    interfaces[current] = curr_lines
                current = line.split(':')[0].strip()
                curr_lines = [line]
            else:
                curr_lines.append(line)
        if current:
            interfaces[current] = curr_lines

        skip = {'lo0', 'gif0', 'stf0', 'utun0', 'utun1', 'utun2', 'utun3', 'awdl0', 'llw0', 'bridge0'}
        for name, block in interfaces.items():
            if name in skip:
                continue
            active = False
            media = None
            for bline in block:
                bline = bline.strip()
                if bline.startswith('status:'):
                    if 'active' in bline.lower():
                        active = True
                if bline.startswith('media:'):
                    media = bline.split(':', 1)[1].strip()
            if active and media:
                return {
                    'interface': name,
                    'media': media,
                }
    except Exception:
        pass
    return {}


def _get_wan_interface_info_windows():
    try:
        out = subprocess.check_output(['ipconfig'], text=True)
        lines = out.splitlines()
        interfaces = {}
        current = None
        curr_lines = []
        for line in lines:
            line = line.rstrip()
            if line and not line.startswith(' ') and not line.startswith('\t') and ':' in line:
                if current:
                    interfaces[current] = curr_lines
                current = line.split(':')[0].strip()
                curr_lines = [line]
            else:
                curr_lines.append(line)
        if current:
            interfaces[current] = curr_lines

        skip = {'Loopback Pseudo-Interface 1'}
        for name, block in interfaces.items():
            if name in skip:
                continue
            has_ip = False
            for bline in block:
                bline = bline.strip()
                if bline.startswith('IPv4 Address') and ':' in bline:
                    parts = bline.split(':', 1)
                    if len(parts) == 2 and parts[1].strip() and not parts[1].strip().startswith('127.'):
                        has_ip = True
            if has_ip:
                return {
                    'interface': name,
                    'media': 'Ethernet/Wi-Fi',
                }
    except Exception:
        pass
    return {}
