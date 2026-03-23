# -*- coding: utf-8 -*-
"""
@author: bav@geus.dk

tip list:
    %matplotlib inline
    %matplotlib qt
    import pdb; pdb.set_trace()
"""
import pandas as pd
import numpy as np
import os, logging
import xarray as xr
import sys, importlib
# purge cached package + submodules
# only useful in debugging mode
for name in list(sys.modules):
    if name == "pypromice" or name.startswith("pypromice."):
        del sys.modules[name]
importlib.invalidate_caches()
from pypromice.pipeline.get_l2 import get_l2
from pypromice.pipeline.join_l2 import join_l2
from pypromice.pipeline.get_l2tol3 import get_l2tol3
from pypromice.pipeline.join_l3 import join_l3

logging.getLogger('matplotlib.font_manager').disabled = True
logging.getLogger("pypromice").setLevel(logging.DEBUG)
logging.getLogger("pypromice.pipeline").setLevel(logging.DEBUG)
logging.getLogger("pypromice.pipeline.get_l2").setLevel(logging.DEBUG)
logging.getLogger('numba').setLevel(logging.WARNING)

data_folder = '/media/ice/Baptiste/geussnow01/aws-dev'

# %%

def process_l2_l3(station):

    print(station)
    # Loading the L1 data:
    path_to_l0 = '../aws-l0/'
    config_folder = '../aws-l0/metadata/station_configurations/'
    config_file_tx = path_to_l0 + '/tx/config/{}.toml'.format(station)
    config_file_raw = path_to_l0 + '/raw/config/{}.toml'.format(station)
    output_path = f'{data_folder}/L2_test'

    print("\n ======== test get_l2 ========= \n")
    if os.path.isfile(config_file_tx):
        inpath = path_to_l0 + '/tx/'
        pAWS_tx = get_l2(config_file_tx,
                         inpath,
                         output_path+'/tx/',
                         variables=None, metadata=None,
                         data_issues_path='../PROMICE-AWS-data-issues')

    else:
        pAWS_tx = None

    if os.path.isfile(config_file_raw):
        inpath = path_to_l0 + '/raw/'+station+'/'
        pAWS_raw = get_l2(config_file_raw,
                          inpath,
                          output_path+'/raw/',
                         variables=None, metadata=None,
                         data_issues_path='../PROMICE-AWS-data-issues')
    else:
        pAWS_raw = None

    print("\n ======== test join_l2 ========= \n")
    l2_merged = join_l2(f'{data_folder}/L2_test/raw/'+station+'/'+station+'_hour.nc',
                        f'{data_folder}/L2_test/tx/'+station+'/'+station+'_hour.nc',
                        f'{data_folder}/L2_test/level_2/',None,None)

    print("\n ======== test l2tol3 ========= \n")
    l3 = get_l2tol3(config_folder,
                    f'{data_folder}/L2_test/level_2/'+station+'/'+station+'_hour.nc',
                    f'{data_folder}/L3_test/stations/', None, None, None)
    return pAWS_tx, pAWS_raw, l2_merged, l3


# %% test join_l3


def get_join_l3(site):

    print(" ======== test join_l3 ========= \n")
    path_l3_stations = f'{data_folder}/L3_test/stations/'
    config_folder = '../aws-l0/metadata/station_configurations/'
    folder_gcnet = '../GC-Net-level-1-data-processing/L1/hourly'
    folder_glaciobasis = '../historical-zac-data/'

    print(site)
    for f in [f'{data_folder}/L3_test/sites/{site}/{site}_hour.nc',
              f'{data_folder}/L3_test/sites/{site}/{site}_day.nc',
              f'{data_folder}/L3_test/sites/{site}/{site}_month.nc']:
        if os.path.exists(f):
            os.remove(f)

    l3_merged, sorted_list_station_data = join_l3(config_folder, site, path_l3_stations,
                        folder_gcnet, folder_glaciobasis, f'{data_folder}/L3_test/sites/', None, None)
    return l3_merged, sorted_list_station_data


if __name__ == '__main__':
    station_list = ['CEN1', 'CEN2', 'CP1', 'DY2', 'EGP', 'FRE', 'HUM', 'JAR', 'JAR_O', 'KAN_B', 'KAN_L',
        'KAN_Lv3', 'KAN_M', 'KAN_Tv3', 'KAN_U', 'KPC_L', 'KPC_Lv3', 'KPC_U', 'KPC_Uv3',
        'LYN_L', 'LYN_T', 'MIT', 'NAE', 'NAU', 'NEM', 'NSE', 'NUK_B', 'NUK_K', 'NUK_L',
        'NUK_Lv3', 'NUK_N', 'NUK_P', 'NUK_U', 'NUK_Uv3', 'ORO', 'QAS_A', 'QAS_L',
        'QAS_Lv3', 'QAS_M', 'QAS_Mv3', 'QAS_U', 'QAS_Uv3', 'RED_Lv3', 'SCO_L', 'SCO_Lv3',
        'SCO_U', 'SCO_Uv3', 'SDL', 'SDM', 'SER_B', 'SWC', 'SWC_O', 'TAS_A', 'TAS_Av3',
        'TAS_L', 'TAS_U', 'THU_L', 'THU_L2', 'THU_U', 'THU_U2', 'THU_U2v3', 'TUN',
        'UPE_L', 'UPE_U', 'UWN', 'WEG_B', 'WEG_L', 'ZAC_A', 'ZAC_Lv3', 'ZAC_Uv3']
 
    site_list = ['CEN', 'CP1', 'DY2', 'EGP', 'FRE', 'HUM', 'JAR', 'KAN_B', 'KAN_L', 'KAN_M', 'KAN_T',
        'KAN_U', 'KPC_L', 'KPC_U', 'LYN_L', 'LYN_T', 'MIT', 'NAE', 'NAU', 'NEM', 'NSE',
        'NUK_B', 'NUK_K', 'NUK_L', 'NUK_N', 'NUK_P', 'NUK_U', 'ORO', 'QAS_A', 'QAS_L',
        'QAS_M', 'QAS_U', 'RED_L', 'SCO_L', 'SCO_U', 'SDL', 'SDM', 'SER_B', 'SWC', 'TAS_A',
        'TAS_L', 'TAS_U', 'THU_L', 'THU_L2', 'THU_U', 'TUN', 'UPE_L', 'UPE_U', 'UWN',
        'WEG_B', 'WEG_L', 'ZAC_A', 'ZAC_L', 'ZAC_U']

    # for station in ['SWC', 'SWC_O']:
    for station in station_list:
        pAWS_tx, pAWS_raw, l2_merged, l3 = process_l2_l3(station)

    for site in site_list:
    # for site in ['SWC']:
        l3_merged, sorted_list_station_data = get_join_l3(site)
