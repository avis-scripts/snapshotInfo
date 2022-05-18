import atexit, getpass, os, time, webbrowser, numpy, pandas
from pyVim.connect import Disconnect, SmartConnectNoSSL
from pyVmomi import vim

global service_instance


def get_child_snapshots(snapshot):
    results = []
    snapshots = snapshot.childSnapshotList
    for snapshot in snapshots:
        results.append(snapshot)
        results += get_child_snapshots(snapshot)
    return results


def get_all_vm_snapshots(vm):
    results = []
    try:
        root_snapshots = vm.snapshot.rootSnapshotList
    except:
        root_snapshots = []
    for snapshot in root_snapshots:
        results.append(snapshot)
        results += get_child_snapshots(snapshot)
    return results


def output(filename):
    file_csv = f"csv/{filename}.csv"
    file_html = f"html/{filename}.html"
    file_data = pandas.read_csv(rf'{file_csv}', index_col=False)
    html = file_data.to_html()
    file_path = os.path.abspath(file_html)
    url = 'file://' + file_path
    with open(file_path, 'w') as f:
        f.write(html)
    webbrowser.open(url)


vcenter = input("Enter vCenter IP or FQDN: ")
user = input("Enter vCenter user name [default administrator@vsphere.local]: ")
user = user or "administrator@vsphere.local"
password = getpass.getpass(f"Enter password for {user} on {vcenter}: ")
port = 443

start_time = time.time()

try:
    service_instance = SmartConnectNoSSL(host=vcenter, user=user, pwd=password, port=port)
    atexit.register(Disconnect, service_instance)
except IOError as io_error:
    print(io_error)
    raise SystemExit("Unable to connect to vCenter")
except:
    raise SystemExit("Unable to connect to vCenter")

content = service_instance.RetrieveContent()
container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
print(f"There are {len(container.view)} virtual machines on vCenter: {vcenter}")

vms_in_vc = []
for i in range(0, len(container.view)):
    summary = container.view[i].summary
    name = summary.config.name
    moid = summary.vm
    vms_in_vc.append({"Name": name, "moid": moid})
all_vms = pandas.DataFrame(vms_in_vc)

input_vm_data = pandas.read_csv("input/input_vms.csv", index_col=False)

found_vms = input_vm_data.merge(all_vms)
found_vms.to_csv("csv/found_vms.csv", index=False)
merged_list = found_vms.to_dict("records")

mask = input_vm_data.isin(all_vms.to_dict(orient='list'))
missing = input_vm_data[~mask].dropna()
missing.to_csv("csv/missing.csv", index=False)

all_found_vms = []
for i in merged_list:
    summary = i["moid"].summary
    moid = str(i["moid"]).replace('vim.VirtualMachine:', '').strip("\'")
    name = summary.config.name
    power_state = i["moid"].runtime.powerState.replace("powered", "")
    path = summary.config.vmPathName
    guest_os = summary.config.guestFullName
    snpshot = ""
    snapshots = get_all_vm_snapshots(i["moid"])
    for snapshot in snapshots:
        snpshot += snapshot.name + ". "
    all_found_vms.append({"Name": name, "VM MOID": moid, "Path": path, "Guest": guest_os, "Power State": power_state,
                          "Snapshot": snpshot.replace("%252f", "/")})

df = pandas.DataFrame(all_found_vms)
df.to_csv("csv/found_vms_details.csv", index=False)
df = pandas.read_csv("csv/found_vms_details.csv", index_col=False)

df = df.replace(numpy.nan, "No Snapshot")
df.to_csv("csv/found_vms_details.csv", index=False)
no_snaps = df[df['Snapshot'].str.contains('No Snapshot', regex=False)]
has_snaps = df[~df['Snapshot'].str.contains('No Snapshot', regex=False)]
no_snaps.to_csv("csv/no_snaps.csv", index=False)
has_snaps.to_csv("csv/has_snaps.csv", index=False)

output("found_vms_details")
output("no_snaps")
output("has_snaps")
output("missing")
end_time = time.time()
time_taken = round(abs(start_time - end_time), 2)
print(f"Done!! Check csv and html files for output. Script completed in {time_taken} seconds.")
