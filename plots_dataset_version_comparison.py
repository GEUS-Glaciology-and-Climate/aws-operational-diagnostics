# -*- coding: utf-8 -*-
"""
@author: bav@geus.dk

tip list:
    %matplotlib inline
    %matplotlib qt
    import pdb; pdb.set_trace()
"""
# if the first thing you want to do is downloading the remote data
# from download_ssh import main
# main()

import matplotlib.pyplot as plt
import pandas as pd
import os, toml
import xarray as xr
import numpy as np
import argparse

import matplotlib
matplotlib.use('Agg')
import tocgen

def main(old_version = 'V33',
         path_to_thredds='/media/ice/Baptiste/geussnow01/thredds-data/',
         path_to_dataverse='/media/ice/Baptiste/geussnow01/dataverse/'):
    new_version = 'thredds'
    for res in ['month','day','hour']:
    # for res in ['hour']:
        path_old = f'{path_to_dataverse}/{old_version}/{res}/'
        path_new = f'{path_to_thredds}/level_3_sites/csv/{res}/'
    
        df_meta = pd.read_csv(f'{path_to_thredds}/metadata/AWS_sites_metadata.csv')
        df_meta2 = pd.read_csv(f'{path_to_thredds}/metadata/AWS_stations_metadata.csv')

        from datetime import date
        today = date.today().strftime("%Y%m%d")

        filename = f'plot_compilations/{old_version}_versus_{new_version}_{res}.md'
        figure_folder=f'figures/version_comparisons/{old_version}_versus_{new_version}_{res}'

        os.makedirs('plot_compilations', exist_ok=True)
        os.makedirs(figure_folder, exist_ok=True)

        f = open(filename, "w")
        def Msg(txt):
            f = open(filename, "a")
            print(txt)
            f.write(txt + "\n")

        Msg('# Comparison of data '+new_version+' to '+old_version+' (old).')

        plt.close('all')

        #%%
        for station in np.unique(df_meta.site_id):
        # for station in ['EGP']:
            plt.close('all')

            if station in ['UWN','ORO','NUK_P']:
                continue

            Msg('## '+station)
            file = f'{path_new}{station}_{res}.csv'
            try:
                df_new = pd.read_csv(file)
            except:
                file =f'{path_new}/{station}/{station}_{res}.csv'
                if os.path.isfile(file):
                    df_new = pd.read_csv(file)
                else:
                    Msg('No new file for this station')
                    continue
            
            df_new.time = pd.to_datetime(df_new.time, utc=True)
            df_new = df_new.set_index('time')
            
            df_old = pd.DataFrame()
            df_old['time'] = df_new.index.values

            file = f'{path_old}{station}_{res}.csv'
            if not os.path.isfile(file):
                Msg('cannot find old file for '+station)

            if os.path.isfile(file):
                print(file)
                df_old = pd.read_csv(file)

            df_old.time = pd.to_datetime(df_old.time, utc=True)
            df_old = df_old.set_index('time')
            
            if res == "hour":
                today = pd.Timestamp.utcnow().normalize()
                df_old = df_old.loc[slice(today - pd.DateOffset(years=1), today), :]
                df_new = df_new.loc[slice(today - pd.DateOffset(years=1), today), :]
                if len(df_new) == 0:
                    Msg(f"No data from {station} in the last year")
                    continue

            Msg('Variables in new file:\n'+ ', '.join(df_new.columns.values))
            Msg('\nNew variables not in old files:\n'+ ', '.join(
                [v for v in df_new.columns if v not in df_old.columns]
                ))
            Msg('\nOld variables removed from new files:\n'+ ', '.join(
                [v for v in df_old.columns if v not in df_new.columns]
                ))
            Msg(' ')
            var_list = df_new.columns.values
            # var_list = ['rainfall_u','rainfall_cor_u','rainfall_l','rainfall_cor_l']
            var_list_list = [var_list[i:i+5] for i in range(0, len(var_list), 5)]

            if res == 'month':
                size=8
            else:
                size=6

            for k, var_list in enumerate(var_list_list):
                fig, ax_list = plt.subplots(len(var_list),1,sharex=True, figsize=(13,13))
                if len(var_list)==1:
                    ax_list = [ax_list]

                for var, ax in zip(var_list, ax_list):
                    ax.set_ylabel(var)

                    var_old = var.replace('rainfall_cor_u','precip_u_rate').replace('rainfall_cor_l','precip_l_rate')
                    var_old = var.replace('rainfall_u','precip_u_cor').replace('rainfall_l','precip_l_cor')

                    if var in df_old.columns:
                        ax.plot(df_old[var].index, df_old[var].values,
                                marker='^',linestyle='None', label=old_version,
                                alpha=0.7, markersize=size*1.3, color='tab:blue')
                    elif var_old in df_old.columns:
                        ax.plot(df_old[var_old].index,
                                df_old[var_old].values,
                                marker='^',linestyle='None', label=f'{old_version} - old name {var_old}',
                                alpha=0.7, markersize=size*1.3, color='tab:blue')
                    else:
                        print(var,'not in old data')


                    if var in df_new.columns:
                        ax.plot(df_new[var].index, df_new[var].values,
                                marker='o',markeredgecolor='None', linestyle='None',
                                label=new_version, alpha=0.7,markersize=size,
                                color='tab:orange')
                    else:
                        print(var,'not in new data')
                    ax.legend(loc='lower left')
                    ax.grid()
                    if res == 'hour':
                        end = pd.Timestamp.today()
                        start = end - pd.DateOffset(years=1)
                        ax.set_xlim(start, end)
                    # ax.set_xlim(df_new.index[0], df_new.index[-1])

                plt.suptitle(f'{station} {k+1}/{len(var_list_list)}')
                fig.savefig(figure_folder+'/%s_%i.png'%(station,k), dpi =90)
                # plt.close(fig)
                Msg(f'![{station}](../{figure_folder}/{station}_{k}.png)')
            Msg(' ')
        tocgen.processFile(filename, filename[:-3]+"_toc.md")
        f.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the script with optional parameters.")
    parser.add_argument("--dataverse_version", type=str, default="V32", help="Version of the dataverse data to use (default: V32)")

    args = parser.parse_args()
    
    main(old_version=args.dataverse_version)
