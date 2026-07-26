import json
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.db import connection
from django.core.cache import cache
from apps.scan.models import Scan, IspInfo, ConnectionTrace
from apps.scan.scanner import get_public_ip, get_isp_info, get_wan_interface_info, get_gateway, trace_route, get_router_clients
from .models import DbMaintenance

DASHBOARD_PAGE_SIZE = 10
CLIENTS_PAGE_SIZE = 25
DB_TABLE_PAGE_SIZE = 20

ALLOWED_SORT_FIELDS = {'ip', 'device', 'os', 'brand', 'mac_address', 'latency_ms', 'scanned_at'}

COUNTRY_CODES = {
    'United States': 'US', 'China': 'CN', 'Japan': 'JP', 'Germany': 'DE',
    'United Kingdom': 'GB', 'France': 'FR', 'South Korea': 'KR', 'India': 'IN',
    'Canada': 'CA', 'Brazil': 'BR', 'Russia': 'RU', 'Australia': 'AU',
    'Italy': 'IT', 'Spain': 'ES', 'Mexico': 'MX', 'Indonesia': 'ID',
    'Netherlands': 'NL', 'Sweden': 'SE', 'Poland': 'PL', 'Belgium': 'BE',
    'Turkey': 'TR', 'Switzerland': 'CH', 'Taiwan': 'TW', 'Hong Kong': 'HK',
    'Singapore': 'SG', 'Malaysia': 'MY', 'Thailand': 'TH', 'Vietnam': 'VN',
    'Philippines': 'PH', 'United Arab Emirates': 'AE', 'Saudi Arabia': 'SA',
    'South Africa': 'ZA', 'Egypt': 'EG', 'Nigeria': 'NG', 'Kenya': 'KE',
    'Israel': 'IL', 'Ukraine': 'UA', 'Romania': 'RO', 'Bulgaria': 'BG',
    'Croatia': 'HR', 'Czech Republic': 'CZ', 'Slovakia': 'SK', 'Hungary': 'HU',
    'Austria': 'AT', 'Denmark': 'DK', 'Norway': 'NO', 'Finland': 'FI',
    'Ireland': 'IE', 'Portugal': 'PT', 'Greece': 'GR', 'Luxembourg': 'LU',
    'New Zealand': 'NZ', 'Chile': 'CL', 'Argentina': 'AR', 'Colombia': 'CO',
    'Peru': 'PE', 'Venezuela': 'VE', 'Ecuador': 'EC', 'Bolivia': 'BO',
    'Paraguay': 'PY', 'Uruguay': 'UY', 'Dominican Republic': 'DO',
    'Guatemala': 'GT', 'Honduras': 'HN', 'El Salvador': 'SV',
    'Nicaragua': 'NI', 'Costa Rica': 'CR', 'Panama': 'PA',
    'Jamaica': 'JM', 'Trinidad and Tobago': 'TT', 'Bahamas': 'BS',
    'Bangladesh': 'BD', 'Pakistan': 'PK', 'Sri Lanka': 'LK', 'Nepal': 'NP',
    'Myanmar': 'MM', 'Cambodia': 'KH', 'Laos': 'LA', 'Brunei': 'BN',
    'Mongolia': 'MN', 'Iran': 'IR', 'Iraq': 'IQ', 'Qatar': 'QA',
    'Kuwait': 'KW', 'Bahrain': 'BH', 'Oman': 'OM', 'Jordan': 'JO',
    'Lebanon': 'LB', 'Kazakhstan': 'KZ', 'Uzbekistan': 'UZ',
    'Azerbaijan': 'AZ', 'Georgia': 'GE', 'Armenia': 'AM', 'Moldova': 'MD',
    'Lithuania': 'LT', 'Latvia': 'LV', 'Estonia': 'EE', 'Slovenia': 'SI',
    'Serbia': 'RS', 'North Macedonia': 'MK', 'Albania': 'AL',
    'Bosnia and Herzegovina': 'BA', 'Montenegro': 'ME', 'Cyprus': 'CY',
    'Malta': 'MT', 'Iceland': 'IS', 'Morocco': 'MA', 'Algeria': 'DZ',
    'Tunisia': 'TN', 'Libya': 'LY', 'Sudan': 'SD', 'Ethiopia': 'ET',
    'Somalia': 'SO', 'Djibouti': 'DJ', 'Eritrea': 'ER', 'Chad': 'TD',
    'Niger': 'NE', 'Mali': 'ML', 'Burkina Faso': 'BF', 'Guinea': 'GN',
    'Sierra Leone': 'SL', 'Gambia': 'GM', 'Mauritania': 'MR',
    'Cape Verde': 'CV', 'Gabon': 'GA', 'Republic of the Congo': 'CG',
    'Democratic Republic of the Congo': 'CD', 'Angola': 'AO',
    'Mozambique': 'MZ', 'Zimbabwe': 'ZW', 'Zambia': 'ZM',
    'Malawi': 'MW', 'Tanzania': 'TZ', 'Uganda': 'UG', 'Rwanda': 'RW',
    'Madagascar': 'MG', 'Mauritius': 'MU', 'Seychelles': 'SC',
    'Maldives': 'MV', 'Bhutan': 'BT', 'Timor-Leste': 'TL',
    'Papua New Guinea': 'PG', 'Fiji': 'FJ',
}


