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
        -orbit_df: dataframe containing orbit information (returned by op.CalculateNextOrbit)
    '''
    sat=op.SelectSatFromName(sat_name)  #get satellite object
    orbit_df=op.CalculateNextOrbit(sat, my_lat, my_lon, time_delta,24,elevation_start)   #get orbit dataframe
    
    return orbit_df

def Orbit2steps(orbit_df, az_resolution, elev_resolution):
    '''Brief: Calculate steps to make in each point by differenciating both angles.
    Parameters:
        -orbit_df: orbit containing time points, azimuth and elevation columns
        -az_resolution: azimutal angle [°] per step
        -elev_resolution: elevation angle [°] per step
    Returns:
        -steps_df: dataframe containing three columns:
            -Time: time point in milliseconds
            -Elev Steps: amount of elevation steps to make in that point
            -Az Steps: amount of azimuth steps to make in that point
        -start_data: list containing the following values:
            -orbit_start: time point where orbit starts in seconds
            -points_amount: amount of points
            -az_dir: azimuth direction (1: clockwise, -1: counterclockwise)
            -start_az_steps: steps needed to orient system to starting azimuth angle
            -start_az_steps: steps needed to orient system to starting elevation angle
            -elev_dir_change: time point where elevation changes direction in milliseconds
    '''
    #create orbit_df copy
    steps_df = orbit_df.copy()
    
    #get start point time in seconds (not taking milliseconds into account)
    orbit_start = math.trunc(steps_df['Time'].iloc[0])
    steps_df['Time'] -= orbit_start
    
    #Convert times to milliseconds (integer)
    steps_df["Time"] = (steps_df["Time"]*1000).astype(int)
    
    #get azimuth and elevation start angle
    azimuth_start = steps_df['Azimuth'].iloc[0]
    elevation_start = steps_df['Elevation'].iloc[0]
    
    #convert azimuth start angle from (0,360) to (-180,180)
    if azimuth_start > 180:
        azimuth_start -= 360
    if azimuth_start <- 180:
        azimuth_start += 360
    
    #convert azimuth and elevation start angle to steps
    start_az_steps = int(azimuth_start / az_resolution)
    start_elev_steps = int(elevation_start / elev_resolution)

        
    #Calculate azimuth and elevation derivative
    steps_df['dElev'] = (steps_df['Elevation'] - steps_df['Elevation'].shift(1)).fillna(0)
    steps_df['dAz'] = (steps_df['Azimuth'] - steps_df['Azimuth'].shift(1)).fillna(0)
    
    #get azimuth direction
    az_dir = int(np.sign(steps_df['dAz'].iloc[1]))
    
    #Initialize steps columns
    steps_df['Elev Steps'] = 0
    steps_df['Az Steps'] = 0
    steps_df.index.name = "Index"  #set index name (irrelevant)
    
    dir_setted = False    #a boolean is used to know if the direction change in elevation has happened
    
    az_angle, elev_angle = 0, 0 #initialize counters
    
    print("Calculating steps:")
    #iterate over each orbit point
    for ind in tqdm(steps_df.index):
        
        #If azimuth angle changes from 0 to 359 or vice versa, a correction is made to the azimuth delta
        if abs(steps_df['dAz'][ind]) > 300:
            if(steps_df['dAz'][ind]) > 0:
                steps_df['dAz'][ind] -= 360
            if(steps_df['dAz'][ind]) < 0:
                steps_df['dAz'][ind] += 360
           
        #evaluate if azimuth acumulated angle is greater than the angle per step
        # if it is, add a step to the step column and substract the angle per step
        #repeat until az_angle is smaller than the angle per step
        az_angle += abs(steps_df['dAz'][ind]) 
        while az_angle >= az_resolution:
            az_angle=az_angle-az_resolution
            steps_df['Az Steps'][ind] += 1
    
        elev_angle += abs(steps_df['dElev'][ind])
        while elev_angle >= elev_resolution:
            elev_angle = elev_angle-elev_resolution
            steps_df['Elev Steps'][ind] += 1
       
        #evaluate if elevation derivative became negative, indicating a
        #direction change. If the point is the direction change, save its time
        if steps_df['dElev'][ind] < 0 and dir_setted == False:
            elev_dir_change = int(steps_df['Time'][ind])
            dir_setted = True
        
        #remove rows without steps
        if steps_df['Az Steps'][ind] == 0 and steps_df['Elev Steps'][ind] == 0:
            steps_df.drop([ind],axis=0,inplace=True)
    
    #Create list of start values
    points_amount = len(steps_df["Time"])
    start_data = (orbit_start, points_amount, az_dir, start_az_steps, start_elev_steps, elev_dir_change)
         
    #remove irrelevant columns
    steps_df.drop(steps_df.columns.difference(['Time','Elev Steps','Az Steps']), axis=1, inplace=True)
    
    return steps_df, start_data
    

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
        
    print("Starting serial transfer:")
    
    n, cont = 0, 0
    serial_device.write(b'\x01')
    while True:
        while serial_device.read(1) != b'\x01':
            True
        if n==0:
            # current time
            print("Sending data:")
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
            print("amount of points: ",start_data[1])
            print("elevation start angle: ",start_data[4])
            print("elevation direction change: ",start_data[5])

            TxSerial(start_data[1]) #amount of points
            TxSerial(start_data[4]) #elevation start angle
            TxSerial(start_data[5]) #elevation direction change
            
        elif n==3:
            #Send azimuth direction and start angle
            print("azimut direction ",start_data[2])
            print("azimuth start angle: ",start_data[3])

            
            TxSerial_atoi(start_data[2],4)  #azimuth direction
            TxSerial_atoi(start_data[3],7)  #azimuth start angle
            #this values are sent separately because of their possible negative sign, as they are send as chars
           
        elif n==4:
            #send points
            for i in points:
                cont+=1
                if(cont!=0 and cont % 1000 == 0):
                    print("points send:", cont, "/",start_data[1])
                    while serial_device.read(1) != b'\x01':
                        True
                        
                TxSerial(i)
                i+=1
            print("points send:", start_data[1], "/",start_data[1])
            break

        #increment state variable
        n+=1
    Rx = serial_device.read(1)
    if(Rx == b'\x01'):
        print("Data stored in EEPROM succesfully")
    elif(Rx ==b'\x02'):
        print("Data could not be stored in EEPROM, maybe EEPROM is disconnected or corrupted?")
    else:
        print("unknown sequence reached, debug needed")
            