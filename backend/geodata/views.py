from numpy import isinf
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse
from pathlib import Path
from django.conf import settings
from geodata.models import NDVIData


class NDVIListAPI(APIView):
    """获取NDVI数据列表"""
    permission_classes = [AllowAny]  # 添加这行

    def get(self, request):
        queryset = NDVIData.objects.all().order_by('-acquisition_date')[:10]

        data = []
        for item in queryset:
            # 处理特殊浮点值
            min_val = None if isinf(item.min_value) else item.min_value
            max_val = None if isinf(item.max_value) else item.max_value
            mean_val = None if isinf(item.mean_value) else item.mean_value

            data.append({
                'id': item.id,
                'name': item.name,
                'date': item.acquisition_date.strftime('%Y-%m-%d'),
                'resolution': item.resolution,
                'min': min_val,
                'max': max_val,
                'mean': mean_val,
                'thumbnail_url': request.build_absolute_uri(item.thumbnail.url),
                'coverage': {
                    'type': 'Polygon',
                    'coordinates': [list(item.coverage.coords[0])]
                } if item.coverage else None
            })

        return Response(data)


class NDVIDownloadAPI(APIView):
    """下载NDVI数据"""
    permission_classes = [AllowAny]  # 添加这行

    def get(self, request, pk):
        try:
            ndvi_data = NDVIData.objects.get(pk=pk)
            data_dir = Path(settings.BASE_DIR) / ndvi_data.data_dir

            # 创建ZIP压缩包
            import zipfile
            from io import BytesIO

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for tif_file in data_dir.glob('*.tif'):
                    zipf.write(tif_file, tif_file.name)
                # 包含元数据文件
                metadata_file = data_dir / 'metadata.json'
                if metadata_file.exists():
                    zipf.write(metadata_file, 'metadata.json')

            zip_buffer.seek(0)

            return FileResponse(
                zip_buffer,
                as_attachment=True,
                filename=f"{ndvi_data.name}.zip",
                content_type='application/zip'
            )

        except NDVIData.DoesNotExist:
            return Response({'error': '数据不存在'}, status=404)