def _resolve_sort(sort_param, order_param, default_field='scanned_at'):
    sort = sort_param if sort_param in ALLOWED_SORT_FIELDS else default_field
    order = order_param if order_param in ('asc', 'desc') else 'desc'
    db_sort = sort if order == 'asc' else f'-{sort}'
    return db_sort, sort, order


@login_required
def dashboard(request):
    cache_key = 'dashboard_stats'
    stats = cache.get(cache_key)
    if stats is None:
        stats = {
            'total_devices': Scan.objects.count(),
            'unique_ip_count': Scan.objects.values('ip').distinct().count(),
            'os_stats': list(Scan.objects.values('os').annotate(count=Count('id')).order_by('-count')[:20]),
            'brand_stats': list(Scan.objects.values('brand').annotate(count=Count('id')).order_by('-count')[:20]),
        }
        cache.set(cache_key, stats, 300)

    db_sort, current_sort, current_order = _resolve_sort(
        request.GET.get('sort', 'scanned_at'),
        request.GET.get('order', 'desc'),
    )

    page_obj = Paginator(
        Scan.objects.all().order_by(db_sort),
        DASHBOARD_PAGE_SIZE,
    ).get_page(request.GET.get('page', 1))

    context = {
        'total_devices': stats['total_devices'],
        'unique_ip_count': stats['unique_ip_count'],
        'os_stats': stats['os_stats'],
        'brand_stats': stats['brand_stats'],
        'recent_scans': page_obj,
        'page_obj': page_obj,
        'current_sort': current_sort,
        'current_order': current_order,
        'os_labels': json.dumps([item['os'] for item in stats['os_stats']]),
        'os_data': json.dumps([item['count'] for item in stats['os_stats']]),
        'brand_labels': json.dumps([item['brand'] for item in stats['brand_stats']]),
        'brand_data': json.dumps([item['count'] for item in stats['brand_stats']]),
    }
    return render(request, 'dashboard.html', context)


