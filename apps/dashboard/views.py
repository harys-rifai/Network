import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from apps.scan.models import Scan, ScanPort, ScanMacHistory, IspInfo
from apps.scan.scanner import get_public_ip, get_isp_info, get_wan_interface_info
from .models import DbMaintenance
from .models import DbMaintenance

@login_required
def dashboard(request):
    total_devices = Scan.objects.count()
    os_stats = Scan.objects.values('os').annotate(count=Count('id')).order_by('-count')
    brand_stats = Scan.objects.values('brand').annotate(count=Count('id')).order_by('-count')

    sort = request.GET.get('sort', '-scanned_at')
    order = request.GET.get('order', 'desc')
    allowed = {'ip', 'device', 'os', 'brand', 'mac_address', 'scanned_at'}
    if sort not in allowed:
        sort = '-scanned_at'
    if order not in {'asc', 'desc'}:
        order = 'desc'
    if order == 'asc' and sort.startswith('-'):
        sort = sort[1:]
    elif order == 'desc' and not sort.startswith('-'):
        sort = f'-{sort}'

    recent_page = Paginator(Scan.objects.all().order_by(sort), 10).get_page(request.GET.get('page', 1))

    os_labels = [item['os'] for item in os_stats]
    os_data = [item['count'] for item in os_stats]
    brand_labels = [item['brand'] for item in brand_stats]
    brand_data = [item['count'] for item in brand_stats]

    context = {
        'total_devices': total_devices,
        'os_stats': os_stats,
        'brand_stats': brand_stats,
        'recent_scans': recent_page,
        'page_obj': recent_page,
        'current_sort': sort if not sort.startswith('-') else sort[1:],
        'current_order': order,
        'os_labels': json.dumps(os_labels),
        'os_data': json.dumps(os_data),
        'brand_labels': json.dumps(brand_labels),
        'brand_data': json.dumps(brand_data),
    }
    return render(request, 'dashboard.html', context)

