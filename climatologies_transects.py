# -*- coding: utf-8 -*-
"""
@author: bav@geus.dk

tip list:
    %matplotlib inline
    %matplotlib qt
    import pdb; pdb.set_trace()
"""


import matplotlib
# matplotlib.use("Agg")
import matplotlib.patheffects as pe
import math
from pathlib import Path
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from tqdm import tqdm
import geopandas as gpd
import matplotlib.image as mpimg

SKIP = ["NUK_P", "NUK_B", "SER_B", "UWN", "ORO", "NUK_N", "QAS_A", "TAS_U"]
mm_to_pt = 72 / 25.4
r_pt = 8 * mm_to_pt

CLOCK_OFFSETS_PT = {
    1: [(r_pt, 0)],
    2: [(-0.9 * r_pt, 0.5 * r_pt), (0.9 * r_pt, 0.5 * r_pt)],
    3: [(-0.9 * r_pt, 0.5 * r_pt), (0.9 * r_pt, 0.5 * r_pt), (0, -r_pt)],
}

def hydrological_doy(index):
    doy = index.dayofyear.values - 244
    doy[doy < 0] += 365
    return doy


def snow_accum_transform(d, focus_year):
    out = {}
    for y in sorted(d.index.year.unique()):
        start = pd.Timestamp(f"{y-1}-09-01")
        end = pd.Timestamp(f"{y}-08-31")
        dy = d.loc[(d.index >= start) & (d.index < end), ["snow_height"]].copy()
        if dy.empty or dy["snow_height"].isnull().all():
            continue
        dy["x"] = hydrological_doy(dy.index)
        fvi = dy["snow_height"].first_valid_index()
        if fvi is None:
            continue
        ref = dy["snow_height"].loc[slice(fvi, fvi + pd.Timedelta("30D"))].min()
        dy["y"] = dy["snow_height"] - ref
        out[y] = dy[["x", "y"]].dropna()
    return out


def ablation_transform(d, focus_year):
    out = {}
    d = d.copy()
    d["z_ice_surf"] = d["z_surf_combined"].cummin()

    m = (
        d[d.index.month.isin([6, 7, 8])]["z_surf_combined"]
        .isnull()
        .resample("YE")
        .sum()
    )
    for t, v in m.items():
        if v > 15:
            d.loc[str(t.year), "z_ice_surf"] = np.nan

    for y in sorted(d.index.year.unique()):
        dy = d.loc[
            (d.index >= f"{y}-04-01") & (d.index < f"{y}-10-31"),
            ["z_ice_surf"],
        ].copy()
        if dy.empty or dy["z_ice_surf"].isnull().all():
            continue
        dy["x"] = dy.index.dayofyear
        fvi = dy["z_ice_surf"].first_valid_index()
        if fvi is None:
            continue
        z0 = dy["z_ice_surf"].loc[slice(fvi, fvi + pd.Timedelta("10D"))].mean()
        dy["y"] = dy["z_ice_surf"] - z0
        out[y] = dy[["x", "y"]].dropna()
    return out


def weather_transform(d, var, focus_year):
    out = {}
    for y in sorted(d.index.year.unique()):
        dy = d.loc[str(y), [var]].copy()
        if dy.empty or dy[var].isnull().all():
            continue
        g = dy.groupby(dy.index.dayofyear)[var].mean()
        out[y] = pd.DataFrame({"x": g.index.values, "y": g.values})
    return out


def default_style():
    return { "grid": True, "xlim": None, "ylim": None, "ylabel": "",
        "ticks": None, "ticklabels": None, "rotation": 45 }


def snow_style():
    ticks = list(np.cumsum([30, 31, 30, 31, 31, 29, 31, 30, 31, 30, 31, 31]))
    labels = [
        "Sept." if i < 30 else "Oct." if i < 60 else "Nov." if i < 90 else
        "Dec." if i < 120 else  "Jan." if i < 150 else  "Feb." if i < 180 else
        "Mar." if i < 210 else "Apr." if i < 240 else "May" if i < 270 else
        "Jun." if i < 300 else "Jul." if i < 330 else "Aug." if i < 360 else ""
        for i in ticks
    ]
    s = default_style()
    s.update( { "xlim": (1, 365), "ylim": (0, None), "ylabel": "Snow height (m)",
            "ticks": ticks, "ticklabels": labels, } )
    return s


