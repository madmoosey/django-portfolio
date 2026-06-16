from django.contrib import admin

from .models import DeforestationAlert, TreeCoverBaseline, TreeCoverLoss


@admin.register(TreeCoverBaseline)
class TreeCoverBaselineAdmin(admin.ModelAdmin):
    pass


@admin.register(TreeCoverLoss)
class TreeCoverLossAdmin(admin.ModelAdmin):
    pass


@admin.register(DeforestationAlert)
class DeforestationAlertAdmin(admin.ModelAdmin):
    pass
