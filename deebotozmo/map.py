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
        self.rooms = []
        self.charger_position = None
        self.robot_position = None

        self.colors = {"floor": "#badaff", "wall": "#4e96e2", "carpet": "#1a81ed"}

        self.draw_charger = False
        self.draw_robot = False

        self.room_colors = {"Default": (186,203,255,255),
        "Living Room": (181,235,255,255),
        "Dinning Room": "",
        "Bedroom": (212,223,255,255),
        "Study": "",
        "Bathroom": (247,197,181,255),
        "Kitchen": "",
        "Laundry": "",
        "Lounge": "",
        "StoreRoom": "",
        "Kids room": (253,247,226,255),
        "Sunroom": ""}

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
    
    def updateRobotPosition(self, cordx, cordy):
        _LOGGER.debug("New robot position: " + str(cordx) + ',' + str(cordy))
        
        self.robot_position = {'x':cordx ,'y': cordy}

        self.draw_robot = True
        self.isMapUpdated = False

    def updateChargerPosition(self, cordx, cordy):
        _LOGGER.debug("New charger position: " + str(cordx) + ',' + str(cordy))
        
        self.charger_position = {'x':cordx ,'y': cordy}
        
        self.draw_charger = True
        self.isMapUpdated = False

    def GetBase64Map(self):
        if self.isMapUpdated == False:
            _LOGGER.debug("GetBase64Map begin")

            resizeFactor = 10
            pixelWidth = 50
            offset = 400

            im = Image.new("RGBA", (1000, 1000))
            draw = ImageDraw.Draw(im)

            #Draw Rooms
            for room in self.rooms:
                coordsXY = room['values'].split(';')
                listcord = []
                _sumx = 0
                _sumy = 0
                _points = 0
                
                for cord in coordsXY:
                    cord = cord.split(',')

                    x = (int(cord[0])/pixelWidth)+offset
                    y = (int(cord[1])/pixelWidth)+offset

                    listcord.append(x)
                    listcord.append(y)

                    # Sum for center point
                    _sumx = _sumx + x
                    _sumy = _sumy + y


                draw.line(listcord,fill=(255,0,0),width=1)
                
                centerX = _sumx / len(coordsXY)
                centerY = _sumy / len(coordsXY)

                ImageDraw.floodfill(im,xy=(centerX,centerY),value=self.room_colors[room['subtype']])

                draw.line(listcord,fill=(0,0,0,0),width=1)

            #Draw MAP
            imageX = 0
            imageY = 0

            for i in range(64):
                if i > 0:
                    if i % 8 != 0:
                            imageY += 100
                    else:
                        imageX += 100
                        imageY = 0

                for y in range(100):
                    for x in range(100):
                        if self.buffer[i][x][y] == 0x01: #floor
                            if im.getpixel((imageX+x,imageY+y)) == (0,0,0,0):
                                draw.point((imageX+x,imageY+y), fill=self.colors['floor'])
                        if self.buffer[i][x][y] == 0x02: #wall
                            draw.point((imageX+x,imageY+y), fill=self.colors['wall'])
                        if self.buffer[i][x][y] == 0x03: #carpet
                            if im.getpixel((imageX+x,imageY+y)) == (0,0,0,0):
                                draw.point((imageX+x,imageY+y), fill=self.colors['carpet'])

            del draw

            # Resize * resizeFactor
            im = im.resize((im.size[0]*resizeFactor, im.size[1]*resizeFactor), Image.NEAREST)

            if self.draw_charger:
                #Draw Current Deebot Position
                robot_icon = Image.open("robot.png")
                im.paste(robot_icon, (int(((self.robot_position['x']/pixelWidth)+offset)*resizeFactor), int(((self.robot_position['y']/pixelWidth)+offset)*resizeFactor)), robot_icon.convert('RGBA'))

            if self.draw_robot:
                #Draw charger
                charger_icon = Image.open("charger.png")
                im.paste(charger_icon, (int(((self.charger_position['x']/pixelWidth)+offset)*resizeFactor), int(((self.charger_position['y']/pixelWidth)+offset)*resizeFactor)), charger_icon.convert('RGBA'))

            #Flip
            im = ImageOps.flip(im)

            #Crop
            imageBox = im.getbbox()
            cropped=im.crop(imageBox)

            #save
            buffered = BytesIO()

            cropped.save(buffered, format="PNG")

            self.isMapUpdated = True

            self.base64Image = base64.b64encode(buffered.getvalue())
            _LOGGER.debug("GetBase64Map done")

        return self.base64Image