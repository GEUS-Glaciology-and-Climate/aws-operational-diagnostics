
import matplotlib.pyplot as plt
import pandas as pd
import os
import matplotlib
import matplotlib.dates as mdates
from datetime import datetime
matplotlib.use('Agg')
import tocgen
import numpy as np
import argparse
from pathlib import Path
import math
from tqdm import tqdm
SKIP = ['NUK_P','NUK_B','SER_B','UWN','ORO', 'NUK_N','QAS_A','TAS_U']
# %% Snow height climatology plots
def main(path_thredds = "../thredds-data/"):
    path_new=Path(path_thredds) /"level_3_sites/csv/day"

    out=Path("figures/snow_height_mosaic.png")
    
    N_COLS=4
    ticks=list(np.cumsum([30,31,30,31,31,29,31,30,31,30,31,31]))
    labels=["Sept." if i<30 else "Oct." if i<60 else "Nov." if i<90 else "Dec." if i<120 else "Jan." if i<150 else
            "Feb." if i<180 else "Mar." if i<210 else "Apr." if i<240 else "May"  if i<270 else "Jun." if i<300 else
            "Jul." if i<330 else "Aug." if i<360 else "" for i in ticks]
    
    years=np.arange(1990,2027)
    cmap=plt.get_cmap("tab20",len(years))
    year_color={y:cmap(i) for i,y in enumerate(years)}
    focus_year=2026
    
    stations=[]
    for fn in sorted(os.listdir(path_new)):
        if not fn.endswith("_day.csv"): continue
        s=fn.replace("_day.csv","")
        if s in SKIP: continue
        stations.append(s)
    if not stations: raise SystemExit("no stations")
    
    n=len(stations); nrows=math.ceil(n/N_COLS)
    fig,ax=plt.subplots(nrows,N_COLS,figsize=(N_COLS*3.2,nrows*2.2),sharex=True,sharey=False)
    ax=np.atleast_2d(ax)
    
    handles={}
    for i, st in enumerate(tqdm(stations, desc="Plotting snow height")):
        r,c=divmod(i,N_COLS); a=ax[r,c]
        fp=path_new/f"{st}_day.csv"
        d=pd.read_csv(fp,usecols=lambda c:c in["time",'z_surf_combined',"snow_height"])
        if "snow_height" not in d.columns: 
            d['snow_height'] = d['z_surf_combined']
            print(st, 'misses snow_height')
        d["time"]=pd.to_datetime(d["time"],errors="coerce")
        d["snow_height"]=pd.to_numeric(d["snow_height"],errors="coerce")
        d=d.dropna(subset=["time"]).set_index("time").sort_index()
        if d["snow_height"].dropna().empty: a.axis("off"); continue
    
        for y in sorted(d.index.year.unique().tolist()):
            start=pd.Timestamp(f"{y-1}-09-01"); end=pd.Timestamp(f"{y}-08-31")
            dy=d.loc[(d.index>=start)&(d.index<end),["snow_height"]].copy()
            if dy.empty or dy["snow_height"].isnull().all(): continue
            dy["doy"]=dy.index.dayofyear.values-244
            dy.loc[dy["doy"]<0,"doy"]=365+dy.loc[dy["doy"]<0,"doy"]
            fvi=dy["snow_height"].first_valid_index()
            if fvi is None: continue
            ref=dy["snow_height"].loc[slice(fvi,fvi+pd.to_timedelta("30D"))].min()
            yy=dy["snow_height"]-ref
            if y in year_color:
                if y == focus_year:
                    a.plot(dy["doy"],yy,color='w',lw=3)[0]
                    ln=a.plot(dy["doy"],yy,color='k',lw=2)[0]
                else:
                    ln=a.plot(dy["doy"],yy,color=year_color[y],lw=1.2)[0]
                handles.setdefault(y,ln)
    
        a.set_title(st)
        a.set_ylim(bottom=0)
        a.grid(True)
        a.set_xlim(1,365)
    
    for j in range(n,nrows*N_COLS):
        r,c=divmod(j,N_COLS); ax[r,c].axis("off")
    
    for a in ax[-1,:]:
        if a.axison:
            a.set_xticks(ticks)
            a.set_xticklabels(labels,rotation=45,ha="right")
    
    handles=dict(sorted(handles.items(),reverse=True))
    fig.legend(handles.values(),[str(y) for y in handles.keys()],
                loc="center right",bbox_to_anchor=(0.98,0.5),title="Year",ncol=1)
    
    fig.text(0.01,0.5,"Snow Height (m)",va="center",rotation="vertical")
    fig.tight_layout(rect=[0.03,0.02,0.95,1])
    out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out,dpi=120)
    plt.close(fig)
    
    # %% ablation climatology
    df_meta=pd.read_csv(path_thredds+"/metadata/AWS_sites_metadata.csv").set_index("site_id")
    out=Path("figures/ablation_mosaic.png")
    
    N_COLS=4; XMIN,XMAX=120,290
    ticks=list(np.cumsum([30,31,30,31,31,29,31,30,31,30,31,31]))
    def labs(ts):
        return ["Jan." if i<30 else "Feb." if i<60 else "Mar." if i<90 else "Apr." if i<120 else "May" if i<150 else
                "Jun." if i<180 else "Jul." if i<210 else "Aug." if i<240 else "Sept." if i<270 else "Oct." if i<300 else
                "Nov." if i<330 else "Dec." if i<360 else "" for i in ts]
    
    labels=labs(ticks)
    
    stations=[]
    for s in df_meta.index:
        if s in SKIP: continue
        fp=path_new/f"{s}_day.csv"
        if not fp.exists(): continue
        d=pd.read_csv(fp,usecols=lambda c:c in["time","z_surf_combined"])
        li=d["z_surf_combined"].last_valid_index()
        if li is None or d.loc[li,"z_surf_combined"]>0: continue
        stations.append(s)
    
    n=len(stations); nrows=math.ceil(n/N_COLS)
    fig,ax=plt.subplots(nrows,N_COLS,figsize=(N_COLS*3.2,nrows*2.2),sharex=True)
    ax=np.atleast_2d(ax)
    
    handles={}
    for i, s in enumerate(tqdm(stations, desc="Plotting ablation")):
        r,c=divmod(i,N_COLS); a=ax[r,c]
        d=pd.read_csv(path_new/f"{s}_day.csv",usecols=lambda c:c in["time","z_surf_combined"])
        d["time"]=pd.to_datetime(d["time"],errors="coerce")
        d["z_surf_combined"]=pd.to_numeric(d["z_surf_combined"],errors="coerce")
        d=d.dropna(subset=["time"]).set_index("time").sort_index()
        d["z_ice_surf"]=d["z_surf_combined"].cummin()
        m=d[d.index.month.isin([6,7,8])]["z_surf_combined"].isnull().resample("YE").sum()
        for t,v in m.items():
            if v>15: d.loc[str(t.year),"z_ice_surf"]=np.nan
        for y in sorted(d.index.year.unique().tolist()):
            dy=d.loc[(d.index>=f"{y}-04-01")&(d.index<f"{y}-10-31"),["z_surf_combined","z_ice_surf"]].copy()
            if dy.empty or dy["z_surf_combined"].isnull().all(): continue
            dy["doy"]=dy.index.dayofyear
            fvi=dy["z_ice_surf"].first_valid_index()
            if fvi is None: continue
            z0=dy["z_ice_surf"].loc[slice(fvi,fvi+pd.to_timedelta("10D"))].mean()
            if y == focus_year:
                a.plot(dy["doy"],dy["z_ice_surf"]-z0,color='w',lw=3)[0]
                ln=a.plot(dy["doy"],dy["z_ice_surf"]-z0,color='k',lw=2)[0]
            else:
                ln=a.plot(dy["doy"],dy["z_ice_surf"]-z0,color=year_color[y],lw=1.2)[0]
            handles.setdefault(y,ln)
        a.set_title(s); a.grid(True); a.set_xlim(XMIN,XMAX)
    
    for j in range(n,nrows*N_COLS):
        r,c=divmod(j,N_COLS); ax[r,c].axis("off")
    
    for a in ax[-1,:]:
        if a.axison: a.set_xticks(ticks); a.set_xticklabels(labels,rotation=45,ha="right")
    
    fig.legend(handles.values(),[str(y) for y in handles.keys()],
                loc="center right",bbox_to_anchor=(0.98,0.5),title="Year",ncol=1)
    fig.text(0.01,0.5,"Snow Height (m)",va="center",rotation="vertical")
    fig.tight_layout(rect=[0.03,0.02,0.95,1])
    out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out,dpi=120)
    plt.close(fig)
    
    # %% t_u rh_u p_u wspd_u
    VARS=["t_u","rh_u","p_u","wspd_u"]  # add more here
    N_COLS=4

    def doy_ticks_labels():
        ticks=list(np.cumsum([31,28,31,30,31,30,31,31,30,31,30,31]))
        labs=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return ticks,labs
    
    def plot_var_mosaic(var, out_png):
        stations= [s for s in list(df_meta.index) if s not in SKIP]
        n=len(stations); nrows=math.ceil(n/N_COLS)
        fig,ax=plt.subplots(nrows,N_COLS,figsize=(N_COLS*3.2,nrows*2.2),sharex=True,sharey=False)
        ax=np.atleast_2d(ax)
        handles={}
    
        for i, s in enumerate(tqdm(stations, desc=f"Plotting {var} climatlogy")):
            r,c=divmod(i,N_COLS); a=ax[r,c]
            fp=path_new/f"{s}_day.csv"
            if not fp.exists(): a.axis("off"); continue
            d=pd.read_csv(fp,usecols=lambda c:c in["time",var])
            if "time" not in d.columns or var not in d.columns: a.axis("off"); continue
            d["time"]=pd.to_datetime(d["time"],errors="coerce")
            d[var]=pd.to_numeric(d[var],errors="coerce")
            d=d.dropna(subset=["time"]).set_index("time").sort_index()
            if d[var].dropna().empty: a.axis("off"); continue
    
            for y in sorted(d.index.year.unique().tolist()):
                dy=d.loc[str(y),[var]].copy()
                if dy.empty: continue
                g=dy.groupby(dy.index.dayofyear)[var].mean()
                if y == focus_year:
                    a.plot(g.index,g.values,color='w',lw=3)[0]
                    ln=a.plot(g.index,g.values,color='k',lw=2)[0]
                else:
                    ln=a.plot(g.index,g.values,color=year_color[y],lw=1.1)[0]
                handles.setdefault(y,ln)
    
            a.set_title(s)
            a.grid(True)
    
        for j in range(n,nrows*N_COLS):
            r,c=divmod(j,N_COLS); ax[r,c].axis("off")
    
        ticks,labs=doy_ticks_labels()
        for a in ax[-1,:]:
            if a.axison:
                a.set_xticks(ticks)
                a.set_xticklabels(labs,rotation=45,ha="right")
    
        handles=dict(sorted(handles.items(),reverse=True))
        fig.legend(handles.values(),[str(y) for y in handles.keys()],
                   loc="center right",bbox_to_anchor=(0.98,0.5),title="Year",ncol=1)
    
        fig.text(0.01,0.5,var,va="center",rotation="vertical")
        fig.tight_layout(rect=[0.03,0.02,0.95,1])
        out_png.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(out_png,dpi=120)
        plt.close(fig)
    
    for var in VARS:
        plot_var_mosaic(var, Path(f"figures/climatology/{var}_mosaic.png"))

    


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the script with optional parameters.")
    parser.add_argument("--path_thredds", type=str, default="../thredds-data", 
                        help="Path to thredds data")

    args = parser.parse_args()
    
    main(path_thredds=args.path_thredds)
