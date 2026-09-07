"""
Button Box Control Panel - GUI version
------------------------------------------
Combines everything the console script did into one window, plus:
  - Live status: vJoy connection, connected boards, current flag,
    last button pressed, a live fuel-remaining gauge (from iRacing
    telemetry), manual flag-trigger buttons for testing, and a
    scrolling log
  - An editable button-mapping table (Code -> vJoy button #) - no
    more editing Python source to rename or renumber a button
  - A live Display Preview using the actual icon artwork (embedded
    as base64 PNGs - no separate image files needed)
  - System tray support: closing the window minimizes to tray
    instead of quitting; right-click the tray icon for Show/Hide/Quit

Mappings are stored in button_mappings.json, next to this script.
On first run, that file is created automatically with your current
known mapping as the defaults.

SETUP
-----
pip install pyserial pyvjoy pyirsdk pillow pystray
(tkinter ships with Python on Windows - nothing extra to install for it)

Run: python button_box_gui.py
"""

import base64
import io
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import serial
import serial.tools.list_ports
import pyvjoy
from PIL import Image, ImageTk, ImageDraw

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except Exception:
    PYSTRAY_AVAILABLE = False

try:
    import irsdk
    IRSDK_AVAILABLE = True
except ImportError:
    IRSDK_AVAILABLE = False

