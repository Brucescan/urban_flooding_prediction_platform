import json
import time
import ee
import geemap
from datetime import datetime, timedelta
import logging
from django.core.management.base import BaseCommand
from pathlib import Path
from geodata.models import NDVIData  # 根据你的实际应用调整导入路径
from django.core.files import File
import numpy as np
from PIL import Image
from osgeo import gdal

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'NDVI数据'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_logging()

    def setup_logging(self):
        # 创建logs目录（如果不存在）
        logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # 设置日志文件名（包含当前时间）
        log_filename = f"pipline_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        log_filepath = logs_dir / log_filename

        # 配置日志记录器
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 创建文件处理器
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)

    def log(self, message, level=logging.INFO):
        """统一记录日志"""
        self.stdout.write(message)  # 保持控制台输出
        if level == logging.INFO:
            self.logger.info(message)
        elif level == logging.WARNING:
            self.logger.warning(message)
        elif level == logging.ERROR:
            self.logger.error(message)
        elif level == logging.DEBUG:
            self.logger.debug(message)
    def add_arguments(self, parser):
        parser.add_argument('--output',
                            type=str,
                            default='./data_pipeline/data/ndvi',
                            help='输出目录（相对项目根目录）')
        parser.add_argument('--service-account',  # 新增参数
                            type=str,
                            default='/root/.config/earthengine/service-account.json',
                            help='GEE服务账户文件路径')

    def handle(self, *args, **kwargs):
        # 路径解析
        base_dir = Path(__file__).resolve().parent.parent.parent
        output_dir = (base_dir / kwargs['output']).resolve()

        # 显式传递服务账户路径
        self.service_account = Path(kwargs['service_account']).resolve()

        try:
            self._init_gee()
            ndvi_data = self.get_sentinel2_data()
            self.export_ndvi(ndvi_data, output_dir)
            self.log(self.style.SUCCESS(f'数据已保存至：{output_dir}'))
        except Exception as e:
            logger.error(f'下载失败：{str(e)}')
            raise e  # 抛出详细错误

    def _init_gee(self):
        """显式服务账户初始化"""
        # 验证服务账户文件存在
        if not self.service_account.exists():
            raise FileNotFoundError(f"服务账户文件不存在: {self.service_account}")

        try:
            # 显式指定服务账户
            credentials = ee.ServiceAccountCredentials(
                email=None,  # 自动从JSON读取
                key_file=str(self.service_account)
            )
            ee.Initialize(credentials)  # 强制使用服务账户
            logger.info("GEE服务账户认证成功")
        except ee.EEException as e:
            logger.error(f"GEE初始化失败: {str(e)}")
            raise

    def get_sentinel2_data(self):
        """修复后的Sentinel-2 NDVI逻辑"""
        dataset_path = 'COPERNICUS/S2_SR_HARMONIZED'
        bei_jing = ee.FeatureCollection("projects/ee-brucepengyuan/assets/bei_jing")
        valid_geometry = bei_jing.geometry().bounds()

        # 时间范围调整为滚动窗口（确保数据新鲜）
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')  # 延长至45天
        end_date = today.strftime('%Y-%m-%d')

        # 数据加载与过滤
        s2_collection = ee.ImageCollection(dataset_path) \
            .filterDate(start_date, end_date) \
            .filterBounds(valid_geometry) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))  # 更严格云量过滤

        # 云掩膜处理（网页2增强版）
        def cloud_masking(element):
            # 显式转换Feature为Image对象
            element = ee.Feature(element)  # 新增类型转换

            s2_img = ee.Image(element.get('primary')).select('B4', 'B8', 'QA60')
            cloud_img = ee.Image(element.get('secondary'))

            # 增强掩膜逻辑（网页2方法）
            qa_mask = s2_img.select('QA60').bitwiseAnd(0b11 << 10).eq(0)
            cloud_mask = cloud_img.select('probability').lt(15)
            full_mask = qa_mask.And(cloud_mask)

            return ee.Image(s2_img.updateMask(full_mask))  # 二次类型保险

        # 云掩膜处理（优化版）
        cloud_prob = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY') \
            .filterDate(start_date, end_date) \
            .filterBounds(valid_geometry)

        # 精确关联影像与云数据
        joined_collection = ee.Join.inner().apply(
            primary=s2_collection,
            secondary=cloud_prob,
            condition=ee.Filter.equals(
                leftField='system:index',
                rightField='system:index'
            )
        )
        # 应用处理并计算NDVI
        # processed_images = joined_collection.map(process_joined_element)
        processed_images = ee.ImageCollection(joined_collection.map(cloud_masking)) \
            .filter(ee.Filter.neq('system:band_names', None))

        # NDVI计算（类型安全）
        ndvi_collection = processed_images.map(
            lambda img: img.addBands(  # 保留原始波段
                img.normalizedDifference(['B8', 'B4']).rename('NDVI')
            )
        ).select(['NDVI'])  # 仅保留NDVI波段
        # 空集合检查
        if ndvi_collection.size().getInfo() == 0:
            raise ValueError(f"{start_date}至{end_date}无有效数据")

        return ndvi_collection.median().clip(valid_geometry)

    def export_ndvi(self, image, output_dir):
        """增强导出稳定性"""

        # 若为空图像则抛出异常
        if not image.bandNames().size().gt(0).getInfo():
            raise ValueError("生成图像为空，请检查输入数据")
        # filename = f"beijing_ndvi_{datetime.now().strftime('%Y%m%d')}"
        # output_path = output_dir / filename
        # output_path.mkdir(parents=True, exist_ok=True)

        # 从get_sentinel2_data获取边界
        valid_geometry = self.get_sentinel2_data().geometry()

        # 创建日期子目录
        date_str = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / date_str
        output_path.mkdir(parents=True, exist_ok=True)

        # 生成元数据文件
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'data_source': 'Sentinel-2',
            'bands': image.bandNames().getInfo(),
            'crs': 'EPSG:4526',
            'resolution': '10m'
        }
        with open(output_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f)

        self.log("开始下载分块数据...")
        # 下载分块
        full_fishnet = geemap.fishnet(
            valid_geometry,
            rows=8,
            cols=6,
            delta=0.5,
            crs='EPSG:4526'  # 显式指定坐标系
        )
        fishnet_features = full_fishnet.toList(2)  # 仅获取前两个特征
        partial_fishnet = ee.FeatureCollection(fishnet_features)
        image = image.setDefaultProjection(crs='EPSG:4526', scale=10)
        # 检查输出目录是否创建成功
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        # 执行下载并验证结果
        download_result = self.download_and_validate_tiles(
            image=image.clip(valid_geometry),
            output_path=output_path,
            fishnet=partial_fishnet
        )

        if not download_result:
            raise RuntimeError("分块下载验证失败")

        # 保存到数据库
        self.save_to_database(image, output_path, metadata)

        return output_path

    def download_and_validate_tiles(self, image, output_path, fishnet):
        """改进后的下载和验证方法"""
        try:
            # 清理输出目录
            for f in output_path.glob('*.tif'):
                try:
                    f.unlink()
                except:
                    pass

            # 获取预期分块数
            expected_tiles = fishnet.size().getInfo() if hasattr(fishnet, 'size') else 2

            # 使用更可靠的下载方法
            self.log(f"开始下载{expected_tiles}个分块...")


            self.log(f"geemap下载")
            # 方法2：逐个分块下载
            for i, feature in enumerate(fishnet.getInfo()['features']):
                region = ee.Feature(feature).geometry()
                filename = f"tile_{i + 1}.tif"
                self.log(f"下载分块 {i + 1}/{expected_tiles}...")

                try:
                    geemap.download_ee_image(
                        image=image.clip(region),
                        filename=str(output_path / filename),
                        scale=10,
                        crs='EPSG:4526',
                        region=region,
                    )
                except Exception as e:
                    self.log(f"分块 {i + 1} 下载失败: {str(e)}")
                    raise

            # 验证下载的文件
            tile_files = sorted(output_path.glob('*.tif'))
            if len(tile_files) != expected_tiles:
                raise RuntimeError(f"下载文件数量不匹配: 期望 {expected_tiles}, 实际 {len(tile_files)}")

            # 详细验证每个文件
            for tile in tile_files:
                if not self._validate_tile_completely(tile):
                    raise RuntimeError(f"文件验证失败: {tile.name}")

            return True

        except Exception as e:
            self.log(self.style.ERROR(f"下载验证失败: {str(e)}"))
            # 输出详细的调试信息
            self._debug_download_status(output_path)
            return False

    def _validate_tile_completely(self, tile_path):
        """更全面的文件验证"""
        try:
            # 检查文件基本属性
            if not tile_path.exists() or tile_path.stat().st_size < 1024:  # 至少1KB
                return False

            # 检查GDAL是否能打开
            ds = gdal.Open(str(tile_path))
            if ds is None:
                return False

            # 检查波段
            band = ds.GetRasterBand(1)
            if band is None:
                ds = None
                return False

            # 检查统计数据
            try:
                stats = band.GetStatistics(True, True)
                if stats is None or len(stats) != 4:
                    ds = None
                    return False
            except:
                ds = None
                return False

            # 尝试读取少量数据
            try:
                sample = band.ReadAsArray(0, 0, 10, 10)
                if sample is None:
                    ds = None
                    return False
            except:
                ds = None
                return False

            ds = None
            return True
        except:
            return False

    def _debug_download_status(self, output_path):
        """输出下载状态调试信息"""
        self.log("\n=== 下载调试信息 ===")
        self.log(f"输出目录内容: {[f.name for f in output_path.glob('*')]}")

        for tif_file in output_path.glob('*.tif'):
            self.log(f"\n文件: {tif_file.name}")
            self.log(f"大小: {tif_file.stat().st_size} 字节")

            try:
                with open(tif_file, 'rb') as f:
                    header = f.read(100)
                    self.log(f"文件头: {header[:20].hex()}...")
            except Exception as e:
                self.log(f"读取文件头失败: {str(e)}")

    def save_to_database(self, ee_image, output_path, metadata):
        """将NDVI数据保存到数据库"""
        from django.conf import settings
        from django.db import transaction
        from django.core.exceptions import ObjectDoesNotExist

        try:
            self.log("分块下载完成，开始合并...")
            temp_tif = output_path / 'merged.tif'
            self.merge_tiles(output_path, temp_tif)

            self.log("合并完成，计算统计数据...")
            stats, coverage = self.calculate_stats(temp_tif)

            # 修正特殊值
            def fix_float(value):
                return None if value in (float('-inf'), float('inf'), float('nan')) else value
            self.log("生成缩略图...")
            thumbnail_path = output_path / 'thumbnail.png'
            self.generate_thumbnail(temp_tif, thumbnail_path)

            self.log("保存到数据库...")
            date_str = output_path.name
            rel_path = output_path.relative_to(settings.BASE_DIR)

            # 使用事务确保数据一致性
            with transaction.atomic():
                # 检查是否已存在相同日期的记录
                try:
                    existing_data = NDVIData.objects.get(name=f"beijing_ndvi_{date_str}")
                    self.log(self.style.WARNING(f"数据已存在，将更新记录: {existing_data.id}"))

                    # 更新现有记录
                    with open(thumbnail_path, 'rb') as thumb_file:
                        existing_data.acquisition_date = datetime.strptime(date_str, '%Y%m%d').date()
                        existing_data.resolution = 10.0
                        existing_data.data_dir = str(rel_path)
                        existing_data.min_value = stats['min']
                        existing_data.max_value = stats['max']
                        existing_data.mean_value = stats['mean']
                        existing_data.coverage = coverage
                        existing_data.metadata = metadata

                        # 删除旧的缩略图
                        if existing_data.thumbnail:
                            existing_data.thumbnail.delete()

                        # 保存新缩略图
                        existing_data.thumbnail.save(
                            f"ndvi_thumb_{date_str}.png",
                            File(thumb_file)
                        )

                        existing_data.save()
                        ndvi_data = existing_data

                except NDVIData.DoesNotExist:
                    # 创建新记录
                    with open(thumbnail_path, 'rb') as thumb_file:
                        ndvi_data = NDVIData(
                            name=f"beijing_ndvi_{date_str}",
                            acquisition_date=datetime.strptime(date_str, '%Y%m%d').date(),
                            resolution=10.0,
                            data_dir=str(rel_path),
                            min_value=fix_float(stats['min']),
                            max_value=fix_float(stats['max']),
                            mean_value=fix_float(stats['mean']),
                            coverage=coverage,
                            metadata=metadata
                        )
                        ndvi_data.thumbnail.save(
                            f"ndvi_thumb_{date_str}.png",
                            File(thumb_file)
                        )
                        ndvi_data.save()

            # 清理临时文件
            temp_tif.unlink()
            self.log(self.style.SUCCESS("保存成功！"))

            return ndvi_data

        except Exception as e:
            self.log(self.style.ERROR(f"保存到数据库失败: {str(e)}"))
            raise RuntimeError(f"Database save failed: {str(e)}")

    def merge_tiles(self, tile_dir, output_path):
        """修正后的合并分块方法"""
        from osgeo import gdal
        import glob

        # 获取所有分块文件
        tile_files = sorted(tile_dir.glob('*.tif'))
        if not tile_files:
            raise ValueError("未找到分块文件")

        # 准备文件列表
        file_list = [str(f) for f in tile_files]

        # 方法1：使用新API（GDAL >= 2.1）
        try:
            # 创建VRT
            vrt_path = str(output_path.with_suffix('.vrt'))
            vrt = gdal.BuildVRT(
                destName=vrt_path,
                srcDSOrSrcDSTab=file_list,
                options=gdal.BuildVRTOptions(resampleAlg='near', addAlpha=False)
            )

            if vrt is None:
                raise RuntimeError("无法构建VRT文件")

            # 转换为实际TIFF
            dataset = gdal.Translate(
                destName=str(output_path),
                srcDS=vrt,
                options=gdal.TranslateOptions(
                    format='GTiff',
                    creationOptions=['COMPRESS=LZW', 'TILED=YES']
                )
            )

            # 清理资源
            vrt = None
            dataset = None

            # 删除临时VRT文件
            Path(vrt_path).unlink(missing_ok=True)
            return True

        except Exception as e:
            # 方法1失败时尝试方法2
            self.log(f"VRT方法失败，尝试直接合并: {str(e)}")
            return self.merge_tiles_direct(tile_files, output_path)

    def merge_tiles_direct(self, tile_files, output_path):
        """直接合并方法（备用方案）"""
        from osgeo import gdal

        # 使用第一个分块作为模板
        src_ds = gdal.Open(str(tile_files[0]))
        driver = gdal.GetDriverByName('GTiff')

        # 创建输出文件
        dst_ds = driver.CreateCopy(
            str(output_path),
            src_ds,
            0,
            options=['COMPRESS=LZW', 'TILED=YES']
        )

        # 合并所有分块
        for tile in tile_files[1:]:
            temp_ds = gdal.Open(str(tile))
            if temp_ds is None:
                continue

            # 计算偏移量（确保不越界）
            src_transform = temp_ds.GetGeoTransform()
            dst_transform = dst_ds.GetGeoTransform()

            xoff = int((src_transform[0] - dst_transform[0]) / dst_transform[1])
            yoff = int((dst_transform[3] - src_transform[3]) / abs(dst_transform[5]))

            # 确保偏移量有效
            if xoff < 0 or yoff < 0:
                continue

            # 确保读取范围不超过目标范围
            xsize = min(temp_ds.RasterXSize, dst_ds.RasterXSize - xoff)
            ysize = min(temp_ds.RasterYSize, dst_ds.RasterYSize - yoff)

            if xsize <= 0 or ysize <= 0:
                continue

            # 执行合并
            data = temp_ds.GetRasterBand(1).ReadAsArray()
            dst_ds.GetRasterBand(1).WriteArray(data, xoff, yoff)
            temp_ds = None

        dst_ds.FlushCache()
        dst_ds = None
        src_ds = None
        return True

    def calculate_stats(self, tif_path):
        """添加边界安全检查的计算方法"""
        ds = gdal.Open(str(tif_path))
        if ds is None:
            raise ValueError(f"无法打开文件: {tif_path}")

        # 获取栅格尺寸
        width = ds.RasterXSize
        height = ds.RasterYSize

        # 限制读取范围不超过实际尺寸
        read_width = min(3000, width)  # 示例值，根据实际情况调整
        read_height = min(3000, height)

        band = ds.GetRasterBand(1)

        # 安全读取数据
        try:
            array = band.ReadAsArray(
                xoff=0,
                yoff=0,
                win_xsize=read_width,
                win_ysize=read_height
            )
        except Exception as e:
            raise RuntimeError(f"读取栅格数据失败: {str(e)}")

        # 计算统计信息
        stats = {
            'min': float(np.nanmin(array)),
            'max': float(np.nanmax(array)),
            'mean': float(np.nanmean(array)),
            'stddev': float(np.nanstd(array))
        }

        # 获取空间范围（修正负值问题）
        transform = ds.GetGeoTransform()
        x_min = max(transform[0], 0)  # 确保不小于0
        y_max = max(transform[3], 0)
        x_max = x_min + transform[1] * width
        y_min = y_max + transform[5] * height

        from django.contrib.gis.geos import Polygon
        coverage = Polygon.from_bbox((
            max(x_min, 0),
            max(y_min, 0),
            max(x_max, 0),
            max(y_max, 0)
        ))

        ds = None  # 关闭数据集

        return stats, coverage

    def generate_thumbnail(self, tif_path, output_path, size=(256, 256)):
        """生成缩略图"""
        ds = gdal.Open(str(tif_path))
        band = ds.GetRasterBand(1)
        array = band.ReadAsArray()

        # 归一化处理
        array = (array - array.min()) / (array.max() - array.min()) * 255
        array = array.astype(np.uint8)

        # 创建缩略图
        im = Image.fromarray(array)
        im.thumbnail(size)
        im.save(output_path)
