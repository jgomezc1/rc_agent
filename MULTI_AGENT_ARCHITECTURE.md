# StructuBIM Multi-Agent Architecture

## System Overview

This document defines the three-agent architecture for the RC Agent system, designed to support different users and phases of reinforced concrete construction projects.

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Data Sources"
        P1[Phase 1 JSON<br/>Solutions Summary]
        P2[Phase 2 JSON<br/>Detailed Metrics]
        MS[Master Schedule]
        MD[Market Data]
        SC[Site Conditions]
    end

    subgraph "Agent 1: Trade-Off Analyst Agent (T-OAA)"
        T1[1. Ingestion<br/>Load Phase 1 Data]
        T2[2. User Input<br/>Constraints & Goals]
        T3[3. Filtering<br/>Remove Infeasible]
        T4[4. Pareto Analysis<br/>MOO & Pareto Front]
        T5[5. Recommendation<br/>Top 3-5 Solutions]

        T1 --> T2 --> T3 --> T4 --> T5
    end

    subgraph "Agent 2: Procurement & Logistics Agent (P&L-A)"
        PL1[1. Solution Retrieval<br/>Get Chosen RS-P Details]
        PL2[2. Schedule Alignment<br/>Link to Construction Timeline]
        PL3[3. JIT Optimization<br/>LRM Framework]
        PL4[4. Logistics Grouping<br/>Consolidate Orders]

        PL1 --> PL2 --> PL3 --> PL4
    end

    subgraph "Agent 3: Field Adaptability Agent (F-AA)"
        F1[1. Proactive Risk Scan<br/>Review Constructability]
        F2[2. Constraint/Crisis Trigger<br/>Site Event Detection]
        F3[3. Alternate Solution Query<br/>Find RS-A Candidates]
        F4[4. Net Impact Analysis<br/>Calculate Trade-offs]
        F5[5. Adaptive Recommendation<br/>Actionable Directive]

        F1 --> F2
        F2 --> F3 --> F4 --> F5
    end

    subgraph "Users & Outputs"
        U1[Project Managers<br/>Estimators<br/>Design Leads]
        U2[Procurement Manager<br/>Logistics Manager]
        U3[Site Superintendent<br/>Foreman<br/>QC Inspector]

        O1[Optimal Solution Set<br/>RS-P Selection]
        O2[Purchase Orders<br/>JIT Delivery Plan]
        O3[Crisis Response<br/>Mixed-Solution Plan]
    end

    %% Data flow to agents
    P1 --> T1
    U1 --> T2
    T5 --> O1

    O1 --> PL1
    P2 --> PL1
    MS --> PL2
    MD --> PL3
    PL4 --> O2
    U2 --> PL2

    O1 --> F1
    P2 --> F1
    SC --> F2
    U3 --> F2
    P1 --> F3
    F5 --> O3

    %% Styling
    classDef agentBox fill:#e1f5ff,stroke:#0066cc,stroke-width:3px
    classDef dataBox fill:#fff4e6,stroke:#ff9800,stroke-width:2px
    classDef userBox fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    classDef outputBox fill:#e8f5e9,stroke:#4caf50,stroke-width:2px

    class T1,T2,T3,T4,T5,PL1,PL2,PL3,PL4,F1,F2,F3,F4,F5 agentBox
    class P1,P2,MS,MD,SC dataBox
    class U1,U2,U3 userBox
    class O1,O2,O3 outputBox
```

---

## Detailed Workflow Sequence

```mermaid
sequenceDiagram
    actor PM as Project Manager
    actor ProcMgr as Procurement Manager
    actor Site as Site Superintendent

    participant TOAA as Trade-Off Analyst Agent
    participant PLA as Procurement & Logistics Agent
    participant FAA as Field Adaptability Agent

    participant P1 as Phase 1 JSON
    participant P2 as Phase 2 JSON

    rect rgb(225, 245, 255)
        Note over PM,TOAA: STAGE 1: OPTIMIZATION
        PM->>TOAA: Define constraints & goals
        TOAA->>P1: Load all solutions
        P1-->>TOAA: N solutions data
        TOAA->>TOAA: 1. Filter infeasible solutions
        TOAA->>TOAA: 2. Perform Pareto analysis (MOO)
        TOAA->>TOAA: 3. Generate recommendations
        TOAA-->>PM: Top 3-5 solutions with trade-offs
        PM->>TOAA: Select Primary Solution (RS-P)
    end

    rect rgb(255, 244, 230)
        Note over ProcMgr,PLA: STAGE 2: IMPLEMENTATION
        PM->>PLA: Chosen RS-P ID
        PLA->>P2: Retrieve detailed metrics
        P2-->>PLA: Element/story breakdown
        ProcMgr->>PLA: Master schedule & market data
        PLA->>PLA: 1. Align schedule to timeline
        PLA->>PLA: 2. Apply LRM framework (JIT)
        PLA->>PLA: 3. Group materials by type
        PLA-->>ProcMgr: Purchase orders & delivery plan
    end

    rect rgb(255, 243, 224)
        Note over Site,FAA: STAGE 3: ADAPTATION
        FAA->>P2: Scan constructability index
        FAA-->>Site: Proactive alerts on high-risk elements

        alt Crisis Occurs
            Site->>FAA: Material shortage / QC issue
            FAA->>P1: Query alternate solutions
            P1-->>FAA: RS-A candidates
            FAA->>FAA: Calculate net impact
            FAA-->>Site: Recommended action with metrics
            Site->>FAA: Approve solution switch
        end
    end
