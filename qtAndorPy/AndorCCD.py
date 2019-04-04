from ctypes import c_char_p, windll, c_int, byref, c_float, c_long, c_ulong
import numpy as np
from AndorErrorCodes import AndorErrorCodes as er
from threading import Event

class AndorCCD:
    

    
    #Load the dll of the CCD and initialize the CCD - return the instance of the class 
    def __init__(self, dllFolder,dllName):
        self.dllFolder          = dllFolder
        self.dllName            = dllName
        
        self.readyForNextAqc    = True
        self.currentTemp = 999
        self.actualExposureTime = 0
        self.actualAccumulate = 0
        self.actualKinetic = 0
        self.accumComplete = 0
        self.pixelX = 0 #1024
        self.pixelY = 0 #255
        self.data = 0 #contains the data of the last aqcuisition
        

        
        #load the dll 
        self.__ccd = windll.LoadLibrary(dllFolder+dllName)
        #initiate the ccd (needs to have info on the detector coming from the detector.ini file)
        self.E = self.__ccd.Initialize(c_char_p(dllFolder.encode('utf-8')))

        # set aqcuisition to accumulate
        self.E = self.__ccd.SetAcquisitionMode(c_int(2))
        #set read mode to full vertical binning
        self.E = self.__ccd.SetReadMode(c_int(0))
        #set vertical speed to the maximum
        self.setVerticalSpeedToMax()
        #set horizontal speed to max
        self.setHorizontalSpeedToMax()
        #set the AD channel to the first one available 
        self.E = self.__ccd.SetADChannel(c_int(0))
        #set trigger mode to internal
        self.E = self.__ccd.SetTriggerMode(c_int(0))
        #set pixelX and pixelY to the detector size
        self.getDetectorSize()
        
        #after initializing get the current temperature of the CCD
        if(self.E == er.DRV_SUCCESS):
            self.getTemperature()
    
    #get the number of pixels of the ccd       
    def getDetectorSize(self):
        w = c_int(0)
        h = c_int(0)
        self.E = self.__ccd.GetDetector(byref(w),byref(h))
        self.pixelX = w.value #1024
        self.pixelY = h.value #255
        #fill the data property with correct amount as np.array
        self.data = np.zeros((self.pixelX,1))
    
    #cancel any aqcuisition that is busy and cancel any waiting to block    
    def cancelAqc(self):
        
        self.E = self.__ccd.CancelWait()
        self.E = self.__ccd.AbortAcquisition()
        self.readyForNextAqc = True
        
   
    #sets the exposure time of the CCD to t seconds - actual exposure time can be obtained with getExposureTime
    def setExposureTime(self,t,n):
        self.E = self.__ccd.SetExposureTime(c_float(t))
        self.E = self.__ccd.SetNumberAccumulations(c_int(n))
        #set accumulation cycle time
        self.__ccd.SetAccumulationCycleTime(c_float(0))
        self.getExposureTime()
    
    #perform an aqcuisition using the integration time t (in seconds) with n accumulations
    #Äready is an Event object
    def performAqcuisition(self,t,n):
        if(self.readyForNextAqc):
            #set this signal to false such it can be checked from outside that no more calls are made for aqc 
            self.readyForNextAqc = False
            #set integration time and et number of accumulations
            self.setExposureTime(t,n)

            #get the effective integrationtimes
            self.getExposureTime()
            #start the aqcuisition
            self.__ccd.StartAcquisition()
            #first simply wait for the aqcuisition to finish
            for i in range(0,n):
                self.__ccd.WaitForAcquisition()
            #get the data
            data = (c_long * self.pixelX)()
            self.__ccd.GetAcquiredData(data, c_ulong(self.pixelX))
            #♣store this data into a numpy array 
            self.data = np.array(data)/n
            self.readyForNextAqc = True

            
        
    def getExposureTime(self):
        exp = c_float(0)
        accum = c_float(0)
        kinetic = c_float(0)
        errorValue = self.__ccd.GetAcquisitionTimings(byref(exp),byref(accum), byref(kinetic))
        if(errorValue==er.DRV_SUCCESS):
            self.actualExposureTime = exp.value
            self.actualAccumulate = accum.value
            self.actualKinetic = kinetic.value
        else:
            self.actualExposureTime = 0
            self.actualAccumulate = 0
            self.actualKinetic = 0
        self.E = errorValue
        
    def getAqcuisitionProgress(self):
        accum = c_long(0)
        series = c_long(0)
        self.E = self.__ccd.GetAcquisitionProgress(byref(accum),byref(series))
        self.accumComplete = accum.value
        
    def coolerOn(self,desiredTemp):
        self.E = self.__ccd.SetTemperature(desiredTemp) 
        self.E = self.__ccd.CoolerON() 
        
    def coolerOff(self):
        self.E = self.__ccd.CoolerOFF()
    
    def getTemperature(self):
         temp = c_int(self.currentTemp)
         self.E = self.__ccd.GetTemperature(byref(temp)) 
         self.currentTemp = temp.value
 
    #Set Vertical speed to maximum recommended
    def setVerticalSpeedToMax(self):
        index = c_int(0)
        speed = c_float(0)
        self.E = self.__ccd.GetFastestRecommendedVSSpeed(byref(index), byref(speed))

        
    def setHorizontalSpeedToMax(self):
        STemp = 0
        HSnumber = 0
        index = c_int(0)
        speed = c_float(0)
        self.__ccd.GetNumberHSSpeeds(c_int(0),c_int(0),byref(index));
        index = index.value
        for i in range(0, index, 1):
          self.__ccd.GetHSSpeed(c_int(0), c_int(0), c_int(i), byref(speed))
          if(speed.value > STemp):
            STemp = speed.value;
            HSnumber = i;      
        self.E = self.__ccd.SetHSSpeed(c_int(0),HSnumber)       
    
    def __del__(self):
        self.E = self.__ccd.ShutDown() 
        del self.__ccd