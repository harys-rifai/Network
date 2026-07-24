import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.core.paginator import Paginator
from django.db import connection
from django.core.cache import cache
from apps.scan.models import Scan, IspInfo
from apps.scan.scanner import get_public_ip, get_isp_info, get_wan_interface_info, get_gateway
from .models import DbMaintenance

DASHBOARD_PAGE_SIZE = 10
CLIENTS_PAGE_SIZE = 25
DB_TABLE_PAGE_SIZE = 20

ALLOWED_SORT_FIELDS = {'ip', 'device', 'os', 'brand', 'mac_address', 'scanned_at'}


def _resolve_sort(sort_param, order_param, default_field='scanned_at'):
    sort = sort_param if sort_param in ALLOWED_SORT_FIELDS else default_field
    order = order_param if order_param in ('asc', 'desc') else 'desc'
    db_sort = sort if order == 'asc' else f'-{sort}'
    return db_sort, sort, order


@login_required
def dashboard(request):
    total_devices = Scan.objects.count()
    unique_ip_count = Scan.objects.values('ip').distinct().count()
    os_stats = Scan.objects.values('os').annotate(count=Count('id')).order_by('-count')
    brand_stats = Scan.objects.values('brand').annotate(count=Count('id')).order_by('-count')

    db_sort, current_sort, current_order = _resolve_sort(
        request.GET.get('sort', 'scanned_at'),
        request.GET.get('order', 'desc'),
    )

    page_obj = Paginator(
        Scan.objects.all().order_by(db_sort),
        DASHBOARD_PAGE_SIZE,
    ).get_page(request.GET.get('page', 1))

    context = {
        'total_devices': total_devices,
        'unique_ip_count': unique_ip_count,
        'os_stats': os_stats,
        'brand_stats': brand_stats,
        'recent_scans': page_obj,
        'page_obj': page_obj,
        'current_sort': current_sort,
        'current_order': current_order,
        'os_labels': json.dumps([item['os'] for item in os_stats]),
        'os_data': json.dumps([item['count'] for item in os_stats]),
        'brand_labels': json.dumps([item['brand'] for item in brand_stats]),
        'brand_data': json.dumps([item['count'] for item in brand_stats]),
    }
    return render(request, 'dashboard.html', context)


@login_required
def network_map(request):
    scans = list(Scan.objects.all())
    total = len(scans)
    online = sum(1 for s in scans if s.open_ports)
    gateway_ip = None
    for s in scans:
        if s.gateway:
            gateway_ip = s.gateway
            break

    ISP_ID = -2
    GATEWAY_ID = -1

    # Build node & edge lists — single pass, no duplicate edges
    nodes = []   # ISP placeholder filled after cache lookup
    edges = []
    gateway_node = None

    for scan in scans:
        is_gateway = gateway_ip and str(scan.ip) == str(gateway_ip)
        if is_gateway and gateway_node is None:
            gateway_node = {
                'id': GATEWAY_ID,
                'label': f"Gateway\n{gateway_ip}",
                'title': f"Gateway Router\nOS: {scan.os}\nBrand: {scan.brand or 'Unknown'}",
                'shape': 'icon',
                'icon': {'face': 'FontAwesome', 'code': '\uf6ff', 'size': 50, 'color': '#22c55e'},
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
        # Every device connects to gateway
        edges.append({
            'from': scan.id,
            'to': GATEWAY_ID,
            'color': {'color': '#22c55e', 'highlight': '#facc15'},
        })

    # Gateway node
    if gateway_node is None:
        gateway_node = {
            'id': GATEWAY_ID,
            'label': f"Gateway\n{gateway_ip or '192.168.1.1'}",
            'title': 'Gateway Router',
            'shape': 'icon',
            'icon': {'face': 'FontAwesome', 'code': '\uf6ff', 'size': 50, 'color': '#22c55e'},
            'font': {'color': '#22c55e', 'size': 13,
                     'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'},
        }

    # ISP node (filled below after cache)
    isp_node = {
        'id': ISP_ID,
        'label': 'ISP',
        'title': 'Internet Service Provider',
        'shape': 'icon',
        'icon': {'face': 'FontAwesome', 'code': '\uf0c2', 'size': 50, 'color': '#60a5fa'},
        'font': {'color': '#93c5fd', 'size': 13,
                 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'},
    }

    # ISP → Gateway edge (only once)
    edges.append({'from': ISP_ID, 'to': GATEWAY_ID, 'color': {'color': '#60a5fa', 'highlight': '#93c5fd'}})

    # Cache lookups
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

    # Update ISP node label/title now that we have data
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
        'scans': scans,
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
    scans = Scan.objects.all()

    # Determine gateway IP safely
    gateway_scan = scans.filter(gateway__isnull=False).order_by('-scanned_at').first()
    gateway_ip = gateway_scan.gateway if gateway_scan else None

    if not gateway_ip:
        fallback = scans.filter(router__isnull=False).order_by('-scanned_at').first()
        gateway_ip = fallback.router if fallback else None

    if not gateway_ip:
        gateway_ip = get_gateway()

    # Router info dict
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
    client_qs = scans.exclude(ip=gateway_ip).order_by('-scanned_at') if gateway_ip else scans.order_by('-scanned_at')
    total_clients = client_qs.count()

    # Build lightweight client dicts for current page only (paginate queryset first)
    paginator = Paginator(client_qs, CLIENTS_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    from apps.scan.scanner import mac_to_vendor
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
        'total_devices': scans.count(),
        'total_clients': total_clients,
        'page_obj': page_obj,
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
