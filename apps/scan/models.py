from django.db import models
import json

class Scan(models.Model):
    ip = models.GenericIPAddressField()
    device = models.CharField(max_length=255)
    os = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True, null=True)
    gateway = models.GenericIPAddressField(blank=True, null=True, db_index=True)
    router = models.GenericIPAddressField(blank=True, null=True)
    dns = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    latency_ms = models.FloatField(blank=True, null=True)
    open_ports = models.JSONField(blank=True, null=True)
    services = models.JSONField(blank=True, null=True)
    public_ip = models.GenericIPAddressField(blank=True, null=True)
    isp_name = models.CharField(max_length=255, blank=True, null=True)
    isp_org = models.CharField(max_length=255, blank=True, null=True)
    server_info = models.CharField(max_length=255, blank=True, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-scanned_at']
        indexes = [
            models.Index(fields=['ip', 'scanned_at']),
            models.Index(fields=['os', 'brand']),
            models.Index(fields=['device']),
            models.Index(fields=['mac_address']),
            models.Index(fields=['public_ip']),
            models.Index(fields=['isp_name']),
        ]

    def __str__(self):
        return f"{self.ip} - {self.device}"


class ScanPort(models.Model):
    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name='port_entries')
    port = models.IntegerField()
    service = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ['scan', 'port']
        ordering = ['port']
        indexes = [
            models.Index(fields=['port']),
        ]

    def __str__(self):
        return f"{self.scan.ip}:{self.port} ({self.service or 'unknown'})"


class ScanMacHistory(models.Model):
    ip = models.GenericIPAddressField()
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['ip', 'last_seen']),
            models.Index(fields=['mac_address']),
        ]

    def __str__(self):
        return f"{self.ip} - {self.mac_address}"


class OuiVendor(models.Model):
    prefix = models.CharField(max_length=6, unique=True)
    vendor = models.CharField(max_length=255)

    class Meta:
        ordering = ['prefix']
        indexes = [
            models.Index(fields=['prefix']),
        ]

    def __str__(self):
        return f"{self.prefix} - {self.vendor}"


class PortService(models.Model):
    port = models.IntegerField(unique=True)
    service = models.CharField(max_length=100)

    class Meta:
        ordering = ['port']
        indexes = [
            models.Index(fields=['port']),
        ]

    def __str__(self):
        return f"{self.port} - {self.service}"


class IspInfo(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    isp = models.CharField(max_length=255, blank=True, null=True)
    org = models.CharField(max_length=255, blank=True, null=True)
    as_number = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    region = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['ip']),
            models.Index(fields=['country']),
            models.Index(fields=['city']),
        ]

    def __str__(self):
        return f"{self.ip} - {self.isp or self.org or 'Unknown'}"
