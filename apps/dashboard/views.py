import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.conf import settings
from django.db import connection
from apps.scan.models import Scan

@login_required
def dashboard(request):
    total_devices = Scan.objects.count()
    os_stats = Scan.objects.values('os').annotate(count=Count('id')).order_by('-count')
    brand_stats = Scan.objects.values('brand').annotate(count=Count('id')).order_by('-count')

    sort = request.GET.get('sort', '-scanned_at')
    order = request.GET.get('order', 'desc')
    allowed = {'ip', 'device', 'os', 'brand', 'scanned_at'}
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
    gateway_id = 0
    nodes = []
    edges = []
    for scan in scans:
        is_gateway = scan.gateway and str(scan.gateway) == str(gateway_ip)
        if is_gateway:
            gateway_id = scan.id
        nodes.append({
            'id': scan.id,
            'label': f"{scan.ip}\n{scan.device}",
            'title': f"{scan.os} · {scan.brand or 'Unknown'}\nLatency: {scan.latency_ms or 'N/A'} ms",
            'color': '#22c55e' if is_gateway else '#facc15',
            'font': { 'color': '#e5e7eb', 'size': 12 }
        })
        if scan.gateway and not is_gateway:
            edges.append({'from': scan.id, 'to': gateway_id or 0, 'arrows': 'to', 'color': { 'color': '#22c55e', 'highlight': '#facc15' }})
    if gateway_id == 0 and scans.exists():
        nodes.insert(0, {
            'id': 0,
            'label': f"Gateway\n{gateway_ip or '192.168.1.1'}",
            'title': 'Gateway Router',
            'color': '#22c55e',
            'font': { 'color': '#e5e7eb', 'size': 13 }
        })
        for scan in scans:
            if scan.id != 0:
                edges.append({'from': scan.id, 'to': 0, 'arrows': 'to', 'color': { 'color': '#22c55e', 'highlight': '#facc15' }})
    networks = {'nodes': nodes, 'edges': edges}
    return render(request, 'network_map.html', {
        'networks': json.dumps(networks),
        'total_devices': total,
        'online_count': online,
        'gateway_ip': gateway_ip or '192.168.1.1',
        'scans': scans,
    })

from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.core.paginator import Paginator
from django.db import connection
from apps.scan.models import Scan
from .models import DbMaintenance

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
        table_name = request.POST.get('table_name')
        if action == 'vacuum' and table_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'VACUUM FULL {table_name};')
                record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                record.vacuum_status = 'Done'
                record.last_maintenance = datetime.now()
                record.save()
                message = f'VACUUM FULL completed on {table_name}.'
            except Exception as e:
                error = str(e)
        elif action == 'reindex' and table_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'REINDEX TABLE {table_name};')
                record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                record.rebuild_status = 'Done'
                record.last_maintenance = datetime.now()
                record.save()
                message = f'Reindex completed on {table_name}.'
            except Exception as e:
                error = str(e)
        elif action == 'indexes' and table_name:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'REINDEX TABLE {table_name};')
                record, _ = DbMaintenance.objects.get_or_create(table_name=table_name)
                record.index_status = 'Done'
                record.last_maintenance = datetime.now()
                record.save()
                message = f'Index rebuilt on {table_name}.'
            except Exception as e:
                error = str(e)

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
