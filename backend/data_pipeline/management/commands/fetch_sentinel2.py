import ee
import geemap
import os
from datetime import datetime, timedelta
import logging
from django.core.management.base import BaseCommand
from pathlib import Path

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'NDVI数据'

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
            self.stdout.write(self.style.SUCCESS(f'数据已保存至：{output_dir}'))
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
        henan = ee.FeatureCollection("projects/ee-brucepengyuan/assets/he_nan")
        valid_geometry = henan.geometry().bounds()

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
        print("Joined集合首个元素类型:",
              ee.Algorithms.ObjectType(joined_collection.first()).getInfo())  # 应显示Feature

        # 应用处理并计算NDVI
        # processed_images = joined_collection.map(process_joined_element)
        processed_images = ee.ImageCollection(joined_collection.map(cloud_masking)) \
            .filter(ee.Filter.neq('system:band_names', None))
        print("处理后集合首个元素类型:",
              ee.Algorithms.ObjectType(processed_images.first()).getInfo())  # 应显示Image

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
        # 检查图像元数据
        print("波段信息:", image.bandNames().getInfo())  # 应显示['NDVI']
        print("非空检查:", image.bandNames().size().gt(0).getInfo())  # 应返回True

        # 若为空图像则抛出异常
        if not image.bandNames().size().gt(0).getInfo():
            raise ValueError("生成图像为空，请检查输入数据")
        filename = f"beijing_ndvi_{datetime.now().strftime('%Y%m%d')}"
        output_path = output_dir / filename
        output_path.mkdir(parents=True, exist_ok=True)

        # 从get_sentinel2_data获取边界
        valid_geometry = self.get_sentinel2_data().geometry()

        # 生成鱼网分块（关键步骤）[2,5](@ref)
        fishnet = geemap.fishnet(
            valid_geometry,
            rows=8,
            cols=6,
            delta=0.5
        )
        geemap.download_ee_image_tiles(
            image=image,
            # filename=str(output_path),
            # region=image.geometry(),
            scale=10,  # 分辨率改为10米（网页1）
            crs='EPSG:4526',  # 中国专用投影坐标系
            num_threads=10,
            # quiet=True,
            features=fishnet,
            out_dir=output_dir,
        )
