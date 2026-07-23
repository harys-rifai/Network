import ipaddress
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    for name, block in interfaces.items():
        if name in ('lo0', 'gif0', 'stf0', 'utun0', 'utun1', 'utun2', 'utun3', 'awdl0', 'llw0', 'bridge0'):
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
        servers = set()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('nameserver['):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    servers.add(parts[1].strip())
        return list(servers)
    except Exception:
        return []

def scan_host(ip, ports=(22, 80, 443, 445, 139, 3389, 53, 5353)):
    open_ports = []
    hostname = None
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except Exception:
        pass
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect((str(ip), port))
            s.close()
            open_ports.append(port)
        except Exception:
            pass
    return {'ip': str(ip), 'open_ports': open_ports, 'hostname': hostname}

def guess_device_from_hostname(hn):
    if not hn:
        return 'Unknown'
    h = hn.lower()
    if 'router' in h or 'gateway' in h or 'gw' in h:
        return 'Router'
    if 'switch' in h:
        return 'Switch'
    if 'server' in h:
        return 'Server'
    if 'pc-' in h or 'laptop' in h or 'macbook' in h or 'imac' in h:
        return 'PC'
    if 'phone' in h or 'iphone' in h or 'android' in h:
        return 'Phone'
    if 'printer' in h:
        return 'Printer'
    if 'firewall' in h:
        return 'Firewall'
    if 'ap' in h or 'access-point' in h:
        return 'Access Point'
    return 'Unknown'

def guess_os_from_ports(open_ports, hostname):
    ports = set(open_ports)
    hn = (hostname or '').lower()
    if 'mac' in hn or 'apple' in hn:
        return 'macOS'
    if 'iphone' in hn or 'ios' in hn:
        return 'iOS'
    if 'android' in hn:
        return 'Android'
    if 445 in ports and 139 in ports:
        return 'Windows'
    if 3389 in ports:
        return 'Windows'
    if 22 in ports and 80 not in ports and 443 not in ports:
        return 'Linux'
    if 22 in ports and (80 in ports or 443 in ports):
        return 'Linux'
    if 80 in ports or 443 in ports:
        return 'Unknown'
    if 53 in ports or 5353 in ports:
        return 'Embedded'
    return 'Unknown'

def guess_brand(hostname, open_ports):
    if not hostname:
        return 'Unknown'
    h = hostname.lower()
    brands = {
        'cisco': ['cisco'], 'ubiquiti': ['ubiquiti', 'unifi', 'dream machine', 'udm'],
        'mikrotik': ['mikrotik', 'routeros'], 'netgear': ['netgear'], 'tp-link': ['tp-link', 'tplink'],
        'asus': ['asus'], 'apple': ['apple', 'macbook', 'imac', 'iphone', 'ipad'],
        'juniper': ['juniper'], 'd-link': ['d-link', 'dlink']
    }
    for brand, keys in brands.items():
        for k in keys:
            if k in h:
                return brand.title()
    return 'Unknown'

def scan_network(subnet=None, max_hosts=254, max_workers=100):
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
                device = guess_device_from_hostname(res['hostname'])
                os_name = guess_os_from_ports(res['open_ports'], res['hostname'])
                brand = guess_brand(res['hostname'], res['open_ports'])
                results.append({
                    'ip': res['ip'],
                    'device': device,
                    'os': os_name,
                    'brand': brand,
                    'gateway': gateway_ip,
                    'router': gateway_ip,
                    'dns': dns_servers[0] if dns_servers else None,
                })
    return results
