import LabosaTrack as lst
import orbit_prediction as op
import serial, sys

my_lat=-34.54
my_lon=-58.5
sat_name="MAROC-TUBSAT"
time_delta=0.4 #seconds
elevation_start=0 #degrees
mechanical_resolution=0.05
mode = 1

if(mode!=2):
    try:
        serial_device=serial.Serial(port='COM8', baudrate=115200,stopbits=1,timeout=16,write_timeout=1)
    except:
        print("ERROR: Couldn't connect to serial port")
        sys.exit()

if(mode==0 or mode== 2):
    #### 0 Calculate ISS pass 
    orbit = lst.SatTrack(my_lat, my_lon, sat_name, time_delta, elevation_start)
    steps,start_data = lst.Orbit2steps(orbit, mechanical_resolution)
    compressed_steps = lst.CompressOrbitData(steps)
    

    lst.SerialSend(serial_device,compressed_steps,start_data)

if(mode==1):
    ### 1 Calculate next sat pass
    TLEs = op.DownloadTLEs()
    sat = op.NextSatPass(TLEs,my_lat,my_lon,10, 70)
    print(sat.name)
    orbit = lst.SatTrack(my_lat, my_lon, sat.name, time_delta, elevation_start)
    steps,start_data = lst.Orbit2steps(orbit, mechanical_resolution)
    compressed_steps = lst.CompressOrbitData(steps)
    
    lst.SerialSend(serial_device,compressed_steps,start_data)