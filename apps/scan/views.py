from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.core.paginator import Paginator
import ipaddress
from .models import Scan
from .scanner import scan_network, get_active_interface

@login_required
def scan_list(request):
    sort = request.GET.get('sort', '-scanned_at')
    order = request.GET.get('order', 'desc')
    allowed = {'ip', 'device', 'os', 'brand', 'mac_address', 'latency_ms', 'scanned_at'}
    if sort not in allowed:
        sort = '-scanned_at'
    if order not in {'asc', 'desc'}:
        order = 'desc'
    if order == 'asc' and sort.startswith('-'):
        sort = sort[1:]
    elif order == 'desc' and not sort.startswith('-'):
        sort = f'-{sort}'

    queryset = Scan.objects.all().order_by(sort)
    unique_ip_count = queryset.values('ip').count()
    unique_mac_count = queryset.exclude(mac_address__isnull=True).exclude(mac_address='').values('mac_address').count()
    duplicate_ips = queryset.values('ip').annotate(cnt=Count('id')).filter(cnt__gt=1).count()
    duplicate_macs = queryset.exclude(mac_address__isnull=True).exclude(mac_address='').values('mac_address').annotate(cnt=Count('id')).filter(cnt__gt=1).count()

    page_number = request.GET.get('page', 1)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(page_number)
    return render(request, 'scan_list.html', {
        'page_obj': page_obj,
        'filtered_queryset': queryset,
        'current_sort': sort if not sort.startswith('-') else sort[1:],
        'current_order': order,
        'duplicate_ips': duplicate_ips,
        'duplicate_macs': duplicate_macs,
        'unique_ip_count': unique_ip_count,
        'unique_mac_count': unique_mac_count,
    })

@login_required
def scan_detail(request, pk):
    scan = get_object_or_404(Scan, pk=pk)
    return render(request, 'scan_detail.html', {'scan': scan})

@login_required
def scan_edit(request, pk):
    scan = get_object_or_404(Scan, pk=pk)
    if request.method == 'POST':
        scan.ip = request.POST.get('ip', scan.ip)
        scan.device = request.POST.get('device', scan.device)
        scan.os = request.POST.get('os', scan.os)
        scan.brand = request.POST.get('brand', scan.brand)
        scan.gateway = request.POST.get('gateway') or None
        scan.router = request.POST.get('router') or None
        scan.dns = request.POST.get('dns') or None
        scan.save()
        messages.success(request, 'Scan record updated.')
        return redirect('scan_list')
    return render(request, 'scan_form.html', {'scan': scan})

@login_required
def scan_delete(request, pk):
    scan = get_object_or_404(Scan, pk=pk)
    if request.method == 'POST':
        scan.delete()
        messages.success(request, 'Scan record deleted.')
        return redirect('scan_list')
    return render(request, 'scan_confirm_delete.html', {'scan': scan})

@login_required
def scan_trigger(request):
    if request.method == 'POST':
        subnet = request.POST.get('subnet') or None
        max_hosts = int(request.POST.get('count', 254))
        try:
            results = scan_network(subnet=subnet, max_hosts=max_hosts, max_workers=100)
        except Exception as e:
            messages.error(request, f'Scan failed: {str(e)}')
            return redirect('scan_trigger')
        added = 0
        updated = 0
        for r in results:
            services_dict = dict(zip(r.get('open_ports', []), r.get('services', []))) if r.get('open_ports') else None
            obj, created = Scan.objects.update_or_create(
                ip=r['ip'],
                defaults={
                    'device': r['device'],
                    'os': r['os'],
                    'brand': r['brand'],
                    'gateway': r['gateway'],
                    'router': r['router'],
                    'dns': r['dns'],
                    'mac_address': r.get('mac_address'),
                    'latency_ms': r.get('latency_ms'),
                    'open_ports': r.get('open_ports'),
                    'services': services_dict,
                }
            )
            if created:
                added += 1
            else:
                updated += 1
        msg = f'Scan completed. {added} new, {updated} updated.'
        messages.success(request, msg)
        return redirect('scan_list')
    iface_name, ip_addr, netmask = get_active_interface()
    subnet = None
    if ip_addr and netmask:
        try:
            subnet = str(ipaddress.IPv4Network(f'{ip_addr}/{netmask}', strict=False))
        except Exception:
            subnet = None
    return render(request, 'scan_trigger.html', {'subnet': subnet})
