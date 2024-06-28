import errno
import os
import shutil
import sys

import boto3
import requests
from fp.fp import FreeProxy

from gui.gui_utils import DownloadBarFrame, DownloadProgressBar, InformationTable

SRID = "4326"
TIME_FORMAT = "T00:00:00.000Z"
TIME_END_FORMAT = "T12:00:00.000Z"
ENDPOINT_URL = "https://eodata.dataspace.copernicus.eu/"
BUCKET = "eodata"


def get_tile_list(satellite_grid, input_shapefile):
    if input_shapefile.crs != satellite_grid.crs:
        input_shapefile = input_shapefile.to_crs(satellite_grid.crs)
    # Convert second shapefile to single polygon
    single_polygon = input_shapefile.geometry.unary_union
    # Loop through polygons in first shapefile and check for intersection with single polygon
    selected_polygons = []
    tiles = []
    for _, row in satellite_grid.iterrows():
        if row.geometry.intersects(single_polygon):
            selected_polygons.append(row)

    sorted_list = sorted(selected_polygons, key=lambda x: (single_polygon.difference(x.geometry)).area, reverse=False)

    for tile_grid in sorted_list:
        if tile_grid.geometry.intersects(single_polygon):
            single_polygon = single_polygon.difference(tile_grid.geometry)
            tiles.append(tile_grid["Name"])

    return tiles


def get_folder_size(folder_path):
    total_size = 0
    for path, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(path, file)
            total_size += os.path.getsize(file_path)
    return total_size


def make_path(path):
    try:
        os.makedirs(path)
    except EnvironmentError as _error:
        if _error.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def generate_filter_query(qp):
    """Генерация строки фильтра для запроса к хранилищу данных."""
    filter_query = (
        f"Collection/Name eq '{qp['setillite']}' "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq '{qp['producttype']}') "
        f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
        f"and att/OData.CSC.DoubleAttribute/Value lt {qp['cloud_percentage']}) "
        f"and OData.CSC.Intersects(area=geography'SRID={SRID};{qp['footprint']}') "
        f"and ContentDate/Start gt {qp['date_start']}{TIME_FORMAT} "
        f"and ContentDate/Start lt {qp['date_end']}{TIME_END_FORMAT}"
    )
    return filter_query


def get_s3path(qp, satellite_grid, input_shapefile):
    try:
        filter_query = generate_filter_query(qp)
        all_proxies = FreeProxy(timeout=1, rand=True).get_proxy_list(repeat=False)

        for proxy in all_proxies:
            proxies = {"http": proxy, "https": proxy}
            url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter={filter_query}"

            try:
                result = requests.get(url, timeout=60, allow_redirects=False, proxies=proxies).json()
                zones = get_tile_list(satellite_grid, input_shapefile)
                print("Зоны, покрывающие область интересов:", ", ".join(map(str, zones)))
                if result.get("value"):
                    products_s3path = [
                        product["S3Path"]
                        for product in result["value"]
                        if any(zone == product["Name"][39:44] for zone in zones)
                    ]
                    if products_s3path:
                        return products_s3path
                    else:
                        print("Продукты не найдены в каталоге CDSE")
                        sys.exit()
                else:
                    print("В каталоге CDSE не найдено продуктов с указанными параметрами")
                    sys.exit()

            except requests.RequestException as e:
                continue
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit()


def download_file(resource, bucket, obj, target_directory):
    target = os.path.join(target_directory, obj.key)

    if obj.key.endswith("/"):
        make_path(target)
    else:
        dirname = os.path.dirname(target)
        if dirname != "":
            make_path(dirname)
        resource.Object(bucket, obj.key).download_file(target)


def download_sentinel_images(
    access_key, secret_key, qp, satellite_grid, input_shapefile, target_directory, master_frame
):
    s3_path = get_s3path(qp, satellite_grid, input_shapefile)

    data_for_table = [[path.split("/")[-1], "необходимо загрузить"] for path in s3_path]
    information_table = InformationTable(master=master_frame, data=data_for_table)
    products_path = []
    for s3path_prod in s3_path:
        s3path = s3path_prod.removeprefix(f"/{BUCKET}/")
        file_name = s3path.split("/")[-1]
        dirname = os.path.dirname(s3path)

        if not os.path.exists(os.path.join(target_directory, dirname)):
            make_path(os.path.join(target_directory, dirname))
        fls = os.listdir(os.path.join(target_directory, dirname))

        resource = boto3.resource(
            service_name="s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key, endpoint_url=ENDPOINT_URL
        )
        s3path = s3path + ""
        objects = list(resource.Bucket(BUCKET).objects.filter(Prefix=s3path))

        s3_size = sum([obj.size for obj in objects])
        if not objects:
            raise Exception("Продукты не найдены в каталоге CDSE")

        size_directory = get_folder_size(os.path.join(target_directory, s3path))

        download_location = os.path.join(target_directory, s3path)

        if file_name in fls and s3_size == size_directory:
            print(f"Файл {file_name} находится в папке")
            for row_num, row in enumerate(data_for_table):
                if row[0] == file_name:
                    # Изменить значение в поле 1 на new_status
                    information_table.insert(row_num, 1, "в папке")
                    break
            products_path.append(s3path)

        else:
            if os.path.exists(os.path.join(download_location, "GRANULE")):
                shutil.rmtree(os.path.join(download_location, "GRANULE"))

            print(f"Продукт {file_name} не находится в папке. Необходимо загрузить...")
            for row_num, row in enumerate(data_for_table):
                if row[0] == file_name:
                    # Изменить значение в поле 1 на new_status
                    information_table.insert(row_num, 1, "загрузка...")
                    break

            download_barr = DownloadBarFrame(master=master_frame)
            DownloadProgressBar(download_barr.download_barr_frame, download_location, s3_size)

            for obj in objects:
                download_file(resource, BUCKET, obj, target_directory)
            print(f"Продукт Sentinel-2: {file_name} загружен!")
            for row_num, row in enumerate(data_for_table):
                if row[0] == file_name:
                    # Изменить значение в поле 1 на new_status
                    information_table.insert(row_num, 1, "загружено!")
                    break
            products_path.append(s3path)

    return products_path
