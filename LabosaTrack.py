import orbit_prediction as op
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None  # default='warn'
from tqdm import tqdm
import time, math

def SatTrack(my_lat,my_lon,sat_name,time_delta,elevation_start):
    '''Brief: calculates satellite pass and returns two elements: a dataframe containing
    time points and steps and a list of start values
    Parameters:
        -my_lat: observer's latitude
        -my_lon: observer's longitude
        -sat_name: satellite name
        -time_delta: time between points
        -elevation_start: elevation angle to start calculating orbit
    Returns:
        -orbit_df: dataframe containing orbit information (returned by CalculateNextOrbit)
    '''
    sat=op.SelectSatFromName(sat_name)  #get satellite object
    orbit_df=op.CalculateNextOrbit(sat, my_lat, my_lon, time_delta,24,elevation_start)   #get orbit dataframe
    
    return orbit_df

def Orbit2steps(orbit_df,mechanical_resolution):
    '''Brief: Calculate steps to make in each point by differenciating both angles.
    Parameters:
        -orbit_df: orbit containing time points, azimuth and elevation columns
        -mechanical_resolution: angle per step
    Returns:
        -steps_df: dataframe containing three columns:
            -Time: time point in milliseconds
            -Elev Steps: amount of elevation steps to make in that point
            -Az Steps: amount of azimuth steps to make in that point
        -start_data: list containing the following values:
            -orbit_start: time point where orbit starts in seconds
            -points_amount: amount of points
            -az_dir: azimuth direction (1: clockwise, -1: counterclockwise)
            -azimuth_start: azimuth angle in orbit start in millidegrees
            -elevation_start: elevation angle in orbit start in millidegrees
            -elev_dir_change: time point where elevation changes direction in milliseconds
            -mechanical_resolution: angle per step in millidegrees
    '''
    #create orbit_df copy
    steps_df=orbit_df.copy()
    
    #get start point time in seconds (not taking milliseconds into account)
    orbit_start=math.trunc(steps_df['Time'].iloc[0])
    steps_df['Time']-=orbit_start
    
    #Convert times to milliseconds (integer)
    steps_df["Time"]=(steps_df["Time"]*1000).astype(int)
    
    #get azimuth start angle
    azimuth_start=steps_df['Azimuth'].iloc[0]
    
    #convert azimuth start angle from (0,360) to (-180,180)
    if azimuth_start>180:
        azimuth_start-=360
    if azimuth_start<-180:
        azimuth_start+=360
        
    #convert azimuth start to millidegrees
    azimuth_start=int(azimuth_start*1000)
    #get elevation start angle in millidegrees (integer)
    elevation_start=int((steps_df['Elevation'].iloc[0])*1000)
        
    #Calculate azimuth and elevation derivative
    steps_df['dElev'] = (steps_df['Elevation'] - steps_df['Elevation'].shift(1)).fillna(0)
    steps_df['dAz'] = (steps_df['Azimuth'] - steps_df['Azimuth'].shift(1)).fillna(0)
    
    #get azimuth direction
    az_dir=int(np.sign(steps_df['dAz'].iloc[1]))
    
    #Initialize steps columns
    steps_df['Elev Steps']=0
    steps_df['Az Steps']=0
    steps_df.index.name="Index"  #set index name (irrelevant)
    
    dir_setted= False    #a boolean is used to know if the direction change in elevation happened
    
    az_step_count,az_angle,elev_step_count,elev_angle=0,0,0,0 #initialize counters
    
    print("Calculating steps:")
    #iterate over each orbit point
    for ind in tqdm(steps_df.index):
        
        #If azimuth angle changes from 0 to 359 or vice versa, a correction is made to the azimuth delta
        if abs(steps_df['dAz'][ind])>300:
            if(steps_df['dAz'][ind])>0:
                steps_df['dAz'][ind]-=360
            if(steps_df['dAz'][ind])<0:
                steps_df['dAz'][ind]+=360
           
        #evaluate if azimuth acumulated angle is greater than the angle per step
        # if it is, add a step to the step column and substract the angle per step
        #repeat until az_angle is smaller than the angle per step
        az_angle += abs(steps_df['dAz'][ind]) 
        while az_angle >= mechanical_resolution:
            az_step_count+=1
            az_angle=az_angle-mechanical_resolution
            steps_df['Az Steps'][ind]+=1
    
        elev_angle += abs(steps_df['dElev'][ind])
        while elev_angle >= mechanical_resolution:
            elev_step_count+=1
            elev_angle=elev_angle-mechanical_resolution
            steps_df['Elev Steps'][ind]+=1
       
        #evaluate if elevation derivative became negative, indicating a
        #direction change. If the point is the direction change, save its time
        if steps_df['dElev'][ind] < 0 and dir_setted == False:
            elev_dir_change=int(steps_df['Time'][ind])
            dir_setted=True
        
        #remove rows without steps
        if steps_df['Az Steps'][ind] == 0 and steps_df['Elev Steps'][ind] == 0:
            steps_df.drop([ind],axis=0,inplace=True)
    
    #Create list of start values
    points_amount=len(steps_df["Time"])
    start_data=(orbit_start, points_amount, az_dir,azimuth_start,elevation_start,elev_dir_change,int(mechanical_resolution*1000))
         
    #remove irrelevant columns
    steps_df.drop(steps_df.columns.difference(['Time','Elev Steps','Az Steps']), axis=1, inplace=True)
    
    return steps_df,start_data
    

