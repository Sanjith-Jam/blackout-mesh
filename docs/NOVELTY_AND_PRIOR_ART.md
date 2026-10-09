# PriorityGrid: Prior Art Comparison and Novelty Claims

This document provides a source-backed comparison of the PriorityGrid prototype against established methods in occupancy sensing, demand response, and smart grid pedagogy. It explicitly separates standard reused techniques from our measured integration value, and bounds our novelty claims to prevent claiming the invention of existing methods.

## 1. Prior Art Comparison Matrix

The table below contrasts our implemented prototype with standard academic and industrial baselines.

| Domain / Task | Baseline Prior Art | PriorityGrid Implementation | Novelty / Integration Claim |
|---------------|-------------------|-----------------------------|----------------------------|
| **Occupancy Sensing** | CO2/PIR-based thresholding and standard Random Forest models (e.g., [Candanedo et al., 2016](https://archive.ics.uci.edu/ml/datasets/Occupancy+Detection+)) | Multi-sensor ML integration predicting `ACTIVE`/`INACTIVE` state | **Implementation only.** We reuse standard ML techniques for occupancy. We do not claim novel sensor fusion algorithms, only the practical integration of these signals into a priority shedding pipeline. |
| **Demand Response & Shedding** | Optimization-based load shedding and frequency regulation (e.g., standard SCADA systems) | Rule-based fair allocation matrix (`proposed_mask`) driven by ML occupancy scores | **Integration Value.** Our claim is limited to the end-to-end latency and deterministic fairness of linking ML occupancy directly to sub-second load shedding for isolated microgrids. |
| **Topology-Aware Diagnosis** | Graph-based fault localization in distribution networks | Ranked hypothesis generation across simultaneous faults (`diagnose()`) | **Measured Improvement.** We contribute a transparent, explainable ranking engine that abstains safely under ambiguity rather than forcing a single confident misdiagnosis. |
| **Hardware-in-the-Loop** | Commercial digital twins and expensive testbeds (e.g., OPAL-RT) | ESP32-based visual indication and simulated classrooms | **Pedagogical Integration.** A low-cost, web-based visualizer combined with ESP32 edge nodes designed specifically for student demonstration and teaching. |

*Citations & Licenses:*
* Occupancy Detection Data: Candanedo, L. M., & Feldheim, V. (2016). Accurate occupancy detection of an office room from light, temperature, humidity and CO2 measurements using statistical learning models. Energy and Buildings. DOI: 10.1016/j.enbuild.2016.01.036. (Open/Academic license).
* PriorityGrid relies entirely on permissively licensed open-source libraries (scikit-learn, FastAPI, React).

## 2. Technical Claims and Limitations

To maintain academic and engineering integrity, we strictly separate what we have built from what we propose.

### What We Reused (No Novelty Claimed)
* **Random Forest Classification:** We utilize standard `scikit-learn` models. We did not invent the algorithm.
* **WebSocket Streaming:** Standard full-duplex communication for state broadcasting.
* **Basic Thresholding:** Hardcoded fallback rules for sensor limits.

### What We Implemented and Measured (Our Claimed Value)
* **Blind Diagnosis Engine:** We successfully implemented a deterministic diagnostic engine that evaluates conflicting sensor streams to produce a ranked list of fault hypotheses.
* **Fair Allocation:** A deterministic bitmask-based allocation policy that gracefully sheds load based on real-time ML activity scores, preventing cascade failures.
* **Full-Stack Observability:** An integrated React/Zustand frontend that visualizes abstract grid states and ML predictions in real-time for educational purposes.

### Explicit Limitations and Negative Findings (For Judges)
* ❌ **No "Mesh" Routing Claim:** Despite the working name "blackout-mesh", the current prototype **does not** implement a multi-hop mesh routing protocol. We communicate radially via WebSockets. We make zero claims regarding RF propagation, packet routing, or mesh resilience until real packet-path evidence is captured.
* ❌ **No Campus-Scale Accuracy:** The ML models are trained on limited dataset samples. Generalization to a real campus environment is proposed, not demonstrated.
* ❌ **No Real Power Switching:** The system currently simulates power loads (e.g., 5000W sources). It does not interface with actual high-voltage relays or certified protection equipment.
* ❌ **No Measured Energy Savings:** We have not conducted a longitudinal study to prove physical energy or cost savings.

## 3. Claim Verification Checklist

When evaluating this project, please verify our claims against this strict boundary:
- [x] Does the pitch differentiate between the demonstrated software UI and the proposed electrical hardware? **Yes.**
- [x] Are we claiming to invent CO2 occupancy sensing? **No.**
- [x] Are we claiming to have built a physical multi-hop mesh network? **No.**
- [x] Are the diagnosis capabilities explicitly bounded by their uncertainty? **Yes, the engine yields ranked hypotheses and handles ambiguity gracefully.**