# ---------------------------------------------------------------
# Icon artwork, embedded directly as base64 PNGs (white icon, real
# alpha transparency) so this stays a single self-contained file -
# no separate image assets to keep track of or lose. Sourced from
# the same SVGs used to build the ESP32 firmware's icons.h.
# ---------------------------------------------------------------
ICON_B64 = {

    "RESET": "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",
    "TORTOISE": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAFZElEQVR4nO2aW6hUVRjHf+eYZuXxinZTMQozS/HBLtZDYUI30uihoCAjKagQ7EJFSEGChm+GmAm9dMMgK0PRopJQLDBKCyqzILMsTc1b3s7p/HpYe5p9xpk9e52Z2g/OHxZsZq9vfZd1+f7f2tOmciqjvWgDikYrAEUbUDRaASjagKLRCkDRBhSNVgCKNqBotAJQtAFFoxWAog0oGq0AFG1A0TitSeMMB24ArgUuBkYBg5J3R4H9wFZgC7AW2AR0N0l3Y1AbaePU19XjxmGb+rDat0H9DbfeCp6mzldPRDpeiW/Uq4sMQJvxV2JDgRXAdU1ahJ3AHGBJE8YaBtxJsO08whbfRdhyy4EfTpKIjNgw9YsGZ70W5jYwk+3qk+rhjPH/VpeoA9OyMUpOVz9tkrO1MCfCnrTzr0Xo+FwdbC8CsKQh1/KhS50SYRPqM73Q85Eatn+Eosnq3t75lRtvGA7YvDZdZHwGKmGWOQNwVup5vLq1lwrrYaHaJ9EzNoddqEvrjLlT7azx7ke1vZ6CNvVjdV7yjDpIfVntjnaxOn5VZ6R03mI4zKbXsa2vui9j3LssT9qBGn2m1QvAzFTn5eqQ1Ltr1A/y+3kS9qvPGQKKYfbnWp6x79V+GbbdmDH2voq+K2v0ez7L+Q719wqBHeqtFf0uVReomw2pJgv71HfVe9QBqTHGqp9U6f9ohn2vZujpVq9I+g01rLJqWJdFhOYBc2u8Wwc8DXxW8fsgYCwwmkCY2oDDwJ6EhPxEzxpgKPAE8AjQr4qevcCFwIGK30cC3wNn1DKeUINsACYCZ9fos71WdEepf9WZTdWN6oUZs5TVZqkHc+iYV0X2zRxyeXCwVjW4EDgzI7olTKFcUc5OIv0l8AuhAuwEOggU9RJgMrAI2EyY/Y4cOuYAiwmUth1YANyRQy4P2qrNzHXmP+F3Ws4Om3LKPJj0nxoxUy8kMjdFyOTB6krnh6s/Rwyw2HJKOppT5kXL/OJQTpnjlrfa+xH2ZeEPdVza+f6GnJ8X3Yb7ANRpEXLfpnQui5BbnshcYHbRUw9d6lvqaFNM8Ax1beRAa8yXkqrhqkTuigiZbvXyRO6xHH23q1sMB/Vqw2q9Tz3f1KovOR9LaLos59mB5ssYaZS2AeqqCLl1hjOnj6Gqq/b+bitK3qwWuwxLWJQaZF4v5P8ypFoMBc2xCNmZidwky6zxUwMzjU7HmM2nq2G7gSWijlGPRMqXUNrTqM9GyO1RRyRyD6k32wvHTQXg5QjlBw2RLw2wIkK2Gq5PxmlX38spc1S93wacTrcSFZ6YtBL56QsMAQYD5wBXAmOA6cCapM8DwEsNEpHfCORoJ4EUbQAGEMjUNgKZ2k+gwrsIlHorcKJBvf8i5lK0AziUPE8DVlOdv8fia8Il5j5C7fC//nGxFhUeDYwHRhBm4kvKzkOYiVXAbTT2dWkXsIxQMEFwvn+iewzQBRyh/GHl0EkjNArLPGC2gQhVuzw4oL5iz/2POkF92/jLkT3qU/YsiacYLjdrFUidhhug/s3a/yaHYLu6Pqfh3aZYVKpNNKTG3XVk1xtO7lIWKaWzj3Lq154puCmH4ATgq8iF8zShKqtEX0KFOAk4l7Cc/yQs343Ajor+bcCHwNQI3bsIB3NzoI60/k1OCcfUx5s5A8lqqHVlVQ3fNVN/6WF+HaVd6jv2/vIjT5thuAfMwnF7XqA2ZQuUFsMU4F7CCTwU2E1YshuAlcnS+6/RRuAFtwOXET6zdxD4wiZgKWE7NU9hKgCnJE75f4i0AlC0AUWjFYCiDSgarQAUbUDRaAWgaAOKRisARRtQNFoBKNqAotEKQNEGFI1/AKTE4G3uJUQoAAAAAElFTkSuQmCC",
    "WHEEL_REPAIR": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAJGUlEQVR4nN2be7BXVRXHv/cij0ApCOMpDEg2hmLSkI8iDRVknOghNZSmg46M4pCG5IRYapmj00xljZIpSCaoDIiiTCgFhU5BGtSoiWiKpTwFuQIC9/Xpj3VOZ//O3fs8fnC7v/rO7Lm/316Pvdc6e+299jq/WweoBnCMpGskfUXSRyU1Sdog6X5JD0pqaa+B62rAASMkLZc0JEBfLenLkva0x+Ad7YA+ktZLOi6H7ylJEyQd8cnWH2mFJTFL+cZL0nhJX2iPCXSkA+okfb0E/0XtMYmOdEBvSf1K8I9oj0l0pAPKxnO7bFYd6YB3JW0rwf9ye0yio1fAwhL8C9pjErVwDG6QNCiH7//2GHxHZtibGTy/lzRZZvzRkr4vaZOknZJ+J+mcw5oBUAutJ/Bd4AXgILAPWANMATpFPJ8H3qQtWoCLqh27o0OgCPpLukPSNzJ49ks6SdLmsso7OgSyUCdpqqSNyjZeknpIuquqQWp0BZwg6VeSTi8pd6GkR8sI1KIDhkh6XnZCSFKjpC4FZd+W9HFJ7xUdrBZD4EYlxh+U9OcSsgMl3VZmsFp0wNnO5x9LGh7gaw70XyXptKKD1aIDYsP+JWmF/BemNxQukNRLukfSUUUGq0UHPB39nSnpswGelZK6Zeg4RdKMQqPVQBKUbv2BpdHnZzyJD8AkoClAi7EfGPq/mgh1ktRT0g61XcotsuRoRwE9K2SpdhC1GAKSGXme/HG8XtL7BfWcL7tHBFGrDpBs8j6slNS1hJ6fSuoVItaqA+pkhVAf8jbANPpKuj04UI3uAZ+Q1QnS2C/pw5IGSHq9hD4knSFpXZpQaytgoKSrJd0boK+RdEjlVoBkK2q2j1AoWWhnDJe9+fmSLIOry+BdGf0tswfEGB/JHXI7O8oBI5UYPbKEXOyAsitAsgvVEFk16T/4bzqgTtKVkq6TdHwV8pskvRR9/tARmlNVe0AnWfWlXhavTbJNJt0eScnNkHS3qjN+l6QpSoqi1dQBD8hXMSqZpn4O+FuUaj4A/DYjFT2Ykn0tJ3X1yT8JXA580NEzHKsZlsUSPDYVNXwosNijdGfGgI0kBU0BrxeY5F5gETAZK5T65jKjgJ40moBRPn15htcBNwMHqhgU4ERH1y0Bnl3AfGAi0C1nPgK6Ahsj2feBhgLz+E5IX95go4taGsAdjq5OwE1YKLwI3A2cCxyVMwdfOwtYDfykwBzmZ+kKZYL1smNqm6Qlkj6SsbnslFVut8jqd/0lDYtaoywDW1/FppWHCZKWKfske0Z2qToU5Ah4ZmbkvRZgu8erTcC9wBgq49xtJwLfA14FxmY8hcFVrICTgD05T/4fwLF5unwroJ+kV2T3cR/+IDvPN3ponWXHootestdZx0t6XPYarIekUZIukFVvJkp6IviUKjFA0lpl/7Jkt2zlbcrgMXi8MjfDq3OAzg7vWOA+YDNwCGgFtgKPA5ekeC/FjjYfNgFdCjz5Y4C/5jz5RuAcR2YQdnQW2gRPxZa9D+5mMhhY6dAOAFOx93fueb8Jyx1iuUmYk3z4do7xnYBlOcYTzSPtsDNCetMdawJK15I8oVOBbSn6rx0dl6ZoTVgyE9N/FBijgeyYvSvD6Bg/xO+wM0N63S/d8BcaW4HTIp4BwNtYhtY7UvwesMrRc0MkNx3oAdwINAPjI3oPYEvAgHGBiV5fwPjFQD1+hxVygLDX0btTih9z6IuivglO302RgRMjI1/CqrkxvQvmxLeA7lHf9NQYzcDP8OcEXyQcljHWAR8g7LBPF3HANdiRlU5vJ0f0kSTxO8+Z7LWeCS0lCZlLnP5ro76+KaP2YcfWPCz7dJ3nO4ZdbAb6OTKTaOuwz1DAAb7LSjPJReQHKdrfgTsdvqXYRrkr6lsK/CYl80dnvD8FDBrk8Jwb4InRAJzs8I/G3gekMYYCDtjsEXzLoa+OlM/CLiSxAa1UhsRA7CgEeAO4FbgCc3ALycqYHzDqBEfXrRnGN2OnTsw7lLabc4yqHfCcQ38F28Hj74M8PHG7LaJd5vSNi/qGpHjScB0QejMElmW6Yy7J4A1monkFEbc+h5LX1lJSlvLV8OpTPHJkSfGE0F3S6Az64tT31gzesUEK2Stgi0NfhS33JcAC4N2IpxU7AWK+wcCOiNYEPAX8ErvrN5OEwAOBpxWvgKz4307lZilgdgb/ax7+wptgr4h+s9PfCiwEros+twDLgYdILinzsI1zryP3rDPeusBkh+HfdF084jHmYxn8AKd7ZCoccCUW5++kBC+O6CNIjpfZjty3PIMtIzkmP+X0T4/6+lN5VO3HjsG5JE8qK/6n+YwB/pIhc6dPJt0xlbYVluUOfUHU5y75OVhl5ixst30Wq9jEDjgaWyWbSSo+aae1APeQhEd3whcnqKw0uW1mhsx2PImW+6UrtuR9iBOJvtiPFV/Asr5vRjKPOXqmRTJzgbOx5dpIcinqSbJHpHE+1cV/3AZk2ABwXlomrWBVQHA9Sap5MpYfuFjm6EinuYdIwkjAzwNj7AH6kB//D6eNSLXVGbLz0vxp4VMIe3ARiecHAE84tFasQnQLlSH0IpUXETctTmOGw5cV/1eljUi1qRmyDVTeGbwFkV9kKFiYUnAmdut6GdvIGoF/Ys76KpXlsqnYavDhVSwEDyf+49YrYxyAC8lxwLEkZ7wPa7GaQNYk3NYXuD9DH8AFDn+18e+2rMLJYnIcIOxmCLY7b22rgxZsNYzHX8qqAz4J3E5lHhBjH4mTn0zJHk78x+1rGToO4LxpCpXF6ySNk9QgK1b28TFF2Csrom6VlZ/7ywqgef8QNUmWvq6UtM/pXyNpTEBmmqQ5OXolS6O3y/6/wIcpkuZLyn0xMirDk4eL6z3jdeXw4t9tD2boeTTmy7uQbJB0g4r/KqsIkPSw7NecafRW+McPO+QvxYfwUAYteUNd0JvHYTHvVnRbya/WpOnPk1GdwTLFdEkuxn0F5xq3zoTrA4tivjIKhdXWnouUzAWezjC+FUuAWqOJXE5l0TLUZnl0NWCXnbLzvcyj6yC2QVflgHiHHxb9vQJ/zLaQlMoHkUo+CrSrsdxgN7CCwKvtgu1i7N3AHizBqiiQ/huru9DNinvxxwAAAABJRU5ErkJggg==",
    "BATTERY": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEUElEQVR4nO2aT4hVdRTHP5OWT4g3T2jRrDQrUlr01GRm40ItsF0uXLTMVMgWQaLUwjRDqKkRJHUhmCi0FjdiiwqMoIhsVvNGzD8RtHCjSTDO9N6cFr+Z8b035/fvvnv5ie9+4DLM7/7+nPvl3HN/5/zegIjQzzyR2oDUlAKkNiA1pQCpDUhNKUBqA1JTCpDagNSUAqQ2IDV9L8DSiL5DwBvAGmAQI96g0q8J/AacAKY9c9aA94HngW+Bbxx968Ae4Jm5/6eAB8AMcBO4MrduHCLiu6oicl5EmhLHRc+8FRH5vWvMQUvfuohMBaw5LiLrAp5p4fJ1eEVEbkQ9dicrHXOPKv3vWPqeiljzgYi861i343LFgEHgArA62q38jAAfFDAvwDLM6/daUG+HOucjVNewvQIVEWlYxhy1jAl9Bdr5W0RWWOZbuAZErwgNAX8BS5R714E/gRZwX7nvC4KjwH6lvQGsxwQ2jTqdQXA5UAGqwDrgSWXMe8Apy3wGizI7Lap+6FPUc42IHkybIjLcw7zrReQfZd5LvrG2GLBGabsOfOZU000F+Brdq8aAX3qY+ypwUml/yTfQJkBNabsdbo/KEWCt0t4ADvU4N8Atpa3mG2QT4CmlbSbGmi6G0aP+LLAb+3sfw39Km/YcHdgE0AKKtkAIy4Az6K7/BfBTxnm70ezTnqODGAGaUeY85AjwstLeAA5nnFMjVw/QyHKCMgzsU9rzdH0XA74ORWaDFeAs9qifl+v72Iwj6StSgE+wR/2PC1y3m++BX7F8EYoSwOb6LWAnxbt+N3VM2r2ImHpAKC7Xv0t4EiTABHAcuJeDXZo3FiLAQdtimH38jsj53gQ2kv0rNI/q7UW8Artznq8ObMp5zgX6viZYhABf5TzfBKbeVwhFxIBPMUXKbZhtcAgvYHL6blrAO3N/e2VWayxCADDVXVeFt50KJp3VOAb8nItFZv+xiEchBtg2TJPkt2Eax3xOF1GUB4Ti2jC9TT4bpi3Aj1g+oykFcKXJY+Tn+j+4bsa8At7MKhJbmjxJPhUiCMhgbQJouXWe3uJKk3eRzfUzFXFiBPBWVwJxuf6XZE+TM5XxbAJoA73VlUBcFaJeXD9XD7irtK2KscZCkWnyc0qb9hwd2AS4prS9CHwUY1EXrjS51w3PBmCv0q49RwdZjsZuYGrw7Udj08Bl3Lu/z4EDSrvrSOx14C3gaeXe/NHYIGYbrQXpzEdjWQ9Hbef7GxxHYiOWMTtEZDaDDfMEHY66blYl/rcBsef7o471r0Su3U5LRLY65g76fcB9YDsmsyuCooqj05h48F1Q7wCVqiJyTsJ+IhP6E5cpEXnVs26WV2B8bq3gk2VbENR4FpPjr+VhibmG2SKHBME65nwf4DQmQ/PhCoL/Yr7zM8AfmITHllZbiRHgseRRqAckpRQgtQGpKQVIbUBqSgFSG5CaUoDUBqSmFCC1AanpewH+B37ItCuF6dadAAAAAElFTkSuQmCC",
    "GAS_CAN": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAADg0lEQVR4nO2bTUgWQRjHf69KhSAUlkREKYGQERhBRWEHT0LflBB0E6pDhyDKWx3q0KFDUHSwg4fAg0VQFih06NKH1qEOKUVfh+gDXyswTELz6TCubOt+zK6j8+777g8G3vfZnWee+e/O7MzsbE5EKGXKbAdgm7QKUA3sARrm6iiNAjQDH4EeYBC4BlQkdZZLYR/wCtjgsd0HDgNjcZ2lUYAxoNLH/gzYDeTjOEtjE3gQYN8CPAHWxXGWxjugBugDNgUcH0bdCc91nMW5A9YCnaiOZxIQQ+kLcA/YpRnHMLAT6A04XgM8RIkQjYjopIMiMirzT4eI5DRjWiQiN0J8TYhIW5QfnYJqZWEq73BcIyYn5UTkYoivKRE5F+ZDp5BOk7XT4KeIlGnE5U4nRGQyxGeHiFT45dVxPmSwcro0aMTlTQdE5HeIzx4RqfTm03kKTALlHttl4KlWJxPNTR/bIeB2Al87gEchxwdQQ+iZsYLOENJbeYB+4Fas0OLhV6YOjyOOb0U9PbahLmwqB0JzZTPQ5PwpRQEAVjg/SlWAGRJPIz1UozqgxSHnCDA0nQoGEwI0A3eAKs3zLwHtBso1gokmcAX9ygOcYfZ83homBKhboDzzggkBgubnQfxCjSMKAhMCHAXuAn8izhPUVHofMGKgXCOY6ATzwH4DfkyRx/Wcj6IYxwFX45xsahxQSFwAPgAtqHFJa9jJxSgAQNd0AtX3BFKoTaAb/TXFPHA2aUGFKkAclgPngSNJMheDAA4tSTIVkwBhE7FAikmARBTqUyBqzfEUallrzhSqAFFrjq0YEqDkm0AmgO0AbJMJYDsA22QC2A7ANpkAtgOwTSaA7QBskwlgOwDbZALYDsA2aRXAb6nbry65gPxTYZnSgN+7xXof2/qA/DO7xNIqwGsf20bUUplDFf6vyQR44/zx7hNcCpxEfYri3D5+r5a+A+Pa4Yaz2sfWD3ya/j0CXAdeuo7XAe/wv4CDwHtgO+qdgZcB3Mtprl2TFSLywvCOT1OMi0ij/L/Lsyuhr71uP24Fm4BGrWu28CwBjnls7cDXmH66Ud8azZDWPgDgM+obA10ReoG2WVZJbxNw0ipRzeFvQN4fInJaRMr98ut0ggBrgJUk38OrgwCjwFtgwmX36wT9qEVthK4HlgHfUC9X+gj5miyN3wwZJc19gBEyAWwHYJuSF+Af8jYFm4b1i/wAAAAASUVORK5CYII=",
    "TIRE_WHEEL": "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",
    "ARROW_UP": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABH0lEQVR4nO2ZwQrCMBAFU/HgJ3uzR/96PciCILRpEzO78Q30UDzkzSAoZDGzArKWUm6llDs14EodXN7yj493JoKZEc9q3zyJLVHksQiR5JEI0eSHR4goPzRCVPlhESLLD4kQXf7nETLI/zRCFnmne4RM8k7XCNnknW4RMso7XSJklXeaI2SWd5oiZJd3TkeYQd45FWEWeedwhJnknUMRZpN3qiPMKO9URZhV3tmNsJjt3gugFwcdWLY+vIxaERUFoAfQKAA9gEYB6AE0Ndfjm7+jFbT+j2g9f5O//wYoAD2ARgHoATQKQA+gUQB6AI0C0ANoFIAeQKMA9AAaBaAH0CgAPYBGAegBNApAD6BRAHoAjQLQA2gUgB5AowD0AJoX0uO14RYTEgYAAAAASUVORK5CYII=",
    "ARROW_RIGHT": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABWklEQVR4nO3ZSW7CQBAF0EfEIkdmB1tO7SwIUQYmm+4UVe0vWd4guf5TIXnYTNNk5LxFDxCdFSB6gOisANEDRGcFiB4gOq8AMN05Dj0v/goA97LXESEDAB0RsgDQCSETAB0QsgHQGCEjAA0RsgLQCCEzAA0QsgPwJEIFAJ5AqALAQoRKACxAqAbATISKAMxAqArAgwhbp2fuqtl/ng/XflB5A865uQkjAHADYRQAriCMBMAFhNEA+IUwIgDfELaxc4Rmz7gbcM77yABH7EYFOGLHmH+Br/KMB/CjPGMB/CnPOAAXyzMGwNXynG6ENv83y8X0fB9xszy1N+BueeoCPFSemgAPl6cewKzy1AKYXZ46AIvKUwNgcXnyAzxVntwAT5cnL0CT8uQEaFaefABNy5MLoHl58gB0KU8OgG7leY0PI6HvIzJsQNesANEDRGcFiB4gOitA9ADR+QAzOTuF9oo9kQAAAABJRU5ErkJggg==",
    "ARROW_DOWN": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABPklEQVR4nO3asQ6CUBBEUTR+tKV2+sd2Y2Nloi7v7e6FOJMQGgIzJ3RwkLQUZ/YBh5QWH3KsvPkeYgC6AB0D0AXoGIAuQMcAdAE6BqAL0DEAXYCOAegCdAxAF6BjALoAHQPQBegYgC5AxwB0AToGoAvQMQBdgI4B6AJ0ToFryn8gKH7+1/8L/v4NMABdgI4B6AJ0DEAXoBMBuJe3qMv15xWSIsdN+8tFgW1RgL0hhMZrJcBeEMLjNQCwdYRV4zUIsFWE1eM1AbA1hKHxmgTYCsLweCUA0AhT45UEQCFMj1ciQDdCynglA3QhpI1XAUA1Qup4FQFUIaSPrwTIRigZXw2QhVA2vgNgFqF0fBfAKEL5+E6AtQgt47sBoght4wmAXwit4ymATwjt40mAdwRkvKTQ5/GqnF/nx7IsF6rEE0nRiJLHvCixAAAAAElFTkSuQmCC",
    "ARROW_LEFT": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABdUlEQVR4nO3by27CQAyF4T+o79xlT3c8cnfpgiJ6AXKb6ZHtsYRYIEU+XyJIZsw0zzOV6+RuwF0DwN2AuwaAuwF3DQB3A+7qDXAG5oWXtXoCnIHXjsdvUr0AQoSHPgBhwkN7gFDhoS1AuPDQDiBkeGgDEDY8HAcIHR6OAYQPD/sBUoSHfQBpwsN2gFThYRtAuvCwHiBleFgHkDY8wMvC5/8R3rom8OwKSH3mr/UIoER4uA9QJjz8BSgVHn4ClAsPN4CS4eECUDY8XAA+3E046wQIeDf3Yavrd4AoivD9V0AURPh9HyCKIdy7ExSFEB49C4giCM+eBkUBhKX1AH29v3XsYep47MVasyIkEl8Ja9cERVKELavCIiHC1n0BkQxhz86QSISwd29QJEE4sjssEiAcnQ8QwRFaTIiIwAitZoREUISWU2IiIELrOUERDKHHpKgIhNBrVlgEQeg5LS4CIEzjf4PFawC4G3DXAHA34K4B4G7AXZ913D7zbmNtwQAAAABJRU5ErkJggg==",
}


