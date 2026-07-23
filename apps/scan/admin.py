from django.contrib import admin
from .models import Scan

@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ['ip', 'device', 'os', 'brand', 'gateway', 'scanned_at']
    list_filter = ['os', 'scanned_at']
    search_fields = ['ip', 'device', 'os', 'brand']
    readonly_fields = ['scanned_at']
