GNITC vicinity geometry

Both snapshots are © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0.

`gnitc_map.geojson` is the 3,000 m radius OSM context cache, clipped around 17.161849, 78.659909.
Source: https://api.openstreetmap.org/api/0.6/map?bbox=78.6317,17.1349,78.6881,17.1888
Retrieved 2026-10-10. SHA-256 of source OSM XML: 4f562272785628565cf3771b58c853e99f6dc8a1ca2fcb361d1a84e34d359e9d

`gnitc_map_1500m.geojson` preserves the checked 1,500 m candidate.
Source: https://api.openstreetmap.org/api/0.6/map?bbox=78.6458,17.1484,78.6740,17.1753
Retrieved 2026-10-10. SHA-256 of source OSM XML: 040d4857a49eb0716db24be5c9e86c47c252dfde36a76f0db878892ca7f0cdd0

`gnitc_map_500m.geojson` preserves the original 500 m cache used as SHIFT topology input.
Source: https://api.openstreetmap.org/api/0.6/map?bbox=78.654909,17.156849,78.664909,17.166849
Retrieved 2026-10-10. SHA-256 of source OSM XML: 53d91c1062b62cc88bbc5e9aea5fb96fb6325d93c3ce4a566347793cb7af7ccc

All files contain volunteered building and road geometry, not a surveyed campus plan or evidence
of electrical assets or line locations. The larger cache is map context only: generated wires and
loads remain the synthetic network based on the preserved 500 m cache. Attribution and license
metadata are embedded in each GeoJSON file.
