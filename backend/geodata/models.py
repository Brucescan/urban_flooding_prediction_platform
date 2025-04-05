# models.py
from pathlib import Path

from django.contrib.gis.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class NDVIData(models.Model):
    """NDVI数据存储模型"""
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="数据标识，如beijing_ndvi_20240101"
    )
    acquisition_date = models.DateField(
        help_text="数据采集日期"
    )
    processing_date = models.DateTimeField(
        auto_now_add=True,
        help_text="数据处理时间"
    )
    resolution = models.FloatField(
        default=10.0,
        help_text="分辨率(米)"
    )
    data_dir = models.CharField(
        max_length=255,
        help_text="数据存储目录(相对路径)"
    )
    min_value = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]  # NDVI值范围在-1到1之间
    )

    max_value = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]
    )

    mean_value = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]
    )
    coverage = models.PolygonField(
        srid=4326,
        help_text="数据覆盖范围"
    )
    thumbnail = models.ImageField(
        upload_to='ndvi_thumbnails/',
        null=True,
        blank=True,
        help_text="缩略图预览"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="原始元数据"
    )

    class Meta:
        verbose_name = "NDVI数据"
        verbose_name_plural = "NDVI数据"
        ordering = ['-acquisition_date']

    def __str__(self):
        return f"{self.name} ({self.acquisition_date})"

    def get_absolute_path(self):
        """获取数据绝对路径"""
        from django.conf import settings
        return Path(settings.BASE_DIR) / self.data_dir

    def get_tile_paths(self):
        """获取所有分块文件路径"""
        data_dir = self.get_absolute_path()
        return sorted(data_dir.glob('*.tif'))

    def save(self, *args, **kwargs):
        # 在保存前清理特殊值
        def clean_value(value):
            if value in (float('-inf'), float('inf'), float('nan')):
                return None
            return max(-1.0, min(1.0, value))  # 确保在有效范围内

        self.min_value = clean_value(self.min_value)
        self.max_value = clean_value(self.max_value)
        self.mean_value = clean_value(self.mean_value)
        super().save(*args, **kwargs)
