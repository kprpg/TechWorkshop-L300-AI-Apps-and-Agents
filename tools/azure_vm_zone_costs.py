import argparse
import requests
import sys
from typing import Dict, List, Optional, Tuple


API_BASE = "https://prices.azure.com/api/retail/prices"


def fetch_prices(filter_expr: str, currency: str = "USD") -> List[Dict]:
    """Fetch all records from Azure Retail Prices API for the given filter.

    Handles pagination via NextPageLink and returns a combined list.
    """
    results: List[Dict] = []
    next_link: Optional[str] = None
    while True:
        if next_link:
            resp = requests.get(next_link, timeout=60)
        else:
            params = {
                "currencyCode": currency,
                "$filter": filter_expr,
            }
            resp = requests.get(API_BASE, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])
        results.extend(items)
        next_link = data.get("NextPageLink")
        if not next_link:
            break
    return results


def select_vm_price(records: List[Dict], windows: bool = True) -> Optional[Dict]:
    """Select the best matching VM price record.

    - Prefer type == Consumption, unitOfMeasure contains 'Hour'
    - For Windows, require 'Windows' in productName
    - Exclude Spot/Low Priority meters
    """
    def is_match(r: Dict) -> bool:
        if r.get("type") != "Consumption":
            return False
        uom = (r.get("unitOfMeasure") or "").lower()
        if "hour" not in uom:
            return False
        pname = (r.get("productName") or "")
        sname = (r.get("skuName") or "")
        mname = (r.get("meterName") or "")
        if windows and "Windows" not in pname:
            return False
        # Exclude Spot/Low Priority
        ex = "spot" in sname.lower() or "spot" in mname.lower() or "low priority" in mname.lower()
        if ex:
            return False
        return True

    matches = [r for r in records if is_match(r)]
    if not matches:
        return None
    # If multiple, pick the one with highest retailPrice to avoid dev/test or weird meters
    matches.sort(key=lambda r: r.get("retailPrice") or 0.0, reverse=True)
    return matches[0]


def select_disk_price(records: List[Dict], redundancy: str) -> Optional[Dict]:
    """Select managed disk monthly price record for the requested redundancy.

    redundancy: 'lrs' or 'zrs'
    Prefer Consumption, unitOfMeasure contains 'Month', productName contains 'Premium SSD Managed Disks'.
    """
    redundancy = redundancy.lower()
    def is_match(r: Dict) -> bool:
        if r.get("type") != "Consumption":
            return False
        uom = (r.get("unitOfMeasure") or "").lower()
        if "month" not in uom:
            return False
        pname = (r.get("productName") or "")
        mname = (r.get("meterName") or "")
        if "Premium SSD Managed Disks" not in pname:
            return False
        if redundancy == "lrs" and "lrs" in mname.lower():
            return True
        if redundancy == "zrs" and "zrs" in mname.lower():
            return True
        return False

    matches = [r for r in records if is_match(r)]
    if not matches:
        return None
    # Expect one. If multiple, pick the highest price to be conservative.
    matches.sort(key=lambda r: r.get("retailPrice") or 0.0, reverse=True)
    return matches[0]


def find_interzone_bandwidth_rate(region: str, currency: str = "USD") -> Optional[Dict]:
    """Attempt to find the inter-zone data transfer price (per GB) for a region.

    This uses heuristics because naming varies. It searches Networking/Bandwidth meters that
    include 'Zone' and 'GB' in unit.
    """
    filters = [
        f"serviceFamily eq 'Networking' and armRegionName eq '{region}' and priceType eq 'Consumption'",
        f"serviceName eq 'Bandwidth' and armRegionName eq '{region}' and priceType eq 'Consumption'",
    ]
    for f in filters:
        recs = fetch_prices(f, currency)
        candidates = []
        for r in recs:
            uom = (r.get("unitOfMeasure") or "").lower()
            pname = (r.get("productName") or "").lower()
            mname = (r.get("meterName") or "").lower()
            if "gb" not in uom:
                continue
            if "bandwidth" not in pname:
                continue
            if "zone" in mname or "inter-zone" in mname or "inter zone" in mname:
                candidates.append(r)
        if candidates:
            candidates.sort(key=lambda r: r.get("retailPrice") or 0.0)
            return candidates[0]
    return None


def get_vm_hourly_price(region: str, vm_size: str, windows: bool, currency: str) -> Optional[Dict]:
    # Broad fetch for all consumption VM meters in region; then filter in Python.
    f = (
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' and priceType eq 'Consumption'"
    )
    recs = fetch_prices(f, currency)
    # Narrow down to desired size variants.
    target_lower = vm_size.lower().replace("standard_", "").strip()
    filtered = [r for r in recs if target_lower in (r.get("skuName","" ).lower()) or target_lower in (r.get("armSkuName","" ).lower())]
    if not filtered:
        return None
    return select_vm_price(filtered, windows=windows)


def get_disk_monthly_price(region: str, disk_sku: str, redundancy: str, currency: str) -> Optional[Dict]:
    # Query storage family for this disk SKU (e.g., P10)
    f = (
        f"serviceFamily eq 'Storage' and armRegionName eq '{region}' and priceType eq 'Consumption' and "
        f"skuName eq '{disk_sku.upper()}'"
    )
    recs = fetch_prices(f, currency)
    return select_disk_price(recs, redundancy)