@login_required
def network_map(request):
    base_qs = Scan.objects.all()
    total = base_qs.count()
    online = base_qs.filter(open_ports__isnull=False).exclude(open_ports=[]).count()

    gateway_ip = cache.get('network_gateway_ip')
    if gateway_ip is None:
        gs = base_qs.filter(gateway__isnull=False).order_by('-scanned_at').first()
        gateway_ip = gs.gateway if gs else None
        if not gateway_ip:
            rf = base_qs.filter(router__isnull=False).order_by('-scanned_at').first()
            gateway_ip = rf.router if rf else None
        if not gateway_ip:
            gateway_ip = get_gateway()
        cache.set('network_gateway_ip', gateway_ip or '', 300)

    gateway_scan = base_qs.filter(gateway=gateway_ip).order_by('-scanned_at').first() if gateway_ip else None
    gateway_node = None

    # Only fetch a limited page of devices for the map to keep it responsive
    device_paginator = Paginator(base_qs.order_by('-scanned_at'), 20)
    device_page = device_paginator.get_page(request.GET.get('device_page', 1))
    device_list = list(device_page.object_list)

    ISP_ID = -2
    GATEWAY_ID = -1

    nodes = []
    edges = []

    for scan in device_list:
        is_gateway = gateway_ip and str(scan.ip) == str(gateway_ip)
        if is_gateway and gateway_node is None:
            gateway_node = {
                'id': GATEWAY_ID,
                'label': f"Gateway\n{gateway_ip}",
                'title': f"Gateway Router\nOS: {scan.os}\nBrand: {scan.brand or 'Unknown'}",
                'shape': 'image',
                'image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2VmNDQ0NCIgZmlsbC1vcGFjaXR5PSIwLjg1Ij48cGF0aCBkPSJNMTIgMkM2LjQ4IDIgMiA2LjQ4IDIgMTJzNC40OCAxMCAxMCAxMCAxMC00LjQ4IDEwLTEwUzE3LjUyIDIgMTIgMnptLTEgMTcuOTNjLTMuOTUtLjQ5LTctMy44NS03LTcuOTMgMC0uNjIuMDgtMS4yMS4yMS0xLjc5TDkgMTV2MWMwIDEuMS45IDIgMiAydjEuOTN6bTYuOS0yLjU0Yy0uMjYtLjgxLTEtMS4zOS0xLjktMS4zOWgtMXYtM2MwLS41NS0uNDUtMS0xLTFIOHYtMmgyYy41NSAwIDEtLjQ1IDEtMVY3aDJjMS4xIDAgMi0uOSAyLTJ2LS40MWMyLjkzIDEuMTkgNSA0LjA2IDUgNy40MSAwIDIuMDgtLjggMy45Ny0yLjEgNS4zOXoiLz48L3N2Zz4=',
                'size': 35,
                'font': {'color': '#22c55e', 'size': 13,
                         'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'},
            }
        nodes.append({
            'id': scan.id,
            'label': f"{scan.ip}\n{scan.device}",
            'title': f"{scan.os} · {scan.brand or 'Unknown'}\nLatency: {scan.latency_ms or 'N/A'} ms",
            'color': '#22c55e' if is_gateway else '#facc15',
            'font': {'color': '#e5e7eb', 'size': 12},
        })

        if scan.open_ports:
            edge_color = {'color': '#3b82f6', 'highlight': '#60a5fa'}
        elif scan.latency_ms is not None:
            edge_color = {'color': '#facc15', 'highlight': '#fde047'}
        else:
            edge_color = {'color': '#ef4444', 'highlight': '#f87171'}

        edges.append({
            'from': scan.id,
            'to': GATEWAY_ID,
            'color': edge_color,
        })

    if gateway_node is None:
        gateway_node = {
            'id': GATEWAY_ID,
            'label': f"Gateway\n{gateway_ip or '192.168.1.1'}",
            'title': 'Gateway Router',
            'shape': 'image',
            'image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2VmNDQ0NCIgZmlsbC1vcGFjaXR5PSIwLjg1Ij48cGF0aCBkPSJNMTIgMkM2LjQ4IDIgMiA2LjQ4IDIgMTJzNC40OCAxMCAxMCAxMCAxMC00LjQ4IDEwLTEwUzE3LjUyIDIgMTIgMnptLTEgMTcuOTNjLTMuOTUtLjQ5LTctMy44NS03LTcuOTMgMC0uNjIuMDgtMS4yMS4yMS0xLjc5TDkgMTV2MWMwIDEuMS45IDIgMiAydjEuOTN6bTYuOS0yLjU0Yy0uMjYtLjgxLTEtMS4zOS0xLjktMS4zOWgtMXYtM2MwLS41NS0uNDUtMS0xLTFIOHYtMmgyYy41NSAwIDEtLjQ1IDEtMVY3aDJjMS4xIDAgMi0uOSAyLTJ2LS40MWMyLjkzIDEuMTkgNSA0LjA2IDUgNy40MSAwIDIuMDgtLjggMy45Ny0yLjEgNS4zOXoiLz48L3N2Zz4=',
            'size': 35,
            'font': {'color': '#22c55e', 'size': 13,
                     'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'},
        }

    isp_node = {
        'id': ISP_ID,
        'label': 'ISP',
        'title': 'Internet Service Provider',
        'shape': 'image',
        'image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiIGZpbGwtb3BhY2l0eT0iMC44NSI+PHBhdGggZD0iTTE5LjM1IDEwLjA0QzE4LjY3IDYuNTkgMTUuNjQgNCAxMiA0IDkuMTEgNCA2LjYgNS42NCA1LjM1IDguMDQgMi4zNCA4LjM2IDAgMTAuOTEgMCAxNGMwIDMuMzEgMi42OSA2IDYgNmgxM2MyLjc2IDAgNS0yLjI0IDUtNSAwLTIuNjQtMi4wNS00Ljc4LTQuNjUtNC45NnoiLz48L3N2Zz4=',
        'size': 35,
        'font': {'color': '#93c5fd', 'size': 13,
                 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'},
    }

    edges.append({'from': ISP_ID, 'to': GATEWAY_ID, 'color': {'color': '#60a5fa', 'highlight': '#93c5fd'}})

    public_ip = cache.get('network_public_ip')
    isp_info = cache.get('network_isp_info') or {}
    wan_info = cache.get('network_wan_info') or {}
    if public_ip is None:
        public_ip = get_public_ip()
        cache.set('network_public_ip', public_ip, 300)
    if not isp_info:
        isp_info = get_isp_info(public_ip) or {}
        cache.set('network_isp_info', isp_info, 300)
    if not wan_info:
        wan_info = get_wan_interface_info() or {}
        cache.set('network_wan_info', wan_info, 300)

    isp_label = isp_info.get('isp') or isp_info.get('org') or 'ISP'
    isp_title_parts = []
    for key, label in [('isp', 'ISP'), ('org', 'Org'), ('as', 'AS')]:
        if isp_info.get(key):
            isp_title_parts.append(f"{label}: {isp_info[key]}")
    if public_ip:
        isp_title_parts.append(f"Public IP: {public_ip}")
    loc = ', '.join(filter(None, [isp_info.get('city'), isp_info.get('region'), isp_info.get('country')]))
    if loc:
        isp_title_parts.append(f"Location: {loc}")
    if wan_info.get('interface'):
        isp_title_parts.append(f"Interface: {wan_info['interface']}")
    isp_node['label'] = isp_label
    isp_node['title'] = '\n'.join(isp_title_parts) or 'Internet Service Provider'

    all_nodes = [isp_node, gateway_node] + nodes
    networks = {'nodes': all_nodes, 'edges': edges}

    return render(request, 'network_map.html', {
        'networks': json.dumps(networks),
        'total_devices': total,
        'online_count': online,
        'gateway_ip': gateway_ip or '192.168.1.1',
        'scans': device_list,
        'device_page': device_page,
        'isp_name': isp_info.get('isp') or 'Unknown',
        'isp_org': isp_info.get('org') or 'Unknown',
        'public_ip': public_ip or 'Unknown',
        'isp_location': loc or 'Unknown',
        'isp_as': isp_info.get('as') or 'Unknown',
        'wan_interface': wan_info.get('interface') or 'Unknown',
        'wan_media': wan_info.get('media') or 'Unknown',
    })


@login_required
def router_clients(request):
    base_qs = Scan.objects.all()

    # Determine gateway IP safely
    gateway_ip = cache.get('network_gateway_ip')
    if gateway_ip is None:
        gs = base_qs.filter(gateway__isnull=False).order_by('-scanned_at').first()
        gateway_ip = gs.gateway if gs else None
        if not gateway_ip:
            rf = base_qs.filter(router__isnull=False).order_by('-scanned_at').first()
            gateway_ip = rf.router if rf else None
        if not gateway_ip:
            gateway_ip = get_gateway()
        cache.set('network_gateway_ip', gateway_ip or '', 300)

    # Router info dict
    gateway_scan = base_qs.filter(gateway=gateway_ip).order_by('-scanned_at').first() if gateway_ip else None
    if gateway_scan:
        router_info = {
            'ip': gateway_ip or gateway_scan.ip,
            'device': gateway_scan.device,
            'os': gateway_scan.os,
            'brand': gateway_scan.brand or 'Unknown',
            'mac_address': gateway_scan.mac_address or 'Unknown',
            'latency_ms': gateway_scan.latency_ms,
            'open_ports': gateway_scan.open_ports or [],
            'services': gateway_scan.services or {},
            'server_info': gateway_scan.server_info,
            'dns': gateway_scan.dns,
            'scanned_at': gateway_scan.scanned_at,
        }
    else:
        router_info = {
            'ip': gateway_ip or 'Unknown',
            'device': 'Unknown', 'os': 'Unknown', 'brand': 'Unknown',
            'mac_address': 'Unknown', 'latency_ms': None,
            'open_ports': [], 'services': {}, 'server_info': None,
            'dns': None, 'scanned_at': None,
        }

    # Cache ISP / WAN info
    public_ip = cache.get('network_public_ip')
    isp_info = cache.get('network_isp_info') or {}
    wan_info = cache.get('network_wan_info') or {}
    if public_ip is None:
        public_ip = get_public_ip()
        cache.set('network_public_ip', public_ip, 300)
    if not isp_info:
        isp_info = get_isp_info(public_ip) or {}
        cache.set('network_isp_info', isp_info, 300)
    if not wan_info:
        wan_info = get_wan_interface_info() or {}
        cache.set('network_wan_info', wan_info, 300)

    db_isp = IspInfo.objects.filter(ip=public_ip).first() if public_ip else None
    router_isp = {
        'isp':     (db_isp.isp     if db_isp else None) or isp_info.get('isp')     or 'Unknown',
        'org':     (db_isp.org     if db_isp else None) or isp_info.get('org')     or 'Unknown',
        'as':      (db_isp.as_number if db_isp else None) or isp_info.get('as')   or 'Unknown',
        'country': (db_isp.country if db_isp else None) or isp_info.get('country') or 'Unknown',
        'region':  (db_isp.region  if db_isp else None) or isp_info.get('region')  or 'Unknown',
        'city':    (db_isp.city    if db_isp else None) or isp_info.get('city')    or 'Unknown',
    }

    # Build client queryset (exclude gateway IP if known)
    client_qs = base_qs.exclude(ip=gateway_ip).order_by('-scanned_at') if gateway_ip else base_qs.order_by('-scanned_at')
    total_clients = client_qs.count()

    # Search filter
    search_query = request.GET.get('q', '').strip()
    if search_query:
        client_qs = client_qs.filter(
            Q(ip__icontains=search_query) |
            Q(device__icontains=search_query) |
            Q(os__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(mac_address__icontains=search_query) |
            Q(isp_name__icontains=search_query) |
            Q(public_ip__icontains=search_query)
        )
    total_filtered = client_qs.count()

    # Build lightweight client dicts for current page only (paginate queryset first)
    paginator = Paginator(client_qs, CLIENTS_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    client_list = []
    for scan in page_obj.object_list:
        mac = scan.mac_address
        client_list.append({
            'ip': scan.ip,
            'device': scan.device,
            'os': scan.os,
            'brand': scan.brand or 'Unknown',
            'mac_address': mac or '—',
            'vendor': mac_to_vendor(mac) if mac else 'Unknown',
            'latency_ms': scan.latency_ms if scan.latency_ms is not None else '—',
            'open_ports': scan.open_ports or [],
            'services': scan.services or {},
            'gateway': scan.gateway,
            'dns': scan.dns,
            'public_ip': scan.public_ip,
            'isp_name': scan.isp_name or router_isp.get('isp'),
            'isp_org': scan.isp_org or router_isp.get('org'),
            'scanned_at': scan.scanned_at,
        })

    return render(request, 'router_clients.html', {
        'router': router_info,
        'router_isp': router_isp,
        'router_wan': wan_info,
        'public_ip': public_ip or 'Unknown',
        'clients': client_list,
        'total_devices': base_qs.count(),
        'total_clients': total_clients,
        'total_filtered': total_filtered,
        'page_obj': page_obj,
        'search_query': search_query,
    })

    return render(request, 'router_clients.html', {
        'router': router_info,
        'router_isp': router_isp,
        'router_wan': wan_info,
        'public_ip': public_ip or 'Unknown',
        'clients': client_list,
        'total_devices': scans.count(),
        'total_clients': total_clients,
        'total_filtered': total_filtered,
        'page_obj': page_obj,
        'search_query': search_query,
    })


@login_required
def analytics(request):
    cache_key = 'analytics_page'
    ctx = cache.get(cache_key)
    if ctx is None:
        traces = ConnectionTrace.objects.all()
        scans = Scan.objects.all()

        total_traces = traces.count()
        total_devices = scans.count()

        dest_counter = Counter()
        country_counter = Counter()
        org_counter = Counter()
        ip_counter = Counter()
        total_hops = 0

        for t in traces.only('destination', 'destination_ip', 'hops')[:500]:
            dest_counter[t.destination] += 1
            if t.destination_ip:
                ip_counter[t.destination_ip] += 1
            hops = t.hops or []
            total_hops += len(hops)
            for hop in hops:
                country = hop.get('country') or 'Unknown'
                org = hop.get('org') or 'Unknown'
                if country and country not in ('Local', 'LAN', 'Private'):
                    country_counter[country] += 1
                if org:
                    org_counter[org] += 1

        top_destinations = dest_counter.most_common(15)
        top_countries = country_counter.most_common(15)
        top_orgs = org_counter.most_common(15)
        top_dest_ips = ip_counter.most_common(15)

        world_map_data = {}
        for country, count in country_counter.most_common():
            code = COUNTRY_CODES.get(country)
            if code:
                world_map_data[code] = count

        os_stats = list(scans.values('os').annotate(count=Count('id')).order_by('-count'))
        brand_stats = list(scans.values('brand').annotate(count=Count('id')).order_by('-count'))
        device_type_stats = list(scans.values('device').annotate(count=Count('id')).order_by('-count'))

        recent_traces_qs = list(traces.order_by('-created_at')[:15])

        ctx = {
            'total_traces': total_traces,
            'total_devices': total_devices,
            'total_hops': total_hops,
            'unique_destinations': len(dest_counter),
            'unique_countries': len(country_counter),
            'top_destinations': top_destinations,
            'top_countries': top_countries,
            'top_orgs': top_orgs,
            'top_dest_ips': top_dest_ips,
            'os_stats': os_stats,
            'brand_stats': brand_stats,
            'device_type_stats': device_type_stats,
            'recent_traces': recent_traces_qs,
            'chart_top_dest_labels': json.dumps([item[0] for item in top_destinations]),
            'chart_top_dest_data': json.dumps([item[1] for item in top_destinations]),
            'chart_country_labels': json.dumps([item[0] for item in top_countries]),
            'chart_country_data': json.dumps([item[1] for item in top_countries]),
            'chart_os_labels': json.dumps([item['os'] for item in os_stats]),
            'chart_os_data': json.dumps([item['count'] for item in os_stats]),
            'chart_brand_labels': json.dumps([item['brand'] for item in brand_stats]),
            'chart_brand_data': json.dumps([item['count'] for item in brand_stats]),
            'chart_country_map': json.dumps(world_map_data),
        }
        cache.set(cache_key, ctx, 300)

    router_clients = cache.get('router_clients')
    if router_clients is None:
        try:
            router_clients = get_router_clients()
            cache.set('router_clients', router_clients, 120)
        except Exception:
            cache.set('router_clients', [], 300)
            router_clients = []

    ctx = dict(ctx)
    ctx['router_clients_count'] = len(router_clients)
    ctx['recent_traces'] = Paginator(ctx.get('recent_traces', []), 15).get_page(request.GET.get('analytics_trace_page', 1))
    ctx['top_destinations'] = Paginator(ctx.get('top_destinations', []), 10).get_page(request.GET.get('dest_page', 1))
    ctx['top_countries'] = Paginator(ctx.get('top_countries', []), 10).get_page(request.GET.get('country_page', 1))

    return render(request, 'analytics.html', ctx)


@login_required
def trace_connection(request):
    traces = []
    error = None
    destination = ''
    dest_ip = None
    result = None
    router_clients = []
    trace_id = None

    if request.method == 'POST':
        destination = request.POST.get('destination', '').strip()
        if destination:
            parsed = urlparse(destination)
            hostname = parsed.hostname or parsed.path.split('/')[0] if parsed.path else destination
            if not hostname:
                hostname = destination.replace('https://', '').replace('http://', '').split('/')[0]

            destination = hostname
            try:
                import socket
                dest_ip = socket.gethostbyname(destination)
            except Exception:
                dest_ip = destination

            trace_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
            try:
                ConnectionTrace.objects.create(
                    destination=destination,
                    destination_ip=dest_ip,
                    status=ConnectionTrace.STATUS_RUNNING,
                    trace_id=trace_id,
                )
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': f'Failed to start trace: {e}'}, status=400)
                error = f'Failed to start trace: {e}'
                trace_id = None
                cache.delete('analytics_page')
                destination = ''
                dest_ip = None
            else:
                cache.delete('analytics_page')

                cache.set(f'trace_progress_{trace_id}', {'status': 'running', 'hops': []}, 300)

                try:
                    import threading
                    def run_trace():
                        try:
                            result = trace_route(destination)
                            hops = result.get('hops', [])
                            cache.set(f'trace_progress_{trace_id}', {'status': 'done', 'hops': hops}, 300)
                            ConnectionTrace.objects.filter(trace_id=trace_id).update(
                                status=ConnectionTrace.STATUS_DONE,
                                hops=hops,
                                error=result.get('error'),
                            )
                        except Exception as e:
                            cache.set(f'trace_progress_{trace_id}', {'status': 'error', 'hops': [], 'error': str(e)}, 300)
                            ConnectionTrace.objects.filter(trace_id=trace_id).update(
                                status=ConnectionTrace.STATUS_ERROR,
                                error=str(e),
                            )

                    thread = threading.Thread(target=run_trace, daemon=True)
                    thread.start()
                except Exception as e:
                    error = str(e)
                    ConnectionTrace.objects.filter(trace_id=trace_id).update(
                        status=ConnectionTrace.STATUS_ERROR,
                        error=str(e),
                    )

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'trace_id': trace_id,
                    'destination': destination,
                    'destination_ip': dest_ip,
                    'error': error,
                })

    recent_traces_qs = ConnectionTrace.objects.all()
    recent_paginator = Paginator(recent_traces_qs, 15)
    recent_page = recent_paginator.get_page(request.GET.get('trace_page', 1))

    router_clients = cache.get('router_clients')
    if router_clients is None:
        try:
            from apps.scan.scanner import get_router_clients
            router_clients = get_router_clients()
            cache.set('router_clients', router_clients, 120)
        except Exception:
            router_clients = []

    return render(request, 'trace_connection.html', {
        'recent_traces': recent_page,
        'destination': destination,
        'dest_ip': dest_ip,
        'result': result,
        'error': error,
        'router_clients': router_clients,
        'trace_id': trace_id,
    })


@login_required
def db_maintenance(request):
    db_vendor = connection.vendor
    table_stats = {}
    raw_tables = []
    error = None
    message = None

    if db_vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            raw_tables = [row[0] for row in cursor.fetchall()]

            for table in raw_tables:
                cursor.execute(
                    "SELECT pg_size_pretty(pg_total_relation_size(%s));", [table]
                )
                size = cursor.fetchone()[0]

                # Safe row count via pg_class to avoid SQL injection risk
                cursor.execute(
                    "SELECT reltuples::bigint FROM pg_class WHERE relname = %s;", [table]
                )
                row = cursor.fetchone()
                count = row[0] if row else 0

                cursor.execute(
                    "SELECT COUNT(*) FROM pg_indexes WHERE tablename = %s;", [table]
                )
                idx_count = cursor.fetchone()[0]

                table_stats[table] = {'size': size, 'count': count, 'index_count': idx_count}

    if request.method == 'POST':
        action = request.POST.get('action')
        selected_tables = request.POST.getlist('selected_tables')
        single_table = request.POST.get('table_name')
        tables_to_process = selected_tables or ([single_table] if single_table else [])

        # Validate table names against known tables to prevent injection
        tables_to_process = [t for t in tables_to_process if t in raw_tables]

        processed = 0
        for table_name in tables_to_process:
            try:
                with connection.cursor() as cursor:
                    if action == 'vacuum':
                        cursor.execute(f'VACUUM FULL "{table_name}";')
                        status_field = 'vacuum_status'
                    elif action in ('reindex', 'indexes'):
                        cursor.execute(f'REINDEX TABLE "{table_name}";')
                        status_field = 'rebuild_status' if action == 'reindex' else 'index_status'
                    else:
                        continue
                record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                setattr(record, status_field, 'Done')
                record.last_maintenance = datetime.now()
                record.save()
                processed += 1
            except Exception as e:
                error = str(e)
                break

        if not error and processed:
            label = {'vacuum': 'VACUUM FULL', 'reindex': 'Reindex', 'indexes': 'Index rebuild'}.get(action, action)
            message = f'{label} completed on {processed} table{"s" if processed > 1 else ""}.'

    # Assemble rows for display
    maintenance_records = []
    for table in raw_tables:
        record, _ = DbMaintenance.objects.get_or_create(table_name=table)
        stats = table_stats.get(table, {})
        maintenance_records.append({
            'table_name': table,
            'vacuum_status': record.vacuum_status,
            'index_status': record.index_status,
            'rebuild_status': record.rebuild_status,
            'record_count': stats.get('count', '-'),
            'table_size': stats.get('size', '-'),
            'last_maintenance': record.last_maintenance,
        })

    # Paginate the table list
    paginator = Paginator(maintenance_records, DB_TABLE_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'db_maintenance.html', {
        'tables': page_obj.object_list,
        'page_obj': page_obj,
        'all_tables': raw_tables,        # needed for checkbox validation JS
        'db_vendor': db_vendor,
        'error': error,
        'message': message,
    })
