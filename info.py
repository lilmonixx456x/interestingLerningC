#!/usr/bin/env python3
# sysinfo.py
# Cross-platform system info collector
# Usage:
#   python3 sysinfo.py            -> print pretty output
#   python3 sysinfo.py -j out.json -> save JSON to out.json
#   python3 sysinfo.py --short    -> shorter output

import os
import sys
import json
import platform
import argparse
import shutil
import subprocess
import datetime
from collections import OrderedDict

# Optional imports
try:
    import psutil
except Exception:
    psutil = None

try:
    import cpuinfo
except Exception:
    cpuinfo = None

try:
    import GPUtil
except Exception:
    GPUtil = None

try:
    import distro  # better Linux distro info
except Exception:
    distro = None

# Helper functions
def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, universal_newlines=True, timeout=10)
        return out.strip()
    except Exception as e:
        return f"<error: {e}>"

def safe_get(obj, attr, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default

def bytes2human(n):
    # human readable bytes
    symbols = ('B','KB','MB','GB','TB','PB')
    i = 0
    while n >= 1024 and i < len(symbols)-1:
        n /= 1024.0
        i += 1
    return f"{n:.2f} {symbols[i]}"

def collect_basic():
    info = OrderedDict()
    info['timestamp'] = datetime.datetime.utcnow().isoformat() + "Z"
    info['platform'] = platform.platform()
    info['system'] = platform.system()
    info['node'] = platform.node()
    info['release'] = platform.release()
    info['version'] = platform.version()
    info['machine'] = platform.machine()
    info['processor'] = platform.processor()
    # Python
    info['python'] = {
        'implementation': platform.python_implementation(),
        'version': platform.python_version(),
        'executable': sys.executable
    }
    if info['system'] == 'Linux':
        info['distro'] = distro.name(pretty=True) if distro else run_cmd("lsb_release -a") or run_cmd("cat /etc/os-release")
    elif info['system'] == 'Darwin':
        info['macos'] = run_cmd("sw_vers")
    elif info['system'] == 'Windows':
        info['windows_ver'] = platform.win32_ver()
    return info

def collect_cpu():
    cpu = OrderedDict()
    try:
        if cpuinfo:
            ci = cpuinfo.get_cpu_info()
            cpu['brand_raw'] = ci.get('brand_raw')
            cpu['arch'] = ci.get('arch')
            cpu['bits'] = ci.get('bits')
            cpu['count_logical'] = psutil.cpu_count(logical=True) if psutil else os.cpu_count()
            cpu['count_physical'] = psutil.cpu_count(logical=False) if psutil else None
            cpu['hz_advertised'] = ci.get('hz_advertised_friendly')
            cpu['hz_actual'] = ci.get('hz_actual_friendly')
            cpu['flags'] = ci.get('flags')
        else:
            cpu['count_logical'] = psutil.cpu_count(logical=True) if psutil else os.cpu_count()
            cpu['count_physical'] = psutil.cpu_count(logical=False) if psutil else None
            cpu['freq'] = safe_get(psutil, 'cpu_freq', lambda: None)() if psutil and hasattr(psutil, 'cpu_freq') else None
            cpu['brand_raw'] = platform.processor()
    except Exception as e:
        cpu['error'] = str(e)
    # load / usage
    try:
        if psutil:
            cpu['usage_percent_per_core'] = psutil.cpu_percent(interval=0.5, percpu=True)
            cpu['usage_percent'] = psutil.cpu_percent(interval=0.2)
            cpu['load_avg'] = os.getloadavg() if hasattr(os, 'getloadavg') else None
    except Exception:
        pass
    return cpu

def collect_memory():
    mem = OrderedDict()
    try:
        if psutil:
            svmem = psutil.virtual_memory()
            mem['total'] = svmem.total
            mem['available'] = svmem.available
            mem['used'] = svmem.used
            mem['percent'] = svmem.percent
        # swap
        if psutil:
            ss = psutil.swap_memory()
            mem['swap_total'] = ss.total
            mem['swap_used'] = ss.used
            mem['swap_percent'] = ss.percent
    except Exception as e:
        mem['error'] = str(e)
    return mem

def collect_disks():
    disks = OrderedDict()
    parts = []
    try:
        if psutil:
            for p in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                except Exception:
                    usage = None
                parts.append({
                    'device': p.device,
                    'mountpoint': p.mountpoint,
                    'fstype': p.fstype,
                    'opts': p.opts,
                    'usage': {
                        'total': usage.total if usage else None,
                        'used': usage.used if usage else None,
                        'free': usage.free if usage else None,
                        'percent': usage.percent if usage else None
                    }
                })
    except Exception as e:
        parts.append({'error': str(e)})
    # overall disk usage of root
    try:
        total, used, free = shutil.disk_usage('/')
        disks['root_total'] = total
        disks['root_used'] = used
        disks['root_free'] = free
    except Exception:
        pass
    disks['partitions'] = parts
    return disks

def collect_network():
    net = OrderedDict()
    try:
        if psutil:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            net_if = {}
            for ifname, addrlist in addrs.items():
                addrs_info = []
                for a in addrlist:
                    addrs_info.append({
                        'family': str(a.family),
                        'address': a.address,
                        'netmask': a.netmask,
                        'broadcast': a.broadcast
                    })
                net_if[ifname] = {
                    'addrs': addrs_info,
                    'isup': stats[ifname].isup if ifname in stats else None,
                    'speed_mbps': stats[ifname].speed if ifname in stats else None
                }
            net['interfaces'] = net_if
            # connections
            try:
                net['connections'] = [dict(conn._asdict()) for conn in psutil.net_connections()[:50]]
            except Exception:
                pass
    except Exception as e:
        net['error'] = str(e)
    # public IP (best-effort, no external requests)
    # don't call external services (no network) — user can run `curl ifconfig.me` if needed
    return net

def collect_processes(limit=30):
    procs = []
    try:
        if psutil:
            for p in psutil.process_iter(['pid','name','username','cpu_percent','memory_percent','exe','cmdline']):
                try:
                    procs.append(p.info)
                except Exception:
                    pass
            # sort by memory usage
            procs = sorted(procs, key=lambda x: x.get('memory_percent') or 0, reverse=True)[:limit]
    except Exception as e:
        return {'error': str(e)}
    return procs

def collect_gpu():
    g = []
    try:
        if GPUtil:
            GPUs = GPUtil.getGPUs()
            for gpu in GPUs:
                g.append({
                    'id': gpu.id,
                    'name': gpu.name,
                    'load': gpu.load,
                    'memoryTotal': gpu.memoryTotal,
                    'memoryUsed': gpu.memoryUsed,
                    'memoryFree': gpu.memoryFree,
                    'temperature': getattr(gpu, 'temperature', None)
                })
        else:
            # platform-specific probes
            if platform.system() == 'Darwin':
                gtxt = run_cmd("system_profiler SPDisplaysDataType -json")
                g.append({'system_profiler_SPDisplaysDataType': gtxt})
            elif platform.system() == 'Linux':
                gtxt = run_cmd("lspci | grep -i --color 'vga\\|3d\\|display' || true")
                g.append({'lspci': gtxt})
            elif platform.system() == 'Windows':
                gtxt = run_cmd("wmic path win32_VideoController get name,driverversion")
                g.append({'wmic': gtxt})
    except Exception as e:
        g.append({'error': str(e)})
    return g

def collect_battery():
    bat = {}
    try:
        if psutil and hasattr(psutil, "sensors_battery"):
            sb = psutil.sensors_battery()
            if sb:
                bat['percent'] = sb.percent
                bat['secsleft'] = sb.secsleft
                bat['power_plugged'] = sb.power_plugged
    except Exception as e:
        bat['error'] = str(e)
    return bat

def collect_installed_packages(limit=200):
    pkgs = {}
    try:
        # Python packages (pip)
        pip_list = run_cmd(f"{sys.executable} -m pip list --format=json")
        try:
            pip_json = json.loads(pip_list)
            pkgs['python_pip'] = pip_json[:limit]
        except Exception:
            pkgs['python_pip_raw'] = pip_list
        # OS packages: best-effort (apt/dpkg/rpm/brew/choco)
        if platform.system() == 'Linux':
            apt = run_cmd("apt list --installed 2>/dev/null | head -n 200")
            pkgs['os_packages_sample'] = apt
        elif platform.system() == 'Darwin':
            brew = run_cmd("brew list --versions 2>/dev/null | head -n 200")
            pkgs['os_packages_sample'] = brew
        elif platform.system() == 'Windows':
            choco = run_cmd("choco list --local-only 2>null | head -n 200")
            pkgs['os_packages_sample'] = choco
    except Exception as e:
        pkgs['error'] = str(e)
    return pkgs

def collect_misc():
    misc = OrderedDict()
    # mounted filesystems
    misc['mounts'] = run_cmd("mount") if platform.system() != 'Windows' else run_cmd("wmic logicaldisk get name,description")
    # system logs (tail)
    if platform.system() == 'Darwin':
        misc['system_profiler'] = run_cmd("system_profiler -detailLevel mini")
    elif platform.system() == 'Linux':
        misc['uname'] = run_cmd("uname -a")
    elif platform.system() == 'Windows':
        misc['systeminfo'] = run_cmd("systeminfo")
    return misc

def collect_all(short=False):
    data = OrderedDict()
    data['basic'] = collect_basic()
    data['cpu'] = collect_cpu()
    data['memory'] = collect_memory()
    data['disks'] = collect_disks()
    data['network'] = collect_network()
    data['processes'] = collect_processes(limit=10 if short else 50)
    data['gpu'] = collect_gpu()
    data['battery'] = collect_battery()
    data['installed'] = collect_installed_packages(limit=50 if short else 300)
    data['misc'] = collect_misc()
    return data

def pretty_print(data, indent=0):
    # concise pretty printer
    def pp(obj, lvl=0):
        pad = "  " * lvl
        if isinstance(obj, dict):
            for k,v in obj.items():
                if isinstance(v, (dict, list)):
                    print(f"{pad}{k}:")
                    pp(v, lvl+1)
                else:
                    if isinstance(v, int) and ('total' in k or 'size' in k or 'free' in k):
                        try:
                            print(f"{pad}{k}: {bytes2human(v)}")
                        except Exception:
                            print(f"{pad}{k}: {v}")
                    else:
                        print(f"{pad}{k}: {v}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    print(f"{pad}- item {i}:")
                    pp(item, lvl+1)
                else:
                    print(f"{pad}- {item}")
        else:
            print(f"{pad}{obj}")
    pp(data, indent)

def main():
    parser = argparse.ArgumentParser(description="Collect detailed system information (cross-platform).")
    parser.add_argument("-j", "--json", help="Write JSON output to file")
    parser.add_argument("--short", action="store_true", help="Shorter output")
    args = parser.parse_args()

    missing = []
    for lib in [('psutil', psutil), ('cpuinfo', cpuinfo), ('GPUtil', GPUtil), ('distro', distro)]:
        if lib[1] is None:
            missing.append(lib[0])
    if missing:
        print("Note: Some optional libs are missing: " + ", ".join(missing))
        print("To install them for richer output run:")
        print(f"  {sys.executable} -m pip install psutil py-cpuinfo GPUtil distro\n")

    data = collect_all(short=args.short)

    if args.json:
        try:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Wrote JSON to {args.json}")
        except Exception as e:
            print("Error writing JSON:", e)

    # pretty print to console (trim heavy fields)
    # Trim processes commandlines for readability
    if 'processes' in data and isinstance(data['processes'], list):
        for p in data['processes']:
            if isinstance(p, dict) and 'cmdline' in p:
                try:
                    p['cmdline'] = " ".join(p['cmdline'])[:200]
                except Exception:
                    pass

    pretty_print(data)

if __name__ == "__main__":
    main()