VJOY_DEVICE_ID = 1
BAUD_RATE = 115200
PORT_HINTS = ["CP210", "CH340", "Silicon Labs", "USB-SERIAL", "USB2.0-Serial"]
FLAG_POLL_INTERVAL = 0.5
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "button_mappings.json")

# Your current mapping, used only to create button_mappings.json the
# very first time this runs. After that, the JSON file is the source
# of truth and this constant is never read again.
DEFAULT_MAPPING = {
    "UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4,
    "BTN_RESET": 5, "BTN_TORTOISE": 6, "BTN_WHEEL_REPAIR": 7, "BTN_BATTERY": 8,
    "autotogglefuel": 9, "8gallons": 10,
    "TIRE_LF": 11, "TIRE_RF": 12, "TIRE_RR": 13, "TIRE_LR": 14,
    "BTN_CENTER": 15,
    "ADJ1_UP": 16, "ADJ1_DOWN": 17,
    "ADJ2_UP": 18, "ADJ2_DOWN": 19,
    "ADJ3_UP": 20, "ADJ3_DOWN": 21,
}

FLAG_COLORS = {
    "NONE": "#333333", "GREEN": "#2ecc71", "YELLOW": "#f1c40f",
    "RED": "#e74c3c", "WHITE": "#ecf0f1", "BLACK": "#111111",
    "CHECKERED": "#ffffff", "BLUE": "#3498db", "DEBRIS": "#f1c40f",
}

