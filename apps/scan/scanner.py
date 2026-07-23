import ipaddress
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT_SERVICES = {
    21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
    80: 'HTTP', 110: 'POP3', 139: 'NetBIOS', 143: 'IMAP', 443: 'HTTPS',
    445: 'SMB', 993: 'IMAPS', 995: 'POP3S', 3389: 'RDP', 5353: 'mDNS',
    5900: 'VNC', 631: 'IPP', 5000: 'UPnP', 7000: 'AirPlay', 548: 'AFP',
    3306: 'MySQL', 5432: 'PostgreSQL', 27017: 'MongoDB', 6379: 'Redis',
    11211: 'Memcached', 1433: 'MSSQL', 1521: 'Oracle', 2375: 'Docker',
    3000: 'Node/HTTP', 3306: 'MySQL', 9200: 'Elasticsearch', 5601: 'Kibana',
}

OUI_VENDORS = {
    '001122': 'Cisco', '00199d': 'Cisco', '0021a1': 'Cisco', '0022:1': 'Cisco',
    '3c5a:b4': 'Cisco', '44:23': 'Cisco', '54:a7': 'Cisco',
    '00:1a:79': 'Cisco', '00:1e:bd': 'Cisco', '00:21:55': 'Cisco',
    '00:25:9c': 'Cisco', '00:26:5a': 'Dell', '00:26:b9': 'Dell',
    '00:14:22': 'Dell', '00:1c:c4': 'Dell', '00:21:9b': 'Dell',
    '00:22:19': 'HP', '00:23:7d': 'HP', '00:26:55': 'HP',
    '00:0e:7f': 'HP', '00:1f:29': 'HP', '00:21:5a': 'HP',
    '00:23:12': 'Apple', '00:23:32': 'Apple', '00:23:61': 'Apple',
    '00:23:df': 'Apple', '00:24:36': 'Apple', '00:25:4b': 'Apple',
    '00:25:bc': 'Apple', '00:26:4a': 'Apple', '00:26:b0': 'Apple',
    '00:26:bb': 'Apple', '00:30:65': 'Apple', '00:50:e4': 'Apple',
    '04:0c:ce': 'Apple', '04:15:52': 'Apple', '04:1e:64': 'Apple',
    '04:26:65': 'Apple', '04:54:53': 'Apple', '04:db:56': 'Apple',
    '08:00:07': 'Apple', '10:1c:0c': 'Apple', '18:3d:a2': 'Apple',
    '18:3d:a2': 'Apple', '20:c9:d0': 'Apple', '28:cf:da': 'Apple',
    '2c:be:08': 'Apple', '30:10:b3': 'Apple', '30:35:ad': 'Apple',
    '38:0f:4a': 'Apple', '38:0f:4a': 'Apple', '3c:07:54': 'Apple',
    '40:30:05': 'Apple', '40:6c:8f': 'Apple', '44:2a:60': 'Apple',
    '48:60:bc': 'Apple', '48:74:6e': 'Apple', '54:26:96': 'Apple',
    '54:4e:90': 'Apple', '58:1c:f8': 'Apple', '58:7f:57': 'Apple',
    '58:b0:35': 'Apple', '5c:8d:4e': 'Apple', '60:03:08': 'Apple',
    '60:c5:47': 'Apple', '64:20:0c': 'Apple', '68:5b:35': 'Apple',
    '6c:40:08': 'Apple', '6c:72:e7': 'Apple', '70:11:24': 'Apple',
    '70:14:a6': 'Apple', '70:3e:97': 'Apple', '74:1b:b2': 'Apple',
    '78:4f:43': 'Apple', '78:6a:89': 'Apple', '7c:11:be': 'Apple',
    '7c:6d:62': 'Apple', '80:be:05': 'Apple', '84:38:35': 'Apple',
    '84:78:ac': 'Apple', '88:53:2e': 'Apple', '88:ae:07': 'Apple',
    '88:cb:87': 'Apple', '8c:1a:b4': 'Apple', '8c:58:77': 'Apple',
    '90:27:e4': 'Apple', '90:72:40': 'Apple', '90:84:0d': 'Apple',
    '94:94:26': 'Apple', '98:01:a7': 'Apple', '9c:04:eb': 'Apple',
    '9c:20:7b': 'Apple', '9c:29:76': 'Apple', '9c:35:eb': 'Apple',
    '9c:f4:8e': 'Apple', 'a0:99:9b': 'Apple', 'a4:b1:97': 'Apple',
    'a4:c3:61': 'Apple', 'a4:d1:8c': 'Apple', 'a8:20:66': 'Apple',
    'a8:5b:78': 'Apple', 'a8:96:75': 'Apple', 'ac:3a:7a': 'Apple',
    'ac:bc:32': 'Apple', 'b0:34:95': 'Apple', 'b8:17:99': 'Apple',
    'b8:27:eb': 'Apple', 'b8:c7:5d': 'Apple', 'bc:3b:af': 'Apple',
    'bc:4c:c4': 'Apple', 'bc:67:78': 'Apple', 'c0:84:7a': 'Apple',
    'c0:ce:cd': 'Apple', 'c0:d0:12': 'Apple', 'c4:2c:03': 'Apple',
    'c8:1e:e7': 'Apple', 'c8:6f:1d': 'Apple', 'c8:bc:c8': 'Apple',
    'cc:29:f5': 'Apple', 'd0:23:db': 'Apple', 'd0:33:11': 'Apple',
    'd0:65:ca': 'Apple', 'd4:61:9d': 'Apple', 'd4:9a:20': 'Apple',
    'd8:1d:72': 'Apple', 'd8:30:62': 'Apple', 'd8:96:95': 'Apple',
    'd8:a2:5e': 'Apple', 'dc:0b:34': 'Apple', 'dc:9b:9c': 'Apple',
    'e0:2a:82': 'Apple', 'e0:5f:b9': 'Apple', 'e0:ac:cb': 'Apple',
    'e0:b9:ba': 'Apple', 'e0:c7:67': 'Apple', 'e4:25:e7': 'Apple',
    'e8:06:88': 'Apple', 'ec:35:86': 'Apple', 'f0:18:98': 'Apple',
    'f0:24:75': 'Apple', 'f0:76:1c': 'Apple', 'f0:99:bf': 'Apple',
    'f0:b4:79': 'Apple', 'f0:cb:a1': 'Apple', 'f4:15:63': 'Apple',
    'f4:37:b7': 'Apple', 'f4:5c:89': 'Apple', 'f8:1e:df': 'Apple',
    'f8:27:93': 'Apple', 'f8:62:14': 'Apple', 'fc:25:3f': 'Apple',
    'fc:fc:48': 'Apple', '00:1e:bd': 'Cisco', '00:23:32': 'Apple',
    '00:26:5a': 'Dell', '00:21:9b': 'Dell', '00:22:19': 'HP',
    '00:23:61': 'Apple', '00:26:bb': 'Apple', '00:50:f2': 'Microsoft',
    '00:15:5d': 'Microsoft', '00:17:fa': 'Microsoft', '00:1d:09': 'Microsoft',
    '00:22:48': 'Microsoft', '00:23:16': 'Microsoft', '00:25:ae': 'Microsoft',
    '00:e0:4c': 'Realtek', '00:e0:4c': 'Realtek', '00:0c:e7': 'Motorola',
}

