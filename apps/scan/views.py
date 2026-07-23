from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
import ipaddress
from .models import Scan
from .scanner import scan_network, get_active_interface

@login_required
def scan_list(request):
    scans = Scan.objects.all()
    return render(request, 'scan_list.html', {'scans': scans})

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
        for r in results:
            Scan.objects.create(
                ip=r['ip'],
                device=r['device'],
                os=r['os'],
                brand=r['brand'],
                gateway=r['gateway'],
                router=r['router'],
                dns=r['dns'],
            )
            added += 1
        messages.success(request, f'Scan completed. {added} live host(s) discovered.')
        return redirect('scan_list')
    iface_name, ip_addr, netmask = get_active_interface()
    subnet = None
    if ip_addr and netmask:
        try:
            subnet = str(ipaddress.IPv4Network(f'{ip_addr}/{netmask}', strict=False))
        except Exception:
            subnet = None
    return render(request, 'scan_trigger.html', {'subnet': subnet})