def ablation_style():
    ticks = list(np.cumsum([30, 31, 30, 31, 31, 29, 31, 30, 31, 30, 31, 31]))
    labels = [
        "Jan." if i < 30 else "Feb." if i < 60 else "Mar." if i < 90 else
        "Apr." if i < 120 else "May" if i < 150 else "Jun." if i < 180 else
        "Jul." if i < 210 else "Aug." if i < 240 else "Sept." if i < 270 else
        "Oct." if i < 300 else "Nov." if i < 330 else "Dec." if i < 360 else ""
        for i in ticks
    ]
    s = default_style()
    s.update(
        {
            "xlim": (120, 290),
            "ylabel": "Ablation (m)",
            "ticks": ticks,
            "ticklabels": labels,
        }
    )
    return s


def weather_style(var):
    ticks = list(np.cumsum([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]))
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    s = default_style()
    label = {'t_u':'Air temperature (°C)',
             'p_u':'Air pressure (hPa)',
             'wspd_u':'Wind speed (m/s)',
             'rh_u': 'Relative humidity (%)',
             't_surf': 'Surface temperature (°C)'
             }
    s.update(  { "xlim": (1, 366),  "ylabel": label[var], "ticks": ticks, 
                "ticklabels": labels })
    return s


def read_station_csv(path_csv, usecols):
    d = pd.read_csv(path_csv, usecols=lambda c: c in usecols)
    if "time" not in d.columns:
        return None
    d["time"] = pd.to_datetime(d["time"], errors="coerce")
    for c in d.columns:
        if c != "time":
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["time"]).set_index("time").sort_index()
    return d


def prepare_series(path_csv, kind, focus_year, var=None):
    if kind == "snow":
        d = read_station_csv(path_csv, ["time", "snow_height", "z_surf_combined"])
        if d is None:
            return {}
        if "snow_height" not in d.columns and "z_surf_combined" in d.columns:
            d["snow_height"] = d["z_surf_combined"]
        if "snow_height" not in d.columns:
            return {}
        return snow_accum_transform(d[["snow_height"]], focus_year)

    if kind == "ablation":
        d = read_station_csv(path_csv, ["time", "z_surf_combined"])
        if d is None or "z_surf_combined" not in d.columns:
            return {}
        return ablation_transform(d[["z_surf_combined"]], focus_year)

    if kind == "weather":
        d = read_station_csv(path_csv, ["time", var])
        if d is None or var not in d.columns:
            return {}
        return weather_transform(d[[var]], var, focus_year)

    raise ValueError(f"Unknown kind: {kind}")


def plot_station_panel(ax, series_by_year, title, year_color, focus_year, style):
    handles = {}
    if not series_by_year:
        ax.axis("off")
        return handles
    # stop = 0
    # for y, dy in sorted(series_by_year.items()):
    #     if dy.empty:
    #         continue
    #     if y == focus_year:
    #         ax.plot(dy["x"], dy["y"], color="w", lw=3, zorder=3)
    #         ln = ax.plot(dy["x"], dy["y"], color="k", lw=2, zorder=4)[0]
    #     else:
    #         ln = ax.plot(dy["x"], dy["y"], color=year_color.get(y, "0.7"), lw=1.2, zorder=2)[0]
    #     handles.setdefault(y, ln)
    for y, dy in sorted(series_by_year.items()):
        if dy.empty:
            continue
        if y == focus_year:
            ax.plot(dy["x"], dy["y"], color="w", lw=3, zorder=3)
            ax.plot(dy["x"], dy["y"], color="#111145", lw=2, zorder=4, label = str(y))[0]
        else:
            ax.plot(dy["x"], dy["y"], color='#7ec1dc', lw=1, zorder=2)[0]
    yrs = np.array([n for n in series_by_year.keys() if n!=focus_year])
    ax.plot(np.nan, np.nan,color='#7ec1dc', lw=1.2, zorder=2, 
         label = f'{np.min(yrs)} - {np.max(yrs)}')
    
    ax.legend(loc='lower right', fontsize=8)

    ax.set_title(title)
    if style["grid"]:
        ax.grid(True)
    if style["xlim"] is not None:
        ax.set_xlim(*style["xlim"])
    if style["ylim"] is not None:
        ax.set_ylim(*style["ylim"])

    return handles


def add_shared_legend(fig, handles, anchor=(0.98, 0.5)):
    if not handles:
        return
    handles = dict(sorted(handles.items(), reverse=True))
    fig.legend(
        handles.values(),
        [str(y) for y in handles.keys()],
        loc="center right",
        bbox_to_anchor=anchor,
        title="Year",
        ncol=1,
    )


