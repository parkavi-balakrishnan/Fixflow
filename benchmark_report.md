# FixFlow Benchmark Report

Samples: 180

| Metric | Result |
| --- | ---: |
| P50 latency | 0.60 ms |
| P95 latency | 3.68 ms |
| Cache hit rate | 82.2% |
| Coverage | 100.0% |
| Schema validity | 100.0% |
| URL leakage rate | 0.0% |
| URL leak matches | 0 |

Latency is measured around each `FixFlowPipeline.troubleshoot` call. Coverage counts responses with at least one goal and one action. Schema validity checks the response model shape; URL leakage checks the serialized response and ignores allowed `bixby://` deeplinks.