```

---

## Agent Capabilities Matrix

```mermaid
graph LR
    subgraph "Trade-Off Analyst Agent"
        T[T-OAA]
        T --> T1[Pareto Front<br/>Identification]
        T --> T2[Constraint<br/>Filtering]
        T --> T3[Sensitivity<br/>Analysis]
        T --> T4[Trade-off<br/>Explanation]
    end

    subgraph "Procurement & Logistics Agent"
        P[P&L-A]
        P --> P1[JIT Schedule<br/>Generation]
        P --> P2[Consolidation<br/>Optimization]
        P --> P3[Waste<br/>Optimization]
        P --> P4[Supplier<br/>Coordination]
    end

    subgraph "Field Adaptability Agent"
        F[F-AA]
        F --> F1[Risk<br/>Flagging]
        F --> F2[Crisis<br/>Response]
        F --> F3[Mixed-Solution<br/>Recommendation]
        F --> F4[Impact<br/>Recalculation]
    end

    style T fill:#4fc3f7
    style P fill:#ffb74d
    style F fill:#81c784
```

---

## Data Flow Architecture

```mermaid
flowchart TD
    Start([Project Start])

    Start --> Stage1{Stage 1:<br/>Optimization}

    Stage1 --> Input1[User Constraints<br/>+ Phase 1 JSON]
    Input1 --> TOAA[Trade-Off Analyst<br/>Agent]

    TOAA --> Filter[Filter Solutions]
    Filter --> Pareto[Pareto Analysis]
    Pareto --> Recommend[Generate<br/>Recommendations]
    Recommend --> Select[User Selects<br/>RS-P]

    Select --> Stage2{Stage 2:<br/>Implementation}

    Stage2 --> Input2[RS-P + Phase 2 JSON<br/>+ Master Schedule]
    Input2 --> PLA[Procurement &<br/>Logistics Agent]

    PLA --> Schedule[Align Schedule]
    Schedule --> JIT[JIT Optimization<br/>LRM Framework]
    JIT --> Group[Group Materials]
    Group --> PO[Generate Purchase<br/>Orders]

    PO --> Stage3{Stage 3:<br/>Adaptation}

    Stage3 --> Monitor[Monitor Site<br/>Conditions]
    Monitor --> Risk{Risk or<br/>Crisis?}

    Risk -->|No| Continue[Continue<br/>Construction]
    Risk -->|Yes| FAA[Field Adaptability<br/>Agent]

    FAA --> Query[Query Alternates]
    Query --> Impact[Calculate Impact]
    Impact --> Directive[Generate Directive]
    Directive --> Switch[Switch Solution<br/>if Needed]

    Switch --> Continue
    Continue --> Done([Project Complete])

    style TOAA fill:#e1f5ff,stroke:#0066cc,stroke-width:3px
    style PLA fill:#fff4e6,stroke:#ff9800,stroke-width:3px
    style FAA fill:#ffebee,stroke:#f44336,stroke-width:3px
