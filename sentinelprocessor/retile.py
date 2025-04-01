import logging
import os
import hashlib
import zipfile
from tqdm import tqdm

logger = logging.getLogger("retile")


def retile_products(self, products, overlap=32):
    logger.debug("Retiling products with overlap %d" % overlap)
    zipdir = f"{self.dataPath}/extracted"
    virts = []

    paths = []
    for id in products:
        product = products[id]
        paths.append(f"{self.dataPath}/products/{product['title']}")

    with tqdm(desc="Unzipping products",
              total=len(paths),
              unit="tile") as progress:
        for zipp in paths:
            ziptitle = zipp.split("/")[-1]
            if os.path.exists(f"{zipdir}/{ziptitle}"):
                continue
            with zipfile.ZipFile(zipp, 'r') as zipref:
                zipref.extractall(zipdir)
            os.remove(zipp)
            progress.update()

    with tqdm(desc="Reprojecting image tiles",
              total=len(products),
              unit="tile") as progress:
        for id in products:
            product = products[id]
            bandpaths = f"{zipdir}/{product['title']}"
            virts.append(f"{bandpaths}/tile.vrt")
            os.system(f"gdalbuildvrt -q -separate %s %s %s %s %s"
                      % (f"{bandpaths}/rgb.vrt", f"{bandpaths}/B02.tif", f"{bandpaths}/B03.tif",
                         f"{bandpaths}/B04.tif", f"{bandpaths}/B08.tif"))
            os.system("gdalwarp -q -t_srs EPSG:3857 %s %s" %
                      (f"{bandpaths}/rgb.vrt", f"{bandpaths}/tile.vrt"))
            progress.update()

    source_tiles = ' '.join(virts)
    tilesize = 10008 + overlap * 2

    logger.info("Building image mosaic VRT")
    os.system("gdalbuildvrt mosaic.vrt %s" % source_tiles)
    # os.system("gdalwarp -te %s %s %s %s virt.vrt virt2.vrt" % (s1[0], s1[1], s2[0], s2[1]))

    logger.info("Retiling images with tilesize %s" % tilesize)
    os.mkdir(f"{self.dataPath}/retiled")
    os.system(
        'gdal_retile -ps %s %s -overlap %s -targetDir %s %s' % (
            tilesize, tilesize, overlap, f"{self.dataPath}/retiled", "mosaic.vrt"))

    directory = os.fsencode(f"{self.dataPath}/retiled")
    dirlist = os.listdir(directory)
    processeddir = f"{self.dataPath}/processed"
    os.mkdir(processeddir)

    processpaths = []

    with tqdm(desc="Final tile preprocessing",
              total=len(dirlist),
              unit="tile") as progress:
        for file in dirlist:
            filename = os.fsdecode(file)
            filename_full = f"{self.dataPath}/retiled/{filename}"
            file_hash = hashlib.md5(filename.encode()).hexdigest()
            os.system("gdal_translate -q -of COG %s %s" %
                      (filename_full, f"{processeddir}/{file_hash}.tif"))
            os.remove(filename_full)
            processpaths.append(f"{processeddir}/{file_hash}.tif")
            progress.update()

    return processpaths