def CompressOrbitData(steps_df):
    '''Brief: compresses all information of a point in 32 bits
    Parameters:
        -steps_df: dataframe containing orbit times and steps
    Returns:
        -points_df: dataframe containing a single column with times and steps
    '''
    points_df = []    #create empty list
    
    print("Compressing steps:")
    for ind in tqdm(steps_df.index):    #iterate dataframe
        value = int(steps_df["Time"][ind] << 8 | steps_df["Az Steps"][ind] << 4 | steps_df["Elev Steps"][ind]) #create a single int with bit displacement, bits 3-0: Elev steps, bits 7-4: Az steps, bits 31-8: time
        points_df.append(value)   #add value to list
    return points_df


def SerialSend(serial_device,points,start_data):
    '''Brief: Rutine that sends all data through serial port
    Parameters:
        -serial_device: serial object
        -points: list containing data to be sent
        -start_data: list contaning values returned by Orbit2Steps
    '''
    def TxSerial(Txdata):
        serial_device.write(Txdata.to_bytes(4,"big"))
        
    def TxSerial_atoi(Txdata,dataSize):
        Tx=str(Txdata).encode()
        Tx+=bytes(dataSize-len(Tx))
        serial_device.write(Tx)
        print(Tx)
        
    print("Start serial transfer:")
    
    n, cont = 0, 0
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
            print("current time:",t, op.GetDatetimeFromUNIX(t))
            
        elif n==1:
            #Send alarm time
            t=start_data[0]
            TxSerial(t)
            print("alarm time:",t, op.GetDatetimeFromUNIX(t))
            
        elif n==2:
            #Send amount of points, elevation start angle, elevation direction change and mechanical resolution
            print(start_data)
            TxSerial(start_data[1])
            TxSerial(start_data[4])
            TxSerial(start_data[5])
            TxSerial(start_data[6])
            
        elif n==3:
            #Send azimuth direction and start angle
            TxSerial_atoi(start_data[2],4)
            TxSerial_atoi(start_data[3],7)
            #this values are sent separately because of their possible negative sign, as they are send as chars
           
        elif n==4:
            #send points
            for i in points:
                cont+=1
                if(cont!=0 and cont % 1000 == 0):
                    print(cont)
                    while serial_device.read(1)!=b'\x01':
                        True        
                TxSerial(i)
                i+=1
            break
        
        #increment state variable
        n+=1