```

---

## Agent Interaction Model

```mermaid
graph TB
    subgraph "Phase 1: Pre-Construction (Value Finding)"
        TOAA[Trade-Off Analyst Agent<br/>T-OAA]
        TOAA_IN[Inputs:<br/>• Phase 1 JSON<br/>• User Constraints<br/>• Optimization Goals]
        TOAA_OUT[Outputs:<br/>• Optimal Solution Set<br/>• Trade-off Analysis<br/>• Sensitivity Reports<br/>• RS-P Selection]

        TOAA_IN --> TOAA --> TOAA_OUT
    end

    subgraph "Phase 2: Pre-Construction (JIT Planning)"
        PLA[Procurement & Logistics Agent<br/>P&L-A]
        PLA_IN[Inputs:<br/>• RS-P ID<br/>• Phase 2 JSON<br/>• Master Schedule<br/>• Market Data]
        PLA_OUT[Outputs:<br/>• JIT Delivery Plan<br/>• Purchase Orders<br/>• Logistics Schedule<br/>• Waste Report]

        PLA_IN --> PLA --> PLA_OUT
    end

    subgraph "Phase 3: Construction (Risk Mitigation)"
        FAA[Field Adaptability Agent<br/>F-AA]
        FAA_IN[Inputs:<br/>• RS-P ID<br/>• Phase 2 JSON<br/>• Site Conditions<br/>• Phase 1 JSON all]
        FAA_OUT[Outputs:<br/>• Risk Alerts<br/>• Alternate Solutions RS-A<br/>• Impact Analysis<br/>• Action Directives]

        FAA_IN --> FAA --> FAA_OUT
    end

    TOAA_OUT -->|RS-P Selected| PLA_IN
    TOAA_OUT -->|RS-P + All Solutions| FAA_IN
    PLA_OUT -->|Delivery Timeline| FAA_IN
    FAA_OUT -.->|Crisis Feedback| TOAA_IN

    style TOAA fill:#bbdefb,stroke:#1976d2,stroke-width:4px
    style PLA fill:#ffe0b2,stroke:#f57c00,stroke-width:4px
    style FAA fill:#ffccbc,stroke:#d84315,stroke-width:4px
```

---

## Key Features & Capabilities

### 1. Trade-Off Analyst Agent (T-OAA)
**Purpose:** Macro-level decision-making for optimal solution selection

**Key Capabilities:**
- **Pareto Front Identification:** Multi-objective optimization to find non-dominated solutions
- **Constraint Filtering:** Hard constraint validation (budget, schedule, material availability)
- **Recommendation Generation:** Detailed trade-off analysis of top 3-5 solutions
- **Sensitivity Analysis:** Real-time re-ranking with variable adjustments

**Input Data:**
- Phase 1 JSON (all solution summaries)
- Project constraints (budget, timeline, material preferences)
- Optimization weights (cost vs. time vs. CO₂ vs. constructability)

**Output Data:**
- Optimal Solution Set (3-5 solutions)
- Trade-off narratives
- Pareto front visualization
- Selected Primary Solution (RS-P)

---

### 2. Procurement & Logistics Agent (P&L-A)
**Purpose:** Transform chosen solution into executable procurement and delivery plan

**Key Capabilities:**
- **JIT Schedule Generation:** Least Responsible Moment (LRM) framework implementation
- **Consolidation Optimization:** Group identical materials across elements/stories
- **Waste Optimization:** Analyze cut lengths and splice patterns
- **Supplier Coordination:** Generate optimized purchase orders

**Input Data:**
- Chosen RS-P ID
- Phase 2 JSON (detailed element breakdown)
- Master construction schedule
- Market data (lead times, pricing)

**Output Data:**
- Phased procurement schedule
- Purchase order list
- Logistics plan
- Waste optimization report

---

### 3. Field Adaptability Agent (F-AA)
**Purpose:** Real-time problem-solving and construction momentum maintenance

**Key Capabilities:**
- **Proactive Risk Flagging:** Alert on high constructability index elements
- **Crisis Response:** Quick alternate solution identification
- **Mixed-Solution Recommendation:** Floor-by-floor solution switching
- **Impact Recalculation:** Real-time cost/schedule analysis

**Input Data:**
- Chosen RS-P ID
- Phase 2 JSON (detailed metrics)
- Current site conditions
- Phase 1 JSON (all solutions for alternatives)

**Output Data:**
- Constructability alerts
- Alternate solution recommendations (RS-A)
- Net impact analysis (cost, schedule, materials)
- Actionable directives

---

## Implementation Notes

### Agent Communication Protocol
1. **Sequential Flow:** T-OAA → P&L-A → F-AA (primary workflow)
2. **Feedback Loops:** F-AA can trigger re-analysis in T-OAA for major changes
3. **Data Sharing:** All agents access Phase 1 & Phase 2 JSON as needed
4. **State Management:** Each agent maintains context of selected solution (RS-P)

### Critical Interactions
- **T-OAA to P&L-A:** RS-P selection triggers procurement planning
- **P&L-A to F-AA:** Delivery schedule informs risk assessment
- **F-AA to T-OAA:** Crisis may require re-optimization with new constraints

### Export Capabilities
- All agents support "Export to Sheets" functionality
- Standard report formats for stakeholder communication
- Real-time dashboard updates

---

## Next Steps for Implementation

1. **Refactor existing Phase 1 tools** → Map to T-OAA capabilities
2. **Refactor existing Phase 2 tools** → Split between P&L-A and F-AA
3. **Implement agent orchestration** → Define communication protocols
4. **Create specialized prompts** → Tailored system prompts for each agent
5. **Build user interfaces** → Role-based access for different stakeholders
6. **Add state management** → Track solution selection across agent transitions

