#Import statements needed for plotting with matplotlib in the UI
from matplotlib.backends.qt_compat import QtCore, QtWidgets, is_pyqt5
if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt4agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
#End of import statements for matplotlib

from PyQt5 import QtWidgets
#from PyQt5.QtCore import (QThreadPool, QObject, pyqtSignal)
import sys 
import numpy as np
import time
from threading import Timer

from AndorCCD import AndorCCD
import AndorPyQTUI 

class MainApp(QtWidgets.QMainWindow, AndorPyQTUI.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        
        #variable for mumbo jumbo button mayhem in pyqt
        self.singleAqc_call = 0
        
        #create instance of ccd and set error code and initial values of UI
        self.ccd = AndorCCD('./Andor_420OE_CC_001/','Atmcd32d.dll')
        #set the update code in the UI and start timer to check every now and then for error code and temperature
        self.updateTimer = Timer(0.25,self.updateErrorCodeAndStatus).start()
        
        self.updateTemp()
        self.ccd.setExposureTime(self.integrationTime_ctrl.value(),self.avg_ctrl.value())
        #set up a timer for continous measurement
        self._timerAqc = Timer(self.ccd.actualKinetic+0.021,self.startAqcuisition)

        #event handler definitions
        #file save
        self.actionSave.triggered.connect(self.saveFile)
        #cooler on and off button
        self.startCooling_btn.clicked.connect(lambda: self.ccd.coolerOn(self.temperature_ctrl.value()))
        self.stopCooling_btn.clicked.connect(self.ccd.coolerOff)
        #single aqcuisition button
        self.singleAqc_btn.clicked.connect(self.singleAqcd)
        #start and stop continous aqcuisition
        self.stop_btn.clicked.connect(self.stopAqcuisition)
        self.start_btn.clicked.connect(self.startAqcuisition)
        
        #change of integration time and averaging
        self.integrationTime_ctrl.valueChanged.connect(self.integrationChanged)
        self.avg_ctrl.valueChanged.connect(self.integrationChanged)        
        
        #        code for matplotlib implementation to add a figure in drawLayout 
        dynamic_canvas = FigureCanvas(Figure(figsize=(500, 300)))
        self.drawLayout.addWidget(dynamic_canvas)
        self.addToolBar(QtCore.Qt.BottomToolBarArea,NavigationToolbar(dynamic_canvas, self))
        self._dynamic_ax = dynamic_canvas.figure.subplots()
        self._timer = dynamic_canvas.new_timer(21, [(self._update_canvas, (), {})])
        self._timer.start()
    
    #change the integration time and reset the timer for aqcuisition if it was already running
    def integrationChanged(self):
        self.stopAqcuisition()            
        self.ccd.setExposureTime(self.integrationTime_ctrl.value(),self.avg_ctrl.value())
    
    def enableB(self):
        self.singleAqc_btn.setEnabled(True)
        self.singleAqc_btn.repaint()
        
    #Perform a single aqcuisition, only do this when no measurement is busy
    def singleAqcd(self):
        #mumbo jumbo for button mayhem in qtpy
        if(time.perf_counter() - self.singleAqc_call<1):
            return
        
        #disable button 
        self.singleAqc_btn.setEnabled(False)
        #more mumbo jumbo for button mayhem in qtpy
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.processEvents()
        
        #finally do what we wanted to do on button click
        self.ccd.performAqcuisition(self.integrationTime_ctrl.value(),self.avg_ctrl.value())

        #reinstate the button to enabled
        self.singleAqc_btn.setEnabled(True)
        
        #more mumbo jumbo for button mayhem in qtpy
        self.singleAqc_call = time.perf_counter()
        

        
    #create a new timer when the button is clicked
    def startAqcuisition(self): 
        self.ccd.performAqcuisition(self.integrationTime_ctrl.value(),self.avg_ctrl.value())
        self._timerAqc = Timer(self.ccd.actualKinetic+0.021,self.startAqcuisition)
        self._timerAqc.start()

    #stop the new timer when the button is clicked
    def stopAqcuisition(self): 
        self._timerAqc.cancel()
        self.ccd.cancelAqc()


    
    def _update_canvas(self):
        self._dynamic_ax.clear()
        t = np.linspace(0, self.ccd.pixelX , self.ccd.pixelX)
        # Shift the sinusoid as a function of time.
        self._dynamic_ax.plot(t, self.ccd.data)
        self._dynamic_ax.figure.canvas.draw()
        
        
#save the data when needed to a file given by the user (always let it end at .txt)
    def saveFile(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(self,'Save data to:','./')
        if(filename[0]!=''):
            np.savetxt(filename[0], self.ccd.data, delimiter='\t', newline='\r\n')
   
    def updateErrorCodeAndStatus(self):
        
        self.ccd.getAqcuisitionProgress()

        self.errorcode_lbl.setText(str(self.ccd.E) + 
                                   '\r\n exp:' + str(self.ccd.actualExposureTime) + 
                                   '\r\n accum:' + str(self.ccd.actualAccumulate) + 
                                   '\r\n kinetic: '+str(self.ccd.actualKinetic) + 
                                   '\r\n progress: ' + str(int(self.ccd.accumComplete/self.avg_ctrl.value()*100)) )
        self.updateTimer = Timer(0.025,self.updateErrorCodeAndStatus)
        self.updateTimer.start()
        
#    Update temperature and set safeToClose Flag accordingly
    def updateTemp(self):
        self.ccd.getTemperature()
        if(self.ccd.currentTemp<0):
            self.safeToClose = 0
        else:
            self.safeToClose = 1
        
        
        self.currentTemp_lbl.setText(str(self.ccd.currentTemp))    
        Timer(1, self.updateTemp).start()
    
#    Override of the closeEvent of the window, make sure the ccd is warmed up according to regulations to 0° first
    def closeEvent(self, event):
        self.ccd.coolerOff()
        while(self.safeToClose!=1):
            time.sleep(0.5)
        event.accept() # let the window close


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    form = MainApp()                             
    form.show()  
    app.exec_()
    
#    sys.exit(app.exec_())
    
if __name__ == '__main__':             
    main()  