# ---------------------------------------------------------------
# Mirrors the exact button positions from button_box_8btn.ino's
# buildLayout(). This is a SCHEMATIC view (shapes + text labels),
# not a pixel-perfect copy of the real icon graphics - it's meant
# to show you what's where and what's currently pressed, not
# replace looking at the actual screen.
# ---------------------------------------------------------------
SCREEN_W, SCREEN_H = 320, 240

PAGES_LAYOUT = [
    [],  # Page 0: blank flag page - no buttons
    [    # Page 1: D-pad + center circle
        {"code": "UP",    "icon": "ARROW_UP",    "shape": "rect",   "x": 135, "y": 5,   "w": 90, "h": 76},
        {"code": "LEFT",  "icon": "ARROW_LEFT",  "shape": "rect",   "x": 45,  "y": 81,  "w": 90, "h": 76},
        {"code": "RIGHT", "icon": "ARROW_RIGHT", "shape": "rect",   "x": 225, "y": 81,  "w": 90, "h": 76},
        {"code": "DOWN",  "icon": "ARROW_DOWN",  "shape": "rect",   "x": 135, "y": 157, "w": 90, "h": 76},
        {"code": "BTN_CENTER", "label": "OK",    "shape": "circle", "x": 149, "y": 88,  "w": 62, "h": 62, "fill": "#e74c3c"},
    ],
    [    # Page 2: Reset / Tortoise / Wheel Repair / Battery
        {"code": "BTN_RESET",        "icon": "RESET",        "shape": "rect", "x": 45,  "y": 5,   "w": 131, "h": 111},
        {"code": "BTN_TORTOISE",     "icon": "TORTOISE",     "shape": "rect", "x": 184, "y": 5,   "w": 131, "h": 111},
        {"code": "BTN_WHEEL_REPAIR", "icon": "WHEEL_REPAIR", "shape": "rect", "x": 45,  "y": 124, "w": 131, "h": 111},
        {"code": "BTN_BATTERY",      "icon": "BATTERY",      "shape": "rect", "x": 184, "y": 124, "w": 131, "h": 111},
    ],
    [    # Page 3: 2x fuel can + 4x tire (tags match the sketch's current LF/RF swap)
        {"code": "autotogglefuel", "icon": "GAS_CAN",    "tag": "Auto", "shape": "rect", "x": 45,  "y": 5,   "w": 84, "h": 111},
        {"code": "TIRE_RF",        "icon": "TIRE_WHEEL", "tag": "LF",   "shape": "rect", "x": 137, "y": 5,   "w": 84, "h": 111},
        {"code": "TIRE_LF",        "icon": "TIRE_WHEEL", "tag": "RF",   "shape": "rect", "x": 229, "y": 5,   "w": 84, "h": 111},
        {"code": "8gallons",       "icon": "GAS_CAN",    "tag": "8g",   "shape": "rect", "x": 45,  "y": 124, "w": 84, "h": 111},
        {"code": "TIRE_RR",        "icon": "TIRE_WHEEL", "tag": "LR",   "shape": "rect", "x": 137, "y": 124, "w": 84, "h": 111},
        {"code": "TIRE_LR",        "icon": "TIRE_WHEEL", "tag": "RR",   "shape": "rect", "x": 229, "y": 124, "w": 84, "h": 111},
    ],
    [    # Page 4: 3 up/down adjuster pairs
        {"code": "ADJ1_UP",   "icon": "ARROW_UP",   "tag": "ADJ1", "shape": "rect", "x": 45,  "y": 5,   "w": 84, "h": 111},
        {"code": "ADJ2_UP",   "icon": "ARROW_UP",   "tag": "ADJ2", "shape": "rect", "x": 137, "y": 5,   "w": 84, "h": 111},
        {"code": "ADJ3_UP",   "icon": "ARROW_UP",   "tag": "ADJ3", "shape": "rect", "x": 229, "y": 5,   "w": 84, "h": 111},
        {"code": "ADJ1_DOWN", "icon": "ARROW_DOWN", "tag": "ADJ1", "shape": "rect", "x": 45,  "y": 124, "w": 84, "h": 111},
        {"code": "ADJ2_DOWN", "icon": "ARROW_DOWN", "tag": "ADJ2", "shape": "rect", "x": 137, "y": 124, "w": 84, "h": 111},
        {"code": "ADJ3_DOWN", "icon": "ARROW_DOWN", "tag": "ADJ3", "shape": "rect", "x": 229, "y": 124, "w": 84, "h": 111},
    ],
]
PAGE_NAMES = ["Flag (blank)", "D-Pad", "Reset/Tortoise/Repair/Battery", "Fuel & Tires", "Adjusters"]