def write_plot_gallery_markdown(
    station_groups,
    out_dir="./plot_compilations",
    filename="plot_gallery.md",
    kinds=("snow_height", "t_u"),
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / filename

    lines = ["# PROMICE / GC-Net plot compilation", ""]

    for kind in kinds:
        lines.append(f"## {kind.replace('_', ' ').title()}")
        lines.append("")

        for stations in station_groups:
            img_name = f"{kind}_{'_'.join(stations)}.png"
            lines.append(f"### {' – '.join(stations)}")
            lines.append("")
            lines.append(f"![{img_name}](../figures/climatology/{img_name})")
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {md_path}")


def load_station_points(path_meta):
    meta = pd.read_csv(path_meta)
    cols = {c.lower(): c for c in meta.columns}

    site_col = cols.get("site_id", cols.get("stid", cols.get("station", None)))
    lat_col = cols.get("latitude_last_valid", cols.get("lat", None))
    lon_col = cols.get("longitude_last_valid", cols.get("lon", None))

    if site_col is None or lat_col is None or lon_col is None:
        raise ValueError("Metadata file must contain site_id/stid and latitude/longitude columns")

    meta = meta[[site_col, lat_col, lon_col]].rename(
        columns={site_col: "site_id", lat_col: "latitude", lon_col: "longitude"}
    )
    meta = meta.dropna(subset=["site_id", "latitude", "longitude"])
    gdf = gpd.GeoDataFrame(
        meta,
        geometry=gpd.points_from_xy(meta["longitude"], meta["latitude"]),
        crs=4326,
    ).to_crs(3413)
    return gdf.set_index("site_id")


def plot_group_map(ax, greenland_gdf, ice_gdf, station_points, stations):
    if greenland_gdf is not None:
        greenland_gdf.plot(ax=ax, color="0.85", edgecolor="0.35", linewidth=0.5)
    if ice_gdf is not None:
        ice_gdf.plot(ax=ax, color="white", edgecolor="0.5", linewidth=0.5)

    pts = station_points.loc[station_points.index.intersection(stations)].copy()
    
    if not pts.empty:
        pts.plot(ax=ax, markersize=30, zorder=4, color='#b3e0f3')
        pts.plot(ax=ax, markersize=25, zorder=5, color='#111145')
    
        offsets = CLOCK_OFFSETS_PT.get(len(pts), [(r_pt, 0)] * len(pts))
    
        for (name, row), (dx, dy) in zip(pts.iterrows(), offsets):
            ax.annotate(
                name,
                xy=(row.geometry.x, row.geometry.y),
                xytext=(dx, dy),
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=11,
                arrowprops=dict(arrowstyle="-", lw=0.5, color="0.4"),
                path_effects=[pe.withStroke(linewidth=3, foreground="white")],
            )

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def plot_grouped_mosaic(
    station_groups,
    path_csv_dir,
    out_png,
    kind,
    focus_year=2026,
    var=None,
    path_meta=None,
    path_greenland=None,
    path_ice=None,
):
    years = np.arange(1990, 2027)
    cmap = plt.get_cmap("tab20", len(years))
    year_color = {y: cmap(i) for i, y in enumerate(years)}

    if kind == "snow":
        style = snow_style()
    elif kind == "ablation":
        style = ablation_style()
    elif kind == "weather":
        style = weather_style(var)
    else:
        raise ValueError(kind)

    station_points = load_station_points(path_meta) if path_meta else None
    greenland_gdf = gpd.read_file(path_greenland).to_crs(3413) if path_greenland else None
    ice_gdf = gpd.read_file(path_ice).to_crs(3413) if path_ice else None

    for ig, stations in enumerate(station_groups):
        n_groups = len(stations)
    
        fig = plt.figure(figsize=(7, 3 * 1.7))
        # replace GridSpec definition
        gs = GridSpec(
            nrows=n_groups,
            ncols=2,
            figure=fig,
            width_ratios=[3, 1],  # plot | legend | map
            wspace=0.2,
            hspace=0.35,
            left=0.1,   # left margin as fraction of figure width
        )
    
        all_handles = {}
        group_start = ig * n_groups

        # legend_ax = fig.add_subplot(gs[0:n_groups, 1])
        map_ax = fig.add_subplot(gs[0:n_groups, 1])
        if station_points is not None:
            plot_group_map(map_ax, greenland_gdf, ice_gdf, station_points, stations)
        else:
            map_ax.axis("off")

        for ir, st in enumerate(stations):
            ax = fig.add_subplot(gs[ir, 0])
            path_csv = Path(path_csv_dir) / f"{st}_day.csv"
            if not path_csv.exists() or st in SKIP:
                ax.axis("off")
                continue

            series_by_year = prepare_series(path_csv, kind=kind, focus_year=focus_year, var=var)
            handles = plot_station_panel(
                ax=ax,
                series_by_year=series_by_year,
                title=st,
                year_color=year_color,
                focus_year=focus_year,
                style=style,
            )
            all_handles.update(handles)

            if ir < len(stations) - 1:
                ax.set_xticklabels([])
            else:
                ax.set_xticks(style["ticks"])
                ax.set_xticklabels(style["ticklabels"], rotation=style["rotation"], ha="right")

        # add after plotting all station panels in the group
        # legend_ax.axis("off")
        # if all_handles:
        #     hh = dict(sorted(all_handles.items(), reverse=True))
        #     legend_ax.legend(
        #         hh.values(),
        #         [str(y) for y in hh.keys()],
        #         loc="center",
        #         frameon=False,
        #         title="Year",
        #     )
        
        fig.text(0.02, 0.5, style["ylabel"], va="center", rotation="vertical")
        
        bbox = map_ax.get_position()   # figure coordinates
        logo_width = 0.3
        logo_height = logo_width *0.65  # adjust depending on logo aspect ratio
        logo_left = bbox.x0-0.04
        logo_bottom = bbox.y0 - 0.15
        
        logo = mpimg.imread("figures/Promice_GC-Net_colour.png")
        
        logo_ax = fig.add_axes([logo_left, logo_bottom, logo_width, logo_height])
        logo_ax.imshow(logo)
        logo_ax.axis("off")
        logo_ax.set_aspect("auto")
    
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_png+'_'.join(stations)+'.png', dpi=120, bbox_inches="tight")
        print('Saved : '+out_png+'_'.join(stations)+'.png')


