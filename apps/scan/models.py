from django.db import models
import json

class Scan(models.Model):
    ip = models.GenericIPAddressField(db_index=True)
    device = models.CharField(max_length=255, db_index=True)
    os = models.CharField(max_length=255, db_index=True)
    brand = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    gateway = models.GenericIPAddressField(blank=True, null=True, db_index=True)
    router = models.GenericIPAddressField(blank=True, null=True)
    dns = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True, db_index=True)
    latency_ms = models.FloatField(blank=True, null=True)
    open_ports = models.JSONField(blank=True, null=True)
    services = models.JSONField(blank=True, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-scanned_at']
        indexes = [
            models.Index(fields=['ip', 'scanned_at']),
            models.Index(fields=['os', 'brand']),
        ]

    def __str__(self):
        return f"{self.ip} - {self.device}"
