from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.core.paginator import Paginator
from django.core.cache import cache
import ipaddress
from .models import Scan
from .scanner import scan_network, get_active_interface, get_public_ip, get_isp_info

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
    iface_name, ip_addr, netmask = get_active_interface()
    current_subnet = None
    if ip_addr and netmask:
        try:
            current_subnet = str(ipaddress.IPv4Network(f'{ip_addr}/{netmask}', strict=False))
        except Exception:
            current_subnet = None

    last_scanned_subnet = cache.get('last_scanned_subnet')
    network_changed = current_subnet and current_subnet != last_scanned_subnet

    if request.method == 'POST':
        subnet = request.POST.get('subnet') or current_subnet
        max_hosts = int(request.POST.get('count', 254))
        try:
            scan_result = scan_network(subnet=subnet, max_hosts=max_hosts, max_workers=100)
            results = scan_result[0] if isinstance(scan_result, tuple) else scan_result
            isp_info = scan_result[1] if isinstance(scan_result, tuple) else {}
        except Exception as e:
            messages.error(request, f'Scan failed: {str(e)}')
            return redirect('scan_trigger')
        added = 0
        updated = 0
        public_ip = get_public_ip()
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
                    'public_ip': public_ip,
                    'isp_name': isp_info.get('isp'),
                    'isp_org': isp_info.get('org'),
                    'server_info': r.get('server_info'),
                }
            )
            if created:
                added += 1
            else:
                updated += 1
        if current_subnet:
            cache.set('last_scanned_subnet', current_subnet, timeout=None)
        msg = f'Scan completed. {added} new, {updated} updated.'
        messages.success(request, msg)
        return redirect('scan_list')

    if network_changed and current_subnet:
        cache.set('last_scanned_subnet', current_subnet, timeout=None)
        try:
            scan_result = scan_network(subnet=current_subnet, max_hosts=254, max_workers=100)
            results = scan_result[0] if isinstance(scan_result, tuple) else scan_result
            isp_info = scan_result[1] if isinstance(scan_result, tuple) else {}
        except Exception as e:
            messages.error(request, f'Auto-scan failed: {str(e)}')
            return render(request, 'scan_trigger.html', {'subnet': current_subnet, 'network_changed': True, 'auto_scan_error': str(e)})
        added = 0
        updated = 0
        public_ip = get_public_ip()
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
                    'public_ip': public_ip,
                    'isp_name': isp_info.get('isp'),
                    'isp_org': isp_info.get('org'),
                    'server_info': r.get('server_info'),
                }
            )
            if created:
                added += 1
            else:
                updated += 1
        msg = f'Network changed! Auto-scanned {current_subnet}. {added} new, {updated} updated.'
        messages.success(request, msg)
        return redirect('scan_list')

    return render(request, 'scan_trigger.html', {'subnet': current_subnet})
