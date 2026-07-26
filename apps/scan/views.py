from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.core.cache import cache
from django.http import JsonResponse
import ipaddress
import time
from datetime import datetime
from .models import Scan, ScanPort, ScanMacHistory, IspInfo, ConnectionTrace
from .scanner import scan_network, get_active_interface, get_public_ip, get_isp_info, get_port_services, get_gateway, get_wan_interface_info, mac_to_vendor, trace_route

ALLOWED_SORT_FIELDS = {'ip', 'device', 'os', 'brand', 'mac_address', 'latency_ms', 'scanned_at'}
ITEMS_PER_PAGE = 25
CLIENTS_PAGE_SIZE = 25


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

    cache_key_prefix = 'scan_list_aggs'

    def _get_cached(key, compute_fn):
        cached = cache.get(key)
        if cached is not None:
            return cached
        val = compute_fn()
        cache.set(key, val, 300)
        return val

    dup_ips = _get_cached(
        f'{cache_key_prefix}:dup_ips',
        lambda: queryset.values('ip').annotate(cnt=Count('id')).filter(cnt__gt=1).count()
    )
    dup_macs = _get_cached(
        f'{cache_key_prefix}:dup_macs',
        lambda: queryset.exclude(mac_address__isnull=True).exclude(mac_address='').values('mac_address').annotate(cnt=Count('id')).filter(cnt__gt=1).count()
    )
    unique_ip_count = _get_cached(
        f'{cache_key_prefix}:unique_ips',
        lambda: queryset.values('ip').distinct().count()
    )
    unique_mac_count = _get_cached(
        f'{cache_key_prefix}:unique_macs',
        lambda: queryset.exclude(mac_address__isnull=True).exclude(mac_address='').values('mac_address').distinct().count()
    )

    paginator = Paginator(queryset, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    base_qs = Scan.objects.all()

    # Cache gateway/public/isp/wan to avoid repeated shell/network calls
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

    client_paginator = Paginator(client_qs, CLIENTS_PAGE_SIZE)
    client_page = client_paginator.get_page(request.GET.get('page', 1))

    client_list = []
    for scan in client_page.object_list:
        mac = scan.mac_address
        client_list.append({
            'ip': scan.ip,
            'hostname': scan.device or scan.ip,
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

    return render(request, 'scan_list.html', {
        'page_obj': page_obj,
        'filtered_queryset': queryset,
        'current_sort': current_sort,
        'current_order': current_order,
        'duplicate_ips': dup_ips,
        'duplicate_macs': dup_macs,
        'unique_ip_count': unique_ip_count,
        'unique_mac_count': unique_mac_count,
        'router': router_info,
        'router_isp': router_isp,
        'router_wan': wan_info,
        'public_ip': public_ip or 'Unknown',
        'clients': client_list,
        'total_clients': total_clients,
        'total_filtered': total_filtered,
        'client_page_obj': client_page,
        'search_query': search_query,
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

        for key in ['scan_list_aggs:dup_ips', 'scan_list_aggs:dup_macs', 'scan_list_aggs:unique_ips', 'scan_list_aggs:unique_macs']:
            cache.delete(key)

        messages.success(request, f'Scan complete: {added} added, {updated} updated.')
        return redirect('scan_list')

    return render(request, 'scan_trigger.html', {
        'subnet': current_subnet,
        'iface': iface_name,
    })


@login_required
def trace_progress(request, trace_id):
    record = ConnectionTrace.objects.filter(trace_id=trace_id).first()
    if not record:
        return JsonResponse({'status': 'not_found', 'hops': []})

    cache_key = f'trace_progress_{trace_id}'
    cached = cache.get(cache_key, {})
    return JsonResponse({
        'status': record.status,
        'destination': record.destination,
        'destination_ip': record.destination_ip,
        'hops': cached.get('hops', []),
        'error': record.error,
    })
