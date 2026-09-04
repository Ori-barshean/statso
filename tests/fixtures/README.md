# Offline API fixtures

Captured on 2026-09-05 from:

- `https://api.cbs.gov.il/index/data/price?id=120010&format=json&download=false&coef=true&page=1&pagesize=1000`
- `https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/BR/1.0/MNT_RIB_BOI_D..?format=csv`

The CBS response contains 899 monthly rows. The BOI response contains 11,909 daily rows and derives to
159 interest-rate change points. Regenerate manually with `python3 tools/make_fixtures.py`; CI never calls
the network for tests.