# Slider strip, mirrored on the preview too (matches the real left-edge slider)
SLIDER_X, SLIDER_Y, SLIDER_W, SLIDER_H, HANDLE_H = 5, 10, 27, 220, 50
NUM_PAGES = len(PAGES_LAYOUT)


def handle_y_for_page(page):
    if NUM_PAGES <= 1:
        return SLIDER_Y
    travel = SLIDER_H - HANDLE_H
    return SLIDER_Y + (travel * page) // (NUM_PAGES - 1)


def text_color_for(hex_bg):
    hex_bg = hex_bg.lstrip("#")
    r, g, b = int(hex_bg[0:2], 16), int(hex_bg[2:4], 16), int(hex_bg[4:6], 16)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 150 else "#ffffff"


def format_lap_time(total_seconds):
    if total_seconds is None or total_seconds <= 0:
        return "--:--.---"
    minutes = int(total_seconds // 60)
    secs = total_seconds - minutes * 60
    return f"{minutes}:{secs:06.3f}"


def load_mapping():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    save_mapping(DEFAULT_MAPPING)
    return dict(DEFAULT_MAPPING)


def save_mapping(mapping):
    with open(CONFIG_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def flag_bit(name):
    return getattr(irsdk.Flags, name, 0)


def current_flag_name(ir):
    if not ir.is_connected:
        return "NONE"
    flags = ir["SessionFlags"]
    if flags is None:
        return "NONE"
    if flags & flag_bit("checkered"):
        return "CHECKERED"
    if flags & flag_bit("black") or flags & flag_bit("disqualify"):
        return "BLACK"
    if flags & flag_bit("red"):
        return "RED"
    if flags & (flag_bit("caution") | flag_bit("cautionWaving") | flag_bit("yellow") | flag_bit("yellowWaving")):
        return "YELLOW"
    if flags & flag_bit("debris"):
        return "DEBRIS"
    if flags & flag_bit("blue"):
        return "BLUE"
    if flags & flag_bit("white"):
        return "WHITE"
    if flags & flag_bit("green") or flags & flag_bit("greenHeld"):
        return "GREEN"
    return "NONE"


class Backend:
    """Runs entirely on a background thread. Never touches the GUI
    directly - only pushes messages into a thread-safe queue that the
    main thread polls. Reads the live button mapping through a lock
    so edits made in the GUI take effect immediately, no restart."""

    def __init__(self, mapping_lock, mapping_ref, event_queue):
        self.mapping_lock = mapping_lock
        self.mapping_ref = mapping_ref
        self.q = event_queue
        self.stop_flag = threading.Event()
        self.connections = {}
        self.connections_lock = threading.Lock()
        self.j = None
        self.ir = None
        self.last_flag = None
        self.last_flag_check = 0.0
        self.last_fuel_pct = None
        self.last_best_lap = None

    def log(self, msg):
        self.q.put(("log", msg))

    def get_button(self, code):
        with self.mapping_lock:
            return self.mapping_ref.get(code)

    def connect_vjoy(self):
        while not self.stop_flag.is_set():
            try:
                self.j = pyvjoy.VJoyDevice(VJOY_DEVICE_ID)
                self.log("vJoy connected.")
                self.q.put(("vjoy_status", True))
                return
            except Exception as e:
                self.log(f"vJoy not ready ({e}) - retrying in 5s...")
                self.q.put(("vjoy_status", False))
                time.sleep(5)

    def find_ports(self):
        found = []
        for port in serial.tools.list_ports.comports():
            desc = (port.description or "") + " " + (port.manufacturer or "")
            if any(hint.lower() in desc.lower() for hint in PORT_HINTS):
                found.append(port.device)
        return found

    def run(self):
        self.log("Backend starting - waiting for vJoy...")
        self.connect_vjoy()

        if IRSDK_AVAILABLE:
            self.ir = irsdk.IRSDK()
            self.log("iRacing flag broadcast enabled.")
        else:
            self.log("pyirsdk not installed - flag display disabled.")

        while not self.stop_flag.is_set():
            for port in self.find_ports():
                with self.connections_lock:
                    already_have = port in self.connections
                if not already_have:
                    try:
                        ser = serial.Serial(port, BAUD_RATE, timeout=0.05)
                        time.sleep(2)
                        with self.connections_lock:
                            self.connections[port] = ser
                        self.log(f"Connected to board on {port}")
                        self.q.put(("boards", list(self.connections.keys())))
                    except serial.SerialException:
                        pass

            dead_ports = []
            with self.connections_lock:
                items = list(self.connections.items())
            for port, ser in items:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.handle_line(port, line)
                except (serial.SerialException, OSError):
                    self.log(f"Lost connection to {port}")
                    dead_ports.append(port)

            if dead_ports:
                with self.connections_lock:
                    for port in dead_ports:
                        self.connections[port].close()
                        del self.connections[port]
                self.q.put(("boards", list(self.connections.keys())))

            now = time.time()
            if self.ir is not None and (now - self.last_flag_check) >= FLAG_POLL_INTERVAL:
                self.last_flag_check = now
                if not self.ir.is_connected:
                    self.ir.startup()

                if self.ir.is_connected:
                    flag = current_flag_name(self.ir)
                    if flag != self.last_flag:
                        self.log(f"Flag: {self.last_flag} -> {flag}")
                        self.last_flag = flag
                        self.q.put(("flag", flag))
                        self._send_to_all(f"FLAG:{flag}\n")

                    pct_raw = self.ir["FuelLevelPct"]
                    if pct_raw is not None:
                        pct = round(pct_raw * 100)
                        if pct != self.last_fuel_pct:
                            self.last_fuel_pct = pct
                            self.q.put(("fuel", pct))

                    best_lap = self.ir["LapBestLapTime"]
                    if best_lap is not None and best_lap != self.last_best_lap:
                        self.last_best_lap = best_lap
                        self.log(f"Best lap: {best_lap:.3f}s")
                        self.q.put(("laptime", best_lap))
                        self._send_to_all(f"LAPTIME:{best_lap}\n")
                elif self.last_fuel_pct is not None:
                    self.last_fuel_pct = None
                    self.q.put(("fuel", None))
                    if self.last_best_lap is not None:
                        self.last_best_lap = None
                        self.q.put(("laptime", None))
                        self._send_to_all("LAPTIME:-1\n")

            with self.connections_lock:
                have_connections = bool(self.connections)
            time.sleep(0.01 if have_connections else 2)

        with self.connections_lock:
            for ser in self.connections.values():
                ser.close()

    def _send_to_all(self, message):
        with self.connections_lock:
            items = list(self.connections.items())
        for port, ser in items:
            try:
                ser.write(message.encode("utf-8"))
            except (serial.SerialException, OSError):
                pass

    def trigger_flag(self, name):
        """Manually broadcast a flag, e.g. from the GUI's flag buttons.
        Note: if iRacing is connected and actively sending a different
        flag, the next poll (twice a second) will overwrite this."""
        self.last_flag = name
        self.log(f"Manual flag trigger: {name}")
        self.q.put(("flag", name))
        self._send_to_all(f"FLAG:{name}\n")

    def handle_line(self, port, line):
        if line.startswith("PRESS:"):
            code = line[len("PRESS:"):]
            btn = self.get_button(code)
            if btn is None:
                self.log(f"({port}) No mapping for '{code}'")
            else:
                try:
                    self.j.set_button(btn, 1)
                    self.q.put(("press", port, code, btn))
                except Exception as e:
                    self.log(f"vJoy error on button {btn} ('{code}'): {e} - "
                              f"is vJoy Device 1 configured with at least {btn} buttons?")
        elif line.startswith("RELEASE:"):
            code = line[len("RELEASE:"):]
            btn = self.get_button(code)
            if btn is None:
                self.log(f"({port}) No mapping for '{code}'")
            else:
                try:
                    self.j.set_button(btn, 0)
                    self.q.put(("release", port, code, btn))
                except Exception as e:
                    self.log(f"vJoy error on button {btn} ('{code}'): {e} - "
                              f"is vJoy Device 1 configured with at least {btn} buttons?")
        elif line.startswith("PAGE:"):
            try:
                page_num = int(line[len("PAGE:"):])
                self.q.put(("page", port, page_num))
            except ValueError:
                pass
        elif not line.startswith("FLAG:") and "ready" not in line.lower():
            self.log(f"({port}) {line}")

    def stop(self):
        self.stop_flag.set()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Button Box Control Panel")
        self.geometry("1400x650")

        self.mapping_lock = threading.Lock()
        self.mapping = load_mapping()
        self.event_queue = queue.Queue()

        # Preview state
        self.preview_flag = "NONE"       # shared - same flag broadcasts to every board
        self.best_lap_str = "--:--.---"  # shared - same telemetry value for every board
        self.board_previews = {}         # port -> {"page": int, "pressed_code": str|None}
        self.preview_widgets = {}        # port -> {"frame", "canvas", "page_label"}
        self.PREVIEW_SCALE = 1.0  # true size - matches the real 320x240 screen exactly
        self._icon_cache = {}   # (name, size) -> ImageTk.PhotoImage
        self._base_icons = {name: Image.open(io.BytesIO(base64.b64decode(b64)))
                             for name, b64 in ICON_B64.items()}

        self.fuel_pct = None

        self._apply_dark_theme()

        self.backend = Backend(self.mapping_lock, self.mapping, self.event_queue)
        self.backend_thread = threading.Thread(target=self.backend.run, daemon=True)

        self._build_ui()
        self.backend_thread.start()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.tray_icon = None
        if PYSTRAY_AVAILABLE:
            try:
                self._setup_tray()
            except Exception as e:
                self.after(200, lambda: self._append_log(f"System tray unavailable ({e})."))
        else:
            self.after(200, lambda: self._append_log(
                "pystray not installed - system tray disabled. Run: pip install pystray"
            ))

    def _apply_dark_theme(self):
        BG = "#1e1e1e"
        BG_ALT = "#2b2b2b"
        FG = "#e6e6e6"
        ACCENT = "#3498db"
        BORDER = "#3d3d3d"
        SELECT_BG = "#3a3a3a"

        self.dark_bg_rgb = (0x2b, 0x2b, 0x2b)  # matches BG_ALT, for flattening icons onto

        self.configure(bg=BG)

        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG, foreground=FG, fieldbackground=BG_ALT,
                         bordercolor=BORDER, lightcolor=BG, darkcolor=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=BG_ALT, foreground=FG, bordercolor=BORDER,
                         focusthickness=0, padding=4)
        style.map("TButton", background=[("active", SELECT_BG)])
        style.configure("TNotebook", background=BG, bordercolor=BORDER)
        style.configure("TNotebook.Tab", background=BG_ALT, foreground=FG, padding=(10, 4))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TEntry", fieldbackground=BG_ALT, foreground=FG, bordercolor=BORDER,
                         insertcolor=FG)
        style.configure("Treeview", background=BG_ALT, foreground=FG, fieldbackground=BG_ALT,
                         bordercolor=BORDER)
        style.configure("Treeview.Heading", background=BG, foreground=FG, bordercolor=BORDER)
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=0)
        container.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(container)
        notebook.grid(row=0, column=0, sticky="nsew")

        # ---------------- Persistent Display Preview panels ----------------
        # Lives outside the notebook entirely, top-right, so it stays put
        # no matter which tab (Status / Button Mappings) is selected.
        # One independent sub-panel per connected board.
        preview_outer = ttk.Frame(container)
        preview_outer.grid(row=0, column=1, sticky="n", padx=10, pady=10)

        ttk.Label(preview_outer, text="Display Preview", font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(
            preview_outer,
            text="Schematic - shapes/icons, not pixel-perfect. One panel per connected board.",
            wraplength=300, justify="left", font=("", 8),
        ).pack(anchor="w", pady=(0, 8))

        self.preview_panels_row = ttk.Frame(preview_outer)
        self.preview_panels_row.pack(anchor="n")

        self._rebuild_preview_panels([])  # populated once boards connect

        # ---------------- Status tab ----------------
        status_tab = ttk.Frame(notebook)
        notebook.add(status_tab, text="Status")

        top_frame = ttk.Frame(status_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="vJoy:").grid(row=0, column=0, sticky="w", pady=2)
        self.vjoy_status_label = ttk.Label(top_frame, text="connecting...", foreground="#e67e22")
        self.vjoy_status_label.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(top_frame, text="Boards:").grid(row=1, column=0, sticky="w", pady=2)
        self.boards_label = ttk.Label(top_frame, text="none yet")
        self.boards_label.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(top_frame, text="Flag:").grid(row=2, column=0, sticky="w", pady=2)
        self.flag_swatch = tk.Canvas(top_frame, width=24, height=24, highlightthickness=1, highlightbackground="#888")
        self.flag_swatch.grid(row=2, column=1, sticky="w", padx=5)
        self.flag_rect = self.flag_swatch.create_rectangle(2, 2, 22, 22, fill=FLAG_COLORS["NONE"], outline="")
        self.flag_text = ttk.Label(top_frame, text="NONE")
        self.flag_text.grid(row=2, column=2, sticky="w", padx=5)

        ttk.Label(top_frame, text="Last button:").grid(row=3, column=0, sticky="w", pady=2)
        self.last_button_label = ttk.Label(top_frame, text="-")
        self.last_button_label.grid(row=3, column=1, columnspan=2, sticky="w", padx=5)

        # --- Fuel gauge ---
        ttk.Label(top_frame, text="Fuel:").grid(row=4, column=0, sticky="w", pady=2)
        fuel_frame = ttk.Frame(top_frame)
        fuel_frame.grid(row=4, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        self.fuel_icon_label = tk.Label(fuel_frame, bg=self.cget("bg"))
        self.fuel_icon_label.pack(side="left", padx=(0, 6))
        self._set_fuel_icon(None)

        self.fuel_canvas = tk.Canvas(fuel_frame, width=200, height=18, highlightthickness=1,
                                      highlightbackground="#888", bg="#222222")
        self.fuel_canvas.pack(side="left")
        self.fuel_bar = self.fuel_canvas.create_rectangle(0, 0, 0, 18, fill="#2ecc71", outline="")
        self.fuel_pct_label = ttk.Label(fuel_frame, text="no data (iRacing not running)")
        self.fuel_pct_label.pack(side="left", padx=8)

        # --- Manual flag triggers ---
        ttk.Label(status_tab, text="Manual flag trigger (for testing without iRacing running):").pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        flag_btn_frame = ttk.Frame(status_tab)
        flag_btn_frame.pack(anchor="w", padx=10, pady=(0, 10))
        for name in ["GREEN", "YELLOW", "RED", "BLUE", "DEBRIS", "WHITE", "BLACK", "CHECKERED", "NONE"]:
            ttk.Button(
                flag_btn_frame, text=name, width=10,
                command=lambda n=name: self.backend.trigger_flag(n),
            ).pack(side="left", padx=3)

        # --- Manual raw command entry ---
        ttk.Label(
            status_tab,
            text="Manual command (sent as-is to all connected boards, e.g. FLAG:BLUE, PRESS:UP, RELEASE:UP):",
        ).pack(anchor="w", padx=10, pady=(5, 2))
        cmd_frame = ttk.Frame(status_tab)
        cmd_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.command_entry = ttk.Entry(cmd_frame)
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.command_entry.bind("<Return>", lambda e: self._send_manual_command())
        ttk.Button(cmd_frame, text="Send", command=self._send_manual_command).pack(side="left")

        ttk.Label(status_tab, text="Live log:").pack(anchor="w", padx=10)
        self.log_text = tk.Text(status_tab, height=20, state="disabled", bg="#111111", fg="#dddddd")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # ---------------- Mappings tab ----------------
        map_tab = ttk.Frame(notebook)
        notebook.add(map_tab, text="Button Mappings")

        ttk.Label(map_tab, text="Double-click a button number to edit it. Don't forget to Save.").pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        self.tree = ttk.Treeview(map_tab, columns=("code", "button"), show="headings", height=16)
        self.tree.heading("code", text="Code")
        self.tree.heading("button", text="vJoy Button #")
        self.tree.column("code", width=280)
        self.tree.column("button", width=120, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", self._edit_mapping_cell)

        self._refresh_tree()

        add_frame = ttk.Frame(map_tab)
        add_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(add_frame, text="New code:").pack(side="left")
        self.new_code_entry = ttk.Entry(add_frame, width=25)
        self.new_code_entry.pack(side="left", padx=5)
        ttk.Label(add_frame, text="Button #:").pack(side="left")
        self.new_button_entry = ttk.Entry(add_frame, width=6)
        self.new_button_entry.pack(side="left", padx=5)
        ttk.Button(add_frame, text="Add", command=self._add_mapping).pack(side="left", padx=5)
        ttk.Button(add_frame, text="Delete Selected", command=self._delete_mapping).pack(side="left", padx=5)
        ttk.Button(add_frame, text="Save", command=self._save_mappings).pack(side="right", padx=5)

    def _draw_outlined_text(self, canvas, text, x, y, font_size):
        # Black outline so text stays readable over any background,
        # including the checkered/striped patterns - same trick the
        # firmware uses for the same reason.
        off = 2
        for dx, dy in [(-off, 0), (off, 0), (0, -off), (0, off)]:
            canvas.create_text(x + dx, y + dy, text=text, fill="#000000",
                                font=("", font_size, "bold"), justify="center")
        canvas.create_text(x, y, text=text, fill="#ffffff",
                            font=("", font_size, "bold"), justify="center")

    def _add_preview_panel(self, port):
        self.board_previews[port] = {"page": 0, "pressed_code": None}

        frame = ttk.Frame(self.preview_panels_row, relief="groove", borderwidth=2)
        frame.pack(side="left", padx=(0, 8), pady=(0, 8))

        ttk.Label(frame, text=port, font=("", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        page_label = ttk.Label(frame, text="Page: -", font=("", 9))
        page_label.pack(anchor="w", padx=8, pady=(0, 5))

        canvas_w = int(SCREEN_W * self.PREVIEW_SCALE)
        canvas_h = int(SCREEN_H * self.PREVIEW_SCALE)
        canvas = tk.Canvas(frame, width=canvas_w, height=canvas_h,
                            bg="#000000", highlightthickness=1, highlightbackground="#555")
        canvas.pack(padx=8, pady=(0, 8))

        self.preview_widgets[port] = {"frame": frame, "canvas": canvas, "page_label": page_label}
        self._draw_preview_for_port(port)

    def _rebuild_preview_panels(self, ports):
        # Drop panels for boards that disconnected
        for port in list(self.preview_widgets.keys()):
            if port not in ports:
                self.preview_widgets[port]["frame"].destroy()
                del self.preview_widgets[port]
                self.board_previews.pop(port, None)
        # Add panels for newly-connected boards (existing ones are left
        # alone so their current page/press state isn't disturbed)
        for port in ports:
            if port not in self.preview_widgets:
                self._add_preview_panel(port)

    def _draw_all_previews(self):
        for port in list(self.preview_widgets.keys()):
            self._draw_preview_for_port(port)

    def _draw_preview_for_port(self, port):
        widgets = self.preview_widgets.get(port)
        if widgets is None:
            return
        state = self.board_previews.get(port, {"page": 0, "pressed_code": None})
        page = state["page"]
        pressed_code = state["pressed_code"]

        c = widgets["canvas"]
        c.delete("all")
        s = self.PREVIEW_SCALE

        bg_hex = FLAG_COLORS.get(self.preview_flag, "#333333")

        if self.preview_flag == "CHECKERED":
            sq = 20
            cols = int(SCREEN_W * s // sq) + 1
            rows = int(SCREEN_H * s // sq) + 1
            for r in range(rows):
                for col in range(cols):
                    color = "#ffffff" if (r + col) % 2 == 0 else "#000000"
                    c.create_rectangle(col * sq, r * sq, (col + 1) * sq, (r + 1) * sq, fill=color, outline="")
        elif self.preview_flag == "DEBRIS":
            stripe_w = int(40 * s)
            cols = int(SCREEN_W * s / stripe_w) + 1
            for col in range(cols):
                color = "#f1c40f" if col % 2 == 0 else "#e74c3c"
                c.create_rectangle(col * stripe_w, 0, (col + 1) * stripe_w, SCREEN_H * s, fill=color, outline="")
        else:
            c.create_rectangle(0, 0, SCREEN_W * s, SCREEN_H * s, fill=bg_hex, outline="")

        # Checkered/debris are busy multi-color patterns - plain
        # luminance-based text color would disappear into half of it,
        # so use a distinct accent color for both instead.
        if self.preview_flag in ("CHECKERED", "DEBRIS"):
            text_color = "#3498db"
            outline_color = "#3498db"
        else:
            text_color = text_color_for(bg_hex)
            outline_color = "#aaaaaa"

        # Slider strip, mirroring the real left-edge slider
        c.create_rectangle(
            SLIDER_X * s, 0, (SLIDER_X + SLIDER_W) * s + 6, SCREEN_H * s,
            fill="", outline="#888888", dash=(3, 2),
        )
        handle_y = handle_y_for_page(page)
        c.create_rectangle(
            (SLIDER_X + 2) * s, handle_y * s,
            (SLIDER_X + SLIDER_W - 2) * s, (handle_y + HANDLE_H) * s,
            fill="#3498db", outline="",
        )

        for btn in PAGES_LAYOUT[page]:
            x, y, w, h = btn["x"] * s, btn["y"] * s, btn["w"] * s, btn["h"] * s
            pressed = (btn["code"] == pressed_code)
            fill = "#e67e22" if pressed else btn.get("fill", "")
            outline = "" if fill else outline_color

            if btn["shape"] == "circle":
                c.create_oval(x, y, x + w, y + h, fill=fill or btn.get("fill", "#e74c3c"), outline=outline, width=2)
            else:
                c.create_rectangle(x, y, x + w, y + h, fill=fill, outline=outline, width=2)

            icon_name = btn.get("icon")
            tag = btn.get("tag")
            label = btn.get("label")
            label_color = "#ffffff" if fill else text_color

            if icon_name:
                icon_size = int(min(w, h) * 0.5)
                photo = self._get_icon_rgba(icon_name, icon_size)
                icon_cy = (y + h / 2) - (10 * s / 2.4 if tag else 0)  # nudge up a bit if a tag goes below
                c.create_image(x + w / 2, icon_cy, image=photo)
                if tag:
                    c.create_text(
                        x + w / 2, icon_cy + icon_size / 2 + 12, text=tag, fill=label_color,
                        font=("", 11, "bold"), justify="center",
                    )
            elif label:
                c.create_text(
                    x + w / 2, y + h / 2, text=label, fill=label_color,
                    font=("", 13, "bold"), justify="center",
                )

        if page == 0:
            self._draw_outlined_text(c, "BEST LAP", SCREEN_W * s / 2, 95 * s, 12)
            self._draw_outlined_text(c, self.best_lap_str, SCREEN_W * s / 2, 135 * s, 24)

        page_name = PAGE_NAMES[page] if page < len(PAGE_NAMES) else "?"
        widgets["page_label"].configure(text=f"Page {page + 1} of {NUM_PAGES}: {page_name}")

    def _get_icon_rgba(self, name, size):
        """Icon with real alpha transparency, for drawing on the preview Canvas."""
        key = ("rgba", name, size)
        if key not in self._icon_cache:
            img = self._base_icons[name].resize((size, size), Image.LANCZOS)
            self._icon_cache[key] = ImageTk.PhotoImage(img)
        return self._icon_cache[key]

    def _get_icon_flat(self, name, size, bg_rgb=(240, 240, 240)):
        """Icon flattened onto a solid background, for widgets (like Label)
        that don't reliably alpha-blend against their surroundings."""
        key = ("flat", name, size, bg_rgb)
        if key not in self._icon_cache:
            base = self._base_icons[name].resize((size, size), Image.LANCZOS)
            bg = Image.new("RGB", (size, size), bg_rgb)
            bg.paste(base, (0, 0), base)
            self._icon_cache[key] = ImageTk.PhotoImage(bg)
        return self._icon_cache[key]

    def _set_fuel_icon(self, pct):
        photo = self._get_icon_flat("GAS_CAN", 28, bg_rgb=self.dark_bg_rgb)
        self.fuel_icon_label.configure(image=photo, bg="#2b2b2b")
        self.fuel_icon_label.image = photo  # keep a reference so it isn't garbage-collected

    def _update_fuel_gauge(self, pct):
        self.fuel_pct = pct
        if pct is None:
            self.fuel_canvas.coords(self.fuel_bar, 0, 0, 0, 18)
            self.fuel_pct_label.configure(text="no data (iRacing not running)")
            return
        pct = max(0, min(100, pct))
        width = int(200 * pct / 100)
        color = "#2ecc71" if pct > 40 else ("#f1c40f" if pct > 15 else "#e74c3c")
        self.fuel_canvas.coords(self.fuel_bar, 0, 0, width, 18)
        self.fuel_canvas.itemconfig(self.fuel_bar, fill=color)
        self.fuel_pct_label.configure(text=f"{pct}%")

    def _send_manual_command(self):
        cmd = self.command_entry.get().strip()
        if not cmd:
            return
        self.backend._send_to_all(cmd + "\n")
        self._append_log(f"[manual] Sent: {cmd}")
        self.command_entry.delete(0, "end")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for code, btn in sorted(self.mapping.items(), key=lambda kv: kv[1]):
            self.tree.insert("", "end", iid=code, values=(code, btn))

    def _edit_mapping_cell(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or col != "#2":
            return
        bbox = self.tree.bbox(item, col)
        if not bbox:
            return
        x, y, w, h = bbox
        current_val = self.tree.set(item, "button")
        entry = ttk.Entry(self.tree)
        entry.insert(0, current_val)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus()

        def save_edit(evt=None):
            new_val = entry.get()
            try:
                new_val_int = int(new_val)
            except ValueError:
                entry.destroy()
                return
            self.tree.set(item, "button", new_val_int)
            with self.mapping_lock:
                self.mapping[item] = new_val_int
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def _add_mapping(self):
        code = self.new_code_entry.get().strip()
        btn_str = self.new_button_entry.get().strip()
        if not code or not btn_str:
            return
        try:
            btn = int(btn_str)
        except ValueError:
            messagebox.showerror("Invalid", "Button # must be a number")
            return
        with self.mapping_lock:
            self.mapping[code] = btn
        self._refresh_tree()
        self.new_code_entry.delete(0, "end")
        self.new_button_entry.delete(0, "end")

    def _delete_mapping(self):
        sel = self.tree.selection()
        if not sel:
            return
        for code in sel:
            with self.mapping_lock:
                self.mapping.pop(code, None)
        self._refresh_tree()

    def _save_mappings(self):
        with self.mapping_lock:
            save_mapping(self.mapping)
        messagebox.showinfo("Saved", f"Mappings saved to {os.path.basename(CONFIG_FILE)}")

    def _append_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                item = self.event_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._append_log(item[1])
                elif kind == "vjoy_status":
                    ok = item[1]
                    self.vjoy_status_label.configure(
                        text="connected" if ok else "waiting...",
                        foreground="#2ecc71" if ok else "#e67e22",
                    )
                elif kind == "boards":
                    ports = item[1]
                    self.boards_label.configure(text=", ".join(ports) if ports else "none yet")
                    self._rebuild_preview_panels(ports)
                elif kind == "flag":
                    flag = item[1]
                    self.flag_swatch.itemconfig(self.flag_rect, fill=FLAG_COLORS.get(flag, "#333333"))
                    self.flag_text.configure(text=flag)
                    self.preview_flag = flag
                    self._draw_all_previews()
                elif kind == "page":
                    port, page_num = item[1], item[2]
                    if port in self.board_previews:
                        self.board_previews[port]["page"] = page_num
                        self._draw_preview_for_port(port)
                elif kind == "fuel":
                    self._update_fuel_gauge(item[1])
                elif kind == "laptime":
                    self.best_lap_str = format_lap_time(item[1])
                    self._draw_all_previews()
                elif kind in ("press", "release"):
                    port, code, btn = item[1], item[2], item[3]
                    verb = "PRESS" if kind == "press" else "RELEASE"
                    self.last_button_label.configure(text=f"{verb} {code}  (vJoy #{btn})  [{port}]")
                    self._append_log(f"({port}) {verb} {code} -> vJoy button {btn}")
                    if port in self.board_previews:
                        state = self.board_previews[port]
                        state["pressed_code"] = code if kind == "press" else (
                            None if state["pressed_code"] == code else state["pressed_code"]
                        )
                        self._draw_preview_for_port(port)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _make_tray_image(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(52, 152, 219, 255))
        draw.text((16, 20), "BB", fill=(255, 255, 255, 255))
        return img

    def _setup_tray(self):
        image = self._make_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", lambda: self.after(0, self._show_window), default=True),
            pystray.MenuItem("Hide to Tray", lambda: self.after(0, self._hide_window)),
            pystray.MenuItem("Quit", lambda: self.after(0, self._quit_app)),
        )
        self.tray_icon = pystray.Icon("button_box", image, "Button Box Control Panel", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _hide_window(self):
        self.withdraw()

    def _quit_app(self):
        # vJoy button states persist in the driver even after this process
        # exits - release everything explicitly so nothing gets left
        # stuck "held down" if you quit mid-press.
        if self.backend.j is not None:
            with self.mapping_lock:
                button_nums = list(self.mapping.values())
            for btn in button_nums:
                try:
                    self.backend.j.set_button(btn, 0)
                except Exception:
                    pass

        self.backend.stop()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.destroy()

    def _on_close(self):
        # X always fully quits and disconnects everything - minimizing the
        # window (the normal OS minimize button) is what keeps it running
        # in the background during gameplay. "Hide to Tray" in the tray
        # menu is still available as a manual option if you want that too.
        self._quit_app()


if __name__ == "__main__":
    app = App()
    app.mainloop()
