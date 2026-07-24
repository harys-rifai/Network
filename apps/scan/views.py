from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.core.paginator import Paginator
from django.core.cache import cache
import ipaddress
import time
from datetime import datetime
from .models import Scan, ScanPort, ScanMacHistory, IspInfo
from .scanner import scan_network, get_active_interface, get_public_ip, get_isp_info, get_port_services

ALLOWED_SORT_FIELDS = {'ip', 'device', 'os', 'brand', 'mac_address', 'latency_ms', 'scanned_at'}
ITEMS_PER_PAGE = 25


def _resolve_sort(sort_param, order_param, default='-scanned_at'):
    """Return a safe order_by string from raw query params."""
    sort = sort_param or 'scanned_at'
    order = order_param if order_param in ('asc', 'desc') else 'desc'
    if sort not in ALLOWED_SORT_FIELDS:
        return default, 'scanned_at', 'desc'
    db_sort = sort if order == 'asc' else f'-{sort}'
    return db_sort, sort, order


@login_required
def scan_list(request):
    db_sort, current_sort, current_order = _resolve_sort(
        request.GET.get('sort', 'scanned_at'),
        request.GET.get('order', 'desc'),
    )

    queryset = Scan.objects.all().order_by(db_sort)

    # Duplicate detection over the full queryset
    dup_ips = (
        queryset.values('ip')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
        .count()
    )
    dup_macs = (
        queryset.exclude(mac_address__isnull=True).exclude(mac_address='')
        .values('mac_address')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
        .count()
    )
    unique_ip_count = queryset.values('ip').distinct().count()
    unique_mac_count = (
        queryset.exclude(mac_address__isnull=True).exclude(mac_address='')
        .values('mac_address').distinct().count()
    )

    paginator = Paginator(queryset, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'scan_list.html', {
        'page_obj': page_obj,
        'filtered_queryset': queryset,
        'current_sort': current_sort,
        'current_order': current_order,
        'duplicate_ips': dup_ips,
        'duplicate_macs': dup_macs,
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

    if request.method == 'POST':
        subnet = request.POST.get('subnet') or current_subnet
        max_hosts = int(request.POST.get('count', 254))
        try:
            scan_result = scan_network(subnet=subnet, max_hosts=max_hosts, max_workers=50)
            results = scan_result[0] if isinstance(scan_result, tuple) else scan_result
            isp_info = scan_result[1] if isinstance(scan_result, tuple) else {}
        except RuntimeError as e:
            if 'cannot schedule new futures after interpreter shutdown' in str(e):
                messages.warning(request, 'Thread pool unavailable, retrying with sequential scan...')
                try:
                    scan_result = scan_network(subnet=subnet, max_hosts=max_hosts, max_workers=1)
                    results = scan_result[0] if isinstance(scan_result, tuple) else scan_result
                    isp_info = scan_result[1] if isinstance(scan_result, tuple) else {}
                except Exception as e2:
                    messages.error(request, f'Scan failed: {str(e2)}')
                    return redirect('scan_trigger')
            else:
                messages.error(request, f'Scan failed: {str(e)}')
                return redirect('scan_trigger')
        except Exception as e:
            messages.error(request, f'Scan failed: {str(e)}')
            return redirect('scan_trigger')

        added = 0
        updated = 0
        public_ip = get_public_ip()
        isp_info = isp_info or {}

        if public_ip:
            db_isp, _ = IspInfo.objects.get_or_create(ip=public_ip, defaults=isp_info)
            if not db_isp.isp and isp_info.get('isp'):
                db_isp.isp = isp_info.get('isp')
                db_isp.org = isp_info.get('org')
                db_isp.as_number = isp_info.get('as')
                db_isp.country = isp_info.get('country')
                db_isp.region = isp_info.get('region')
                db_isp.city = isp_info.get('city')
                db_isp.save(update_fields=['isp', 'org', 'as_number', 'country', 'region', 'city'])
            isp_info = {
                'isp': db_isp.isp or isp_info.get('isp'),
                'org': db_isp.org or isp_info.get('org'),
                'as': db_isp.as_number or isp_info.get('as'),
                'country': db_isp.country or isp_info.get('country'),
                'region': db_isp.region or isp_info.get('region'),
                'city': db_isp.city or isp_info.get('city'),
            }

        for r in results:
            # services is stored as {port: service_name} dict
            services_dict = {}
            for port, svc in zip(r.get('open_ports', []), r.get('services', [])):
                services_dict[str(port)] = svc

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

            port_entries = []
            seen_ports = set()
            port_services = get_port_services()
            for p in r.get('open_ports', []):
                if p not in seen_ports:
                    seen_ports.add(p)
                    svc = port_services.get(p)
                    port_entries.append(ScanPort(scan=obj, port=p, service=svc))
            if port_entries:
                ScanPort.objects.bulk_create(port_entries, ignore_conflicts=True)

            mac = r.get('mac_address')
            if mac:
                history, _ = ScanMacHistory.objects.get_or_create(
                    ip=r['ip'],
                    mac_address=mac,
                )
                if history.last_seen < obj.scanned_at:
                    history.last_seen = obj.scanned_at
                    history.save(update_fields=['last_seen'])

        if current_subnet:
            cache.set('last_scanned_subnet', current_subnet, timeout=None)

        messages.success(request, f'Scan complete: {added} added, {updated} updated.')
        return redirect('scan_list')

    return render(request, 'scan_trigger.html', {
        'subnet': current_subnet,
        'iface': iface_name,
    })
