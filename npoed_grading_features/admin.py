from django.contrib import admin
from .models import NpoedGradingFeatures

@admin.register(NpoedGradingFeatures)
class NpoedGradingFeaturesAdmin(admin.ModelAdmin):
    pass