def compute_primary_costs(region: str, vm_size: str, windows: bool, instances: int,
                          disk_sku: str, disk_redundancy: str, currency: str,
                          interzone_gb: float) -> Tuple[float, Dict]:
    details: Dict[str, float] = {}
    total = 0.0

    vm = get_vm_hourly_price(region, vm_size, windows, currency)
    if vm is None:
        raise RuntimeError(f"Could not find VM price for {vm_size} in {region} (windows={windows}).")
    vm_month = instances * 730 * (vm.get("retailPrice") or 0.0)
    details["compute_vm_month"] = vm_month
    total += vm_month

    disk = get_disk_monthly_price(region, disk_sku, disk_redundancy, currency)
    if disk is None:
        raise RuntimeError(f"Could not find disk price for {disk_sku} {disk_redundancy.upper()} in {region}.")
    # Managed disks are priced per-disk per-month (capacity tier), so just multiply by instance count.
    disk_month = instances * (disk.get("retailPrice") or 0.0)
    details["os_disks_month"] = disk_month
    total += disk_month

    if interzone_gb > 0:
        iz = find_interzone_bandwidth_rate(region, currency)
        if iz:
            iz_cost = interzone_gb * (iz.get("retailPrice") or 0.0)
            details["interzone_data_month"] = iz_cost
            total += iz_cost
        else:
            details["interzone_data_month"] = 0.0

    return total, details


def format_money(x: float, currency: str) -> str:
    return f"{currency} {x:,.2f}"


def main():
    parser = argparse.ArgumentParser(description="Estimate zone-redundant VM costs using Azure Retail Prices API.")
    parser.add_argument("--primary", default="eastus2", help="Primary region (e.g., eastus2)")
    parser.add_argument("--dr", default="centralus", help="DR region (e.g., centralus)")
    parser.add_argument("--vm-size", default="D8s v5", help="VM size name as in skuName, e.g., 'D8s v5'")
    parser.add_argument("--os", choices=["windows", "linux"], default="windows", help="OS type for VM pricing")
    parser.add_argument("--instances", type=int, default=2, help="Number of VMs in primary (active-active across zones)")
    parser.add_argument("--os-disk", default="P10", help="OS disk tier, e.g., P10 for 128 GiB")
    parser.add_argument("--disk-redundancy", choices=["lrs", "zrs"], default="lrs", help="Managed disk redundancy")
    parser.add_argument("--interzone-gb", type=float, default=0.0, help="Estimated inter-zone GB per month in primary region")
    parser.add_argument("--currency", default="USD", help="Currency code, e.g., USD, EUR")
    parser.add_argument("--dr-mode", choices=["cold", "warm", "hot"], default="cold", help="DR posture: cold=storage only, warm=1 VM, hot=mirror 2 VMs")

    args = parser.parse_args()

    windows = args.os == "windows"

    try:
        primary_total, primary_details = compute_primary_costs(
            region=args.primary,
            vm_size=args.vm_size,
            windows=windows,
            instances=args.instances,
            disk_sku=args.os_disk,
            disk_redundancy=args.disk_redundancy,
            currency=args.currency,
            interzone_gb=args.interzone_gb,
        )
    except Exception as e:
        print(f"Error computing primary costs: {e}", file=sys.stderr)
        sys.exit(2)

    # DR costs:
    # cold: storage only (replicated disks) — excludes ASR licensing and replication egress
    # warm: 1 VM + 1 disk
    # hot: 2 VMs + 2 disks (mirror primary)
    dr_instances = 0
    if args.dr_mode == "warm":
        dr_instances = 1
    elif args.dr_mode == "hot":
        dr_instances = args.instances

    dr_total = 0.0
    dr_details: Dict[str, float] = {}
    try:
        # For cold DR, treat as 0 instances but include disk storage for the target copy count
        disk_count = args.instances if args.dr_mode in ("cold", "hot") else 1
        # Compute VM costs if applicable
        if dr_instances > 0:
            vm = get_vm_hourly_price(args.dr, args.vm_size, windows, args.currency)
            if vm is None:
                raise RuntimeError(f"Could not find DR VM price for {args.vm_size} in {args.dr}.")
            vm_month = dr_instances * 730 * (vm.get("retailPrice") or 0.0)
            dr_details["compute_vm_month"] = vm_month
            dr_total += vm_month

        # Disk storage in DR
        disk = get_disk_monthly_price(args.dr, args.os_disk, args.disk_redundancy, args.currency)
        if disk is None:
            raise RuntimeError(f"Could not find DR disk price for {args.os_disk} {args.disk_redundancy.upper()} in {args.dr}.")
        dr_disk_month = disk_count * (disk.get("retailPrice") or 0.0)
        dr_details["os_disks_month"] = dr_disk_month
        dr_total += dr_disk_month
    except Exception as e:
        print(f"Error computing DR costs: {e}", file=sys.stderr)
        sys.exit(3)

    # Output summary
    print("=== Inputs ===")
    print(f"Primary region: {args.primary}")
    print(f"DR region: {args.dr}")
    print(f"VM size: {args.vm_size} | OS: {args.os}")
    print(f"Instances (primary): {args.instances}")
    print(f"OS Disk: Premium SSD {args.os_disk} ({args.disk_redundancy.upper()})")
    print(f"Inter-zone GB/month (primary): {args.interzone_gb}")
    print(f"DR mode: {args.dr_mode}")
    print(f"Currency: {args.currency}")
    print()

    print("=== Primary (Monthly) ===")
    for k, v in primary_details.items():
        print(f"{k}: {format_money(v, args.currency)}")
    print(f"Total: {format_money(primary_total, args.currency)}")
    print()

    print("=== DR (Monthly) ===")
    for k, v in dr_details.items():
        print(f"{k}: {format_money(v, args.currency)}")
    print(f"Total: {format_money(dr_total, args.currency)}")
    if args.dr_mode == "cold":
        print("Note: Cold DR excludes Azure Site Recovery per-instance fees and replication egress; add those separately.")


if __name__ == "__main__":
    main()
