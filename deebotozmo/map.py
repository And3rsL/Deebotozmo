from io import BytesIO
import base64
import lzma
import numpy as np
import logging
from PIL import Image, ImageDraw, ImageOps
#import matplotlib.path as mplPath

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

        self.room_colors = [(238,225,235,255),(239,236,221,255),(228,239,223,255),(225,234,239,255),(238,223,216,255),(240,228,216,255),(233,139,157,255),(239,200,201,255),(201,2019,239,255)]
        self.robot_png = "iVBORw0KGgoAAAANSUhEUgAAAAYAAAAGCAIAAABvrngfAAAACXBIWXMAAAsTAAALEwEAmpwYAAAF0WlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDUgNzkuMTYzNDk5LCAyMDE4LzA4LzEzLTE2OjQwOjIyICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ0MgMjAxOSAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyMC0wNS0yNFQxMjowMzoxNiswMjowMCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo0YWM4NWY5MC1hNWMwLTE2NDktYTQ0MC0xMWM0NWY5OGQ1MDYiIHhtcE1NOkRvY3VtZW50SUQ9ImFkb2JlOmRvY2lkOnBob3Rvc2hvcDo3Zjk3MTZjMi1kZDM1LWJiNDItYjMzZS1hYjYwY2Y4ZTZlZDYiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpiMzhiNGZlMS1lOGNkLTJjNDctYmQwZC1lNmZiNzRhMjFkMDciIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIj4gPHhtcE1NOkhpc3Rvcnk+IDxyZGY6U2VxPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY3JlYXRlZCIgc3RFdnQ6aW5zdGFuY2VJRD0ieG1wLmlpZDpiMzhiNGZlMS1lOGNkLTJjNDctYmQwZC1lNmZiNzRhMjFkMDciIHN0RXZ0OndoZW49IjIwMjAtMDUtMjRUMTI6MDM6MTYrMDI6MDAiIHN0RXZ0OnNvZnR3YXJlQWdlbnQ9IkFkb2JlIFBob3Rvc2hvcCBDQyAyMDE5IChXaW5kb3dzKSIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6NGFjODVmOTAtYTVjMC0xNjQ5LWE0NDAtMTFjNDVmOThkNTA2IiBzdEV2dDp3aGVuPSIyMDIwLTA1LTI0VDEyOjAzOjE2KzAyOjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgQ0MgMjAxOSAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPC9yZGY6U2VxPiA8L3htcE1NOkhpc3Rvcnk+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+AP7+NwAAAFpJREFUCJllzEEKgzAQhtFvMkSsEKj30oUXrYserELA1obhd+nCd4BnksZ53X4Cnr193ov59Iq+o2SA2vz4p/iKkgkRouTYlbhJ/jBqww03avPBTNI4rdtx9ScfWyYCg52e0gAAAABJRU5ErkJggg=="
        self.charger_png = "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAOCAYAAAAWo42rAAAAdUlEQVQoU2NkQAP/nzD8BwkxyjAwIkuhcEASRCmEKYKZhGwq3ER0ReiKSVOIyzRkU8EmwhUyKzAwSNyHyL9QZGD4+wDMBLmVEasimFHIiuEKpcHBhwmeQryBMJFohcjuw2s1SBKHZ8BWo/gauyshvobJEYoZAEOSPXnhzwZnAAAAAElFTkSuQmCC"

    def isUpdatePiece(self, index, mapPiece):
        _LOGGER.debug("isUpdatePiece " + str(index) + ' ' + str(mapPiece))

        value = str(index) + '-' + str(mapPiece)
        
        if self.mapPieces[index] != value:
            self.mapPieces[index] = value

            if str(mapPiece) != '1295764014':
                self.isMapUpdated = False
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
        if(self.robot_position != None):
            if (self.robot_position['x'] != cordx) or (self.robot_position['y'] != cordy):
                _LOGGER.debug("New robot position: " + str(cordx) + ',' + str(cordy))
                self.robot_position = {'x':cordx ,'y': cordy}
                self.isMapUpdated = False
        else:
            _LOGGER.debug("robot position set: " + str(cordx) + ',' + str(cordy))
            self.robot_position = {'x':cordx ,'y': cordy}
            self.isMapUpdated = False
            self.draw_robot = True

    def updateChargerPosition(self, cordx, cordy):
        if(self.charger_position != None):
            if (self.charger_position['x'] != cordx) or (self.charger_position['y'] != cordy):
                _LOGGER.debug("New charger position: " + str(cordx) + ',' + str(cordy))
                self.charger_position = {'x':cordx ,'y': cordy}
                self.isMapUpdated = False
        else:
            _LOGGER.debug("charger position set: " + str(cordx) + ',' + str(cordy))
            self.charger_position = {'x':cordx ,'y': cordy}
            self.isMapUpdated = False
            self.draw_charger = True

    #def isInsideRoom(self, room, point):
    #    roomBorder = mplPath.Path(room)
    #    return roomBorder.contains_point(point)

    def GetBase64Map(self):
        if self.isMapUpdated == False:
            _LOGGER.debug("GetBase64Map begin")

            resizeFactor = 10
            pixelWidth = 50
            offset = 400

            im = Image.new("RGBA", (3000, 3000))
            draw = ImageDraw.Draw(im)
            roomnr = 0

            _LOGGER.debug("GetBase64Map draw_rooms")
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

                ImageDraw.floodfill(im,xy=(centerX,centerY),value=self.room_colors[roomnr % len(self.room_colors)])

                draw.line(listcord,fill=(0,0,0,0),width=1)
                roomnr = roomnr +1

            _LOGGER.debug("GetBase64Map draw_map")

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

            if self.draw_charger:
                _LOGGER.debug("GetBase64Map draw robot")
                #Draw Current Deebot Position
                robot_icon = Image.open(BytesIO(base64.b64decode(self.robot_png)))
                im.paste(robot_icon, (int(((self.robot_position['x']/pixelWidth)+offset)), int(((self.robot_position['y']/pixelWidth)+offset))), robot_icon.convert('RGBA'))

            if self.draw_robot:
                _LOGGER.debug("GetBase64Map draw charger")
                #Draw charger
                charger_icon = Image.open(BytesIO(base64.b64decode(self.charger_png)))
                im.paste(charger_icon, (int(((self.charger_position['x']/pixelWidth)+offset)), int(((self.charger_position['y']/pixelWidth)+offset))), charger_icon.convert('RGBA'))


            _LOGGER.debug("GetBase64Map flip")

            #Flip
            im = ImageOps.flip(im)

            _LOGGER.debug("GetBase64Map crop")
            #Crop
            imageBox = im.getbbox()
            im=im.crop(imageBox)

            _LOGGER.debug("GetBase64Map resize")
            # Resize * resizeFactor
            im = im.resize((im.size[0]*resizeFactor, im.size[1]*resizeFactor), Image.NEAREST)

            _LOGGER.debug("GetBase64Map save")
            #save
            buffered = BytesIO()

            im.save(buffered, format="PNG")

            self.isMapUpdated = True

            self.base64Image = base64.b64encode(buffered.getvalue())
            _LOGGER.debug("GetBase64Map done")
        else:
            _LOGGER.debug("GetBase64Map NO NEED TO UPDATE")

        return self.base64Image