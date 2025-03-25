from django.conf import settings
import subprocess


class GDALWrapper:
    def __init__(self):
        self.gdal_path = settings.GDAL_LIBRARY_PATH

    def calculate_ndvi(self, b04_path, b08_path, output_path, compress_level):
        """调用GDAL计算NDVI"""
        cmd = [
            'gdal_calc.py',
            '-A', b04_path,
            '-B', b08_path,
            '--calc="(B-A)/(B+A+1e-10)*1.0"',
            '--outfile', output_path,
            '--NoDataValue=-9999',
            '--type=Float32',
            '--co', f'COMPRESS=LZW',
            '--co', f'PREDICTOR=2',
            '--co', f'ZLEVEL={compress_level}'
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"GDAL执行失败: {proc.stderr.decode()}")