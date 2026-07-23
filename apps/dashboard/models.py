from django.db import models

class DbMaintenance(models.Model):
    table_name = models.CharField(max_length=255, unique=True)
    vacuum_status = models.CharField(max_length=50, default='Ready')
    index_status = models.CharField(max_length=50, default='-')
    rebuild_status = models.CharField(max_length=50, default='-')
    record_count = models.IntegerField(null=True, blank=True)
    table_size = models.CharField(max_length=50, null=True, blank=True)
    last_maintenance = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['table_name']

    def __str__(self):
        return f"{self.table_name} - {self.vacuum_status}"
