from django.contrib.gis.db import models

class SatelliteRaster(models.Model):
    RASTER_TYPES = (
        ('NDVI', '植被指数'),
        ('LST', '地表温度'),
        ('NL', '夜间灯光'),
    )
    name = models.CharField(max_length=100)
    rast = models.RasterField(srid=3857)  # GeoDjango Raster字段
    acquisition_date = models.DateField()
    data_type = models.CharField(max_length=4, choices=RASTER_TYPES)
    metadata = models.JSONField(default=dict)  # 存储min/max等统计值

    def get_wms_url(self):
        """生成GeoServer WMS访问URL"""
        return (
            f"http://geoserver:8080/geoserver/wms?"
            f"layers=webgis:{self.name}&format=image/png"
        )
