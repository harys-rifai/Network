from django.db import models
import json

class Scan(models.Model):
    ip = models.GenericIPAddressField(db_index=True)
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
    public_ip = models.GenericIPAddressField(blank=True, null=True, db_index=True)
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
