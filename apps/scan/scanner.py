import ipaddress
import json
import re
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
    3000: 'Node/HTTP', 9200: 'Elasticsearch', 5601: 'Kibana',
}

OUI_VENDORS = {
    '001122': 'Cisco',
    '00199D': 'Cisco',
    '0021A1': 'Cisco',
    '001A79': 'Cisco',
    '001EBD': 'Cisco',
    '002155': 'Cisco',
    '00259C': 'Cisco',
    '00265A': 'Dell',
    '0026B9': 'Dell',
    '001422': 'Dell',
    '001CC4': 'Dell',
    '00219B': 'Dell',
    '002219': 'HP',
    '00237D': 'HP',
    '002655': 'HP',
    '000E7F': 'HP',
    '001F29': 'HP',
    '00215A': 'HP',
    '002312': 'Apple',
    '002332': 'Apple',
    '002361': 'Apple',
    '0023DF': 'Apple',
    '002436': 'Apple',
    '00254B': 'Apple',
    '0025BC': 'Apple',
    '00264A': 'Apple',
    '0026B0': 'Apple',
    '0026BB': 'Apple',
    '003065': 'Apple',
    '0050E4': 'Apple',
    '040CCE': 'Apple',
    '041552': 'Apple',
    '041E64': 'Apple',
    '042665': 'Apple',
    '045453': 'Apple',
    '04DB56': 'Apple',
    '080007': 'Apple',
    '101C0C': 'Apple',
    '183DA2': 'Apple',
    '20C9D0': 'Apple',
    '28CFDA': 'Apple',
    '2CBE08': 'Apple',
    '3010B3': 'Apple',
    '3035AD': 'Apple',
    '380F4A': 'Apple',
    '3C0754': 'Apple',
    '403005': 'Apple',
    '406C8F': 'Apple',
    '442A60': 'Apple',
    '4860BC': 'Apple',
    '48746E': 'Apple',
    '542696': 'Apple',
    '544E90': 'Apple',
    '581CF8': 'Apple',
    '587F57': 'Apple',
    '58B035': 'Apple',
    '5C8D4E': 'Apple',
    '600308': 'Apple',
    '60C547': 'Apple',
    '64200C': 'Apple',
    '685B35': 'Apple',
    '6C4008': 'Apple',
    '6C72E7': 'Apple',
    '701124': 'Apple',
    '7014A6': 'Apple',
    '703E97': 'Apple',
    '741BB2': 'Apple',
    '784F43': 'Apple',
    '786A89': 'Apple',
    '7C11BE': 'Apple',
    '7C6D62': 'Apple',
    '80BE05': 'Apple',
    '843835': 'Apple',
    '8478AC': 'Apple',
    '88532E': 'Apple',
    '88AE07': 'Apple',
    '88CB87': 'Apple',
    '8C1AB4': 'Apple',
    '8C5877': 'Apple',
    '9027E4': 'Apple',
    '907240': 'Apple',
    '90840D': 'Apple',
    '949426': 'Apple',
    '9801A7': 'Apple',
    '9C04EB': 'Apple',
    '9C207B': 'Apple',
    '9C2976': 'Apple',
    '9C35EB': 'Apple',
    '9CF48E': 'Apple',
    'A0999B': 'Apple',
    'A4B197': 'Apple',
    'A4C361': 'Apple',
    'A4D18C': 'Apple',
    'A82066': 'Apple',
    'A85B78': 'Apple',
    'A89675': 'Apple',
    'AC3A7A': 'Apple',
    'ACBC32': 'Apple',
    'B03495': 'Apple',
    'B81799': 'Apple',
    'B827EB': 'Apple',
    'B8C75D': 'Apple',
    'BC3BAF': 'Apple',
    'BC4CC4': 'Apple',
    'BC6778': 'Apple',
    'C0847A': 'Apple',
    'C0CECD': 'Apple',
    'C0D012': 'Apple',
    'C42C03': 'Apple',
    'C81EE7': 'Apple',
    'C86F1D': 'Apple',
    'C8BCC8': 'Apple',
    'CC29F5': 'Apple',
    'D023DB': 'Apple',
    'D03311': 'Apple',
    'D065CA': 'Apple',
    'D4619D': 'Apple',
    'D49A20': 'Apple',
    'D81D72': 'Apple',
    'D83062': 'Apple',
    'D89695': 'Apple',
    'D8A25E': 'Apple',
    'DC0B34': 'Apple',
    'DC9B9C': 'Apple',
    'E02A82': 'Apple',
    'E05FB9': 'Apple',
    'E0ACCB': 'Apple',
    'E0B9BA': 'Apple',
    'E0C767': 'Apple',
    'E425E7': 'Apple',
    'E80688': 'Apple',
    'EC3586': 'Apple',
    'F01898': 'Apple',
    'F02475': 'Apple',
    'F0761C': 'Apple',
    'F099BF': 'Apple',
    'F0B479': 'Apple',
    'F0CBA1': 'Apple',
    'F41563': 'Apple',
    'F437B7': 'Apple',
    'F45C89': 'Apple',
    'F81EDF': 'Apple',
    'F82793': 'Apple',
    'F86214': 'Apple',
    'FC253F': 'Apple',
    'FCFC48': 'Apple',
    '0050F2': 'Microsoft',
    '00155D': 'Microsoft',
    '0017FA': 'Microsoft',
    '001D09': 'Microsoft',
    '002248': 'Microsoft',
    '002316': 'Microsoft',
    '0025AE': 'Microsoft',
    '00E04C': 'Realtek',
    '000CE7': 'Motorola',
    '8217AF': 'Xiaomi',
    'CA7D57': 'Samsung',
    '928D37': 'Huawei',
    'FAF566': 'Oppo',
    '669A95': 'Vivo',
    'AAF94F': 'Realme',
    '1626D7': 'Xiaomi',
    '1EB5B9': 'Samsung',
    '3C5AB4': 'Google',
    'AC3743': 'Huawei',
    'FCDC4F': 'Samsung',
    '380E4D': 'Xiaomi',
    '480EEC': 'Samsung',
    '549A0F': 'Oppo',
    '703ACE': 'Vivo',
    '001A11': 'Samsung',
    '001D0D': 'Sony',
    '001EDC': 'Samsung',
    '002119': 'Samsung',
    '002339': 'Samsung',
    '002454': 'Samsung',
    '002666': 'Samsung',
    '00E061': 'Samsung',
    '0808C2': 'Samsung',
    '0C1420': 'Samsung',
    '103025': 'Samsung',
    '14F65A': 'Xiaomi',
    '182195': 'Samsung',
    '1C62B8': 'Samsung',
    '240AC4': 'Vivo',
    '286CAB': 'Xiaomi',
    '2C5491': 'Xiaomi',
    '380B40': 'Samsung',
    '44650D': 'Samsung',
    '48137E': 'Samsung',
    '4C3B74': 'Huawei',
    '50642B': 'Xiaomi',
    '549B12': 'Samsung',
    '582D34': 'Oppo',
    '5C497D': 'Samsung',
    '606BBD': 'Samsung',
    '683E26': 'Oppo',
    '6C709F': 'Xiaomi',
    '78521A': 'Samsung',
    '804A14': 'Oppo',
    '881196': 'Huawei',
    '904C81': 'Huawei',
    '9C8CD8': 'Huawei',
    'A0EDCD': 'Vivo',
    'AC4223': 'Xiaomi',
    'B06EBF': 'Oppo',
    'B83765': 'Xiaomi',
    'BC7FA8': 'Huawei',
    'C0210D': 'Samsung',
    'CC07AB': 'Xiaomi',
    'D8490F': 'Huawei',
    'E0DCA2': 'Vivo',
    'E89C25': 'Asus',
    'EC233D': 'Xiaomi',
    'F077C8': 'Xiaomi',
    'F83E95': 'Vivo',
    'FC64BA': 'Xiaomi',
    '043604': 'Huawei',
    '0C771A': 'Oppo',
    '185680': 'Oppo',
    '2418C6': 'Vivo',
    '286D97': 'Oppo',
    '3431C4': 'Huawei',
    '486DFB': 'Xiaomi',
    '549A08': 'Oppo',
    '644BF0': 'Xiaomi',
    '683F7D': 'Oppo',
    '6C5C3D': 'Huawei',
    '788C77': 'Xiaomi',
    '808917': 'Oppo',
    '885A92': 'Huawei',
    '98523D': 'Oppo',
    'A48D3B': 'Vivo',
    'B07C25': 'Xiaomi',
    'B43052': 'Huawei',
    'C0EEFB': 'Oppo',
    'CC81DA': 'Vivo',
    'D494E8': 'Huawei',
    'E47E9A': 'Xiaomi',
    'F4C714': 'Oppo',
    'FC167D': 'Vivo',
    'D49A20': 'Apple',
    'F49F54': 'Xiaomi',
    'ACBCD7': 'Samsung',
    '2C6939': 'Xiaomi',
    '485929': 'Xiaomi',
    '64CC2E': 'Xiaomi',
    'A41115': 'Xiaomi'
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
        out = subprocess.check_output(['arp', '-a'], text=True)
        for line in out.splitlines():
            line = line.strip()
            if f'({ip})' in line or f' {ip} ' in line:
                parts = line.split()
                for p in parts:
                    p = p.strip()
                    if ':' in p and len(p) == 17:
                        return p.lower()
    except Exception:
        pass
    return None

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
    try:
        out = subprocess.check_output(
            ['ping', '-c', '1', '-W', '1000', str(ip)],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        ttl = None
        m = re.search(r'ttl=(\d+)', out, re.IGNORECASE)
        if m:
            ttl = int(m.group(1))
        return True, ttl
    except Exception:
        return False, None

def scan_host(ip, ports=(22, 80, 443, 445, 139, 3389, 53, 5353, 5900, 631, 5000, 7000, 548, 3306, 5432, 6379, 2375, 9200, 8080, 8443, 1883, 8883, 554, 8000, 9090, 10001)):
    open_ports = []
    hostname = None
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except Exception:
        pass

    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.7)
            s.connect((str(ip), port))
            s.close()
            open_ports.append(port)
        except Exception:
            pass
    latency_ms = measure_latency(ip, open_ports) if open_ports else None
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

    alive_ips = set()
    alive_with_ttl = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping_host, ip): ip for ip in hosts}
        for future in as_completed(futures):
            ip = futures[future]
            is_alive, ttl = future.result()
            if is_alive:
                alive_ips.add(str(ip))
                alive_with_ttl[str(ip)] = ttl

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_host, ip): ip for ip in hosts}
        for future in as_completed(futures):
            res = future.result()
            ip_str = res['ip']
            if ip_str not in alive_ips:
                continue

            hostname = res['hostname']
            mac = res['mac_address']
            ports = res['open_ports']
            services = res['services']
            latency_ms = res['latency_ms']
            ttl = alive_with_ttl.get(ip_str)
            brand = guess_brand(hostname, mac, services)

            if ports:
                device = guess_device_from_hostname(hostname, ports)
                os_name = guess_os_from_ports(ports, hostname)
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
                'open_ports': ports,
                'services': services,
                'server_info': detect_server_info(hostname, ports, services),
            })
    public_ip = get_public_ip()
    isp_info = get_isp_info(public_ip)
    for r in results:
        r['public_ip'] = public_ip
        r['isp_name'] = isp_info.get('isp')
        r['isp_org'] = isp_info.get('org')
    return results, isp_info


def get_public_ip():
    try:
        out = subprocess.check_output(
            ['curl', '-s', '--max-time', '3', 'https://api.ipify.org'],
            text=True, timeout=5,
        )
        ip = out.strip()
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            return ip
    except Exception:
        pass
    return None


def get_isp_info(public_ip=None):
    ip = public_ip or get_public_ip()
    if not ip:
        return {}
    try:
        out = subprocess.check_output(
            ['curl', '-s', '--max-time', '3', f'https://ip-api.com/json/{ip}?fields=isp,org,as,country,regionName,city,status,message'],
            text=True, timeout=5,
        )
        data = json.loads(out)
        if data.get('status') == 'success':
            return {
                'isp': data.get('isp'),
                'org': data.get('org'),
                'as': data.get('as'),
                'country': data.get('country'),
                'region': data.get('regionName'),
                'city': data.get('city'),
            }
    except Exception:
        pass
    return {}


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
