from io import BytesIO
import base64
import lzma
import numpy as np
import logging
from PIL import Image, ImageDraw, ImageOps

_LOGGER = logging.getLogger(__name__)

class Map:
    def __init__(self):
        self.buffer = np.zeros((64, 100, 100))
        self.mapPieces = np.empty((64), np.dtype('U100'))
        self.isMapUpdated = False
        self.base64Image = None

    def isUpdatePiece(self, index, mapPiece):
        _LOGGER.debug("isUpdatePiece " + str(index) + ' ' + str(mapPiece))

        value = str(index) + '-' + str(mapPiece)
        
        if self.mapPieces[index] != value:
            self.mapPieces[index] = value

            self.isMapUpdated = False

            if str(mapPiece) != '1295764014':
                return True
            else:
                return False

        _LOGGER.debug("AddMapPiece not to update")

    def AddMapPiece(self, mapPiece, b64):
        _LOGGER.debug("AddMapPiece " + str(mapPiece) + ' ' + str(b64))

        decoded = self.decompress7zBase64Data(b64)

        decoded = list(decoded)
        MATRIX_PIECE = np.reshape(decoded,(100,100))

        self.buffer[mapPiece] = MATRIX_PIECE
        _LOGGER.debug("AddMapPiece done")

    def decompress7zBase64Data(self, data):
        _LOGGER.debug("decompress7zBase64Data begin")
        finalArray = bytearray()

        # Decode Base64
        data = base64.b64decode(data)

        i = 0
        for idx in data:
            if (i == 8):
                finalArray += b'\x00\x00\x00\x00'
            finalArray.append(idx)
            i +=1

        dec = lzma.LZMADecompressor(lzma.FORMAT_AUTO, None, None)

        decompressed_data = dec.decompress(finalArray)

        _LOGGER.debug("decompress7zBase64Data done")
        return decompressed_data
    
    def GetBase64Map(self):
        if self.isMapUpdated == False:
            _LOGGER.debug("GetBase64Map begin")
            im = Image.new("RGBA", (6400, 6400))
            draw = ImageDraw.Draw(im)

            _LOGGER.debug("GetBase64Map finish initializing")

            imageX = 0
            imageY = 0

            for i in range(64):
                if i > 0:
                    if i % 8 != 0:
                            imageY += 100
                    else:
                        imageX += 100
                        imageY = 0

                for x in range(100):
                    for y in range(100):
                        if self.buffer[i][x][y] == 0x01: #floor
                            draw.point((imageX+x,imageY+y), fill=(186,218,255))
                        if self.buffer[i][x][y] == 0x02: #wall
                            draw.point((imageX+x,imageY+y), fill=(78,150,226))


            draw.point((9,22), fill=(255,0,0))
            _LOGGER.debug("GetBase64Map finish drawing")
            
            del draw

            #Flip
            im = ImageOps.flip(im)
            _LOGGER.debug("GetBase64Map finish flip")
            
            #Crop
            imageBox = im.getbbox()
            cropped=im.crop(imageBox)
            _LOGGER.debug("GetBase64Map finish crop")
            #save
            buffered = BytesIO()
            cropped.save(buffered, format="PNG")
            _LOGGER.debug("GetBase64Map finish saving")
            self.isMapUpdated = True

            self.base64Image = base64.b64encode(buffered.getvalue())

        return self.base64Image