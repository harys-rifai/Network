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

@login_required
def db_maintenance(request):
    result = None
    error = None
    action = None
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with connection.cursor() as cursor:
                if action == 'vacuum':
                    cursor.execute('VACUUM VERBOSE ANALYZE scan_scan;')
                    result = 'VACUUM ANALYZE completed successfully on scan_scan.'
                elif action == 'reindex':
                    cursor.execute('REINDEX TABLE scan_scan;')
                    result = 'Reindex completed successfully on scan_scan.'
                elif action == 'slow_query':
                    cursor.execute("""
                        SELECT 
                            now() - pg_stat_activity.query_start AS duration,
                            query,
                            state
                        FROM pg_stat_activity
                        WHERE state = 'active'
                          AND query NOT ILIKE '%pg_stat_activity%'
                        ORDER BY duration DESC
                        LIMIT 20;
                    """)
                    rows = cursor.fetchall()
                    result = {
                        'headers': ['Duration', 'Query', 'State'],
                        'rows': rows
                    }
                else:
                    error = 'Invalid action.'
        except Exception as e:
            error = str(e)
    return render(request, 'db_maintenance.html', {
        'result': result,
        'error': error,
        'action': action,
    })
