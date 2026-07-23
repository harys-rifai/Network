import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.core.paginator import Paginator
from apps.scan.models import Scan

@login_required
def dashboard(request):
    total_devices = Scan.objects.count()
    os_stats = Scan.objects.values('os').annotate(count=Count('id')).order_by('-count')
    brand_stats = Scan.objects.values('brand').annotate(count=Count('id')).order_by('-count')
    recent_page = Paginator(Scan.objects.all(), 10).get_page(request.GET.get('page', 1))

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
        'os_labels': json.dumps(os_labels),
        'os_data': json.dumps(os_data),
        'brand_labels': json.dumps(brand_labels),
        'brand_data': json.dumps(brand_data),
    }
    return render(request, 'dashboard.html', context)

@login_required
def network_map(request):
    scans = Scan.objects.all()
    nodes = []
    edges = []
    for scan in scans:
        nodes.append({'id': scan.id, 'label': f"{scan.ip}\n{scan.device}", 'title': scan.os})
        if scan.gateway:
            edges.append({'from': scan.id, 'to': 0, 'arrows': 'to'})
    # Add gateway node
    if scans.exists():
        nodes.insert(0, {'id': 0, 'label': 'Gateway\n192.168.1.1', 'title': 'Gateway', 'color': '#00ff00'})
    networks = {'nodes': nodes, 'edges': edges}
    return render(request, 'network_map.html', {'networks': json.dumps(networks)})
