from django.db import models

class Scan(models.Model):
    ip = models.GenericIPAddressField()
    device = models.CharField(max_length=255)
    os = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True, null=True)
    gateway = models.GenericIPAddressField(blank=True, null=True)
    router = models.GenericIPAddressField(blank=True, null=True)
    dns = models.GenericIPAddressField(blank=True, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.ip} - {self.device}"
