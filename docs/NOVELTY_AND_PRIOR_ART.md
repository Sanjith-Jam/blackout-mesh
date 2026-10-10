# PriorityGrid: Prior Art Comparison and Novelty Claims

This document compares the PriorityGrid prototype with established methods in occupancy sensing, demand response, diagnosis and educational visualization. It separates standard techniques from the prototype integration and limits claims to what has been implemented and evaluated.

## 1. Prior Art Comparison Matrix

The table contrasts the prototype with broad classes of existing methods; it is a qualitative comparison, not a systematic literature review.

| Domain / Task | Baseline Prior Art | PriorityGrid Implementation | Novelty / Integration Claim |
|---------------|-------------------|-----------------------------|----------------------------|
| **Occupancy Sensing** | CO2/PIR-based thresholding and standard Random Forest models (e.g., [Candanedo et al., 2016](https://archive.ics.uci.edu/ml/datasets/Occupancy+Detection+)) | Multi-sensor ML integration predicting `ACTIVE`/`INACTIVE` state | **Implementation only.** We reuse standard ML techniques for occupancy. We do not claim novel sensor fusion algorithms, only the practical integration of these signals into a priority shedding pipeline. |
| **Demand Response & Shedding** | Optimization-based load shedding and frequency regulation (e.g., standard SCADA systems) | Rule-based fair allocation matrix (`proposed_mask`) driven by ML occupancy scores | **Prototype integration.** The implementation connects occupancy evidence to constrained allocation in a software simulation. No external baseline or independent end-to-end latency/fairness comparison has established an improvement. |
| **Topology-Aware Diagnosis** | Graph-based fault localization in distribution networks | Ranked hypothesis generation across simultaneous faults (`diagnose()`) | **Prototype integration.** The simulator ranks candidate causes and can abstain when evidence is missing or ambiguous. The synthetic benchmark is developer-held-out, not independent field validation; no general diagnostic improvement is claimed. |
| **Hardware-in-the-Loop** | Commercial digital twins and expensive testbeds (e.g., OPAL-RT) | ESP32-based visual indication and simulated classrooms | **Pedagogical Integration.** A low-cost, web-based visualizer combined with ESP32 edge nodes designed specifically for student demonstration and teaching. |

*Citations & Licenses:*
* Occupancy Detection Data: Candanedo, L. M., & Feldheim, V. (2016). Accurate occupancy detection of an office room from light, temperature, humidity and CO2 measurements using statistical learning models. Energy and Buildings. DOI: 10.1016/j.enbuild.2016.01.036..
* Dependencies have their own licenses; consult the repository dependency and notice records before redistribution. This document does not assert that every dependency is permissively licensed.

## 2. Technical Claims and Limitations

To maintain academic and engineering integrity, we strictly separate what we have built from what we propose.

### What We Reused (No Novelty Claimed)
* **Occupancy classification:** The checked-in implementation uses a standard scikit-learn logistic-regression pipeline. The office dataset is a proxy; temporal generalization to campus rooms is not established.
* **WebSocket Streaming:** Standard full-duplex communication for state broadcasting.
* **Safety checks:** Configured thresholds and conservative unknown handling are standard safeguards, not a novel method.

### What the Prototype Implements (No Comparative Improvement Claimed)
* **Telemetry-based diagnosis:** The implementation evaluates validated sensor observations and returns ranked hypotheses with uncertainty. Its synthetic scenarios support development checks only; no real-world diagnostic performance is established.
* **Constrained allocation:** A deterministic policy selects feasible loads under configured capacities and priorities. It does not establish fairness or prevent real grid cascades.
* **Educational visualization:** An integrated frontend displays simulated grid state and model outputs. This is a presentation capability, not a validated operational grid monitor.

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
