from django.contrib import admin
from .models import StormEvent, ActiveAlert

@admin.register(StormEvent)
class StormEventAdmin(admin.ModelAdmin):
    pass

@admin.register(ActiveAlert)
class ActiveAlertAdmin(admin.ModelAdmin):
    pass