def mac_to_vendor(mac):
    if not mac:
        return 'Unknown'
    mac = mac.strip().upper().replace(':','').replace('-','')
    prefix = mac[:6]
    return OUI_VENDORS.get(prefix, 'Unknown')

def get_active_interface():
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

def get_gateway():
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

def get_dns_servers():
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

def get_mac_from_arp(ip):
    try:
        out = subprocess.check_output(['arp', '-a', ip], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith(ip) or ip in line:
                parts = line.split()
                for p in parts:
                    if ':' in p and len(p) == 17:
                        return p.lower()
    except Exception:
        pass
    return None

def scan_host(ip, ports=(22, 80, 443, 445, 139, 3389, 53, 5353, 5900, 631, 5000, 7000, 548, 3306, 5432, 6379, 2375, 9200)):
    open_ports = []
    hostname = None
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except Exception:
        pass

    start = time.time()
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            s.connect((str(ip), port))
            s.close()
            open_ports.append(port)
        except Exception:
            pass
    latency_ms = round((time.time() - start) * 1000, 2) if open_ports else None
    mac = get_mac_from_arp(str(ip))
    services = [PORT_SERVICES[p] for p in open_ports if p in PORT_SERVICES]
    return {
        'ip': str(ip),
        'open_ports': open_ports,
        'hostname': hostname,
        'latency_ms': latency_ms,
        'mac_address': mac,
        'services': services,
    }

def guess_device_from_hostname(hn, ports):
    if not hn:
        return 'Unknown'
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
    if 445 in ports and 139 in ports:
        return 'PC/Server'
    if 3389 in ports:
        return 'PC/Server'
    if 22 in ports and 80 not in ports and 443 not in ports:
        return 'Server/IoT'
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
    if 5000 in ports or 7000 in ports:
        return 'macOS/iOS'
    return 'Unknown'

def guess_brand(hostname, mac):
    if mac:
        v = mac_to_vendor(mac)
        if v != 'Unknown':
            return v
    if not hostname:
        return 'Unknown'
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
    return 'Unknown'

def scan_network(subnet=None, max_hosts=254, max_workers=120):
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

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_host, ip): ip for ip in hosts}
        for future in as_completed(futures):
            res = future.result()
            if res['open_ports']:
                device = guess_device_from_hostname(res['hostname'], res['open_ports'])
                os_name = guess_os_from_ports(res['open_ports'], res['hostname'])
                brand = guess_brand(res['hostname'], res['mac_address'])
                results.append({
                    'ip': res['ip'],
                    'device': device,
                    'os': os_name,
                    'brand': brand,
                    'gateway': gateway_ip,
                    'router': gateway_ip,
                    'dns': dns_servers[0] if dns_servers else None,
                    'mac_address': res['mac_address'],
                    'latency_ms': res['latency_ms'],
                    'open_ports': res['open_ports'],
                    'services': res['services'],
                })
    return results
