import orbit_prediction_V2 as op
from skyfield.api import load, wgs84
import time
import datetime
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None  # default='warn'
from tqdm import tqdm
import serial
import math
    
def Orbit2steps(orbitDf,stepperRes):
    
    del orbitDf['Latitude']
    del orbitDf['Longitude']
    del orbitDf['Distance']
    del orbitDf['Height']
    orbitDf['dAlt'] = (orbitDf['Altitude'] - orbitDf['Altitude'].shift(1)).fillna(0)
    orbitDf['dAz'] = (orbitDf['Azimuth'] - orbitDf['Azimuth'].shift(1)).fillna(0)
    orbitDf['Steps']=0
    orbitDf.index.name="Index"
    
    dirSetted= False
    azStepCount,azAngle,altStepCount,altAngle=0,0,0,0
    for ind in tqdm(orbitDf.index):
        
        if abs(orbitDf['dAz'][ind])>300:
            if(orbitDf['dAz'][ind])>0:
                orbitDf['dAz'][ind]-=360
            if(orbitDf['dAz'][ind])<0:
                orbitDf['dAz'][ind]+=360
            
        azAngle+=abs(orbitDf['dAz'][ind])
        while azAngle>=stepperRes:
            azStepCount+=1
            azAngle=azAngle-stepperRes
            orbitDf['Steps'][ind]+=1
    
        altAngle+=abs(orbitDf['dAlt'][ind])
        while altAngle>=stepperRes:
            altStepCount+=1
            altAngle=altAngle-stepperRes
            orbitDf['Steps'][ind]+=100
       
        if orbitDf['dAlt'][ind]<0 and dirSetted==False:
            AltDirChange=orbitDf['Time'][ind]
            dirSetted=True
           
        if orbitDf['Steps'][ind]==0:
            orbitDf.drop([ind],axis=0,inplace=True)
    
    azimuthStart=orbitDf['Azimuth'].iloc[0]
    if azimuthStart>180:
        azimuthStart-=360
    if azimuthStart<-180:
        azimuthStart+=360
                
    startData={'AzDir':int(np.sign(orbitDf['dAz'].iloc[0])),'Azimuth':azimuthStart,'Altitude':orbitDf['Altitude'].iloc[0],'AltDir Change':AltDirChange,'Stepper Res':stepperRes}
    startDf = pd.DataFrame(startData,index=[0])
    startDf.index.name="start"
    return orbitDf,startDf
    
def PrintOrbitDf(orbitDf,startDf,azStepCount,altStepCount):
    print("Start Azimuth:",startDf['Azimuth'][0])
    print("Start Altitude:",startDf['Altitude'][0])
    print("Azimuth direction",startDf['AzDir'][0])
    print("Maximum Altitude",orbitDf['Altitude'].max())
    print("Maximum dAlt",abs(orbitDf['dAlt']).max())
    print("Maximum dAz",abs(orbitDf['dAz']).max())
    print("Alt steps:",altStepCount)
    print("Az steps:",azStepCount)

def CalculateNextOrbit(sat,myLatLon,timestep,in_hours=48,min_altitude=10):
     ts = load.timescale()
     t0 = ts.now()
     t1 = ts.from_datetime(t0.utc_datetime()+datetime.timedelta(hours=in_hours))
     bluffton = wgs84.latlon(myLatLon[0], myLatLon[1])
     tx, events = sat.find_events(bluffton, t0, t1, altitude_degrees=min_altitude)
     
     # me aseguro que el primer timestamp sea el de rise
     n=0
     while events[n]!=0:
         n+=1
     taux=tx.utc_datetime()
     taux=taux[n+2]-taux[n]
     
     return op.PredictOrbit(sat,myLatLon,tx[n],taux.seconds,timestep)

     
     
def SatTrack(myLatLon,satName,stepperFullRes,microstepping,timeStep):
    stepperRes=stepperFullRes/microstepping

    satellite=op.SelectSatFromName(satName)
    print(satName)
    
    orbitDf=CalculateNextOrbit(satellite, myLatLon, timeStep,24,10)
    orbitDf,startDf=Orbit2steps(orbitDf, stepperRes)
    
    orbitDf.to_csv("csv/StepperSteps.csv")
    startDf.to_csv("csv/StepperStart.csv")

    return orbitDf,startDf

#%%

def SendOrbit_init(stepsDf,startDf,stepperRes):
    print(op.GetDatetimeFromUNIX(stepsDf['Time'].iloc[0]))

    orbitStart=stepsDf['Time'].iloc[0]
    stepsDf['Time']-=orbitStart
    startDf['AltDir Change']-=orbitStart

    startDf["Azimuth"][0]=math.trunc(startDf["Azimuth"][0]*1000)
    startDf["Altitude"][0]=math.trunc(startDf["Altitude"][0]*1000)
    startDf["AltDir Change"][0]=math.trunc(startDf["AltDir Change"][0]*1000)
    startDf["Stepper Res"][0]=math.trunc(startDf["Stepper Res"][0]*1000)
    startDf["Azimuth"]=startDf["Azimuth"].astype(int)
    startDf["Altitude"]=startDf["Altitude"].astype(int)
    startDf["AltDir Change"]=startDf["AltDir Change"].astype(int)
    startDf["Stepper Res"]=startDf["Stepper Res"].astype(int)
       
    return orbitStart,stepsDf,startDf
    
def SerialSend(serial_device,orbitStart,stepsDf,startDf,alarm_offset):
    def TxSerial(Txdata):
        serial_device.write(Txdata.to_bytes(4,"big"))
        
    def TxSerial_atoi(Txdata,dataSize):
        Tx=str(Txdata).encode()
        Tx+=bytes(dataSize-len(Tx))
        serial_device.write(Tx)
        
    timepoints=(stepsDf["Time"]*1000).astype(int)
    steppoints=stepsDf["Steps"].astype(int)
    data=startDf["Altitude"].to_list()+startDf['AltDir Change'].to_list()+ startDf["Stepper Res"].to_list()+timepoints.to_list()+steppoints.to_list()

    
    n=0
    cont=0
    serial_device.write(b'\x01')

    while True:
        while serial_device.read(1)!=b'\x01':
            True
        if n==0:
            # current time
            now=time.time()
            while(time.time() < math.trunc(now)+1):
                True
            t=math.trunc(time.time())
            TxSerial(t)
            print("current time:",op.GetDatetimeFromUNIX(t))
        elif n==1:
            # alarm time (int)
            t=math.trunc(orbitStart)-alarm_offset
            TxSerial(t)
            print("alarm time:",op.GetDatetimeFromUNIX(t))
        elif n==2:
            #alarm decimals
            decimals=int(round(orbitStart-int(orbitStart),3)*1000)
            TxSerial(decimals)
        elif n==3:
            TxSerial(len(timepoints))
        elif n==4:   
           TxSerial_atoi(startDf["AzDir"].iloc[0],4)
           TxSerial_atoi(startDf["Azimuth"].iloc[0],7)
        elif n==5:
            for i in data:
                cont+=1
                if(cont!=0 and cont % 1000 == 0):
                    print(cont)
                    while serial_device.read(1)!=b'\x01':
                        True        
                TxSerial(i)
                i+=1
            break
        n+=1
    
    
def SendOrbit(serial_device,stepsDf,startDf,stepperRes,alarm_offset_seconds):
    
    orbitStart,stepsDf,startDf=SendOrbit_init(stepsDf,startDf,stepperRes)
    print("Start serial transfer")
    SerialSend(serial_device,orbitStart,stepsDf,startDf,alarm_offset_seconds)
    print(startDf)
    
    