@login_required
def network_map(request):
    scans = Scan.objects.all()
    total = scans.count()
    online = scans.filter(open_ports__isnull=False).exclude(open_ports=[]).count()
    gateway_ip = scans.filter(gateway__isnull=False).values_list('gateway', flat=True).first()

    ISP_ID = -2
    GATEWAY_ID = -1

    nodes = [
        {
            'id': ISP_ID,
            'label': 'ISP',
            'title': 'Internet Service Provider',
            'shape': 'icon',
            'icon': { 'face': 'FontAwesome', 'code': '\uf0c2', 'size': 50, 'color': '#60a5fa' },
            'font': { 'color': '#93c5fd', 'size': 13, 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
        },
    ]
    edges = []

    gateway_node = None
    for scan in scans:
        is_gateway = scan.gateway and str(scan.gateway) == str(gateway_ip)
        if is_gateway:
            gateway_node = {
                'id': GATEWAY_ID,
                'label': f"Gateway\n{gateway_ip}",
                'title': f"Gateway Router\nOS: {scan.os}\nBrand: {scan.brand or 'Unknown'}",
                'shape': 'icon',
                'icon': { 'face': 'FontAwesome', 'code': '\uf6ff', 'size': 50, 'color': '#22c55e' },
                'font': { 'color': '#22c55e', 'size': 13, 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
            }
        nodes.append({
            'id': scan.id,
            'label': f"{scan.ip}\n{scan.device}",
            'title': f"{scan.os} · {scan.brand or 'Unknown'}\nLatency: {scan.latency_ms or 'N/A'} ms",
            'color': '#22c55e' if is_gateway else '#facc15',
            'font': { 'color': '#e5e7eb', 'size': 12 }
        })
        if scan.gateway and not is_gateway:
            edges.append({
                'from': scan.id, 'to': GATEWAY_ID,
                'color': { 'color': '#22c55e', 'highlight': '#facc15' }
            })

    if gateway_node:
        nodes[0] = gateway_node

    if not gateway_node:
        nodes.insert(1, {
            'id': GATEWAY_ID,
            'label': f"Gateway\n{gateway_ip or '192.168.1.1'}",
            'title': 'Gateway Router',
            'shape': 'icon',
            'icon': { 'face': 'FontAwesome', 'code': '\uf6ff', 'size': 50, 'color': '#22c55e' },
            'font': { 'color': '#22c55e', 'size': 13, 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
        })
        for scan in scans:
            edges.append({
                'from': scan.id, 'to': GATEWAY_ID,
                'color': { 'color': '#22c55e', 'highlight': '#facc15' }
            })

    if gateway_node:
        edges.append({
            'from': ISP_ID, 'to': GATEWAY_ID,
            'color': { 'color': '#60a5fa', 'highlight': '#93c5fd' }
        })
    else:
        edges.append({
            'from': ISP_ID, 'to': GATEWAY_ID,
            'color': { 'color': '#60a5fa', 'highlight': '#93c5fd' }
        })
        for scan in scans:
            edges.append({
                'from': scan.id, 'to': GATEWAY_ID,
                'color': { 'color': '#22c55e', 'highlight': '#facc15' }
            })

    networks = {'nodes': nodes, 'edges': edges}

    public_ip = cache.get('network_public_ip')
    isp_info = cache.get('network_isp_info')
    wan_info = cache.get('network_wan_info')
    if public_ip is None:
        public_ip = get_public_ip()
        cache.set('network_public_ip', public_ip, 300)
    if isp_info is None:
        isp_info = get_isp_info(public_ip)
        cache.set('network_isp_info', isp_info, 300)
    if wan_info is None:
        wan_info = get_wan_interface_info()
        cache.set('network_wan_info', wan_info, 300)

    isp_label = isp_info.get('isp') or isp_info.get('org') or 'ISP'
    isp_title_parts = []
    if isp_info.get('isp'):
        isp_title_parts.append(f"ISP: {isp_info['isp']}")
    if isp_info.get('org'):
        isp_title_parts.append(f"Org: {isp_info['org']}")
    if public_ip:
        isp_title_parts.append(f"Public IP: {public_ip}")
    if isp_info.get('city') or isp_info.get('region') or isp_info.get('country'):
        loc = ', '.join(filter(None, [isp_info.get('city'), isp_info.get('region'), isp_info.get('country')]))
        isp_title_parts.append(f"Location: {loc}")
    if isp_info.get('as'):
        isp_title_parts.append(f"AS: {isp_info['as']}")
    if wan_info.get('interface'):
        isp_title_parts.append(f"Interface: {wan_info['interface']}")
    if wan_info.get('media'):
        isp_title_parts.append(f"Media: {wan_info['media']}")
    isp_title = '\n'.join(isp_title_parts) if isp_title_parts else 'Internet Service Provider'

    nodes[0] = {
        'id': ISP_ID,
        'label': isp_label,
        'title': isp_title,
        'shape': 'icon',
        'icon': { 'face': 'FontAwesome', 'code': '\uf0c2', 'size': 50, 'color': '#60a5fa' },
        'font': { 'color': '#93c5fd', 'size': 13, 'face': 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
    }

    return render(request, 'network_map.html', {
        'networks': json.dumps(networks),
        'total_devices': total,
        'online_count': online,
        'gateway_ip': gateway_ip or '192.168.1.1',
        'scans': scans,
        'isp_name': isp_info.get('isp') or 'Unknown',
        'isp_org': isp_info.get('org') or 'Unknown',
        'public_ip': public_ip or 'Unknown',
        'isp_location': ', '.join(filter(None, [isp_info.get('city'), isp_info.get('region'), isp_info.get('country')])) or 'Unknown',
        'isp_as': isp_info.get('as') or 'Unknown',
        'wan_interface': wan_info.get('interface') or 'Unknown',
        'wan_media': wan_info.get('media') or 'Unknown',
    })


@login_required
def router_clients(request):
    scans = Scan.objects.all()
    gateway_scan = scans.filter(gateway__isnull=False).order_by('-scanned_at').first()
    gateway_ip = gateway_scan.gateway if gateway_scan else None
    if not gateway_ip:
        gateway_ip = scans.filter(router__isnull=False).order_by('-scanned_at').first().router if scans.filter(router__isnull=False).exists() else None
    if not gateway_ip:
        gateway_ip = get_gateway()

    router_info = {
        'ip': gateway_ip,
        'device': gateway_scan.device if gateway_scan else 'Unknown',
        'os': gateway_scan.os if gateway_scan else 'Unknown',
        'brand': gateway_scan.brand or 'Unknown' if gateway_scan else 'Unknown',
        'mac_address': gateway_scan.mac_address or 'Unknown' if gateway_scan else 'Unknown',
        'latency_ms': gateway_scan.latency_ms if gateway_scan else None,
        'open_ports': gateway_scan.open_ports if gateway_scan else [],
        'services': gateway_scan.services if gateway_scan else {},
        'server_info': gateway_scan.server_info if gateway_scan else None,
        'dns': gateway_scan.dns if gateway_scan else None,
        'scanned_at': gateway_scan.scanned_at if gateway_scan else None,
    }

    public_ip = cache.get('network_public_ip')
    isp_info = cache.get('network_isp_info')
    wan_info = cache.get('network_wan_info')
    if public_ip is None:
        public_ip = get_public_ip()
        cache.set('network_public_ip', public_ip, 300)
    if isp_info is None:
        isp_info = get_isp_info(public_ip)
        cache.set('network_isp_info', isp_info, 300)
    if wan_info is None:
        wan_info = get_wan_interface_info()
        cache.set('network_wan_info', wan_info, 300)

    db_isp = IspInfo.objects.filter(ip=public_ip).first() if public_ip else None
    if db_isp:
        router_isp = {
            'isp': db_isp.isp or isp_info.get('isp') or 'Unknown',
            'org': db_isp.org or isp_info.get('org') or 'Unknown',
            'as': db_isp.as_number or isp_info.get('as') or 'Unknown',
            'country': db_isp.country or isp_info.get('country') or 'Unknown',
            'region': db_isp.region or isp_info.get('region') or 'Unknown',
            'city': db_isp.city or isp_info.get('city') or 'Unknown',
        }
    else:
        router_isp = {
            'isp': isp_info.get('isp') or 'Unknown',
            'org': isp_info.get('org') or 'Unknown',
            'as': isp_info.get('as') or 'Unknown',
            'country': isp_info.get('country') or 'Unknown',
            'region': isp_info.get('region') or 'Unknown',
            'city': isp_info.get('city') or 'Unknown',
        }

    clients = scans.exclude(ip=gateway_ip).order_by('-scanned_at') if gateway_ip else scans.order_by('-scanned_at')
    client_list = []
    for scan in clients:
        mac = scan.mac_address
        if mac:
            from apps.scan.scanner import mac_to_vendor
            vendor = mac_to_vendor(mac)
        else:
            vendor = 'Unknown'
        client_list.append({
            'ip': scan.ip,
            'device': scan.device,
            'os': scan.os,
            'brand': scan.brand or 'Unknown',
            'mac_address': mac or '—',
            'vendor': vendor,
            'latency_ms': scan.latency_ms or '—',
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
        'total_clients': len(client_list),
    })


@login_required
def db_maintenance(request):
    db_vendor = connection.vendor
    tables = []
    table_stats = {}
    maintenance_records = []
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
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute("""
                    SELECT pg_size_pretty(pg_total_relation_size(%s));
                """, [table])
                size = cursor.fetchone()[0]

                cursor.execute(f'SELECT COUNT(*) FROM {table};')
                count = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT indexname FROM pg_indexes WHERE tablename = %s;
                """, [table])
                idx_count = len(cursor.fetchall())

                table_stats[table] = {
                    'size': size,
                    'count': count,
                    'index_count': idx_count,
                }

    if request.method == 'POST':
        action = request.POST.get('action')
        selected_tables = request.POST.getlist('selected_tables')
        single_table = request.POST.get('table_name')

        tables_to_process = selected_tables if selected_tables else ([single_table] if single_table else [])

        for table_name in tables_to_process:
            if action == 'vacuum':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f'VACUUM FULL {table_name};')
                    record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                    record.vacuum_status = 'Done'
                    record.last_maintenance = datetime.now()
                    record.save()
                    message = f'VACUUM FULL completed on {table_name}.' if not message else message
                except Exception as e:
                    error = str(e)
            elif action == 'reindex':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f'REINDEX TABLE {table_name};')
                    record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                    record.rebuild_status = 'Done'
                    record.last_maintenance = datetime.now()
                    record.save()
                    message = f'Reindex completed on {table_name}.' if not message else message
                except Exception as e:
                    error = str(e)
            elif action == 'indexes':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f'REINDEX TABLE {table_name};')
                    record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                    record.index_status = 'Done'
                    record.last_maintenance = datetime.now()
                    record.save()
                    message = f'Index rebuilt on {table_name}.' if not message else message
                except Exception as e:
                    error = str(e)

        if len(tables_to_process) > 1:
            if action == 'vacuum':
                message = f'VACUUM FULL completed on {len(tables_to_process)} tables.'
            elif action == 'reindex':
                message = f'Reindex completed on {len(tables_to_process)} tables.'
            elif action == 'indexes':
                message = f'Index rebuilt on {len(tables_to_process)} tables.'

    for table in tables:
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

    return render(request, 'db_maintenance.html', {
        'tables': maintenance_records,
        'db_vendor': db_vendor,
        'error': error,
        'message': message,
    })
