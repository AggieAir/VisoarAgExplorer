import sys,os,platform,math

# this is needed to find micasense module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import micasense
import micasense.utils 
import micasense.metadata
import micasense.plotutils
import micasense.image 
import micasense.imageutils
import micasense.panel 
import micasense.capture 
import numpy as np

from slampy.image_provider import *

# /////////////////////////////////////////////////////////////////////////////////////////////////////
# see https://github.com/micasense/imageprocessing/blob/master/Alignment.ipynb
class ImageProviderRedEdge(ImageProvider):
	
	#  constructor (TODO: panel_calibration)
	def __init__(self):
		super().__init__()
		self.panel_calibration=None
		self.panel_irradiance=None
		# self.yaw_offset=math.pi # in the sequence I have the yaw is respect to the south
		self.yaw_offset=-(math.pi/2) # in the sequence I have the yaw is respect to the south
	
	# example: NIR_608.TIF  / RGB_608.TIF / Thermal_608.TIF returns 608
	def getGroupId(self,filename):
		filename=os.path.basename(filename)
		v=os.path.splitext(filename)[0].split("_")
		
		if len(v)<2 or not v[-2].isdigit(): 
			return ""

		if not (int(v[1]) % self.skip_value == 0): 
			return ""

		# todo _6.tif  LWIR _6 which has a different resolution 
		# we're resizing the thermal to match the other images properly now, 
		# so we can include it 
		# if (v[-1])=="6":
		# 	return ""

		return v[-2]
	
	# isPanel
	@staticmethod
	def isPanel(img):
		panel = micasense.panel.Panel(micasense.image.Image(img.filenames[0]))
		return panel.panel_detected()

	# findPanels
	def findPanels(self):

		print("Finding panels...")
		self.panels=[]

		# find the first panel
		while self.images and not self.isPanel(self.images[0]):
			print("Dropping",self.images[0].filenames,"because I need a panel")
			self.images.pop(0)

		if not self.images:
			raise Exception("cannot find the panel")

		# skip all panels
		while self.images and self.isPanel(self.images[0]):
			print(self.images[0].filenames,"is panel")
			self.panels.append(self.images[0])
			self.images.pop(0)

		# if not self.images:
		# 	raise Exception("cannot find flight images")

		# print(self.images[0].filenames,"is not panel, starting the flight")

		# not I need to find a detected panel (it must be in self.panels)
		for it in self.panels:
			try:
				panel = micasense.capture.Capture.from_filelist(it.filenames)
				if panel.panel_albedo() is not None:
					self.panel_calibration = panel.panel_albedo()
				else:
					self.panel_irradiance = [0.65] * len(panel.images)  # inexact, but quick
				self.panel_irradiance = panel.panel_irradiance(self.panel_calibration)
				print("panel_irradiance",self.panel_irradiance)
				break
			except:
				pass

	# generateMultiImage
	def generateMultiImage(self, img):
		capture = micasense.capture.Capture.from_filelist(img.filenames)
		capture_warp_matrices = capture.get_warp_matrices()
		# note I'm ignoring distortions here
		# capture.images[I].undistorted(capture.images[I].reflectance())

		# really important- we need to perform these steps first.
		# if we manipulate the image before we align it, the bands will 
		# become misaligned and we'll get worse issues downstream
		multi = capture.reflectance(self.panel_irradiance)
		multi = [single.astype('float32') for single in multi]
		multi = self.alignImage(multi, capture_warp_matrices)
		multi = self.mirrorY(multi)
		multi[0], multi[2] = multi[2], multi[0]
		multi = self.undistortImage(multi)

		if len(multi) >= 5:
			shape = (multi[0].shape[1], multi[0].shape[0])
			multi[4:] = [cv2.resize(single, shape) for single in multi[4:]]

		return multi