# example
def main(path_thredds):
    path_csv_dir = Path(path_thredds) / "level_3_sites/csv/day"
    path_meta = Path(path_thredds) / "metadata/AWS_sites_metadata.csv"

    station_groups = [
        ["KAN_T", "KAN_L", "KAN_M", "KAN_U"],
        ["QAS_L", "QAS_M", "QAS_U"],
        ["SCO_L", "SCO_U"],
        ["KPC_L", "KPC_U"],
        ["JAR", "SWC"],
        ["TAS_L", "TAS_A"],
        ["THU_L", "THU_U"],
        ["NUK_L", "NUK_U"],
        ["UPE_L", "UPE_U"],
        ["ZAC_L", "ZAC_U", "ZAC_A"],
    ]

    path_greenland = "GIS/Land_3413.shp"
    path_ice = "GIS/Greenland_ice_shape.shp"

    plot_grouped_mosaic(
        station_groups=station_groups,
        path_csv_dir=path_csv_dir,
        out_png="figures/climatology/snow_height_",
        kind="snow",
        focus_year=2026,
        path_meta=path_meta,
        path_greenland=path_greenland,
        path_ice=path_ice,
    )

    # plot_grouped_mosaic(
    #     station_groups=station_groups,
    #     path_csv_dir=path_csv_dir,
    #     out_png="figures/ablation",
    #     kind="ablation",
    #     focus_year=2026,
    #     path_meta=path_meta,
    #     path_greenland=path_greenland,
    #     path_ice=path_ice,
    # )

    for var in ["t_u", "t_surf"]: #, "p_u", "wspd_u"]:
        plot_grouped_mosaic(
            station_groups=station_groups,
            path_csv_dir=path_csv_dir,
            out_png=f"figures/climatology/{var}_",
            kind="weather",
            var=var,
            focus_year=2026,
            path_meta=path_meta,
            path_greenland=path_greenland,
            path_ice=path_ice,
        )
    
    write_plot_gallery_markdown(
        station_groups=station_groups,
        out_dir="./plot_compilations",
        filename="all_station_plots.md",
        kinds=["snow_height", "t_u", "t_surf"],
    )
        



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the script with optional parameters.")
    parser.add_argument("--path_thredds", type=str, default="../thredds-data", 
                        help="Path to thredds data")

    args = parser.parse_args()
    
    main(path_thredds=args.path_thredds)
