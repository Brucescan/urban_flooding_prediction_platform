from django.core.management.base import BaseCommand
from data_pipeline.utils.gdal_utils import GDALWrapper
import os

class Command(BaseCommand):
    help = '处理数据'

    def add_arguments(self, parser):
        parser.add_argument('--input', type=str, required=True, help='输入卫星栅格数据的路径')
        parser.add_argument('--output', type=str, required=True, help='输出卫星数据的路径')
        parser.add_argument('--compress', type=int, default=75, help='输出文件的压缩级别')

    def handle(self, *args, **kwargs):
        input_dir = kwargs['input']
        output_file = kwargs['output']
        compress_level = kwargs['compress']

        gdal_wrapper = GDALWrapper()
        try:
            for folder_name in os.listdir(input_dir):
                folder_path = os.path.join(input_dir, folder_name)
                if os.path.isdir(folder_path):
                    b04_path = None
                    b08_path = None
                    for file_name in os.listdir(folder_path):
                        if 'B04_10m.jp2' in file_name:
                            b04_path = os.path.join(folder_path, file_name)
                        elif 'B08_10m.jp2' in file_name:
                            b08_path = os.path.join(folder_path, file_name)

                    if b04_path and b08_path:
                        gdal_wrapper.calculate_ndvi(b04_path, b08_path, output_file, compress_level)
                        self.stdout.write(self.style.SUCCESS(f'Successfully processed NDVI and saved to {output_file}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Missing B04 or B08 band in {folder_name}'))
        except RuntimeError as e:
            self.stdout.write(self.style.ERROR(str(e)))