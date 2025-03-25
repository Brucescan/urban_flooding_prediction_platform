from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.gis.geos import Polygon
from .models import SatelliteRaster


class RasterMetadataAPI(APIView):
    def get(self, request):
        bbox_str = request.query_params.get('bbox', '')
        if bbox_str:
            bbox = [float(coord) for coord in bbox_str.split(',')]
            area = Polygon.from_bbox(bbox)
        else:
            # Default bounding box for Henan province
            area = Polygon.from_bbox([110.9483, 31.5904, 116.6474, 35.0046])

        rasters = SatelliteRaster.objects.filter(
            rast__bboverlaps=area
        ).values('name', 'acquisition_date', 'data_type', 'metadata')

        return Response({
            'count': len(rasters),
            'results': list(rasters)
        })