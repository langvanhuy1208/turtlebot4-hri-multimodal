#!/usr/bin/env python3
"""Named lab poses tied to one map; reuse the strict Vietnamese command grammar."""
import math
import os
import tempfile
from pathlib import Path

import yaml
from semantic_map import OccupancyMap, RegionCatalog, normalize


class LabCatalog(RegionCatalog):
    def __init__(self, filename):
        self.path = Path(filename).expanduser().resolve()
        self.data = yaml.safe_load(self.path.read_text())
        if self.data.get('version') != 1 or self.data.get('frame_id') != 'map':
            raise ValueError('Catalog phải có version: 1 và frame_id: map')
        self.map = OccupancyMap(self.path.parent / self.data['map'])
        if self.map.fingerprint() != self.data['map_sha256']:
            raise ValueError('Bản đồ đã thay đổi; tạo lại catalog và đánh dấu lại địa điểm')
        self.minimum = float(self.data['minimum_clearance_m'])
        if not math.isfinite(self.minimum) or self.minimum < 0.25:
            raise ValueError('minimum_clearance_m phải >= 0.25 m')
        self.regions, self.aliases = {}, {}
        for region in self.data['regions']:
            rid = region['id']
            if not isinstance(rid, str) or not rid.strip() or rid in self.regions:
                raise ValueError('ID trống hoặc trùng')
            self.validate_pose(**region['goal'])
            self.regions[rid] = region
            for alias in [rid, region['name'], *region.get('aliases', [])]:
                key = normalize(alias)
                if not key or (key in self.aliases and self.aliases[key] != rid):
                    raise ValueError(f'Tên gọi trống hoặc trùng: {alias}')
                self.aliases[key] = rid

    def validate_pose(self, x, y, yaw):
        x, y, yaw = map(float, (x, y, yaw))
        if not all(math.isfinite(v) for v in (x, y, yaw)):
            raise ValueError('Tọa độ không hữu hạn')
        u, v = self.map.world_to_pixel(x, y)
        if not (0 <= u < self.map.width and 0 <= v < self.map.height):
            raise ValueError('Điểm nằm ngoài bản đồ')
        if not self.map.free[v, u] or self.map.clearance[v, u] < self.minimum:
            raise ValueError('Điểm nằm trong vật cản/vùng chưa biết hoặc quá gần tường')


def write_yaml(path, data):
    """Atomic replace, so interruption cannot leave half a catalog."""
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.yaml')
    try:
        with os.fdopen(fd, 'w') as stream:
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
        # Validate the entire candidate before replacing the previous catalog.
        LabCatalog(temp)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def create_catalog(map_file, output, minimum=0.35):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError('Catalog đã tồn tại; chọn tệp mới để giữ địa điểm cũ')
    occupancy = OccupancyMap(map_file)
    data = dict(version=1, frame_id='map',
                map=os.path.relpath(occupancy.path, output.parent),
                map_sha256=occupancy.fingerprint(), minimum_clearance_m=minimum, regions=[])
    write_yaml(output, data)


def add_destination(filename, rid, name, aliases, x, y, yaw):
    catalog = LabCatalog(filename)
    if rid in catalog.regions:
        raise ValueError('ID đã tồn tại; dùng ID khác')
    catalog.validate_pose(x, y, yaw)
    catalog.data['regions'].append(dict(id=rid, name=name, aliases=aliases,
                                      goal=dict(x=float(x), y=float(y), yaw=float(yaw))))
    write_yaml(filename, catalog.data)


def gesture_slots(regions, previous):
    """Keep existing finger slots; fill vacant ones as places are taught."""
    ids=list(regions);slots=list(previous)[:3]
    available=iter(r for r in ids if r not in slots)
    for i,rid in enumerate(slots):
        if rid not in ids:slots[i]=next(available,'unconfigured_'+str(i+1))
    while len(slots)<min(3,len(ids)):
        slots.append(next(available))
    return slots or ['unconfigured']
