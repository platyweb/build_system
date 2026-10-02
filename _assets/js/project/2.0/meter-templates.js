// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.

// ─── Meter Template System ────────────────────────────────────────────────────
// Auto-generates live point attributes (id, data-bacnet, data-format) from
// a central meter registry. In HTML, simply use:
//
//   <div data-meter-id="1" data-meter-field="status"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="demand"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="energy"  data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="daily"   data-refresh="10">Loading...</div>
//   <div data-meter-id="1" data-meter-field="monthly" data-refresh="10">Loading...</div>
//
// ─── Updating the registry ───────────────────────────────────────────────────
//   Edit meter_tmp.csv then run:   python generate_meter_registry.py
//   This regenerates the METER_REGISTRY block below from the CSV.
//
// ─── ID Convention ───────────────────────────────────────────────────────────
//   id = "live-{slug}-{field}"
//   where {slug} is the tag column slugified (lowercase, spaces/special → hyphens)
//   and {field} is: status | demand | energy | daily | monthly
//
// ─── BACnet Address Rules ────────────────────────────────────────────────────
//   status:  300|3|{base}|85|-1                   → data-format="status"
//   energy:  300|0|{base}|85|-1                   → data-format="energy"
//   demand:  300|0|{base + powerOffset}|85|-1     → data-format="power"
//            powerOffset = 40  if type is Modbus
//            powerOffset = 82  if type is Calculation
//   daily:   300|0|{daily}|85|-1                  → data-format="energy"
//   monthly: 300|0|{monthly}|85|-1                → data-format="energy"
//
// ─── Placement fields (optional, used by the static page generator) ──────────
//   Meters that appear on a floor or tenant page carry extra fields that
//   the Python build (build.py + floor.html.j2 / tenant_floor.html.j2)
//   groups by to derive the layout:
//
//     floor    : "ground" | "1st" | "2nd" | …       — which floor page
//     column   : 0 | 1 | …                          — which column on that page
//     zone     : "West - Core 1" | …                — group key → floor-card title
//     position : integer                            — order within (floor, column)
//     function : "Fan Coil Units" | …               — short in-card label
//     utility  : "electricity" | "chw" | "lphw" | "lthw"  — drives meter-<u> CSS.
//                A "-virtual" suffix ("lthw-virtual") marks a calculated
//                meter and gives meter-<u>-virtual, which the CSS colours
//                as its utility does plus a #2A0048 right-edge fade.
//     tenant   : "metro" | "carpmael" | "carpmael,sodexo" | …
//                — comma-separated slug(s); identifies which tenant pages
//                  show this meter. Filter is `<tenant_slug> in tenants`.
//
//   These properties are only emitted in the JS for meters where they're set
//   (via the meter_tmp.csv → generate_meter_registry.py round-trip). Runtime
//   code (data-meter-id auto-resolution) does NOT read them — they exist
//   purely for the build-time generator.
// ─────────────────────────────────────────────────────────────────────────────

// ── BEGIN GENERATED METER_REGISTRY ── DO NOT EDIT BY HAND ──
const METER_REGISTRY = [
    { id:   1, tag: "Main Incomer 1 - HV02"                                    , base: 10000, type: "Modbus", daily:       0, monthly:       0, parent_id: 629, floor: "B4", column: null, zone: "", function: "Incomer", utility: "electricity", main_display: false },
    { id:   2, tag: "Main Incomer 2 - HV04"                                    , base: 10100, type: "Modbus", daily:       0, monthly:       0, parent_id: 629, floor: "B4", column: null, zone: "", function: "Incomer", utility: "electricity", tenant_display: true, main_display: false },
    { id:   3, tag: "HV Switch Room Supply - HV14"                             , base: 10200, type: "Modbus", daily:       0, monthly:       0, parent_id: 1, floor: "B4", column: null, zone: "", function: "HV/LL/SB/B2/01.05", utility: "electricity", main_display: false },
    { id:   4, tag: "HV Switch Room Supply - HV16"                             , base: 10300, type: "Modbus", daily:       0, monthly:       0, parent_id: 2, floor: "B4", column: null, zone: "", function: "HV/LL/SB/B2/01.6", utility: "electricity", main_display: false },
    { id:   5, tag: "Generator Feed - GHV6"                                    , base: 10400, type: "Modbus", daily:       0, monthly:       0, parent_id: 630, floor: "B4", column: null, zone: "", function: "HV/GEN/SB/B2/01", utility: "electricity", main_display: false },
    { id:   6, tag: "Generator Feed - GHV7"                                    , base: 10500, type: "Modbus", daily:       0, monthly:       0, parent_id: 630, floor: "B4", column: null, zone: "", function: "HV/GEN/SB/B2/01", utility: "electricity", main_display: false },
    { id:   7, tag: "HV Switch Room Supply - HV15"                             , base: 10600, type: "Modbus", daily:       0, monthly:       0, parent_id: 1, floor: "B4", column: null, zone: "", function: "HV/LL/SB/B2/02.16", utility: "electricity", main_display: false },
    { id:   8, tag: "HV Switch Room Supply - HV17"                             , base: 10700, type: "Modbus", daily:       0, monthly:       0, parent_id: 2, floor: "B4", column: null, zone: "", function: "HV/LL/SB/B2/02.15", utility: "electricity", main_display: false },
    { id:   9, tag: "Generator Feed - GHV8"                                    , base: 10800, type: "Modbus", daily:       0, monthly:       0, parent_id: 630, floor: "B4", column: null, zone: "", function: "HV/GEN/SB/B2/01.07", utility: "electricity", main_display: false },
    { id:  10, tag: "Generator Feed - GHV9"                                    , base: 10900, type: "Modbus", daily:       0, monthly:       0, parent_id: 630, floor: "B4", column: null, zone: "", function: "HV/GEN/SB/B2/01", utility: "electricity", main_display: false },
    { id:  11, tag: "Generator Load Bank GHV5"                                 , base: 11000, type: "Modbus", daily:       0, monthly:       0, parent_id: 630, floor: "B4", column: null, zone: "", function: "HV/LB/48/01", utility: "electricity", main_display: false },
    { id:  12, tag: "LV05 Incomer"                                             , base: 11100, type: "Modbus", daily:       0, monthly:       0, parent_id: 7, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  13, tag: "Shuttle Lift Panel"                                       , base: 11200, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  14, tag: "Vehicle Lift Panel"                                       , base: 11300, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  15, tag: "DB/LL/W/19/01  09/01  01/01"                              , base: 11400, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  16, tag: "ATS/FF/W/B1/01, ATS/FF/E/B3/01 Core Fire Power Supplies"  , base: 11500, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  17, tag: "PDB/B1/02 Changing Area AHU"                              , base: 11600, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", main_display: false },
    { id:  18, tag: "Chiller C4"                                               , base: 11700, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  19, tag: "HV TX 1/2 Cooling A, TX Room 5/6 Cooling A"               , base: 11800, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  20, tag: "Supply to Low Rise Lift Panel"                            , base: 11900, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  21, tag: "ATS/LL/B2/01, ATS/LL/B1/01 Basement / Carpark Ventilation", base: 12000, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  22, tag: "Landlord Busbar B3-L24"                                   , base: 12100, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  23, tag: "Spare x 2 + ATS/LL/00/01 F/A +VA"                         , base: 12200, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  24, tag: "MER Cooling A"                                            , base: 12300, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  25, tag: "MER UPS Bypass Supply, SEC RM UPS BypassSupply"           , base: 12400, type: "Modbus", daily:       0, monthly:       0, parent_id: 12, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  26, tag: "LV06 Incomer"                                             , base: 12500, type: "Modbus", daily:       0, monthly:       0, parent_id: 4, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  27, tag: "ATS/Ll/B4/02 Fuel Trans Pump"                             , base: 12600, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  28, tag: "MER UPS Supply, SEC RM UPS Supply"                        , base: 12700, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  29, tag: "Chiller C3"                                               , base: 12800, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  30, tag: "PDB/B1/03 Bike Area Exhaust Fans"                         , base: 12900, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  31, tag: "HV TX 1/2 Cooling A, TX Room 5/6 Cooling B"               , base: 13000, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  32, tag: "MER Cooling B"                                            , base: 13100, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  33, tag: "DB/LL/E/00/01 09/01 19/01"                                , base: 13200, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  34, tag: "ATS/FF/SW/B1/01 Fire Shaft B1 to B4"                      , base: 13300, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  35, tag: "PDB/B4/01 (Prim) Wet Riser Pump 1"                        , base: 13400, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  36, tag: "PDB/B1/04"                                                , base: 13500, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  37, tag: "B1 Water Heater 2 AHU East Plant Rm"                      , base: 13600, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  38, tag: "B1 Water Heater 1 AHU East Plant Rm"                      , base: 13700, type: "Modbus", daily:       0, monthly:       0, parent_id: 26, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  39, tag: "LV01 Incomer"                                             , base: 13800, type: "Modbus", daily:       0, monthly:       0, parent_id: 3, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  40, tag: "LV02 Incomer"                                             , base: 13900, type: "Modbus", daily:       0, monthly:       0, parent_id: 8, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  41, tag: "Tenants Busbar West L4-L18"                               , base: 14000, type: "Modbus", daily:       0, monthly:       0, parent_id: 39, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  42, tag: "Tenants Busbar West L19-L24"                              , base: 14100, type: "Modbus", daily:       0, monthly:       0, parent_id: 39, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  43, tag: "Tenants Busbar East L4-L18"                               , base: 14200, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  44, tag: "Tenants Busbar East L19-L24"                              , base: 14300, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  45, tag: "AON L9 UPS I/O Panel"                                     , base: 14400, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  46, tag: "AON B3 Mail Room"                                         , base: 14500, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "Basement", column: 1, zone: "North", function: "", utility: "electricity", tenant: "AON", tenant_display: true },
    { id:  47, tag: "AON B2 Staff Welfare Room"                                , base: 14600, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "Basement", column: 1, zone: "North", function: "", utility: "electricity", tenant: "AON", tenant_display: true },
    { id:  48, tag: "AON B1 Security Room"                                     , base: 14700, type: "Modbus", daily:       0, monthly:       0, parent_id: 40, floor: "Basement", column: 1, zone: "North", function: "", utility: "electricity", tenant: "AON", tenant_display: true },
    { id:  49, tag: "LV03 Incomer"                                             , base: 14800, type: "Modbus", daily:       0, monthly:       0, parent_id: 7, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  50, tag: "DB/FF/ W,E B1-01"                                         , base: 14900, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  51, tag: "HV TX 2 Cooling B, Comms Intake Room Cooling A"           , base: 15000, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  52, tag: "DB/LL/B3/03 (South)"                                      , base: 15100, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  53, tag: "DB/LL/B3/04 (Loading Bay)"                                , base: 15200, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  54, tag: "ATS/LL/00/01,03 FCC"                                      , base: 15300, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  55, tag: "Comms Intake  Rm UPS PDU"                                 , base: 15400, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  56, tag: "Retail Tenant Board"                                      , base: 15500, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  57, tag: "Escalator 1 2 on L1, Escalator 3 on L2"                   , base: 15600, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  58, tag: "ATS/LL/B2/01, B1/01"                                      , base: 15700, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  59, tag: "HV, Gen Batt Chargers"                                    , base: 15800, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  60, tag: "CHW Pumps (PDB/B3/01)"                                    , base: 15900, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  61, tag: "COND Pumps (PDB/B3/002)"                                  , base: 16000, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  62, tag: "Chiller Room DB/LL/B3/02"                                 , base: 16100, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  63, tag: "Chiller C2"                                               , base: 16200, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  64, tag: "HV TX 1 Cooling A, TX Room3/4 Cooling A"                  , base: 16300, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  65, tag: "DB/LL/B2/02 South"                                        , base: 16400, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  66, tag: "LV04 Incomer"                                             , base: 16500, type: "Modbus", daily:       0, monthly:       0, parent_id: 4, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  67, tag: "Comms Rm UPS Static Switch"                               , base: 16600, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  68, tag: "ATS/FF/SE/B1/01 Fire Shaft B1 to B4"                      , base: 16700, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  69, tag: "PDB/B4/01 (Sec) Wet Riser Pump 1"                         , base: 16800, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  70, tag: "ATS/Ll/B4/01 Fuel Trans Pump"                             , base: 16900, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  71, tag: "HV TX 1 Cooling B, TX Room3/4 Cooling B"                  , base: 17000, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  72, tag: "Chiller C1"                                               , base: 17100, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  73, tag: "HV TX 2 Cooling A, Comms Intake Room Cooling B"           , base: 17200, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  74, tag: "PDB/B4/02  DCW Pumps"                                     , base: 17300, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  75, tag: "Escalator 1 2 on L2, Escalator 3 on L1"                   , base: 17400, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  76, tag: "HV S/R 1, 2 Batt Chargers A, B Gen HV S/R Batt Charger B" , base: 17500, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  77, tag: "Retail Tenant Board (Secondary)"                          , base: 17600, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  78, tag: "DB/LL/B3/EVC/02"                                          , base: 17700, type: "Modbus", daily:       0, monthly:       0, parent_id: 66, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  79, tag: "LV07 Incomer"                                             , base: 17800, type: "Modbus", daily:       0, monthly:       0, parent_id: 3, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  80, tag: "Tenants Busbar West L25-45"                               , base: 17900, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  81, tag: "DB/LL/W/48/01, 38/01, 28/01"                              , base: 18000, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  82, tag: "ATS/FF/W,E/46/01 Core Fire Power Supplies (Primary)"      , base: 18100, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  83, tag: "Supply to High Rise Lift Panel 1"                         , base: 18200, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  84, tag: "Supply to High Rise Lift Panel 2"                         , base: 18300, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  85, tag: "PDB/L48/01 LTHW Boiler/Pumps"                             , base: 18400, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  86, tag: "ATS/LL/47/01, 47/02, 48/01, 48/02 Gen Aux Panel (Primary)", base: 18500, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  87, tag: "DB/LL/47/03, DB/LL/48/03 ATS (Primary)"                   , base: 18600, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  88, tag: "Fire Fighting Lift Panel 1, 2 (Primary)"                  , base: 18700, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  89, tag: "PSS07 Cooling Unit A, PSS08 Cooling Unit A"               , base: 18800, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  90, tag: "Landlords Busbar Riser L25-L46"                           , base: 18900, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", tenant_display: true },
    { id:  91, tag: "L46 SER UPS Bypass Supply"                                , base: 19000, type: "Modbus", daily:       0, monthly:       0, parent_id: 79, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  92, tag: "LV08 Incomer"                                             , base: 19100, type: "Modbus", daily:       0, monthly:       0, parent_id: 8, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  93, tag: "Tenants Busbar East L25-45"                               , base: 19200, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  94, tag: "Cooling Tower 6 MCC"                                      , base: 19300, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  95, tag: "Cooling Tower 5 MCC"                                      , base: 19400, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  96, tag: "Cooling Tower 4 MCC"                                      , base: 19500, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  97, tag: "Cooling Tower 3 MCC"                                      , base: 19600, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  98, tag: "Cooling Tower 2 MCC"                                      , base: 19700, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id:  99, tag: "Cooling Tower 1 MCC"                                      , base: 19800, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 100, tag: "ATS/FF/W,E/46/01 Core Fire Power Supplies (Sec)"          , base: 19900, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 101, tag: "DB/LL/W/38/01, 28/01"                                     , base: 20000, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 102, tag: "Good Lift GL1"                                            , base: 20100, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 103, tag: "Fire Fighting Lift Panel 1, 2 (Sec)"                      , base: 20200, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 104, tag: "DB/LL/47/03, DB/LL/48/03 ATS (Supply B)"                  , base: 20300, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 105, tag: "ATS/LL/47/01, 48/02, 48/01, 47/02 Gen Aux Panel (Primary)", base: 20400, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 106, tag: "PSS08 Cooling Unit B, PSS07 Cooling Unit B"               , base: 20500, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 107, tag: "PV Cells"                                                 , base: 20600, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 108, tag: "L46 SER UPS  Mains Supply"                                , base: 20700, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 109, tag: "Good Lift GL2"                                            , base: 20800, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 110, tag: "Supply to Mid Rise Lift Panel 1, 2"                       , base: 20900, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity", tenant_display: true },
    { id: 111, tag: "AON Kitchen Extract L46"                                  , base: 21000, type: "Modbus", daily:       0, monthly:       0, parent_id: 92, floor: "B4", column: null, zone: "", function: "SWB-meter", utility: "electricity" },
    { id: 112, tag: "Retail Unit East - Brit Hospitality"                      , base: 21100, type: "Modbus", daily: 2000000, monthly: 2000344, floor: "ground", column: null, zone: "", function: "Retail - HOP", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 113, tag: "Retail Unit West - Black Sheep Coffee"                    , base: 21200, type: "Modbus", daily: 2000001, monthly: 2000345, floor: "ground", column: null, zone: "", function: "Retail - BSC", utility: "electricity", tenant: "Black Sheep", tenant_display: true },
    { id: 114, tag: "Retail Unit Lev 3 Bob Bob Ricard"                         , base: 21300, type: "Modbus", daily: 2000002, monthly: 2000346, floor: "3rd", column: null, zone: "", function: "Retail", utility: "electricity", tenant: "Mezzanine of retail units", tenant_display: true },
    { id: 115, tag: "DB/LL/46/01"                                              , base: 21400, type: "Modbus", daily: 2000066, monthly: 2000411, parent_id: 90, floor: "46th", column: 1, zone: "North", function: "DB/LL/46/01 - L46 LL General Power", utility: "electricity", tenant_display: true },
    { id: 116, tag: "DB/LL/25/02"                                              , base: 21500, type: "Modbus", daily: 2000027, monthly: 2000371, parent_id: 90, floor: "25th", column: 1, zone: "North", function: "DB/LL/25/02 - L25 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 117, tag: "DB/LL/26/02"                                              , base: 21600, type: "Modbus", daily: 2000028, monthly: 2000372, parent_id: 90, floor: "26th", column: 1, zone: "North", function: "DB/LL/26/02 - L26 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 118, tag: "DB/LL/27/02"                                              , base: 21700, type: "Modbus", daily: 2000029, monthly: 2000373, parent_id: 90, floor: "27th", column: 1, zone: "North", function: "DB/LL/27/02 - L27 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 119, tag: "DB/LL/28/02"                                              , base: 21800, type: "Modbus", daily: 2000030, monthly: 2000374, parent_id: 90, floor: "28th", column: 1, zone: "North", function: "DB/LL/28/02 - L28 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 120, tag: "DB/LL/29/02"                                              , base: 21900, type: "Modbus", daily: 2000031, monthly: 2000375, parent_id: 90, floor: "29th", column: 1, zone: "North", function: "DB/LL/29/02 - L29 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 121, tag: "DB/LL/30/02"                                              , base: 22000, type: "Modbus", daily: 2000032, monthly: 2000376, parent_id: 90, floor: "30th", column: 1, zone: "North", function: "DB/LL/30/02 - L30 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 122, tag: "DB/LL/31/02"                                              , base: 22100, type: "Modbus", daily: 2000033, monthly: 2000377, parent_id: 90, floor: "31st", column: 1, zone: "North", function: "DB/LL/31/02 - L31 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 123, tag: "DB/LL/32/02"                                              , base: 22200, type: "Modbus", daily: 2000034, monthly: 2000378, parent_id: 90, floor: "32nd", column: 1, zone: "North", function: "DB/LL/32/02 - L32 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 124, tag: "DB/LL/33/02"                                              , base: 22300, type: "Modbus", daily: 2000035, monthly: 2000379, parent_id: 90, floor: "33rd", column: 1, zone: "North", function: "DB/LL/33/02 - L33 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 125, tag: "DB/LL/34/02"                                              , base: 22400, type: "Modbus", daily: 2000036, monthly: 2000380, parent_id: 90, floor: "34th", column: 1, zone: "North", function: "DB/LL/34/02 - L34 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 126, tag: "DB/LL/35/02"                                              , base: 22500, type: "Modbus", daily: 2000037, monthly: 2000381, parent_id: 90, floor: "35th", column: 1, zone: "North", function: "DB/LL/35/02 - L35 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 127, tag: "DB/LL/36/02"                                              , base: 22600, type: "Modbus", daily: 2000038, monthly: 2000382, parent_id: 90, floor: "36th", column: 1, zone: "North", function: "DB/LL/36/02 - L36 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 128, tag: "DB/LL/37/02"                                              , base: 22700, type: "Modbus", daily: 2000039, monthly: 2000383, parent_id: 90, floor: "37th", column: 1, zone: "North", function: "DB/LL/37/02 - L37 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 129, tag: "DB/LL/38/02"                                              , base: 22800, type: "Modbus", daily: 2000040, monthly: 2000384, parent_id: 90, floor: "38th", column: 1, zone: "North", function: "DB/LL/38/02 - L38 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 130, tag: "DB/LL/39/02"                                              , base: 22900, type: "Modbus", daily: 2000041, monthly: 2000385, parent_id: 90, floor: "39th", column: 1, zone: "North", function: "DB/LL/39/02 - L39 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 131, tag: "DB/LL/40/02"                                              , base: 23000, type: "Modbus", daily: 2000042, monthly: 2000386, parent_id: 90, floor: "40th", column: 1, zone: "North", function: "DB/LL/40/02 - L40 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 132, tag: "DB/LL/41/02"                                              , base: 23100, type: "Modbus", daily: 2000043, monthly: 2000387, parent_id: 90, floor: "41st", column: 1, zone: "North", function: "DB/LL/41/02 - L41 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 133, tag: "DB/LL/42/02"                                              , base: 23200, type: "Modbus", daily: 2000044, monthly: 2000388, parent_id: 90, floor: "42nd", column: 1, zone: "North", function: "DB/LL/42/02 - L42 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 134, tag: "DB/LL/43/02"                                              , base: 23300, type: "Modbus", daily: 2000045, monthly: 2000389, parent_id: 90, floor: "43rd", column: 1, zone: "North", function: "DB/LL/43/02 - L43 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 135, tag: "DB/LL/44/02"                                              , base: 23400, type: "Modbus", daily: 2000046, monthly: 2000390, parent_id: 90, floor: "44th", column: 1, zone: "North", function: "DB/LL/44/02 - L44 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 136, tag: "DB/LL/45/02"                                              , base: 23500, type: "Modbus", daily: 2000047, monthly: 2000391, parent_id: 90, floor: "45th", column: 1, zone: "North", function: "DB/LL/45/02 - L45 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 137, tag: "DB/LL/46/02"                                              , base: 23600, type: "Modbus", daily: 2000048, monthly: 2000392, parent_id: 90, floor: "46th", column: 1, zone: "North", function: "DB/LL/46/02 - L46 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 138, tag: "DB/LL/27/01"                                              , base: 23700, type: "Modbus", daily: 2000059, monthly: 2000404, parent_id: 90, floor: "27th", column: 1, zone: "North", function: "DB/LL/27/01 - L26-L28 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 139, tag: "DB/LL/30/01"                                              , base: 23800, type: "Modbus", daily: 2000060, monthly: 2000405, parent_id: 90, floor: "30th", column: 1, zone: "North", function: "DB/LL/30/01 - L29-L31 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 140, tag: "DB/LL/33/01"                                              , base: 23900, type: "Modbus", daily: 2000061, monthly: 2000406, parent_id: 90, floor: "33rd", column: 1, zone: "North", function: "DB/LL/33/01 - L32-L34 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 141, tag: "DB/LL/36/01"                                              , base: 24000, type: "Modbus", daily: 2000062, monthly: 2000407, parent_id: 90, floor: "36th", column: 1, zone: "North", function: "DB/LL/36/01 - L35-L37 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 142, tag: "DB/LL/39/01"                                              , base: 24100, type: "Modbus", daily: 2000063, monthly: 2000408, parent_id: 90, floor: "39th", column: 1, zone: "North", function: "DB/LL/39/01 - L38-L40 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 143, tag: "DB/LL/42/01"                                              , base: 24200, type: "Modbus", daily: 2000064, monthly: 2000409, parent_id: 90, floor: "42nd", column: 1, zone: "North", function: "DB/LL/42/01 - L41-L43 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 144, tag: "DB/LL/45/01"                                              , base: 24300, type: "Modbus", daily: 2000065, monthly: 2000410, parent_id: 90, floor: "45th", column: 1, zone: "North", function: "DB/LL/45/01 - L44-L46 LL Lift Lobby Power", utility: "electricity", tenant_display: true },
    { id: 145, tag: "DB/LL/B2/01"                                              , base: 24400, type: "Modbus", daily: 2000068, monthly: 2000412, parent_id: 22, floor: "B1", column: null, zone: "", function: "DB/LL/B2/01 - B2 North Power", utility: "electricity" },
    { id: 146, tag: "DB/LL/B1/02"                                              , base: 24500, type: "Modbus", daily: 2000069, monthly: 2000413, parent_id: 22, floor: "B1", column: null, zone: "", function: "DB/LL/B1/02 - B1 Central Power", utility: "electricity" },
    { id: 147, tag: "DB/LL/B1/01"                                              , base: 24600, type: "Modbus", daily: 2000070, monthly: 2000414, parent_id: 22, floor: "B1", column: null, zone: "", function: "DB/LL/B1/01 - B1 North Power", utility: "electricity" },
    { id: 148, tag: "DB/LL/01/02"                                              , base: 24700, type: "Modbus", daily: 2000003, monthly: 2000347, parent_id: 22, floor: "1st", column: 1, zone: "North", function: "DB/LL/01/02 - L01 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 149, tag: "DB/LL/02/02"                                              , base: 24800, type: "Modbus", daily: 2000004, monthly: 2000348, parent_id: 22, floor: "2nd", column: 1, zone: "North", function: "DB/LL/02/02 - L02 LL Mech Plant", utility: "electricity", tenant: "Landlords", tenant_display: true },
    { id: 150, tag: "DB/LL/03/02"                                              , base: 24900, type: "Modbus", daily: 2000005, monthly: 2000349, parent_id: 22, floor: "3rd", column: 1, zone: "North", function: "DB/LL/03/02 - L03 LL Mech Plant", utility: "electricity", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 151, tag: "DB/LL/04/02"                                              , base: 25000, type: "Modbus", daily: 2000006, monthly: 2000350, parent_id: 22, floor: "4th", column: 1, zone: "North", function: "DB/LL/04/02 - L04 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 152, tag: "DB/LL/05/02"                                              , base: 25100, type: "Modbus", daily: 2000007, monthly: 2000351, parent_id: 22, floor: "5th", column: 1, zone: "North", function: "DB/LL/05/02 - L05 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 153, tag: "DB/LL/06/02"                                              , base: 25200, type: "Modbus", daily: 2000008, monthly: 2000352, parent_id: 22, floor: "6th", column: 1, zone: "North", function: "DB/LL/06/02 - L06 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 154, tag: "DB/LL/07/02"                                              , base: 25300, type: "Modbus", daily: 2000009, monthly: 2000353, parent_id: 22, floor: "7th", column: 1, zone: "North", function: "DB/LL/07/02 - L07 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 155, tag: "DB/LL/08/02"                                              , base: 25400, type: "Modbus", daily: 2000010, monthly: 2000354, parent_id: 22, floor: "8th", column: 1, zone: "North", function: "DB/LL/08/02 - L08 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 156, tag: "DB/LL/09/02"                                              , base: 25500, type: "Modbus", daily: 2000011, monthly: 2000355, parent_id: 22, floor: "9th", column: 1, zone: "North", function: "DB/LL/09/02 - L09 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 157, tag: "DB/LL/10/02"                                              , base: 25600, type: "Modbus", daily: 2000012, monthly: 2000356, parent_id: 22, floor: "10th", column: 1, zone: "North", function: "DB/LL/10/02 - L10 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 158, tag: "DB/LL/11/02"                                              , base: 25700, type: "Modbus", daily: 2000013, monthly: 2000357, parent_id: 22, floor: "11th", column: 1, zone: "North", function: "DB/LL/11/02 - L11 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 159, tag: "DB/LL/12/02"                                              , base: 25800, type: "Modbus", daily: 2000014, monthly: 2000358, parent_id: 22, floor: "12th", column: 1, zone: "North", function: "DB/LL/12/02 - L12 LL Mech Plant", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 160, tag: "DB/LL/13/02"                                              , base: 25900, type: "Modbus", daily: 2000015, monthly: 2000359, parent_id: 22, floor: "13th", column: 1, zone: "North", function: "DB/LL/13/02 - L13 LL Mech Plant", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 161, tag: "DB/LL/14/02"                                              , base: 26000, type: "Modbus", daily: 2000016, monthly: 2000360, parent_id: 22, floor: "14th", column: 1, zone: "North", function: "DB/LL/14/02 - L14 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 162, tag: "DB/LL/15/02"                                              , base: 26100, type: "Modbus", daily: 2000017, monthly: 2000361, parent_id: 22, floor: "15th", column: 1, zone: "North", function: "DB/LL/15/02 - L15 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 163, tag: "DB/LL/16/02"                                              , base: 26200, type: "Modbus", daily: 2000018, monthly: 2000362, parent_id: 22, floor: "16th", column: 1, zone: "North", function: "DB/LL/16/02 - L16 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 164, tag: "DB/LL/17/02"                                              , base: 26300, type: "Modbus", daily: 2000019, monthly: 2000363, parent_id: 22, floor: "17th", column: 1, zone: "North", function: "DB/LL/17/02 - L17 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 165, tag: "DB/LL/18/02"                                              , base: 26400, type: "Modbus", daily: 2000020, monthly: 2000364, parent_id: 22, floor: "18th", column: 1, zone: "North", function: "DB/LL/18/02 - L18 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 166, tag: "DB/LL/19/02"                                              , base: 26500, type: "Modbus", daily: 2000021, monthly: 2000365, parent_id: 22, floor: "19th", column: 1, zone: "North", function: "DB/LL/19/02 - L19 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 167, tag: "DB/LL/20/02"                                              , base: 26600, type: "Modbus", daily: 2000022, monthly: 2000366, parent_id: 22, floor: "20th", column: 1, zone: "North", function: "DB/LL/20/02 - L20 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 168, tag: "DB/LL/21/02"                                              , base: 26700, type: "Modbus", daily: 2000023, monthly: 2000367, parent_id: 22, floor: "21st", column: 1, zone: "North", function: "DB/LL/21/02 - L21 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 169, tag: "DB/LL/22/02"                                              , base: 26800, type: "Modbus", daily: 2000024, monthly: 2000368, parent_id: 22, floor: "22nd", column: 1, zone: "North", function: "DB/LL/22/02 - L22 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 170, tag: "DB/LL/23/02"                                              , base: 26900, type: "Modbus", daily: 2000025, monthly: 2000369, parent_id: 22, floor: "23rd", column: 1, zone: "North", function: "DB/LL/23/02 - L23 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 171, tag: "DB/LL/24/02"                                              , base: 27000, type: "Modbus", daily: 2000026, monthly: 2000370, parent_id: 22, floor: "24th", column: 1, zone: "North", function: "DB/LL/24/02 - L24 LL Mech Plant", utility: "electricity", tenant_display: true },
    { id: 172, tag: "DB/GRND/01"                                               , base: 27100, type: "Modbus", daily: 2000067, monthly: 2000394, parent_id: 22, floor: "ground", column: 1, zone: "North", function: "DB/GRND/01 - LL L/SP DB GRD-01", utility: "electricity", tenant_display: true },
    { id: 173, tag: "DB/LL/01/01 Redundent"                                    , base: 27200, type: "Modbus", daily: 2000050, monthly: 2000393, parent_id: 22, floor: "1st", column: 1, zone: "North", function: "DB/LL/01/01 Redundent - LL L/SP DB/LL/01/01 L01 Reception", utility: "electricity", tenant: "AON" },
    { id: 174, tag: "DB/LL/02/01"                                              , base: 27300, type: "Modbus", daily:       0, monthly:       0, parent_id: 22, floor: "2nd", column: 1, zone: "North", function: "DB/LL/02/01 - LL L/SP DB/LL/02/01 L02 Reception", utility: "electricity", tenant: "Landlords", tenant_display: true },
    { id: 175, tag: "DB/LL/03/01"                                              , base: 27400, type: "Modbus", daily: 2000052, monthly: 2000396, parent_id: 22, floor: "3rd", column: 1, zone: "North", function: "DB/LL/03/01 - L02-L04 LL Lift Lobby Power", utility: "electricity", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 176, tag: "DB/LL/06/01"                                              , base: 27500, type: "Modbus", daily: 2000053, monthly: 2000397, parent_id: 22, floor: "6th", column: 1, zone: "North", function: "DB/LL/06/01 - L05-L07 LL Lift Lobby Power", utility: "electricity" },
    { id: 177, tag: "DB/LL/09/01"                                              , base: 27600, type: "Modbus", daily: 2000054, monthly: 2000398, parent_id: 22, floor: "9th", column: 1, zone: "North", function: "DB/LL/09/01 - L08-L10 LL Lift Lobby Power", utility: "electricity" },
    { id: 178, tag: "DB/LL/12/01"                                              , base: 27700, type: "Modbus", daily: 2000051, monthly: 2000399, parent_id: 22, floor: "12th", column: 1, zone: "North", function: "DB/LL/12/01 - L11-L13 LL Lift Lobby Power", utility: "electricity" },
    { id: 179, tag: "DB/LL/15/01"                                              , base: 27800, type: "Modbus", daily: 2000055, monthly: 2000400, parent_id: 22, floor: "15th", column: 1, zone: "North", function: "DB/LL/15/01 - L14-L16 LL Lift Lobby Power", utility: "electricity" },
    { id: 180, tag: "DB/LL/18/01"                                              , base: 27900, type: "Modbus", daily: 2000056, monthly: 2000401, parent_id: 22, floor: "18th", column: 1, zone: "North", function: "DB/LL/18/01 - L17-L19 LL Lift Lobby Power", utility: "electricity" },
    { id: 181, tag: "DB/LL/21/01"                                              , base: 28000, type: "Modbus", daily: 2000057, monthly: 2000402, parent_id: 22, floor: "21st", column: 1, zone: "North", function: "DB/LL/21/01 - L20-L22 LL Lift Lobby Power", utility: "electricity" },
    { id: 182, tag: "DB/LL/24/01"                                              , base: 28100, type: "Modbus", daily: 2000058, monthly: 2000403, parent_id: 22, floor: "24th", column: 1, zone: "North", function: "DB/LL/24/01 - L23-L25 LL Lift Lobby Power", utility: "electricity" },
    { id: 183, tag: "DB/LL/B4/01"                                              , base: 28200, type: "Modbus", daily: 2000073, monthly: 2000417, parent_id: 22, floor: "B4", column: null, zone: "", function: "DB/LL/B4/01 - B4 Domestic Plant room", utility: "electricity" },
    { id: 184, tag: "DB/LL/B3/01"                                              , base: 28300, type: "Modbus", daily: 2000072, monthly: 2000416, parent_id: 22, floor: "B3", column: null, zone: "", function: "DB/LL/B3/01 - B3 North East Riser", utility: "electricity" },
    { id: 185, tag: "DB/LL/B1/04"                                              , base: 28400, type: "Modbus", daily: 2000071, monthly: 2000415, parent_id: 22, floor: "B2", column: null, zone: "", function: "DB/LL/B1/04 - B1 AHU Plant Room", utility: "electricity" },
    { id: 186, tag: "DB/TOC/W/04"                                              , base: 28500, type: "Modbus", daily: 2000161, monthly: 2000505, parent_id: 41, floor: "4th", column: 2, zone: "West", function: "DB/TOC/W/04 - L04 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 187, tag: "DB/LL/01/01"                                              , base: 28600, type: "Modbus", daily:       0, monthly:       0, parent_id: 41, floor: "1st", column: 2, zone: "North", function: "DB/LL/01/01 - L01 Tenant AV Room", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 188, tag: "DB/TOC/W/05"                                              , base: 28700, type: "Modbus", daily: 2000162, monthly: 2000506, parent_id: 41, floor: "5th", column: 2, zone: "West", function: "DB/TOC/W/05 - L05 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 189, tag: "DB/TOC/W/06"                                              , base: 28800, type: "Modbus", daily: 2000164, monthly: 2000508, parent_id: 41, floor: "6th", column: 2, zone: "West", function: "DB/TOC/W/06 - L06 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 190, tag: "DB/KP/4-4R"                                               , base: 28900, type: "Modbus", daily: 2000163, monthly: 2000507, parent_id: 41, floor: "4th", column: 2, zone: "West", function: "DB/KP/4-4R - L04 Tenanat Kitchen Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 191, tag: "DB/TOC/W/07"                                              , base: 29000, type: "Modbus", daily: 2000165, monthly: 2000509, parent_id: 41, floor: "7th", column: 2, zone: "West", function: "DB/TOC/W/07 - L07 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 192, tag: "DB/TOC/W/08"                                              , base: 29100, type: "Modbus", daily: 2000166, monthly: 2000510, parent_id: 41, floor: "8th", column: 2, zone: "West", function: "DB/TOC/W/08 - L08 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 193, tag: "DB/TOC/W/09"                                              , base: 29200, type: "Modbus", daily: 2000167, monthly: 2000511, parent_id: 41, floor: "9th", column: 2, zone: "West", function: "DB/TOC/W/09 - L09 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 194, tag: "DB/TOC/W/10"                                              , base: 29300, type: "Modbus", daily: 2000168, monthly: 2000512, parent_id: 41, floor: "10th", column: 2, zone: "West", function: "DB/TOC/W/10 - L10 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 195, tag: "DB/TOC/W/11"                                              , base: 29400, type: "Modbus", daily: 2000169, monthly: 2000513, parent_id: 41, floor: "11th", column: 2, zone: "West", function: "DB/TOC/W/11 - L11 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 196, tag: "DB/TOC/W/12"                                              , base: 29500, type: "Modbus", daily: 2000170, monthly: 2000514, parent_id: 41, floor: "12th", column: 2, zone: "West", function: "DB/TOC/W/12 - L12 Tenant West Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 197, tag: "DB/TOC/W/13"                                              , base: 29600, type: "Modbus", daily: 2000171, monthly: 2000515, parent_id: 41, floor: "13th", column: 2, zone: "West", function: "DB/TOC/W/13 - L13 Tenant West Floor Power", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 198, tag: "DB/W/14/LGT"                                              , base: 29700, type: "Modbus", daily: 2000172, monthly: 2000516, parent_id: 41, floor: "14th", column: 2, zone: "West", function: "DB/W/14/LGT - L14 Tenant West Floor Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 199, tag: "DB/W/14/SP"                                               , base: 29800, type: "Modbus", daily: 2000174, monthly: 2000518, parent_id: 41, floor: "14th", column: 2, zone: "West", function: "DB/W/14/SP - L14 Tenant West Floor Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 200, tag: "DB/TOC/W/15/01"                                           , base: 29900, type: "Modbus", daily: 2000175, monthly: 2000519, parent_id: 41, floor: "15th", column: 2, zone: "West", function: "DB/TOC/W/15/01 - L15 Tenant West Floor Power", utility: "electricity", tenant: "Virgin Money", tenant_display: true },
    { id: 201, tag: "DB/TOC/W/15/02"                                           , base: 30000, type: "Modbus", daily: 2000176, monthly: 2000520, parent_id: 41, floor: "15th", column: 2, zone: "West", function: "DB/TOC/W/15/02 - L15 Tenant West Floor Power", utility: "electricity", tenant: "Virgin Money", tenant_display: true },
    { id: 202, tag: "DB/TOC/W/16/01"                                           , base: 30100, type: "Modbus", daily: 2000177, monthly: 2000521, parent_id: 41, floor: "16th", column: 2, zone: "West", function: "DB/TOC/W/16/01 - L16 Tenant West Floor Power", utility: "electricity", tenant: "KI Group Services", tenant_display: true },
    { id: 203, tag: "DB/TOC/W/16/02"                                           , base: 30200, type: "Modbus", daily: 2000178, monthly: 2000522, parent_id: 41, floor: "16th", column: 2, zone: "West", function: "DB/TOC/W/16/02 - L16 Tenant West Floor Power", utility: "electricity", tenant: "KI Group Services", tenant_display: true },
    { id: 204, tag: "DB/W/14/MER"                                              , base: 30300, type: "Modbus", daily: 2000173, monthly: 2000517, parent_id: 41, floor: "14th", column: 2, zone: "West", function: "DB/W/14/MER - L14 Tenant West MER Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 205, tag: "TDB/TOC/W/17/01"                                          , base: 30400, type: "Modbus", daily: 2000179, monthly: 2000523, parent_id: 41, floor: "17th", column: 2, zone: "West", function: "T/West FL17 - LTG/FCU - TDB/TOC/W/17/01", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 206, tag: "TDB/TOC/W/17/02"                                          , base: 30500, type: "Modbus", daily: 2000180, monthly: 2000524, parent_id: 41, floor: "17th", column: 2, zone: "West", function: "T/West FL17 - SP - TDB/TOC/W/17/02", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 207, tag: "TDB/TOC/W/18/01"                                          , base: 30600, type: "Modbus", daily: 2000181, monthly: 2000525, parent_id: 41, floor: "18th", column: 2, zone: "West", function: "T/West FL18 - LTG/FCU - TDB/TOC/W/18/01", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 208, tag: "TDB/TOC/W/18/02"                                          , base: 30700, type: "Modbus", daily: 2000182, monthly: 2000526, parent_id: 41, floor: "18th", column: 2, zone: "West", function: "T/West FL18 - SP - TDB/TOC/W/18/02", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 209, tag: "DB/TOC/W/19L"                                             , base: 30800, type: "Modbus", daily: 2000183, monthly: 2000527, parent_id: 42, floor: "19th", column: 2, zone: "West", function: "T/West FL19 - LTG/FCU - DB/TOC/W/19L", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 210, tag: "DB/TOC/W/19P"                                             , base: 30900, type: "Modbus", daily: 2000184, monthly: 2000528, parent_id: 42, floor: "19th", column: 2, zone: "West", function: "T/West FL19 - SP - DB/TOC/W/19P", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 211, tag: "DB/TOC/W/20L"                                             , base: 31000, type: "Modbus", daily: 2000186, monthly: 2000530, parent_id: 42, floor: "20th", column: 2, zone: "West", function: "T/West FL20 - LTG/FCU - DB/TOC/W/20L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 212, tag: "DB/TOC/W/20P"                                             , base: 31100, type: "Modbus", daily: 2000187, monthly: 2000531, parent_id: 42, floor: "20th", column: 2, zone: "West", function: "T/West FL20 - SP - DB/TOC/W/20P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 213, tag: "DB/TEN/W/C1"                                              , base: 31200, type: "Modbus", daily: 2000188, monthly: 2000532, parent_id: 42, floor: "21st", column: 2, zone: "West", function: "T/West FL21 - DB/TEN/W/C1 - DB/TEN/W/C1", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 214, tag: "DB/TOC/W/21L"                                             , base: 31300, type: "Modbus", daily: 2000189, monthly: 2000533, parent_id: 42, floor: "21st", column: 2, zone: "West", function: "T/West FL21 - LTG/FCU - DB/TOC/W/21L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 215, tag: "DB/TOC/W/21P"                                             , base: 31400, type: "Modbus", daily: 2000190, monthly: 2000534, parent_id: 42, floor: "21st", column: 2, zone: "West", function: "T/West FL21 - SP - DB/TOC/W/21P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 216, tag: "DB/TOC/W/22L"                                             , base: 31500, type: "Modbus", daily: 2000191, monthly: 2000535, parent_id: 42, floor: "22nd", column: 2, zone: "West", function: "T/West FL22 - LTG/FCU - DB/TOC/W/22L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 217, tag: "DB/TOC/W/22P"                                             , base: 31600, type: "Modbus", daily: 2000192, monthly: 2000536, parent_id: 42, floor: "22nd", column: 2, zone: "West", function: "T/West FL22 - SP - DB/TOC/W/22P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 218, tag: "DB/TOC/W/23L"                                             , base: 31700, type: "Modbus", daily: 2000193, monthly: 2000537, parent_id: 42, floor: "23rd", column: 2, zone: "West", function: "T/West FL23 - LTG/FCU - DB/TOC/W/23L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 219, tag: "DB/TOC/W/23P"                                             , base: 31800, type: "Modbus", daily: 2000194, monthly: 2000538, parent_id: 42, floor: "23rd", column: 2, zone: "West", function: "T/West FL23 - SP - DB/TOC/W/23P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 220, tag: "Input/ Output Panel A"                                    , base: 31900, type: "Modbus", daily: 2000185, monthly: 2000529, parent_id: 42, floor: "20th", column: 2, zone: "West", function: "T/West FL20 - Input/Output Panel A - I/O Panel A", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 221, tag: "T/West FL25 - Coms Room (Prim.)"                          , base: 32000, type: "Modbus", daily: 2000198, monthly: 2000542, parent_id: 42, floor: "25th", column: 2, zone: "West", function: "T/West FL25 - Coms Room (Prim.) -", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 222, tag: "T/West FL30 - COMMS"                                      , base: 32100, type: "Modbus", daily: 2000211, monthly: 2000555, parent_id: 80, floor: "30th", column: 2, zone: "West", function: "T/West FL30 - COMMS -", utility: "electricity", tenant: "Serve corp", tenant_display: true },
    { id: 223, tag: "T/West FL24 - LTG/FCU"                                    , base: 32200, type: "Modbus", daily: 2000195, monthly: 2000539, parent_id: 42, floor: "24th", column: 2, zone: "West", function: "T/West FL24 - LTG/FCU - DB/TOC/W/24L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 224, tag: "T/West FL24 - SP"                                         , base: 32300, type: "Modbus", daily: 2000197, monthly: 2000541, parent_id: 42, floor: "24th", column: 2, zone: "West", function: "T/West FL24 - SP - DB/TOC/W/24P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 225, tag: "T/West FL25 - LTG/FCU"                                    , base: 32400, type: "Modbus", daily: 2000199, monthly: 2000543, parent_id: 80, floor: "25th", column: 2, zone: "West", function: "T/West FL25 - LTG/FCU - DB/TOC/W/25/01", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 226, tag: "T/West FL25 - SP"                                         , base: 32500, type: "Modbus", daily: 2000200, monthly: 2000544, parent_id: 80, floor: "25th", column: 2, zone: "West", function: "T/West FL25 - SP - DB/TOC/W/25/02", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 227, tag: "T/West FL26 - LTG/FCU"                                    , base: 32600, type: "Modbus", daily: 2000201, monthly: 2000545, parent_id: 80, floor: "26th", column: 2, zone: "West", function: "T/West FL26 - LTG/FCU - TOC/W/26/01", utility: "electricity", tenant: "Aegon / Draft Kings", tenant_display: true },
    { id: 228, tag: "T/West FL26 - SP"                                         , base: 32700, type: "Modbus", daily: 2000202, monthly: 2000546, parent_id: 80, floor: "26th", column: 2, zone: "West", function: "T/West FL26 - SP - TOC/W/26/02", utility: "electricity", tenant: "Aegon / Draft Kings", tenant_display: true },
    { id: 229, tag: "T/West FL27 - LTG/FCU"                                    , base: 32800, type: "Modbus", daily: 2000204, monthly: 2000548, parent_id: 80, floor: "27th", column: 2, zone: "West", function: "T/West FL27 - LTG/FCU - DB/TOC/W/L/27", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 230, tag: "T/West FL27 - SP"                                         , base: 32900, type: "Modbus", daily: 2000205, monthly: 2000549, parent_id: 80, floor: "27th", column: 2, zone: "West", function: "T/West FL27 - SP - DB/TOC/W/P/27", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 231, tag: "T/West FL28 - LTG/FCU"                                    , base: 33000, type: "Modbus", daily: 2000206, monthly: 2000550, parent_id: 80, floor: "28th", column: 2, zone: "West", function: "T/West FL28 - LTG/FCU - DB/TOC/W/L/28", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 232, tag: "T/West FL28 - SP"                                         , base: 33100, type: "Modbus", daily: 2000207, monthly: 2000551, parent_id: 80, floor: "28th", column: 2, zone: "West", function: "T/West FL28 - SP - DB/TOC/W/P/28", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 233, tag: "T/West FL29 - LTG/FCU"                                    , base: 33200, type: "Modbus", daily: 2000209, monthly: 2000553, parent_id: 80, floor: "29th", column: 2, zone: "West", function: "T/West FL29 - LTG/FCU - DB/TOC/W/L/29", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 234, tag: "T/West FL29 - SP"                                         , base: 33300, type: "Modbus", daily: 2000210, monthly: 2000554, parent_id: 80, floor: "29th", column: 2, zone: "West", function: "T/West FL29 - SP - DB/TOC/W/P/29", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 235, tag: "T/West FL30 - LTG/FCU"                                    , base: 33400, type: "Modbus", daily: 2000212, monthly: 2000556, parent_id: 80, floor: "30th", column: 2, zone: "West", function: "T/West FL30 - LTG/FCU - DB/TOC/W/L/30", utility: "electricity", tenant: "Serve corp", tenant_display: true },
    { id: 236, tag: "T/West FL30 - SP"                                         , base: 33500, type: "Modbus", daily: 2000213, monthly: 2000557, parent_id: 80, floor: "30th", column: 2, zone: "West", function: "T/West FL30 - SP - DB/TOC/W/P/30", utility: "electricity", tenant: "Serve corp", tenant_display: true },
    { id: 237, tag: "T/West FL24 - Smoke Extract"                              , base: 33600, type: "Modbus", daily: 2000196, monthly: 2000540, parent_id: 42, floor: "24th", column: 2, zone: "West", function: "T/West FL24 - Smoke Extract -", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 238, tag: "T/West FL29 - Comms Room"                                 , base: 33700, type: "Modbus", daily: 2000208, monthly: 2000552, parent_id: 80, floor: "29th", column: 2, zone: "West", function: "T/West FL29 - Comms Room - DB/MER/PDU/A", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 239, tag: "T/West FL27 - LTG"                                        , base: 33800, type: "Modbus", daily: 2000203, monthly: 2000547, parent_id: 80, floor: "27th", column: 2, zone: "West", function: "T/West FL27 - LTG - DB/TOC/W/27-LTG", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 240, tag: "T/West FL31 - LTG/FCU"                                    , base: 33900, type: "Modbus", daily: 2000214, monthly: 2000558, parent_id: 80, floor: "31st", column: 2, zone: "West", function: "T/West FL31 - LTG/FCU - DB/L31/W/02", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 241, tag: "T/West FL31 - SP"                                         , base: 34000, type: "Modbus", daily: 2000215, monthly: 2000559, parent_id: 80, floor: "31st", column: 2, zone: "West", function: "T/West FL31 - SP - DB/L31/W/01", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 242, tag: "T/West FL32 - LTG/FCU"                                    , base: 34100, type: "Modbus", daily: 2000217, monthly: 2000561, parent_id: 80, floor: "32nd", column: 2, zone: "West", function: "T/West FL32 - LTG/FCU", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 243, tag: "T/West FL32 - SP"                                         , base: 34200, type: "Modbus", daily: 2000218, monthly: 2000562, parent_id: 80, floor: "32nd", column: 2, zone: "West", function: "T/West FL32 - SP", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 244, tag: "T/West FL33 - DB33-1-PWR"                                 , base: 34300, type: "Modbus", daily: 2000221, monthly: 2000565, parent_id: 80, floor: "33rd", column: 2, zone: "West", function: "T/West FL33 - DB33-1-PWR", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 245, tag: "T/West FL33 - DB33-1-LTG"                                 , base: 34400, type: "Modbus", daily: 2000219, monthly: 2000563, parent_id: 80, floor: "33rd", column: 2, zone: "West", function: "T/West FL33 - DB33-1-LTG", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 246, tag: "T/West FL33 - SP"                                         , base: 34500, type: "Modbus", daily: 2000223, monthly: 2000567, parent_id: 80, floor: "33rd", column: 2, zone: "West", function: "T/West FL33 - SP", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 247, tag: "T/West FL34 - LTG/FCU"                                    , base: 34600, type: "Modbus", daily: 2000225, monthly: 2000569, parent_id: 80, floor: "34th", column: 2, zone: "West", function: "T/West FL34 - LTG/FCU", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 248, tag: "T/West FL34 - SP"                                         , base: 34700, type: "Modbus", daily: 2000226, monthly: 2000570, parent_id: 80, floor: "34th", column: 2, zone: "West", function: "T/West FL34 - SP", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 249, tag: "T/West FL35 - LTG/FCU"                                    , base: 34800, type: "Modbus", daily: 2000227, monthly: 2000571, parent_id: 80, floor: "35th", column: 2, zone: "West", function: "T/West FL35 - LTG/FCU - DB/W/L/LV35", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 250, tag: "T/West FL35 - SP"                                         , base: 34900, type: "Modbus", daily: 2000228, monthly: 2000572, parent_id: 80, floor: "35th", column: 2, zone: "West", function: "T/West FL35 - SP - DB/W/P/LV35", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 251, tag: "T/West FL36 - SP/LTG"                                     , base: 35000, type: "Modbus", daily: 2000230, monthly: 2000574, parent_id: 80, floor: "36th", column: 2, zone: "West", function: "T/West FL36 - SP/LTG - L36-TO-EDB-LP2", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 252, tag: "T/WEST FL36 - Comms B"                                    , base: 35100, type: "Modbus", daily: 2000229, monthly: 2000573, parent_id: 80, floor: "36th", column: 2, zone: "West", function: "T/WEST FL36 - Comms B - L36-TO-WIOB-B", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 253, tag: "T/West FL37 - West Total"                                 , base: 35200, type: "Modbus", daily: 2000233, monthly: 2000577, parent_id: 80, floor: "37th", column: 2, zone: "West", function: "T/West FL37 - West Total - L37 FCU/AHU Luminaire", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 254, tag: "T/West FL38 - West Total"                                 , base: 35300, type: "Modbus", daily: 2000237, monthly: 2000581, parent_id: 80, floor: "38th", column: 2, zone: "West", function: "T/West FL38 - West Total - L38 FCU/7HU Luminaire", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 255, tag: "FL35 UPS A  Meter 1"                                      , base: 35400, type: "Modbus", daily:       0, monthly:       0, parent_id: 80, floor: "35th", column: 2, zone: "West", function: "FL35 UPS A  Meter 1 - DB/PDU/35/A", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 256, tag: "FL35 UPS A  Meter 2"                                      , base: 35500, type: "Modbus", daily:       0, monthly:       0, parent_id: 80, floor: "35th", column: 2, zone: "West", function: "FL35 UPS A  Meter 2 - DB/PDU/35/A", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 257, tag: "T/West FL34 - Comms Room"                                 , base: 35600, type: "Modbus", daily: 2000224, monthly: 2000568, parent_id: 80, floor: "34th", column: 2, zone: "West", function: "T/West FL34 - Comms Room", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 258, tag: "T/West FL33 - DB33-1-MECH"                                , base: 35700, type: "Modbus", daily: 2000220, monthly: 2000564, parent_id: 80, floor: "33rd", column: 2, zone: "West", function: "T/West FL33 - DB33-1-MECH", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 259, tag: "T/West FL33 - DB33-1-UPS"                                 , base: 35800, type: "Modbus", daily: 2000222, monthly: 2000566, parent_id: 80, floor: "33rd", column: 2, zone: "West", function: "T/West FL33 - DB33-1-UPS", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 260, tag: "T/West FL37 - FCU"                                        , base: 35900, type: "Modbus", daily: 2000231, monthly: 2000575, parent_id: 80, floor: "37th", column: 2, zone: "West", function: "T/West FL37 - FCU", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 261, tag: "T/West FL37 - LTG"                                        , base: 36000, type: "Modbus", daily: 2000232, monthly: 2000576, parent_id: 80, floor: "37th", column: 2, zone: "West", function: "T/West FL37 - LTG", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 262, tag: "T/West FL38 - FCU"                                        , base: 36100, type: "Modbus", daily: 2000234, monthly: 2000578, parent_id: 80, floor: "38th", column: 2, zone: "West", function: "T/West FL38 - FCU", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 263, tag: "T/West FL38 - SP/LTG"                                     , base: 36200, type: "Modbus", daily: 2000236, monthly: 2000580, parent_id: 80, floor: "38th", column: 2, zone: "West", function: "T/West FL38 - SP/LTG", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 264, tag: "T/West FL38 - Kitchen"                                    , base: 36300, type: "Modbus", daily: 2000235, monthly: 2000579, parent_id: 80, floor: "38th", column: 2, zone: "West", function: "T/West FL38 - Kitchen", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 265, tag: "T/West FL32 - Comms Room (Sec.)"                          , base: 36400, type: "Modbus", daily: 2000216, monthly: 2000560, parent_id: 80, floor: "32nd", column: 2, zone: "West", function: "T/West FL32 - Comms Room (Sec.)", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 266, tag: "T/West FL41 - Comms Room"                                 , base: 36500, type: "Modbus", daily: 2000242, monthly: 2000586, parent_id: 80, floor: "41st", column: 2, zone: "West", function: "T/West FL41 - Comms Room", utility: "electricity", tenant: "FM Global" },
    { id: 267, tag: "T/West FL39 - LTG/FCU"                                    , base: 36600, type: "Modbus", daily: 2000238, monthly: 2000582, parent_id: 80, floor: "39th", column: 2, zone: "West", function: "T/West FL39 - LTG/FCU - DB/TOC/W/39/01", utility: "electricity", tenant: "Brit Insurance" },
    { id: 268, tag: "T/West FL39 - SP"                                         , base: 36700, type: "Modbus", daily: 2000239, monthly: 2000583, parent_id: 80, floor: "39th", column: 2, zone: "West", function: "T/West FL39 - SP - DB/TOC/W/39/02", utility: "electricity", tenant: "Brit Insurance" },
    { id: 269, tag: "T/West FL40 - LTG/FCU"                                    , base: 36800, type: "Modbus", daily: 2000240, monthly: 2000584, parent_id: 80, floor: "40th", column: 2, zone: "West", function: "T/West FL40 - LTG/FCU - TDB/TOC/W/40/02", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 270, tag: "T/West FL40 - SP"                                         , base: 36900, type: "Modbus", daily: 2000241, monthly: 2000585, parent_id: 80, floor: "40th", column: 2, zone: "West", function: "T/West FL40 - SP - TDB/TOC/W/40/01", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 271, tag: "T/West FL41 - LTG/FCU"                                    , base: 37000, type: "Modbus", daily: 2000243, monthly: 2000587, parent_id: 80, floor: "41st", column: 2, zone: "West", function: "T/West FL41 - LTG/FCU", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 272, tag: "T/West FL41 - SP"                                         , base: 37100, type: "Modbus", daily: 2000244, monthly: 2000588, parent_id: 80, floor: "41st", column: 2, zone: "West", function: "T/West FL41 - SP", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 273, tag: "T/West FL42 - DB2"                                        , base: 37200, type: "Modbus", daily: 2000245, monthly: 2000589, parent_id: 80, floor: "42nd", column: 2, zone: "West", function: "T/West FL42 - DB2", utility: "electricity", tenant: "Xcite", tenant_display: true },
    { id: 274, tag: "T/West FL43 - LTG/FCU"                                    , base: 37300, type: "Modbus", daily: 2000246, monthly: 2000590, parent_id: 80, floor: "43rd", column: 2, zone: "West", function: "T/West FL43 - LTG/FCU", utility: "electricity", tenant: "Petredec", tenant_display: true },
    { id: 275, tag: "T/West FL43 - SP"                                         , base: 37400, type: "Modbus", daily: 2000247, monthly: 2000591, parent_id: 80, floor: "43rd", column: 2, zone: "West", function: "T/West FL43 - SP", utility: "electricity", tenant: "Petredec", tenant_display: true },
    { id: 276, tag: "T/West FL44 - SP"                                         , base: 37500, type: "Modbus", daily: 2000248, monthly: 2000592, parent_id: 80, floor: "44th", column: 2, zone: "West", function: "T/West FL44 - SP", utility: "electricity", tenant: "Affinity Shipping", tenant_display: true },
    { id: 277, tag: "T/West FL45 - LTG"                                        , base: 37600, type: "Modbus", daily: 2000249, monthly: 2000593, parent_id: 80, floor: "45th", column: 2, zone: "West", function: "T/West FL45 - LTG - DB/TOC/W/45L", utility: "electricity", tenant: "D-Tek", tenant_display: true },
    { id: 278, tag: "T/West FL45 - SP"                                         , base: 37700, type: "Modbus", daily: 2000251, monthly: 2000595, parent_id: 80, floor: "45th", column: 2, zone: "West", function: "T/West FL45 - SP - DB/TOC/W/45P", utility: "electricity", tenant: "D-Tek", tenant_display: true },
    { id: 279, tag: "FL40 - Kitchen"                                           , base: 37800, type: "Modbus", daily:       0, monthly:       0, parent_id: 80, floor: "40th", column: 2, zone: "West", function: "FL40 - Kitchen", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 280, tag: "T/West FL45 - MCC"                                        , base: 37900, type: "Modbus", daily: 2000250, monthly: 2000594, parent_id: 80, floor: "45th", column: 2, zone: "West", function: "T/West FL45 - MCC", utility: "electricity", tenant: "D-Tek", tenant_display: true },
    { id: 281, tag: "DB/TOC/E/04"                                              , base: 38000, type: "Modbus", daily: 2000076, monthly: 2000420, parent_id: 43, floor: "4th", column: 0, zone: "East", function: "DB/TOC/E/04 - L04 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 282, tag: "DB/TOC/E/05"                                              , base: 38100, type: "Modbus", daily: 2000077, monthly: 2000421, parent_id: 43, floor: "5th", column: 0, zone: "East", function: "DB/TOC/E/05 - L05 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 283, tag: "DB/TOC/E/06"                                              , base: 38200, type: "Modbus", daily: 2000079, monthly: 2000423, parent_id: 43, floor: "6th", column: 0, zone: "East", function: "DB/TOC/E/06 - L06 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 284, tag: "DB/KP/5-5R"                                               , base: 38300, type: "Modbus", daily: 2000078, monthly: 2000422, parent_id: 43, floor: "6th", column: 0, zone: "East", function: "DB/KP/5-5R - L05 Tenant Kitchen Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 285, tag: "DB/TOC/E/07"                                              , base: 38400, type: "Modbus", daily: 2000080, monthly: 2000424, parent_id: 43, floor: "7th", column: 0, zone: "East", function: "DB/TOC/E/07 - L07 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 286, tag: "DB/TOC/E/08"                                              , base: 38500, type: "Modbus", daily: 2000081, monthly: 2000425, parent_id: 43, floor: "8th", column: 0, zone: "East", function: "DB/TOC/E/08 - L08 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 287, tag: "DB/TOC/E/09"                                              , base: 38600, type: "Modbus", daily: 2000082, monthly: 2000426, parent_id: 43, floor: "9th", column: 0, zone: "East", function: "DB/TOC/E/09 - L09 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 288, tag: "DB/TOC/E/10"                                              , base: 38700, type: "Modbus", daily: 2000083, monthly: 2000427, parent_id: 43, floor: "10th", column: 0, zone: "East", function: "DB/TOC/E/10 - L10 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 289, tag: "DB/KP/10-10R"                                             , base: 38800, type: "Modbus", daily: 2000084, monthly: 2000428, parent_id: 43, floor: "10th", column: 0, zone: "East", function: "DB/KP/10-10R - L10 Tenant Kitchen Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 290, tag: "DB/LP2"                                                   , base: 38900, type: "Modbus", daily: 2000074, monthly: 2000418, parent_id: 43, floor: "3rd", column: 0, zone: "East", function: "DB/LP2 - L03 Restaurant Power", utility: "electricity", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 291, tag: "DB/LP3"                                                   , base: 39000, type: "Modbus", daily: 2000075, monthly: 2000419, parent_id: 43, floor: "3rd", column: 0, zone: "East", function: "DB/LP3 - L03 Restaurant Power", utility: "electricity", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 292, tag: "DB/TOC/E/11"                                              , base: 39100, type: "Modbus", daily: 2000085, monthly: 2000429, parent_id: 43, floor: "11th", column: 0, zone: "East", function: "DB/TOC/E/11 - L11 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 293, tag: "DB/TOC/E/12"                                              , base: 39200, type: "Modbus", daily: 2000086, monthly: 2000430, parent_id: 43, floor: "12th", column: 0, zone: "East", function: "DB/TOC/E/12 - L12 Tenant East Floor Power", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 294, tag: "DB/TOC/E/13"                                              , base: 39300, type: "Modbus", daily: 2000087, monthly: 2000431, parent_id: 43, floor: "13th", column: 0, zone: "East", function: "DB/TOC/E/13 - L13 Tenant East Floor Power", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 295, tag: "DB/E/14/LGT"                                              , base: 39400, type: "Modbus", daily: 2000088, monthly: 2000432, parent_id: 43, floor: "14th", column: 0, zone: "East", function: "DB/E/14/LGT - L14 Tenant East Floor Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 296, tag: "DB/E/14/SP"                                               , base: 39500, type: "Modbus", daily: 2000090, monthly: 2000434, parent_id: 43, floor: "14th", column: 0, zone: "East", function: "DB/E/14/SP - L14 Tenant East Floor Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 297, tag: "DB/TOC/E/15/01"                                           , base: 39600, type: "Modbus", daily: 2000091, monthly: 2000435, parent_id: 43, floor: "15th", column: 0, zone: "East", function: "DB/TOC/E/15/01 - L15 Tenant East Floor Power", utility: "electricity", tenant: "Virgin Money", tenant_display: true },
    { id: 298, tag: "DB/TOC/E/15/02"                                           , base: 39700, type: "Modbus", daily: 2000092, monthly: 2000436, parent_id: 43, floor: "15th", column: 0, zone: "East", function: "DB/TOC/E/15/02 - L15 Tenant East Floor Power", utility: "electricity", tenant: "Virgin Money", tenant_display: true },
    { id: 299, tag: "DB/TOC/E/16/01"                                           , base: 39800, type: "Modbus", daily: 2000094, monthly: 2000438, parent_id: 43, floor: "16th", column: 0, zone: "East", function: "DB/TOC/E/16/01 - L16 Tenant East Floor Power", utility: "electricity", tenant: "KI Group Services", tenant_display: true },
    { id: 300, tag: "DB/TOC/E/16/02"                                           , base: 39900, type: "Modbus", daily: 2000095, monthly: 2000439, parent_id: 43, floor: "16th", column: 0, zone: "East", function: "DB/TOC/E/16/02 - L16 Tenant East Floor Power", utility: "electricity", tenant: "KI Group Services", tenant_display: true },
    { id: 301, tag: "DB/COMMS/16/A"                                            , base: 40000, type: "Modbus", daily: 2000093, monthly: 2000437, parent_id: 43, floor: "16th", column: 0, zone: "East", function: "DB/COMMS/16/A - L16 Tenant East COMMS Rm Power", utility: "electricity", tenant: "KI Group Services", tenant_display: true },
    { id: 302, tag: "DB/E/14/MER"                                              , base: 40100, type: "Modbus", daily: 2000089, monthly: 2000433, parent_id: 43, floor: "14th", column: 0, zone: "East", function: "DB/E/14/MER - L14 Tenant East MER Power", utility: "electricity", tenant: "RSH&P", tenant_display: true },
    { id: 303, tag: "TDB/TOC/E/17/01"                                          , base: 40200, type: "Modbus", daily: 2000097, monthly: 2000441, parent_id: 43, floor: "17th", column: 0, zone: "East", function: "T/East FL17 - LTG/FCU - TDB/TOC/E/17/01", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 304, tag: "TDB/TOC/E/17/02"                                          , base: 40300, type: "Modbus", daily: 2000098, monthly: 2000442, parent_id: 43, floor: "17th", column: 0, zone: "East", function: "T/East FL17 - SP - TDB/TOC/E/17/02", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 305, tag: "TDB/TOC/E/18/01"                                          , base: 40400, type: "Modbus", daily: 2000100, monthly: 2000444, parent_id: 43, floor: "18th", column: 0, zone: "East", function: "T/East FL18 - LTG/FCU - TDB/TOC/E/18/01", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 306, tag: "TDB/TOC/E/18/02"                                          , base: 40500, type: "Modbus", daily: 2000101, monthly: 2000445, parent_id: 43, floor: "18th", column: 0, zone: "East", function: "T/East FL18 - SP - TDB/TOC/E/18/02", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 307, tag: "DB/TOC/E/19L"                                             , base: 40600, type: "Modbus", daily: 2000102, monthly: 2000446, parent_id: 44, floor: "19th", column: 0, zone: "East", function: "T/East FL19 - LTG/FCU - DB/TOC/E/19L", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 308, tag: "DB/TOC/E/19P"                                             , base: 40700, type: "Modbus", daily: 2000103, monthly: 2000447, parent_id: 44, floor: "19th", column: 0, zone: "East", function: "T/East FL19 - SP - DB/TOC/E/19P", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 309, tag: "DB/TOC/E/20L"                                             , base: 40800, type: "Modbus", daily: 2000105, monthly: 2000449, parent_id: 44, floor: "20th", column: 0, zone: "East", function: "T/East FL20 - LTG/FCU - DB/TOC/E/20L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 310, tag: "DB/TOC/E/20P"                                             , base: 40900, type: "Modbus", daily: 2000106, monthly: 2000450, parent_id: 44, floor: "20th", column: 0, zone: "East", function: "T/East FL20 - SP - DB/TOC/E/20P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 311, tag: "DB/TOC/E/21L"                                             , base: 41000, type: "Modbus", daily: 2000108, monthly: 2000452, parent_id: 44, floor: "21st", column: 0, zone: "East", function: "T/East FL21 - LTG/FCU - DB/TOC/E/21L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 312, tag: "DB/TOC/E/21P"                                             , base: 41100, type: "Modbus", daily: 2000109, monthly: 2000453, parent_id: 44, floor: "21st", column: 0, zone: "East", function: "T/East FL21 - SP - DB/TOC/E/21P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 313, tag: "DB/TOC/E/22L"                                             , base: 41200, type: "Modbus", daily: 2000110, monthly: 2000454, parent_id: 44, floor: "22nd", column: 0, zone: "East", function: "T/East FL22 - LTG/FCU - DB/TOC/E/22L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 314, tag: "DB/TOC/E/22P"                                             , base: 41300, type: "Modbus", daily: 2000111, monthly: 2000455, parent_id: 44, floor: "22nd", column: 0, zone: "East", function: "T/East FL22 - SP - DB/TOC/E/22P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 315, tag: "DB/TOC/E/23L"                                             , base: 41400, type: "Modbus", daily: 2000112, monthly: 2000456, parent_id: 44, floor: "23rd", column: 0, zone: "East", function: "T/East FL23 - LTG/FCU - DB/TOC/E/23L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 316, tag: "DB/TOC/E/23P"                                             , base: 41500, type: "Modbus", daily: 2000113, monthly: 2000457, parent_id: 44, floor: "23rd", column: 0, zone: "East", function: "T/East FL23 - SP - DB/TOC/E/23P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 317, tag: "Input/ Output Panel B"                                    , base: 41600, type: "Modbus", daily: 2000104, monthly: 2000448, parent_id: 44, floor: "20th", column: 0, zone: "East", function: "T/East FL20 - Input/Output Panel B - I/O Panel A", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 318, tag: "TDB/COMMS/17/A"                                           , base: 41700, type: "Modbus", daily: 2000096, monthly: 2000440, parent_id: 44, floor: "17th", column: 0, zone: "East", function: "T/East FL17 - Comms Room - TDB/COMMS/17/A", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 319, tag: "TDB/COMMS/18/A"                                           , base: 41800, type: "Modbus", daily: 2000099, monthly: 2000443, parent_id: 44, floor: "18th", column: 0, zone: "East", function: "T/East FL18 - Comms Room - TDB/COMMS/18/A", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 320, tag: "DB/TEN/E/C2"                                              , base: 41900, type: "Modbus", daily: 2000107, monthly: 2000451, parent_id: 44, floor: "21st", column: 0, zone: "East", function: "T/East FL21 - DB/TEN/E/C2 - DB/TEN/E/C2", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 321, tag: "T/East FL25 - Coms Room (Sec.)"                           , base: 42000, type: "Modbus", daily: 2000118, monthly: 2000462, parent_id: 93, floor: "25th", column: 0, zone: "East", function: "T/East FL25 - Coms Room (Sec.) -", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 322, tag: "T/East FL24 - LTG/FCU"                                    , base: 42100, type: "Modbus", daily: 2000115, monthly: 2000459, parent_id: 44, floor: "24th", column: 0, zone: "East", function: "T/East FL24 - LTG/FCU - DB/TOC/E/24L", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 323, tag: "T/East FL24 - SP"                                         , base: 42200, type: "Modbus", daily: 2000117, monthly: 2000461, parent_id: 44, floor: "24th", column: 0, zone: "East", function: "T/East FL24 - SP - DB/TOC/E/24P", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 324, tag: "T/East FL25 - LTG/FCU"                                    , base: 42300, type: "Modbus", daily: 2000119, monthly: 2000463, parent_id: 93, floor: "25th", column: 0, zone: "East", function: "T/East FL25 - LTG/FCU - DB/TOC/E/25/01", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 325, tag: "T/East FL25 - SP"                                         , base: 42400, type: "Modbus", daily: 2000120, monthly: 2000464, parent_id: 93, floor: "25th", column: 0, zone: "East", function: "T/East FL25 - SP - DB/TOC/E/25/02", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 326, tag: "T/East FL26 - LTG/FCU"                                    , base: 42500, type: "Modbus", daily: 2000121, monthly: 2000465, parent_id: 93, floor: "26th", column: 0, zone: "East", function: "T/East FL26 - LTG/FCU - DB/TOC/E/26/01", utility: "electricity", tenant: "Aegon / Draft Kings", tenant_display: true },
    { id: 327, tag: "T/East FL26 - SP"                                         , base: 42600, type: "Modbus", daily: 2000122, monthly: 2000466, parent_id: 93, floor: "26th", column: 0, zone: "East", function: "T/East FL26 - SP - DB/TOC/E/26/02", utility: "electricity", tenant: "Aegon / Draft Kings", tenant_display: true },
    { id: 328, tag: "T/East FL27 - LTG/FCU"                                    , base: 42700, type: "Modbus", daily: 2000124, monthly: 2000468, parent_id: 93, floor: "27th", column: 0, zone: "East", function: "T/East FL27 - LTG/FCU - DB/TOC/E/27L", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 329, tag: "T/East FL27 - SP"                                         , base: 42800, type: "Modbus", daily: 2000125, monthly: 2000469, parent_id: 93, floor: "27th", column: 0, zone: "East", function: "T/East FL27 - SP - DB/TOC/E/27P", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 330, tag: "T/East FL28 - LTG/FCU"                                    , base: 42900, type: "Modbus", daily: 2000126, monthly: 2000470, parent_id: 93, floor: "28th", column: 0, zone: "East", function: "T/East FL28 - LTG/FCU - DB/TOC/E/L/28", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 331, tag: "T/East FL28 - SP"                                         , base: 43000, type: "Modbus", daily: 2000127, monthly: 2000471, parent_id: 93, floor: "28th", column: 0, zone: "East", function: "T/East FL28 - SP - DB/TOC/E/P/28", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 332, tag: "T/East FL29 - LTG/FCU"                                    , base: 43100, type: "Modbus", daily: 2000128, monthly: 2000472, parent_id: 93, floor: "29th", column: 0, zone: "East", function: "T/East FL29 - LTG/FCU - DB/TOC/E/L/29", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 333, tag: "T/East FL29 - SP"                                         , base: 43200, type: "Modbus", daily: 2000129, monthly: 2000473, parent_id: 93, floor: "29th", column: 0, zone: "East", function: "T/East FL29 - SP - DB/TOC/E/P/29", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 334, tag: "T/East FL30 - LTG/FCU"                                    , base: 43300, type: "Modbus", daily: 2000131, monthly: 2000475, parent_id: 93, floor: "30th", column: 0, zone: "East", function: "T/East FL30 - LTG/FCU - DB/TL/30/E", utility: "electricity", tenant: "Serve corp", tenant_display: true },
    { id: 335, tag: "T/East FL30 - SP"                                         , base: 43400, type: "Modbus", daily: 2000132, monthly: 2000476, parent_id: 93, floor: "30th", column: 0, zone: "East", function: "T/East FL30 - SP - DB/TP/30/E", utility: "electricity", tenant: "Serve corp", tenant_display: true },
    { id: 336, tag: "T/East FL24 - Smoke Extract"                              , base: 43500, type: "Modbus", daily: 2000116, monthly: 2000460, parent_id: 44, floor: "24th", column: 0, zone: "East", function: "T/East FL24 - Smoke Extract - Smoke Extract", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 337, tag: "T/East FL24 - DB/TOC/E/24PP"                              , base: 43600, type: "Modbus", daily: 2000114, monthly: 2000458, parent_id: 44, floor: "24th", column: 0, zone: "East", function: "T/East FL24 - DB/TOC/E/24PP - DB/TOC/E/24PP", utility: "electricity", tenant: "MS Amlin", tenant_display: true },
    { id: 338, tag: "T/East FL29 -Comms Room"                                  , base: 43700, type: "Modbus", daily: 2000130, monthly: 2000474, parent_id: 93, floor: "29th", column: 0, zone: "East", function: "T/East FL29 -Comms Room - DB/KICHEN/L28", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 339, tag: "T/East FL27 - LTG"                                        , base: 43800, type: "Modbus", daily: 2000123, monthly: 2000467, parent_id: 93, floor: "27th", column: 0, zone: "East", function: "T/East FL27 - LTG - DB/TOC/E/27-LTG", utility: "electricity", tenant: "OMERS", tenant_display: true },
    { id: 340, tag: "T/East FL31 - LTG/FCU"                                    , base: 43900, type: "Modbus", daily: 2000133, monthly: 2000477, parent_id: 93, floor: "31st", column: 0, zone: "East", function: "T/East FL31 - LTG/FCU - DB/L31/W/UPS", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 341, tag: "T/East FL31 - SP"                                         , base: 44000, type: "Modbus", daily: 2000134, monthly: 2000478, parent_id: 93, floor: "31st", column: 0, zone: "East", function: "T/East FL31 - SP - DB/L31/MCCB", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 342, tag: "T/East FL32 - LTG/FCU"                                    , base: 44100, type: "Modbus", daily: 2000136, monthly: 2000480, parent_id: 93, floor: "32nd", column: 0, zone: "East", function: "T/East FL32 - LTG/FCU - DB/TOC/W/01L", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 343, tag: "T/East FL32 - SP"                                         , base: 44200, type: "Modbus", daily: 2000137, monthly: 2000481, parent_id: 93, floor: "32nd", column: 0, zone: "East", function: "T/East FL32 - SP - DB/TOC/W/32/02", utility: "electricity", tenant: "Quadrature" },
    { id: 344, tag: "T/East FL33 - SP"                                         , base: 44300, type: "Modbus", daily: 2000138, monthly: 2000482, parent_id: 93, floor: "33rd", column: 0, zone: "East", function: "T/East FL33 - SP - DB/34/EL", utility: "electricity", tenant: "Quadrature" },
    { id: 345, tag: "T/East FL34 - LTG/FCU"                                    , base: 44400, type: "Modbus", daily: 2000140, monthly: 2000484, parent_id: 93, floor: "34th", column: 0, zone: "East", function: "T/East FL34 - LTG/FCU - DB/34/EP", utility: "electricity", tenant: "Quadrature" },
    { id: 346, tag: "T/East FL34 - SP"                                         , base: 44500, type: "Modbus", daily: 2000141, monthly: 2000485, parent_id: 93, floor: "34th", column: 0, zone: "East", function: "T/East FL34 - SP - DB/E/L/LV35", utility: "electricity", tenant: "Quadrature" },
    { id: 347, tag: "T/East FL35 - LTG/FCU"                                    , base: 44600, type: "Modbus", daily: 2000142, monthly: 2000486, parent_id: 93, floor: "35th", column: 0, zone: "East", function: "T/East FL35 - LTG/FCU - DB/E/P/LV35", utility: "electricity", tenant: "DRW" },
    { id: 348, tag: "T/East FL35 - SP"                                         , base: 44700, type: "Modbus", daily: 2000143, monthly: 2000487, parent_id: 93, floor: "35th", column: 0, zone: "East", function: "T/East FL35 - SP - L36-TO-WDB-LP1", utility: "electricity", tenant: "DRW" },
    { id: 349, tag: "T/East FL36 - SP + LTG"                                   , base: 44800, type: "Modbus", daily: 2000145, monthly: 2000489, parent_id: 93, floor: "36th", column: 0, zone: "East", function: "T/East FL36 - SP + LTG - DB/W/UPS/LV36", utility: "electricity", tenant: "DRW" },
    { id: 350, tag: "T/East FL36 - Comms A"                                    , base: 44900, type: "Modbus", daily: 2000144, monthly: 2000488, parent_id: 93, floor: "36th", column: 0, zone: "East", function: "T/East FL36 - Comms A", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 351, tag: "T/East FL37 - SP"                                         , base: 45000, type: "Modbus", daily: 2000146, monthly: 2000490, parent_id: 93, floor: "37th", column: 0, zone: "East", function: "T/East FL37 - SP", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 352, tag: "T/East FL38 - SP"                                         , base: 45100, type: "Modbus", daily: 2000147, monthly: 2000491, parent_id: 93, floor: "38th", column: 0, zone: "East", function: "T/East FL38 - SP", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 353, tag: "T/East FL34 - Comms Room"                                 , base: 45200, type: "Modbus", daily: 2000139, monthly: 2000483, parent_id: 93, floor: "34th", column: 0, zone: "East", function: "T/East FL34 - Comms Room - DB/34/EIT", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 354, tag: "T/East FL32 - Comms Room (Prim.)"                         , base: 45300, type: "Modbus", daily: 2000135, monthly: 2000479, parent_id: 93, floor: "32nd", column: 0, zone: "East", function: "T/East FL32 - Comms Room (Prim.) - ATS Secondary", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 355, tag: "FL33 DB/L33/K"                                            , base: 45400, type: "Modbus", daily:       0, monthly:       0, parent_id: 93, floor: "33rd", column: 0, zone: "East", function: "FL33 DB/L33/K - ATS Primary", utility: "electricity", tenant: "Quadrature", tenant_display: true },
    { id: 356, tag: "FL35 UPS B Meter 1"                                       , base: 45500, type: "Modbus", daily:       0, monthly:       0, parent_id: 93, floor: "35th", column: 0, zone: "East", function: "FL35 UPS B Meter 1 - DB/PDU/35/B", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 357, tag: "FL35 UPS B Meter 2"                                       , base: 45600, type: "Modbus", daily:       0, monthly:       0, parent_id: 93, floor: "35th", column: 0, zone: "East", function: "FL35 UPS B Meter 2 - DB/PDU/35/B", utility: "electricity", tenant: "DRW", tenant_display: true },
    { id: 358, tag: "T/East FL39 - LTG/FCU"                                    , base: 45700, type: "Modbus", daily: 2000149, monthly: 2000493, parent_id: 93, floor: "39th", column: 0, zone: "East", function: "T/East FL39 - LTG/FCU - DB/TOC/E/39/02", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 359, tag: "T/East FL39 - SP"                                         , base: 45800, type: "Modbus", daily: 2000150, monthly: 2000494, parent_id: 93, floor: "39th", column: 0, zone: "East", function: "T/East FL39 - SP - DB/TOC/E/39/01", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 360, tag: "T/East FL40 - LTG/FCU"                                    , base: 45900, type: "Modbus", daily: 2000151, monthly: 2000495, parent_id: 93, floor: "40th", column: 0, zone: "East", function: "T/East FL40 - LTG/FCU - DB/TOC/E/40/02", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 361, tag: "T/East FL40 - SP"                                         , base: 46000, type: "Modbus", daily: 2000152, monthly: 2000496, parent_id: 93, floor: "40th", column: 0, zone: "East", function: "T/East FL40 - SP - DB/TOC/E/40/01", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 362, tag: "T/East FL41 - LTG/FCU"                                    , base: 46100, type: "Modbus", daily: 2000153, monthly: 2000497, parent_id: 93, floor: "41st", column: 0, zone: "East", function: "T/East FL41 - LTG/FCU - DB/TOC/E/41/02", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 363, tag: "T/East FL41 - SP"                                         , base: 46200, type: "Modbus", daily: 2000154, monthly: 2000498, parent_id: 93, floor: "41st", column: 0, zone: "East", function: "T/East FL41 - SP - DB/TOC/E/41/01", utility: "electricity", tenant: "FM Global", tenant_display: true },
    { id: 364, tag: "T/East FL39 - Comms Room"                                 , base: 46300, type: "Modbus", daily: 2000148, monthly: 2000492, parent_id: 93, floor: "39th", column: 0, zone: "East", function: "T/East FL39 - Comms Room", utility: "electricity", tenant: "Brit Insurance", tenant_display: true },
    { id: 365, tag: "T/East FL42 - DB1"                                        , base: 46400, type: "Modbus", daily: 2000155, monthly: 2000499, parent_id: 93, floor: "42nd", column: 0, zone: "East", function: "T/East FL42 - DB1", utility: "electricity", tenant: "Xcite", tenant_display: true },
    { id: 366, tag: "T/East FL43 - LTG/FCU"                                    , base: 46500, type: "Modbus", daily: 2000157, monthly: 2000501, parent_id: 93, floor: "43rd", column: 0, zone: "East", function: "T/East FL43 - LTG/FCU", utility: "electricity", tenant: "Petredec", tenant_display: true },
    { id: 367, tag: "T/East FL43 - SP"                                         , base: 46600, type: "Modbus", daily: 2000158, monthly: 2000502, parent_id: 93, floor: "43rd", column: 0, zone: "East", function: "T/East FL43 - SP", utility: "electricity", tenant: "Petredec", tenant_display: true },
    { id: 368, tag: "T/East FL42 - Spare"                                      , base: 46700, type: "Modbus", daily: 2000156, monthly: 2000500, parent_id: 93, floor: "42nd", column: 0, zone: "East", function: "T/East FL42 - Spare", utility: "electricity", tenant: "Xcite", tenant_display: true },
    { id: 369, tag: "T/East FL44 - SP"                                         , base: 46800, type: "Modbus", daily: 2000159, monthly: 2000503, parent_id: 93, floor: "44th", column: 0, zone: "East", function: "T/East FL44 - SP - DB/44/EC/TSP", utility: "electricity", tenant: "Affinity Shipping", tenant_display: true },
    { id: 370, tag: "T/East FL45 - SP"                                         , base: 46900, type: "Modbus", daily: 2000160, monthly: 2000504, parent_id: 93, floor: "45th", column: 0, zone: "East", function: "T/East FL45 - SP - DB/TOC/E/45MK", utility: "electricity", tenant: "D-Tek", tenant_display: true },
    { id: 371, tag: "LV03 - EDF HV SW Room 1 - 2"                              , base: 47000, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "LV03 - EDF HV SW Room 1 - 2", utility: "electricity" },
    { id: 372, tag: "LV03 - DB/LL/B3/EVC/01"                                   , base: 47100, type: "Modbus", daily:       0, monthly:       0, parent_id: 49, floor: "B4", column: null, zone: "", function: "LV03 - DB/LL/B3/EVC/01", utility: "electricity" },
    { id: 373, tag: "HM/01/LTHW"                                               , base: 47200, type: "Modbus", daily: 2000252, monthly: 2000596, parent_id: 632, floor: "1st", column: 1, zone: "North", function: "HM/01/LTHW - L01 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 374, tag: "HM/01/CHW"                                                , base: 47300, type: "Modbus", daily: 2000253, monthly: 2000597, parent_id: 631, floor: "1st", column: 1, zone: "North", function: "HM/01/CHW - L01 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 375, tag: "HM/02/LTHW"                                               , base: 47400, type: "Modbus", daily: 2000254, monthly: 2000598, parent_id: 632, floor: "2nd", column: 1, zone: "North", function: "HM/02/LTHW - L02 Tenants LTHW", utility: "lthw", tenant: "Landlords", tenant_display: true },
    { id: 376, tag: "HM/02/CHW"                                                , base: 47500, type: "Modbus", daily: 2000255, monthly: 2000599, parent_id: 631, floor: "2nd", column: 1, zone: "North", function: "HM/02/CHW - L02 Tenants CHW", utility: "chw", tenant: "Landlords", tenant_display: true },
    { id: 377, tag: "HM/03/LTHW"                                               , base: 47600, type: "Modbus", daily: 2000256, monthly: 2000600, parent_id: 632, floor: "3rd", column: 1, zone: "North", function: "HM/03/LTHW - L03 Tenants LTHW", utility: "lthw", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 378, tag: "HM/03/CHW"                                                , base: 47700, type: "Modbus", daily: 2000257, monthly: 2000601, parent_id: 631, floor: "3rd", column: 1, zone: "North", function: "HM/03/CHW - L03 Tenants CHW", utility: "chw", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 379, tag: "HM/03/CHW Restaurant"                                     , base: 47800, type: "Modbus", daily: 2000258, monthly: 2000602, parent_id: 631, floor: "3rd", column: 1, zone: "North", function: "HM/03/CHW Restaurant - L03 Tenants CHW", utility: "chw", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 380, tag: "HM/03/LTHW Restaurant"                                    , base: 47900, type: "Modbus", daily: 2000259, monthly: 2000603, parent_id: 632, floor: "3rd", column: 1, zone: "North", function: "HM/03/LTHW Restaurant - L03 Tenants LTHW", utility: "lthw", tenant: "Bob Bob Restaurant", tenant_display: true },
    { id: 381, tag: "HM/04/LTHW"                                               , base: 48000, type: "Modbus", daily: 2000260, monthly: 2000604, parent_id: 632, floor: "4th", column: 1, zone: "North", function: "HM/04/LTHW - L04 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 382, tag: "HM/04/CHW"                                                , base: 48100, type: "Modbus", daily: 2000261, monthly: 2000605, parent_id: 631, floor: "4th", column: 1, zone: "North", function: "HM/04/CHW - L04 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 383, tag: "HM/05/LTHW"                                               , base: 48200, type: "Modbus", daily: 2000262, monthly: 2000606, parent_id: 632, floor: "5th", column: 1, zone: "North", function: "HM/05/LTHW - L05 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 384, tag: "HM/05/CHW"                                                , base: 48300, type: "Modbus", daily: 2000263, monthly: 2000607, parent_id: 631, floor: "5th", column: 1, zone: "North", function: "HM/05/CHW - L05 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 385, tag: "HM/06/LTHW"                                               , base: 48400, type: "Modbus", daily: 2000264, monthly: 2000608, parent_id: 632, floor: "6th", column: 1, zone: "North", function: "HM/06/LTHW - L06 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 386, tag: "HM/06/CHW"                                                , base: 48500, type: "Modbus", daily: 2000265, monthly: 2000609, parent_id: 631, floor: "6th", column: 1, zone: "North", function: "HM/06/CHW - L06 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 387, tag: "HM/07/LTHW"                                               , base: 48600, type: "Modbus", daily: 2000266, monthly: 2000610, parent_id: 632, floor: "7th", column: 1, zone: "North", function: "HM/07/LTHW - L07 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 388, tag: "HM/07/CHW"                                                , base: 48700, type: "Modbus", daily: 2000267, monthly: 2000611, parent_id: 631, floor: "7th", column: 1, zone: "North", function: "HM/07/CHW - L07 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 389, tag: "HM/08/LTHW"                                               , base: 48800, type: "Modbus", daily: 2000268, monthly: 2000612, parent_id: 632, floor: "8th", column: 1, zone: "North", function: "HM/08/LTHW - L08 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 390, tag: "HM/08/CHW"                                                , base: 48900, type: "Modbus", daily: 2000269, monthly: 2000613, parent_id: 631, floor: "8th", column: 1, zone: "North", function: "HM/08/CHW - L08 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 391, tag: "HM/09/LTHW"                                               , base: 49000, type: "Modbus", daily: 2000270, monthly: 2000614, parent_id: 632, floor: "9th", column: 1, zone: "North", function: "HM/09/LTHW - L09 Tenants LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 392, tag: "HM/09/CHW"                                                , base: 49100, type: "Modbus", daily: 2000271, monthly: 2000615, parent_id: 631, floor: "9th", column: 1, zone: "North", function: "HM/09/CHW - L09 Tenants CHW", utility: "chw", tenant: "AON", tenant_display: true },
    { id: 393, tag: "HM/10/LTHW"                                               , base: 49200, type: "Modbus", daily: 2000272, monthly: 2000616, parent_id: 632, floor: "10th", column: 1, zone: "North", function: "HM/10/LTHW - L10 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 394, tag: "HM/10/CHW"                                                , base: 49300, type: "Modbus", daily: 2000273, monthly: 2000617, parent_id: 631, floor: "10th", column: 1, zone: "North", function: "HM/10/CHW - L10 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 395, tag: "HM/11/LTHW"                                               , base: 49400, type: "Modbus", daily: 2000274, monthly: 2000618, parent_id: 632, floor: "11th", column: 1, zone: "North", function: "HM/11/LTHW - L11 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 396, tag: "HM/11/CHW"                                                , base: 49500, type: "Modbus", daily: 2000275, monthly: 2000619, parent_id: 631, floor: "11th", column: 1, zone: "North", function: "HM/11/CHW - L11 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 397, tag: "HM/12/LTHW"                                               , base: 49600, type: "Modbus", daily: 2000276, monthly: 2000620, parent_id: 632, floor: "12th", column: 1, zone: "North", function: "HM/12/LTHW - L12 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 398, tag: "HM/12/CHW"                                                , base: 49700, type: "Modbus", daily: 2000277, monthly: 2000621, parent_id: 631, floor: "12th", column: 1, zone: "North", function: "HM/12/CHW - L12 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 399, tag: "HM/13/LTHW"                                               , base: 49800, type: "Modbus", daily: 2000278, monthly: 2000622, parent_id: 632, floor: "13th", column: 1, zone: "North", function: "HM/13/LTHW - L13 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 400, tag: "HM/13/CHW"                                                , base: 49900, type: "Modbus", daily: 2000279, monthly: 2000623, parent_id: 631, floor: "13th", column: 1, zone: "North", function: "HM/13/CHW - L13 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 401, tag: "HM/14/LTHW"                                               , base: 50000, type: "Modbus", daily: 2000280, monthly: 2000624, parent_id: 632, floor: "14th", column: 1, zone: "North", function: "HM/14/LTHW - L14 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 402, tag: "HM/14/CHW"                                                , base: 50100, type: "Modbus", daily: 2000281, monthly: 2000625, parent_id: 631, floor: "14th", column: 1, zone: "North", function: "HM/14/CHW - L14 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 403, tag: "HM/15/LTHW"                                               , base: 50200, type: "Modbus", daily: 2000282, monthly: 2000626, parent_id: 632, floor: "15th", column: 1, zone: "North", function: "HM/15/LTHW - L15 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 404, tag: "HM/15/CHW"                                                , base: 50300, type: "Modbus", daily: 2000283, monthly: 2000627, parent_id: 631, floor: "15th", column: 1, zone: "North", function: "HM/15/CHW - L15 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 405, tag: "HM/16/LTHW"                                               , base: 50400, type: "Modbus", daily: 2000284, monthly: 2000628, parent_id: 632, floor: "16th", column: 1, zone: "North", function: "HM/16/LTHW - L16 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 406, tag: "HM/16/CHW"                                                , base: 50500, type: "Modbus", daily: 2000285, monthly: 2000629, parent_id: 631, floor: "16th", column: 1, zone: "North", function: "HM/16/CHW - L16 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 407, tag: "HM/17/LTHW"                                               , base: 50600, type: "Modbus", daily: 2000286, monthly: 2000630, parent_id: 632, floor: "17th", column: 1, zone: "North", function: "HM/17/LTHW - L17 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 408, tag: "HM/17/CHW"                                                , base: 50700, type: "Modbus", daily: 2000287, monthly: 2000631, parent_id: 631, floor: "17th", column: 1, zone: "North", function: "HM/17/CHW - L17 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 409, tag: "HM/18/LTHW"                                               , base: 50800, type: "Modbus", daily: 2000288, monthly: 2000632, parent_id: 632, floor: "18th", column: 1, zone: "North", function: "HM/18/LTHW - L18 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 410, tag: "HM/18/CHW"                                                , base: 50900, type: "Modbus", daily: 2000289, monthly: 2000633, parent_id: 631, floor: "18th", column: 1, zone: "North", function: "HM/18/CHW - L18 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 411, tag: "HM/19/LTHW"                                               , base: 51000, type: "Modbus", daily: 2000290, monthly: 2000634, parent_id: 632, floor: "19th", column: 1, zone: "North", function: "HM/19/LTHW - L19 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 412, tag: "HM/19/CHW"                                                , base: 51100, type: "Modbus", daily: 2000291, monthly: 2000635, parent_id: 631, floor: "19th", column: 1, zone: "North", function: "HM/19/CHW - L19 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 413, tag: "HM/20/LTHW"                                               , base: 51200, type: "Modbus", daily: 2000292, monthly: 2000636, parent_id: 632, floor: "20th", column: 1, zone: "North", function: "HM/20/LTHW - L20 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 414, tag: "HM/20/CHW"                                                , base: 51300, type: "Modbus", daily: 2000293, monthly: 2000637, parent_id: 631, floor: "20th", column: 1, zone: "North", function: "HM/20/CHW - L20 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 415, tag: "HM/21/LTHW"                                               , base: 51400, type: "Modbus", daily: 2000294, monthly: 2000638, parent_id: 632, floor: "21st", column: 1, zone: "North", function: "HM/21/LTHW - L21 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 416, tag: "HM/21/CHW"                                                , base: 51500, type: "Modbus", daily: 2000295, monthly: 2000639, parent_id: 631, floor: "21st", column: 1, zone: "North", function: "HM/21/CHW - L21 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 417, tag: "HM/22/LTHW"                                               , base: 51600, type: "Modbus", daily: 2000296, monthly: 2000640, parent_id: 632, floor: "22nd", column: 1, zone: "North", function: "HM/22/LTHW - L22 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 418, tag: "HM/22/CHW"                                                , base: 51700, type: "Modbus", daily: 2000297, monthly: 2000641, parent_id: 631, floor: "22nd", column: 1, zone: "North", function: "HM/22/CHW - L22 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 419, tag: "HM/23/LTHW"                                               , base: 51800, type: "Modbus", daily: 2000298, monthly: 2000642, parent_id: 632, floor: "23rd", column: 1, zone: "North", function: "HM/23/LTHW - L23 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 420, tag: "HM/23/CHW"                                                , base: 51900, type: "Modbus", daily: 2000299, monthly: 2000643, parent_id: 631, floor: "23rd", column: 1, zone: "North", function: "HM/23/CHW - L23 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 421, tag: "HM/24/LTHW"                                               , base: 52000, type: "Modbus", daily: 2000300, monthly: 2000644, parent_id: 632, floor: "24th", column: 1, zone: "North", function: "HM/24/LTHW - L24 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 422, tag: "HM/24/CHW"                                                , base: 52100, type: "Modbus", daily: 2000301, monthly: 2000645, parent_id: 631, floor: "24th", column: 1, zone: "North", function: "HM/24/CHW - L24 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 423, tag: "HM/25/LTHW"                                               , base: 52200, type: "Modbus", daily: 2000302, monthly: 2000646, parent_id: 632, floor: "25th", column: 1, zone: "North", function: "HM/25/LTHW - L25 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 424, tag: "HM/25/CHW"                                                , base: 52300, type: "Modbus", daily: 2000303, monthly: 2000647, parent_id: 631, floor: "25th", column: 1, zone: "North", function: "HM/25/CHW - L25 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 425, tag: "HM/26/LTHW"                                               , base: 52400, type: "Modbus", daily: 2000304, monthly: 2000648, parent_id: 632, floor: "26th", column: 1, zone: "North", function: "HM/26/LTHW - L26 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 426, tag: "HM/26/CHW"                                                , base: 52500, type: "Modbus", daily: 2000305, monthly: 2000649, parent_id: 631, floor: "26th", column: 1, zone: "North", function: "HM/26/CHW - L26 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 427, tag: "HM/27/LTHW"                                               , base: 52600, type: "Modbus", daily: 2000306, monthly: 2000650, parent_id: 632, floor: "27th", column: 1, zone: "North", function: "HM/27/LTHW - L27 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 428, tag: "HM/27/CHW"                                                , base: 52700, type: "Modbus", daily: 2000307, monthly: 2000651, parent_id: 631, floor: "27th", column: 1, zone: "North", function: "HM/27/CHW - L27 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 429, tag: "HM/28/LTHW"                                               , base: 52800, type: "Modbus", daily: 2000308, monthly: 2000652, parent_id: 632, floor: "28th", column: 1, zone: "North", function: "HM/28/LTHW - L28 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 430, tag: "HM/28/CHW"                                                , base: 52900, type: "Modbus", daily: 2000309, monthly: 2000653, parent_id: 631, floor: "28th", column: 1, zone: "North", function: "HM/28/CHW - L28 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 431, tag: "HM/29/LTHW"                                               , base: 53000, type: "Modbus", daily: 2000310, monthly: 2000654, parent_id: 632, floor: "29th", column: 1, zone: "North", function: "HM/29/LTHW - L29 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 432, tag: "HM/29/CHW"                                                , base: 53100, type: "Modbus", daily: 2000311, monthly: 2000655, parent_id: 631, floor: "29th", column: 1, zone: "North", function: "HM/29/CHW - L29 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 433, tag: "HM/30/LTHW"                                               , base: 53200, type: "Modbus", daily: 2000312, monthly: 2000656, parent_id: 632, floor: "30th", column: 1, zone: "North", function: "HM/30/LTHW - L30 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 434, tag: "HM/30/CHW"                                                , base: 53300, type: "Modbus", daily: 2000313, monthly: 2000657, parent_id: 631, floor: "30th", column: 1, zone: "North", function: "HM/30/CHW - L30 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 435, tag: "HM/31/LTHW"                                               , base: 53400, type: "Modbus", daily: 2000314, monthly: 2000658, parent_id: 632, floor: "31st", column: 1, zone: "North", function: "HM/31/LTHW - L31 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 436, tag: "HM/31/CHW"                                                , base: 53500, type: "Modbus", daily: 2000315, monthly: 2000659, parent_id: 631, floor: "31st", column: 1, zone: "North", function: "HM/31/CHW - L31 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 437, tag: "HM/32/LTHW"                                               , base: 53600, type: "Modbus", daily: 2000316, monthly: 2000660, parent_id: 632, floor: "32nd", column: 1, zone: "North", function: "HM/32/LTHW - L32 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 438, tag: "HM/32/CHW"                                                , base: 53700, type: "Modbus", daily: 2000317, monthly: 2000661, parent_id: 631, floor: "32nd", column: 1, zone: "North", function: "HM/32/CHW - L32 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 439, tag: "HM/33/LTHW"                                               , base: 53800, type: "Modbus", daily: 2000318, monthly: 2000662, parent_id: 632, floor: "33rd", column: 1, zone: "North", function: "HM/33/LTHW - L33 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 440, tag: "HM/33/CHW"                                                , base: 53900, type: "Modbus", daily: 2000319, monthly: 2000663, parent_id: 631, floor: "33rd", column: 1, zone: "North", function: "HM/33/CHW - L33 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 441, tag: "HM/34/LTHW"                                               , base: 54000, type: "Modbus", daily: 2000320, monthly: 2000664, parent_id: 632, floor: "34th", column: 1, zone: "North", function: "HM/34/LTHW - L34 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 442, tag: "HM/34/CHW"                                                , base: 54100, type: "Modbus", daily: 2000321, monthly: 2000665, parent_id: 631, floor: "34th", column: 1, zone: "North", function: "HM/34/CHW - L34 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 443, tag: "HM/35/LTHW"                                               , base: 54200, type: "Modbus", daily: 2000322, monthly: 2000666, parent_id: 632, floor: "35th", column: 1, zone: "North", function: "HM/35/LTHW - L35 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 444, tag: "HM/35/CHW"                                                , base: 54300, type: "Modbus", daily: 2000323, monthly: 2000667, parent_id: 631, floor: "35th", column: 1, zone: "North", function: "HM/35/CHW - L35 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 445, tag: "HM/36/LTHW"                                               , base: 54400, type: "Modbus", daily: 2000324, monthly: 2000668, parent_id: 632, floor: "36th", column: 1, zone: "North", function: "HM/36/LTHW - L36 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 446, tag: "HM/36/CHW"                                                , base: 54500, type: "Modbus", daily: 2000325, monthly: 2000669, parent_id: 631, floor: "36th", column: 1, zone: "North", function: "HM/36/CHW - L36 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 447, tag: "HM/37/LTHW"                                               , base: 54600, type: "Modbus", daily: 2000326, monthly: 2000670, parent_id: 632, floor: "37th", column: 1, zone: "North", function: "HM/37/LTHW - L37 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 448, tag: "HM/37/CHW"                                                , base: 54700, type: "Modbus", daily: 2000327, monthly: 2000671, parent_id: 631, floor: "37th", column: 1, zone: "North", function: "HM/37/CHW - L37 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 449, tag: "HM/38/LTHW"                                               , base: 54800, type: "Modbus", daily: 2000328, monthly: 2000672, parent_id: 632, floor: "38th", column: 1, zone: "North", function: "HM/38/LTHW - L38 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 450, tag: "HM/38/CHW"                                                , base: 54900, type: "Modbus", daily: 2000329, monthly: 2000673, parent_id: 631, floor: "38th", column: 1, zone: "North", function: "HM/38/CHW - L38 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 451, tag: "HM/39/LTHW"                                               , base: 55000, type: "Modbus", daily: 2000330, monthly: 2000674, parent_id: 632, floor: "39th", column: 1, zone: "North", function: "HM/39/LTHW - L39 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 452, tag: "HM/39/CHW"                                                , base: 55100, type: "Modbus", daily: 2000331, monthly: 2000675, parent_id: 631, floor: "39th", column: 1, zone: "North", function: "HM/39/CHW - L39 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 453, tag: "HM/40/LTHW"                                               , base: 55200, type: "Modbus", daily: 2000332, monthly: 2000676, parent_id: 632, floor: "40th", column: 1, zone: "North", function: "HM/40/LTHW - L40 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 454, tag: "HM/40/CHW"                                                , base: 55300, type: "Modbus", daily: 2000333, monthly: 2000677, parent_id: 631, floor: "40th", column: 1, zone: "North", function: "HM/40/CHW - L40 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 455, tag: "HM/41/LTHW"                                               , base: 55400, type: "Modbus", daily: 2000334, monthly: 2000678, parent_id: 632, floor: "41st", column: 1, zone: "North", function: "HM/41/LTHW - L41 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 456, tag: "HM/41/CHW"                                                , base: 55500, type: "Modbus", daily: 2000335, monthly: 2000679, parent_id: 631, floor: "41st", column: 1, zone: "North", function: "HM/41/CHW - L41 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 457, tag: "HM/42/LTHW"                                               , base: 55600, type: "Modbus", daily: 2000336, monthly: 2000680, parent_id: 632, floor: "42nd", column: 1, zone: "North", function: "HM/42/LTHW - L42 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 458, tag: "HM/42/CHW"                                                , base: 55700, type: "Modbus", daily: 2000337, monthly: 2000681, parent_id: 631, floor: "42nd", column: 1, zone: "North", function: "HM/42/CHW - L42 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 459, tag: "HM/43/LTHW"                                               , base: 55800, type: "Modbus", daily: 2000338, monthly: 2000682, parent_id: 632, floor: "43rd", column: 1, zone: "North", function: "HM/43/LTHW - L43 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 460, tag: "HM/43/CHW"                                                , base: 55900, type: "Modbus", daily: 2000339, monthly: 2000683, parent_id: 631, floor: "43rd", column: 1, zone: "North", function: "HM/43/CHW - L43 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 461, tag: "HM/44/LTHW"                                               , base: 56000, type: "Modbus", daily: 2000340, monthly: 2000684, parent_id: 632, floor: "44th", column: 1, zone: "North", function: "HM/44/LTHW - L44 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 462, tag: "HM/44/CHW"                                                , base: 56100, type: "Modbus", daily: 2000341, monthly: 2000685, parent_id: 631, floor: "44th", column: 1, zone: "North", function: "HM/44/CHW - L44 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 463, tag: "HM/45/LTHW"                                               , base: 56200, type: "Modbus", daily: 2000342, monthly: 2000686, parent_id: 632, floor: "45th", column: 1, zone: "North", function: "HM/45/LTHW - L45 Tenants LTHW", utility: "lthw", tenant_display: true },
    { id: 464, tag: "HM/45/CHW"                                                , base: 56300, type: "Modbus", daily: 2000343, monthly: 2000687, parent_id: 631, floor: "45th", column: 1, zone: "North", function: "HM/45/CHW - L45 Tenants CHW", utility: "chw", tenant_display: true },
    { id: 465, tag: "CHW Chiller One Output"                                   , base: 56400, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "B2", column: null, zone: "", function: "CHW Chiller One Output", utility: "chw" },
    { id: 466, tag: "CHW Chiller Two Output"                                   , base: 56500, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "B2", column: null, zone: "", function: "CHW Chiller Two Output", utility: "chw" },
    { id: 467, tag: "CHW Chiller Three Output"                                 , base: 56600, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "B2", column: null, zone: "", function: "CHW Chiller Three Output", utility: "chw" },
    { id: 468, tag: "CHW Chiller Four Output"                                  , base: 56700, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "B2", column: null, zone: "", function: "CHW Chiller Four Output", utility: "chw" },
    { id: 469, tag: "CHW Basement Cooling"                                     , base: 56800, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "B2", column: null, zone: "", function: "CHW Basement Cooling", utility: "chw" },
    { id: 470, tag: "LTHW Basement AHU B1/B2"                                  , base: 56900, type: "Modbus", daily:       0, monthly:       0, floor: "B2", column: null, zone: "", function: "LTHW Basement AHU B1/B2", utility: "lthw" },
    { id: 471, tag: "Aon Post Room - LTHW"                                     , base: 57000, type: "Modbus", daily:       0, monthly:       0, floor: "Basement", column: 0, zone: "North", function: "Aon Post Room - LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 472, tag: "Aon Welfare Room - LTHW"                                  , base: 57100, type: "Modbus", daily:       0, monthly:       0, floor: "Basement", column: 0, zone: "North", function: "Aon Welfare Room - LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 473, tag: "Aon Security Room - LTHW"                                 , base: 57200, type: "Modbus", daily:       0, monthly:       0, floor: "Basement", column: 0, zone: "North", function: "Aon Security Room - LTHW", utility: "lthw", tenant: "AON", tenant_display: true },
    { id: 474, tag: "LTHW Total Boiler Output"                                 , base: 57300, type: "Modbus", daily:       0, monthly:       0, floor: "B2", column: null, zone: "", function: "LTHW Total Boiler Output", utility: "lthw" },
    { id: 475, tag: "CHW FL46 LFCU/RCU"                                        , base: 57400, type: "Modbus", daily:       0, monthly:       0, parent_id: 631, floor: "46th", column: null, zone: "", function: "CHW FL46 LFCU/RCU", utility: "chw", tenant: "Landlords" },
    { id: 476, tag: "Landlords L/SP Apportioned Floor 1"                       , base: 57500, type: "Calculation", daily:       0, monthly:       0, floor: "1st", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 1", utility: "electricity", tenant_display: true },
    { id: 477, tag: "Landlords L/SP Apportioned Floor 3"                       , base: 57600, type: "Calculation", daily:       0, monthly:       0, floor: "2nd|3rd|4th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 3", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 478, tag: "Landlords L/SP Apportioned Floor 6"                       , base: 57700, type: "Calculation", daily:       0, monthly:       0, floor: "5th|6th|7th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 6", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 479, tag: "Landlords L/SP Apportioned Floor 9"                       , base: 57800, type: "Calculation", daily:       0, monthly:       0, floor: "8th|9th|10th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 9", utility: "electricity", tenant: "AON", tenant_display: true },
    { id: 480, tag: "Landlords L/SP Apportioned Floor 12"                      , base: 57900, type: "Calculation", daily:       0, monthly:       0, floor: "11th|12th|13th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 12", utility: "electricity", tenant: "UIB", tenant_display: true },
    { id: 481, tag: "Landlords L/SP Apportioned Floor 15"                      , base: 58000, type: "Calculation", daily:       0, monthly:       0, floor: "14th|15th|16th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 15", utility: "electricity", tenant_display: true },
    { id: 482, tag: "Landlords L/SP Apportioned Floor 18"                      , base: 58100, type: "Calculation", daily:       0, monthly:       0, floor: "17th|18th|19th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 18", utility: "electricity", tenant_display: true },
    { id: 483, tag: "Landlords L/SP Apportioned Floor 21"                      , base: 58200, type: "Calculation", daily:       0, monthly:       0, floor: "20th|21st|22nd", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 21", utility: "electricity", tenant_display: true },
    { id: 484, tag: "Landlords L/SP Apportioned Floor 24"                      , base: 58300, type: "Calculation", daily:       0, monthly:       0, floor: "23rd|24th|25th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 24", utility: "electricity", tenant_display: true },
    { id: 485, tag: "Landlords L/SP Apportioned Floor 27"                      , base: 58400, type: "Calculation", daily:       0, monthly:       0, floor: "26th|27th|28th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 27", utility: "electricity", tenant_display: true },
    { id: 486, tag: "Landlords L/SP Apportioned Floor 30"                      , base: 58500, type: "Calculation", daily:       0, monthly:       0, floor: "29th|30th|31st", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 30", utility: "electricity", tenant_display: true },
    { id: 487, tag: "Landlords L/SP Apportioned Floor 33"                      , base: 58600, type: "Calculation", daily:       0, monthly:       0, floor: "32nd|33rd|34th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 33", utility: "electricity", tenant_display: true },
    { id: 488, tag: "Landlords L/SP Apportioned Floor 36"                      , base: 58700, type: "Calculation", daily:       0, monthly:       0, floor: "35th|36th|37th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 36", utility: "electricity", tenant_display: true },
    { id: 489, tag: "Landlords L/SP Apportioned Floor 39"                      , base: 58800, type: "Calculation", daily:       0, monthly:       0, floor: "38th|39th|40th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 39", utility: "electricity", tenant_display: true },
    { id: 490, tag: "Landlords L/SP Apportioned Floor 42"                      , base: 58900, type: "Calculation", daily:       0, monthly:       0, floor: "41st|42nd|43rd", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 42", utility: "electricity", tenant_display: true },
    { id: 491, tag: "Landlords L/SP Apportioned Floor 45"                      , base: 59000, type: "Calculation", daily:       0, monthly:       0, floor: "44th|45th|46th", column: 1, zone: "North", function: "Landlords L/SP Apportioned Floor 45", utility: "electricity", tenant_display: true },
    { id: 492, tag: "Floor 1 - Tenants Total Electricity"                      , base: 59100, type: "Calculation", daily: 2000688, monthly: 2000825, floor: "1st", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 493, tag: "Floor 2 - Tenants Total Electricity"                      , base: 59200, type: "Calculation", daily: 2000689, monthly: 2000826, floor: "2nd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Landlords" },
    { id: 494, tag: "Floor 3 - Tenants Total Electricity"                      , base: 59300, type: "Calculation", daily: 2000690, monthly: 2000827, floor: "3rd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Bob Bob Restaurant" },
    { id: 495, tag: "Floor 4 - Tenants Total Electricity"                      , base: 59400, type: "Calculation", daily: 2000691, monthly: 2000828, floor: "4th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 496, tag: "Floor 5 - Tenants Total Electricity"                      , base: 59500, type: "Calculation", daily: 2000692, monthly: 2000829, floor: "5th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 497, tag: "Floor 6 - Tenants Total Electricity"                      , base: 59600, type: "Calculation", daily: 2000693, monthly: 2000830, floor: "6th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 498, tag: "Floor 7 - Tenants Total Electricity"                      , base: 59700, type: "Calculation", daily: 2000694, monthly: 2000831, floor: "7th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 499, tag: "Floor 8 - Tenants Total Electricity"                      , base: 59800, type: "Calculation", daily: 2000695, monthly: 2000832, floor: "8th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 500, tag: "Floor 9 - Tenants Total Electricity"                      , base: 59900, type: "Calculation", daily: 2000696, monthly: 2000833, floor: "9th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 501, tag: "Floor 10 - Tenants Total Electricity"                     , base: 60000, type: "Calculation", daily: 2000697, monthly: 2000834, floor: "10th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 502, tag: "Floor 11 - Tenants Total Electricity"                     , base: 60100, type: "Calculation", daily: 2000698, monthly: 2000835, floor: "11th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 503, tag: "Floor 12 - Tenants Total Electricity"                     , base: 60200, type: "Calculation", daily: 2000699, monthly: 2000836, floor: "12th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "AON" },
    { id: 504, tag: "Floor 13 - Tenants Total Electricity"                     , base: 60300, type: "Calculation", daily: 2000700, monthly: 2000837, floor: "13th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "UIB" },
    { id: 505, tag: "Floor 14 - Tenants Total Electricity"                     , base: 60400, type: "Calculation", daily: 2000701, monthly: 2000838, floor: "14th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "RSH&P" },
    { id: 506, tag: "Floor 15 - Tenants Total Electricity"                     , base: 60500, type: "Calculation", daily: 2000702, monthly: 2000839, floor: "15th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Virgin Money" },
    { id: 507, tag: "Floor 16 - Tenants Total Electricity"                     , base: 60600, type: "Calculation", daily: 2000703, monthly: 2000840, floor: "16th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "KI Group Services" },
    { id: 508, tag: "Floor 17 - Tenants Total Electricity"                     , base: 60700, type: "Calculation", daily: 2000704, monthly: 2000841, floor: "17th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 509, tag: "Floor 18 - Tenants Total Electricity"                     , base: 60800, type: "Calculation", daily: 2000705, monthly: 2000842, floor: "18th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 510, tag: "Floor 19 - Tenants Total Electricity"                     , base: 60900, type: "Calculation", daily: 2000706, monthly: 2000843, floor: "19th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "UIB" },
    { id: 511, tag: "Floor 20 - Tenants Total Electricity"                     , base: 61000, type: "Calculation", daily: 2000707, monthly: 2000844, floor: "20th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 512, tag: "Floor 21 - Tenants Total Electricity"                     , base: 61100, type: "Calculation", daily: 2000708, monthly: 2000845, floor: "21st", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 513, tag: "Floor 22 - Tenants Total Electricity"                     , base: 61200, type: "Calculation", daily: 2000709, monthly: 2000846, floor: "22nd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 514, tag: "Floor 23 - Tenants Total Electricity"                     , base: 61300, type: "Calculation", daily: 2000710, monthly: 2000847, floor: "23rd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 515, tag: "Floor 24 - Tenants Total Electricity"                     , base: 61400, type: "Calculation", daily: 2000711, monthly: 2000848, floor: "24th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 516, tag: "Floor 25 - Tenants Total Electricity"                     , base: 61500, type: "Calculation", daily: 2000712, monthly: 2000849, floor: "25th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "DRW" },
    { id: 517, tag: "Floor 26 - Tenants Total Electricity"                     , base: 61600, type: "Calculation", daily: 2000713, monthly: 2000850, floor: "26th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Aegon / Draft Kings" },
    { id: 518, tag: "Floor 27 - Tenants Total Electricity"                     , base: 61700, type: "Calculation", daily: 2000714, monthly: 2000851, floor: "27th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 519, tag: "Floor 28 - Tenants Total Electricity"                     , base: 61800, type: "Calculation", daily: 2000715, monthly: 2000852, floor: "28th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 520, tag: "Floor 29 - Tenants Total Electricity"                     , base: 61900, type: "Calculation", daily: 2000716, monthly: 2000853, floor: "29th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 521, tag: "Floor 30 - Tenants Total Electricity"                     , base: 62000, type: "Calculation", daily: 2000717, monthly: 2000854, floor: "30th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Serve corp" },
    { id: 522, tag: "Floor 31 - Tenants Total Electricity"                     , base: 62100, type: "Calculation", daily: 2000718, monthly: 2000855, floor: "31st", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 523, tag: "Floor 32 - Tenants Total Electricity"                     , base: 62200, type: "Calculation", daily: 2000719, monthly: 2000856, floor: "32nd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 524, tag: "Floor 33 - Tenants Total Electricity"                     , base: 62300, type: "Calculation", daily: 2000720, monthly: 2000857, floor: "33rd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 525, tag: "Floor 34 - Tenants Total Electricity"                     , base: 62400, type: "Calculation", daily: 2000721, monthly: 2000858, floor: "34th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 526, tag: "Floor 35 - Tenants Total Electricity"                     , base: 62500, type: "Calculation", daily: 2000722, monthly: 2000859, floor: "35th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "DRW" },
    { id: 527, tag: "Floor 36 - Tenants Total Electricity"                     , base: 62600, type: "Calculation", daily: 2000723, monthly: 2000860, floor: "36th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "DRW" },
    { id: 528, tag: "Floor 37 - Tenants Total Electricity"                     , base: 62700, type: "Calculation", daily: 2000724, monthly: 2000861, floor: "37th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "DRW" },
    { id: 529, tag: "Floor 38 - Tenants Total Electricity"                     , base: 62800, type: "Calculation", daily: 2000725, monthly: 2000862, floor: "38th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "DRW" },
    { id: 530, tag: "Floor 39 - Tenants Total Electricity"                     , base: 62900, type: "Calculation", daily: 2000726, monthly: 2000863, floor: "39th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 531, tag: "Floor 40 - Tenants Total Electricity"                     , base: 63000, type: "Calculation", daily: 2000727, monthly: 2000864, floor: "40th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 532, tag: "Floor 41 - Tenants Total Electricity"                     , base: 63100, type: "Calculation", daily: 2000728, monthly: 2000865, floor: "41st", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 533, tag: "Floor 42 - Tenants Total Electricity"                     , base: 63200, type: "Calculation", daily: 2000729, monthly: 2000866, floor: "42nd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Xcite" },
    { id: 534, tag: "Floor 43 - Tenants Total Electricity"                     , base: 63300, type: "Calculation", daily: 2000730, monthly: 2000867, floor: "43rd", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Petredec" },
    { id: 535, tag: "Floor 44 - Tenants Total Electricity"                     , base: 63400, type: "Calculation", daily: 2000731, monthly: 2000868, floor: "44th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "Affinity Shipping" },
    { id: 536, tag: "Floor 45 - Tenants Total Electricity"                     , base: 63500, type: "Calculation", daily: 2000732, monthly: 2000869, floor: "45th", column: null, zone: "", function: "Floor Tenants Electricity", utility: "electricity", tenant: "D-Tek" },
    { id: 537, tag: "Floor 1 - Landlords Total Electricity"                    , base: 63600, type: "Calculation", daily: 2000733, monthly: 2000870, floor: "1st", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 538, tag: "Floor 2 - Landlords Total Electricity"                    , base: 63700, type: "Calculation", daily: 2000734, monthly: 2000871, floor: "2nd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Landlords" },
    { id: 539, tag: "Floor 3 - Landlords Total Electricity"                    , base: 63800, type: "Calculation", daily: 2000735, monthly: 2000872, floor: "3rd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Bob Bob Restaurant" },
    { id: 540, tag: "Floor 4 - Landlords Total Electricity"                    , base: 63900, type: "Calculation", daily: 2000736, monthly: 2000873, floor: "4th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 541, tag: "Floor 5 - Landlords Total Electricity"                    , base: 64000, type: "Calculation", daily: 2000737, monthly: 2000874, floor: "5th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 542, tag: "Floor 6 - Landlords Total Electricity"                    , base: 64100, type: "Calculation", daily: 2000738, monthly: 2000875, floor: "6th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 543, tag: "Floor 7 - Landlords Total Electricity"                    , base: 64200, type: "Calculation", daily: 2000739, monthly: 2000876, floor: "7th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 544, tag: "Floor 8 - Landlords Total Electricity"                    , base: 64300, type: "Calculation", daily: 2000740, monthly: 2000877, floor: "8th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 545, tag: "Floor 9 - Landlords Total Electricity"                    , base: 64400, type: "Calculation", daily: 2000741, monthly: 2000878, floor: "9th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 546, tag: "Floor 10 - Landlords Total Electricity"                   , base: 64500, type: "Calculation", daily: 2000742, monthly: 2000879, floor: "10th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 547, tag: "Floor 11 - Landlords Total Electricity"                   , base: 64600, type: "Calculation", daily: 2000743, monthly: 2000880, floor: "11th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 548, tag: "Floor 12 - Landlords Total Electricity"                   , base: 64700, type: "Calculation", daily: 2000744, monthly: 2000881, floor: "12th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "AON" },
    { id: 549, tag: "Floor 13 - Landlords Total Electricity"                   , base: 64800, type: "Calculation", daily: 2000745, monthly: 2000882, floor: "13th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "UIB" },
    { id: 550, tag: "Floor 14 - Landlords Total Electricity"                   , base: 64900, type: "Calculation", daily: 2000746, monthly: 2000883, floor: "14th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "RSH&P" },
    { id: 551, tag: "Floor 15 - Landlords Total Electricity"                   , base: 65000, type: "Calculation", daily: 2000747, monthly: 2000884, floor: "15th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Virgin Money" },
    { id: 552, tag: "Floor 16 - Landlords Total Electricity"                   , base: 65100, type: "Calculation", daily: 2000748, monthly: 2000885, floor: "16th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "KI Group Services" },
    { id: 553, tag: "Floor 17 - Landlords Total Electricity"                   , base: 65200, type: "Calculation", daily: 2000749, monthly: 2000886, floor: "17th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 554, tag: "Floor 18 - Landlords Total Electricity"                   , base: 65300, type: "Calculation", daily: 2000750, monthly: 2000887, floor: "18th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 555, tag: "Floor 19 - Landlords Total Electricity"                   , base: 65400, type: "Calculation", daily: 2000751, monthly: 2000888, floor: "19th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "UIB" },
    { id: 556, tag: "Floor 20 - Landlords Total Electricity"                   , base: 65500, type: "Calculation", daily: 2000752, monthly: 2000889, floor: "20th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 557, tag: "Floor 21 - Landlords Total Electricity"                   , base: 65600, type: "Calculation", daily: 2000753, monthly: 2000890, floor: "21st", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 558, tag: "Floor 22 - Landlords Total Electricity"                   , base: 65700, type: "Calculation", daily: 2000754, monthly: 2000891, floor: "22nd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 559, tag: "Floor 23 - Landlords Total Electricity"                   , base: 65800, type: "Calculation", daily: 2000755, monthly: 2000892, floor: "23rd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 560, tag: "Floor 24 - Landlords Total Electricity"                   , base: 65900, type: "Calculation", daily: 2000756, monthly: 2000893, floor: "24th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 561, tag: "Floor 25 - Landlords Total Electricity"                   , base: 66000, type: "Calculation", daily: 2000757, monthly: 2000894, floor: "25th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "DRW" },
    { id: 562, tag: "Floor 26 - Landlords Total Electricity"                   , base: 66100, type: "Calculation", daily: 2000758, monthly: 2000895, floor: "26th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Aegon / Draft Kings" },
    { id: 563, tag: "Floor 27 - Landlords Total Electricity"                   , base: 66200, type: "Calculation", daily: 2000759, monthly: 2000896, floor: "27th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 564, tag: "Floor 28 - Landlords Total Electricity"                   , base: 66300, type: "Calculation", daily: 2000760, monthly: 2000897, floor: "28th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 565, tag: "Floor 29 - Landlords Total Electricity"                   , base: 66400, type: "Calculation", daily: 2000761, monthly: 2000898, floor: "29th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 566, tag: "Floor 30 - Landlords Total Electricity"                   , base: 66500, type: "Calculation", daily: 2000762, monthly: 2000899, floor: "30th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Serve corp" },
    { id: 567, tag: "Floor 31 - Landlords Total Electricity"                   , base: 66600, type: "Calculation", daily: 2000763, monthly: 2000900, floor: "31st", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 568, tag: "Floor 32 - Landlords Total Electricity"                   , base: 66700, type: "Calculation", daily: 2000764, monthly: 2000901, floor: "32nd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 569, tag: "Floor 33 - Landlords Total Electricity"                   , base: 66800, type: "Calculation", daily: 2000765, monthly: 2000902, floor: "33rd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 570, tag: "Floor 34 - Landlords Total Electricity"                   , base: 66900, type: "Calculation", daily: 2000766, monthly: 2000903, floor: "34th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 571, tag: "Floor 35 - Landlords Total Electricity"                   , base: 67000, type: "Calculation", daily: 2000767, monthly: 2000904, floor: "35th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "DRW" },
    { id: 572, tag: "Floor 36 - Landlords Total Electricity"                   , base: 67100, type: "Calculation", daily: 2000768, monthly: 2000905, floor: "36th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "DRW" },
    { id: 573, tag: "Floor 37 - Landlords Total Electricity"                   , base: 67200, type: "Calculation", daily: 2000769, monthly: 2000906, floor: "37th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "DRW" },
    { id: 574, tag: "Floor 38 - Landlords Total Electricity"                   , base: 67300, type: "Calculation", daily: 2000770, monthly: 2000907, floor: "38th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "DRW" },
    { id: 575, tag: "Floor 39 - Landlords Total Electricity"                   , base: 67400, type: "Calculation", daily: 2000771, monthly: 2000908, floor: "39th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 576, tag: "Floor 40 - Landlords Total Electricity"                   , base: 67500, type: "Calculation", daily: 2000772, monthly: 2000909, floor: "40th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 577, tag: "Floor 41 - Landlords Total Electricity"                   , base: 67600, type: "Calculation", daily: 2000773, monthly: 2000910, floor: "41st", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 578, tag: "Floor 42 - Landlords Total Electricity"                   , base: 67700, type: "Calculation", daily: 2000774, monthly: 2000911, floor: "42nd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Xcite" },
    { id: 579, tag: "Floor 43 - Landlords Total Electricity"                   , base: 67800, type: "Calculation", daily: 2000775, monthly: 2000912, floor: "43rd", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Petredec" },
    { id: 580, tag: "Floor 44 - Landlords Total Electricity"                   , base: 67900, type: "Calculation", daily: 2000776, monthly: 2000913, floor: "44th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Affinity Shipping" },
    { id: 581, tag: "Floor 45 - Landlords Total Electricity"                   , base: 68000, type: "Calculation", daily: 2000777, monthly: 2000914, floor: "45th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "D-Tek" },
    { id: 582, tag: "Floor 46 - Landlords Total Electricity"                   , base: 68100, type: "Calculation", daily: 2000778, monthly: 2000915, floor: "46th", column: null, zone: "", function: "Floor Landlords Electricity", utility: "electricity", tenant: "Landlords" },
    { id: 583, tag: "Floor 1 - Total Electricity"                              , base: 68200, type: "Calculation", daily: 2000779, monthly: 2000916, floor: "1st", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 584, tag: "Floor 2 - Total Electricity"                              , base: 68300, type: "Calculation", daily: 2000780, monthly: 2000917, floor: "2nd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Landlords" },
    { id: 585, tag: "Floor 3 - Total Electricity"                              , base: 68400, type: "Calculation", daily: 2000781, monthly: 2000918, floor: "3rd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Bob Bob Restaurant" },
    { id: 586, tag: "Floor 4 - Total Electricity"                              , base: 68500, type: "Calculation", daily: 2000782, monthly: 2000919, floor: "4th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 587, tag: "Floor 5 - Total Electricity"                              , base: 68600, type: "Calculation", daily: 2000783, monthly: 2000920, floor: "5th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 588, tag: "Floor 6 - Total Electricity"                              , base: 68700, type: "Calculation", daily: 2000784, monthly: 2000921, floor: "6th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 589, tag: "Floor 7 - Total Electricity"                              , base: 68800, type: "Calculation", daily: 2000785, monthly: 2000922, floor: "7th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 590, tag: "Floor 8 - Total Electricity"                              , base: 68900, type: "Calculation", daily: 2000786, monthly: 2000923, floor: "8th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 591, tag: "Floor 9 - Total Electricity"                              , base: 69000, type: "Calculation", daily: 2000787, monthly: 2000924, floor: "9th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 592, tag: "Floor 10 - Total Electricity"                             , base: 69100, type: "Calculation", daily: 2000788, monthly: 2000925, floor: "10th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 593, tag: "Floor 11 - Total Electricity"                             , base: 69200, type: "Calculation", daily: 2000789, monthly: 2000926, floor: "11th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 594, tag: "Floor 12 - Total Electricity"                             , base: 69300, type: "Calculation", daily: 2000790, monthly: 2000927, floor: "12th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON" },
    { id: 595, tag: "Floor 13 - Total Electricity"                             , base: 69400, type: "Calculation", daily: 2000791, monthly: 2000928, floor: "13th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "UIB" },
    { id: 596, tag: "Floor 14 - Total Electricity"                             , base: 69500, type: "Calculation", daily: 2000792, monthly: 2000929, floor: "14th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "RSH&P" },
    { id: 597, tag: "Floor 15 - Total Electricity"                             , base: 69600, type: "Calculation", daily: 2000793, monthly: 2000930, floor: "15th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Virgin Money" },
    { id: 598, tag: "Floor 16 - Total Electricity"                             , base: 69700, type: "Calculation", daily: 2000794, monthly: 2000931, floor: "16th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "KI Group Services" },
    { id: 599, tag: "Floor 17 - Total Electricity"                             , base: 69800, type: "Calculation", daily: 2000795, monthly: 2000932, floor: "17th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 600, tag: "Floor 18 - Total Electricity"                             , base: 69900, type: "Calculation", daily: 2000796, monthly: 2000933, floor: "18th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 601, tag: "Floor 19 - Total Electricity"                             , base: 70000, type: "Calculation", daily: 2000797, monthly: 2000934, floor: "19th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "UIB" },
    { id: 602, tag: "Floor 20 - Total Electricity"                             , base: 70100, type: "Calculation", daily: 2000798, monthly: 2000935, floor: "20th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 603, tag: "Floor 21 - Total Electricity"                             , base: 70200, type: "Calculation", daily: 2000799, monthly: 2000936, floor: "21st", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 604, tag: "Floor 22 - Total Electricity"                             , base: 70300, type: "Calculation", daily: 2000800, monthly: 2000937, floor: "22nd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 605, tag: "Floor 23 - Total Electricity"                             , base: 70400, type: "Calculation", daily: 2000801, monthly: 2000938, floor: "23rd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 606, tag: "Floor 24 - Total Electricity"                             , base: 70500, type: "Calculation", daily: 2000802, monthly: 2000939, floor: "24th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "MS Amlin" },
    { id: 607, tag: "Floor 25 - Total Electricity"                             , base: 70600, type: "Calculation", daily: 2000803, monthly: 2000940, floor: "25th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "DRW" },
    { id: 608, tag: "Floor 26 - Total Electricity"                             , base: 70700, type: "Calculation", daily: 2000804, monthly: 2000941, floor: "26th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Aegon / Draft Kings" },
    { id: 609, tag: "Floor 27 - Total Electricity"                             , base: 70800, type: "Calculation", daily: 2000805, monthly: 2000942, floor: "27th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 610, tag: "Floor 28 - Total Electricity"                             , base: 70900, type: "Calculation", daily: 2000806, monthly: 2000943, floor: "28th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 611, tag: "Floor 29 - Total Electricity"                             , base: 71000, type: "Calculation", daily: 2000807, monthly: 2000944, floor: "29th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "OMERS" },
    { id: 612, tag: "Floor 30 - Total Electricity"                             , base: 71100, type: "Calculation", daily: 2000808, monthly: 2000945, floor: "30th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Serve corp" },
    { id: 613, tag: "Floor 31 - Total Electricity"                             , base: 71200, type: "Calculation", daily: 2000809, monthly: 2000946, floor: "31st", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 614, tag: "Floor 32 - Total Electricity"                             , base: 71300, type: "Calculation", daily: 2000810, monthly: 2000947, floor: "32nd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 615, tag: "Floor 33 - Total Electricity"                             , base: 71400, type: "Calculation", daily: 2000811, monthly: 2000948, floor: "33rd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 616, tag: "Floor 34 - Total Electricity"                             , base: 71500, type: "Calculation", daily: 2000812, monthly: 2000949, floor: "34th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Quadrature" },
    { id: 617, tag: "Floor 35 - Total Electricity"                             , base: 71600, type: "Calculation", daily: 2000813, monthly: 2000950, floor: "35th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "DRW" },
    { id: 618, tag: "Floor 36 - Total Electricity"                             , base: 71700, type: "Calculation", daily: 2000814, monthly: 2000951, floor: "36th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "DRW" },
    { id: 619, tag: "Floor 37 - Total Electricity"                             , base: 71800, type: "Calculation", daily: 2000815, monthly: 2000952, floor: "37th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "DRW" },
    { id: 620, tag: "Floor 38 - Total Electricity"                             , base: 71900, type: "Calculation", daily: 2000816, monthly: 2000953, floor: "38th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "DRW" },
    { id: 621, tag: "Floor 39 - Total Electricity"                             , base: 72000, type: "Calculation", daily: 2000817, monthly: 2000954, floor: "39th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Brit Insurance" },
    { id: 622, tag: "Floor 40 - Total Electricity"                             , base: 72100, type: "Calculation", daily: 2000818, monthly: 2000955, floor: "40th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 623, tag: "Floor 41 - Total Electricity"                             , base: 72200, type: "Calculation", daily: 2000819, monthly: 2000956, floor: "41st", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "FM Global" },
    { id: 624, tag: "Floor 42 - Total Electricity"                             , base: 72300, type: "Calculation", daily: 2000820, monthly: 2000957, floor: "42nd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Xcite" },
    { id: 625, tag: "Floor 43 - Total Electricity"                             , base: 72400, type: "Calculation", daily: 2000821, monthly: 2000958, floor: "43rd", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Petredec" },
    { id: 626, tag: "Floor 44 - Total Electricity"                             , base: 72500, type: "Calculation", daily: 2000822, monthly: 2000959, floor: "44th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Affinity Shipping" },
    { id: 627, tag: "Floor 45 - Total Electricity"                             , base: 72600, type: "Calculation", daily: 2000823, monthly: 2000960, floor: "45th", column: null, zone: "", function: "", utility: "electricity", tenant: "D-Tek" },
    { id: 628, tag: "Floor 46 - Total Electricity"                             , base: 72700, type: "Calculation", daily: 2000824, monthly: 2000961, floor: "46th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "Landlords" },
    { id: 629, tag: "Total Main Incomer Electricity"                           , base: 72800, type: "Calculation", daily:       0, monthly:       0, floor: "B4", column: null, zone: "", function: "Incomer", utility: "electricity" },
    { id: 630, tag: "Total Generators"                                         , base: 72900, type: "Calculation", daily:       0, monthly:       0, parent_id: 629, floor: "B4", column: null, zone: "", function: "Generators", utility: "electricity" },
    { id: 631, tag: "Tenants Total CHW"                                        , base: 73000, type: "Calculation", daily:       0, monthly:       0, floor: "B4", column: null, zone: "", function: "CHW", utility: "chw" },
    { id: 632, tag: "Tenants Total LTHW"                                       , base: 73100, type: "Calculation", daily:       0, monthly:       0, floor: "B4", column: null, zone: "", function: "LTHW", utility: "lthw" },
    { id: 633, tag: "AON Total Electricity"                                    , base: 73200, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 634, tag: "AON Total LTHW"                                           , base: 73300, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 635, tag: "AON Total CHW"                                            , base: 73400, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 636, tag: "Primary CHW"                                              , base: 73500, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 637, tag: "Landlords Total LTHW"                                     , base: 73600, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 638, tag: "Landlords Total CHW"                                      , base: 73700, type: "Calculation", daily:       0, monthly:       0, tenant: "AON" },
    { id: 639, tag: "Apportioned Landlords LTHW"                               , base: 73800, type: "Calculation", daily: 2000974, monthly: 2000988, floor: "1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th|13th|14th|15th|16th|17th|18th|19th|20th|21st|22nd|23rd|24th|25th|26th|27th|28th|29th|30th|31st|32nd|33rd|34th|35th|36th|37th|38th|39th|40th|41st|42nd|43rd|44th|45th", column: 1, zone: "North", function: "Landlords Apportioned LTHW", utility: "lthw", tenant_display: true },
    { id: 640, tag: "Apportioned Landlords CHW"                                , base: 73900, type: "Calculation", daily: 2000975, monthly: 2000989, floor: "1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th|11th|12th|13th|14th|15th|16th|17th|18th|19th|20th|21st|22nd|23rd|24th|25th|26th|27th|28th|29th|30th|31st|32nd|33rd|34th|35th|36th|37th|38th|39th|40th|41st|42nd|43rd|44th|45th", column: 1, zone: "North", function: "Landlords Apportioned CHW", utility: "chw", tenant_display: true },
    { id: 641, tag: "Aon Basement Electricity"                                 , base: 74000, type: "Calculation", daily: 2000962, monthly: 2000976, floor: "Basement", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 642, tag: "Aon Reception Electricity"                                , base: 74100, type: "Calculation", daily: 2000963, monthly: 2000977, floor: "1st", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 643, tag: "Aon Level 04 Electricity"                                 , base: 74200, type: "Calculation", daily: 2000964, monthly: 2000978, floor: "4th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 644, tag: "Aon Level 05 Electricity"                                 , base: 74300, type: "Calculation", daily: 2000965, monthly: 2000979, floor: "5th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 645, tag: "Aon Level 06 Electricity"                                 , base: 74400, type: "Calculation", daily: 2000966, monthly: 2000980, floor: "6th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 646, tag: "Aon Level 07 Electricity"                                 , base: 74500, type: "Calculation", daily: 2000967, monthly: 2000981, floor: "7th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 647, tag: "Aon Level 08 Electricity"                                 , base: 74600, type: "Calculation", daily: 2000968, monthly: 2000982, floor: "8th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 648, tag: "Aon Level 09 Electricity"                                 , base: 74700, type: "Calculation", daily: 2000969, monthly: 2000983, floor: "9th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 649, tag: "Aon Level 10 Electricity"                                 , base: 74800, type: "Calculation", daily: 2000970, monthly: 2000984, floor: "10th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 650, tag: "Aon Level 11 Electricity"                                 , base: 74900, type: "Calculation", daily: 2000971, monthly: 2000985, floor: "11th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 652, tag: "Aon Level 12 Electricity"                                 , base: 75100, type: "Calculation", daily: 2000972, monthly: 2000986, floor: "12th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "AON", tenant_display: true, main_display: false },
    { id: 653, tag: "UIB Level 13 Electricity"                                 , base: 75200, type: "Calculation", daily: 2000973, monthly: 2000987, floor: "13th", column: null, zone: "", function: "Floor Total Electricity", utility: "electricity", tenant: "UIB", tenant_display: true, main_display: false }
];
// ── END GENERATED METER_REGISTRY ──

// ─── BMS_BINDINGS ────────────────────────────────────────────────────────────
// UI bindings to BMS-side BACnet calculation points that aren't physical
// meters (apportioned heat/cool demand, monthly aggregates, vs-last-month
// percentages, floor-incomer instantaneous demand). Looked up by (role,
// floor) at build time to compose summary cards in the floor template.
//
// Schema:
//   role   : string — semantic key; see SUMMARY_CARD_ROLES in _build/build.py
//   floor  : "ground" | "1st" | "2nd" | …
//   id     : HTML element id used by live updaters
//   bacnet : "300|<inst>|<obj>|85|-1"
//
// title and format are NOT stored here — they live in the role catalog so
// each role has one canonical label and format across all floors.
// ── BEGIN GENERATED BMS_BINDINGS ── DO NOT EDIT BY HAND ──
const BMS_BINDINGS = [
    // ─── Ground floor ─────────────────────────────────────────────────────────
    { role: "floor_demand_electricity",         floor: "ground", id: "live-elec-floor1-demand",                bacnet: "300|0|27382|85|-1"   },
    { role: "floor_today_electricity",          floor: "ground", id: "live-elec-total-today-floor1",           bacnet: "300|0|2000239|85|-1" },
    { role: "floor_monthly_electricity",        floor: "ground", id: "live-elec-total-monthly-floor1",         bacnet: "300|0|2000240|85|-1" },
    { role: "floor_monthly_change_electricity", floor: "ground", id: "live-elec-total-monthly-change-floor1",  bacnet: "300|2|100|85|-1"     },

    // ─── 1st floor ────────────────────────────────────────────────────────────
    { role: "floor_demand_electricity",         floor: "1st", id: "live-elec-floor1-demand",                bacnet: "300|0|19982|85|-1"   },
    { role: "floor_demand_heat_apportioned",    floor: "1st", id: "live-heat-floor1-demand",                bacnet: "300|2|550|85|-1"     },
    { role: "floor_demand_cool",                floor: "1st", id: "live-cool-floor1-demand",                bacnet: "300|2|70|85|-1"      },
    { role: "floor_today_electricity",          floor: "1st", id: "live-elec-total-today-floor1",           bacnet: "300|0|2000163|85|-1" },
    { role: "floor_monthly_electricity",        floor: "1st", id: "live-elec-total-monthly-floor1",         bacnet: "300|0|2000162|85|-1" },
    { role: "floor_monthly_change_electricity", floor: "1st", id: "live-elec-total-monthly-change-floor1",  bacnet: "300|2|101|85|-1"     },
    { role: "floor_monthly_heat_apportioned",   floor: "1st", id: "live-heat-total-monthly-floor1",         bacnet: "300|0|2000242|85|-1" },
    { role: "floor_monthly_change_heat",        floor: "1st", id: "live-heat-total-monthly-change-floor1",  bacnet: "300|2|111|85|-1"     },
    { role: "floor_monthly_cool_apportioned",   floor: "1st", id: "live-cool-total-monthly-floor1",         bacnet: "300|0|2000257|85|-1" },
    { role: "floor_monthly_change_cool",        floor: "1st", id: "live-cool-total-monthly-change-floor1",  bacnet: "300|2|121|85|-1"     },

    // ─── 2nd floor ────────────────────────────────────────────────────────────
    { role: "floor_demand_electricity",         floor: "2nd", id: "live-elec-floor2-demand",                bacnet: "300|0|19982|85|-1"   },
    { role: "floor_demand_heat_apportioned",    floor: "2nd", id: "live-heat-floor2-demand",                bacnet: "300|2|51|85|-1"      },
    { role: "floor_demand_cool",                floor: "2nd", id: "live-cool-floor2-demand",                bacnet: "300|2|71|85|-1"      },
    { role: "floor_today_electricity",          floor: "2nd", id: "live-elec-total-today-floor2",           bacnet: "300|0|2000163|85|-1" },
    { role: "floor_monthly_electricity",        floor: "2nd", id: "live-elec-total-monthly-floor2",         bacnet: "300|0|2000162|85|-1" },
    { role: "floor_monthly_change_electricity", floor: "2nd", id: "live-elec-total-monthly-change-floor2",  bacnet: "300|2|102|85|-1"     },
    { role: "floor_monthly_heat_apportioned",   floor: "2nd", id: "live-heat-total-monthly-floor2",         bacnet: "300|0|2000245|85|-1" },
    { role: "floor_monthly_change_heat",        floor: "2nd", id: "live-heat-total-monthly-change-floor2",  bacnet: "300|2|112|85|-1"     },
    { role: "floor_monthly_cool_apportioned",   floor: "2nd", id: "live-cool-total-monthly-floor2",         bacnet: "300|0|2000260|85|-1" },
    { role: "floor_monthly_change_cool",        floor: "2nd", id: "live-cool-total-monthly-change-floor2",  bacnet: "300|2|122|85|-1"     },

    // ─── 3rd floor ────────────────────────────────────────────────────────────
    { role: "floor_demand_electricity",         floor: "3rd", id: "live-elec-floor3-demand",                bacnet: "300|0|2000168|85|-1" },
    { role: "floor_demand_heat_apportioned",    floor: "3rd", id: "live-heat-floor3-demand",                bacnet: "300|2|52|85|-1"      },
    { role: "floor_demand_cool",                floor: "3rd", id: "live-cool-floor3-demand",                bacnet: "300|2|72|85|-1"      },
    { role: "floor_today_electricity",          floor: "3rd", id: "live-elec-total-today-floor3",           bacnet: "300|0|2000169|85|-1" },
    { role: "floor_monthly_electricity",        floor: "3rd", id: "live-elec-total-monthly-floor3",         bacnet: "300|0|2000168|85|-1" },
    { role: "floor_monthly_change_electricity", floor: "3rd", id: "live-elec-total-monthly-change-floor3",  bacnet: "300|2|103|85|-1"     },
    { role: "floor_monthly_heat_apportioned",   floor: "3rd", id: "live-heat-total-monthly-floor3",         bacnet: "300|0|2000248|85|-1" },
    { role: "floor_monthly_change_heat",        floor: "3rd", id: "live-heat-total-monthly-change-floor3",  bacnet: "300|2|113|85|-1"     },
    { role: "floor_monthly_cool_apportioned",   floor: "3rd", id: "live-cool-total-monthly-floor3",         bacnet: "300|0|2000263|85|-1" },
    { role: "floor_monthly_change_cool",        floor: "3rd", id: "live-cool-total-monthly-change-floor3",  bacnet: "300|2|123|85|-1"     },

    // ─── 4th floor ────────────────────────────────────────────────────────────
    { role: "floor_demand_electricity",         floor: "4th", id: "live-elec-floor4-demand",                bacnet: "300|0|20282|85|-1"   },
    { role: "floor_demand_heat_apportioned",    floor: "4th", id: "live-heat-floor4-demand",                bacnet: "300|2|53|85|-1"      },
    { role: "floor_demand_cool",                floor: "4th", id: "live-cool-floor4-demand",                bacnet: "300|2|73|85|-1"      },
    { role: "floor_today_electricity",          floor: "4th", id: "live-elec-total-today-floor4",           bacnet: "300|0|2000172|85|-1" },
    { role: "floor_monthly_electricity",        floor: "4th", id: "live-elec-total-monthly-floor4",         bacnet: "300|0|2000171|85|-1" },
    { role: "floor_monthly_change_electricity", floor: "4th", id: "live-elec-total-monthly-change-floor4",  bacnet: "300|2|104|85|-1"     },
    { role: "floor_monthly_heat_apportioned",   floor: "4th", id: "live-heat-total-monthly-floor4",         bacnet: "300|0|2000251|85|-1" },
    { role: "floor_monthly_change_heat",        floor: "4th", id: "live-heat-total-monthly-change-floor4",  bacnet: "300|2|114|85|-1"     },
    { role: "floor_monthly_cool_apportioned",   floor: "4th", id: "live-cool-total-monthly-floor4",         bacnet: "300|0|2000266|85|-1" },
    { role: "floor_monthly_change_cool",        floor: "4th", id: "live-cool-total-monthly-change-floor4",  bacnet: "300|2|124|85|-1"     },

    // ─── 5th floor ────────────────────────────────────────────────────────────
    // NB: "20005175" preserves a typo present in the original floor_5th.htm.
    { role: "floor_demand_electricity",         floor: "5th", id: "live-elec-floor5-demand",                bacnet: "300|0|20382|85|-1"     },
    { role: "floor_demand_heat_apportioned",    floor: "5th", id: "live-heat-floor5-demand",                bacnet: "300|2|54|85|-1"        },
    { role: "floor_demand_cool",                floor: "5th", id: "live-cool-floor5-demand",                bacnet: "300|2|74|85|-1"        },
    { role: "floor_today_electricity",          floor: "5th", id: "live-elec-total-today-floor5",           bacnet: "300|0|20005175|85|-1"  },
    { role: "floor_monthly_electricity",        floor: "5th", id: "live-elec-total-monthly-floor5",         bacnet: "300|0|2000174|85|-1"   },
    { role: "floor_monthly_change_electricity", floor: "5th", id: "live-elec-total-monthly-change-floor5",  bacnet: "300|2|105|85|-1"       },
    { role: "floor_monthly_heat_apportioned",   floor: "5th", id: "live-heat-total-monthly-floor5",         bacnet: "300|0|2000254|85|-1"   },
    { role: "floor_monthly_change_heat",        floor: "5th", id: "live-heat-total-monthly-change-floor5",  bacnet: "300|2|115|85|-1"       },
    { role: "floor_monthly_cool_apportioned",   floor: "5th", id: "live-cool-total-monthly-floor5",         bacnet: "300|0|2000269|85|-1"   },
    { role: "floor_monthly_change_cool",        floor: "5th", id: "live-cool-total-monthly-change-floor5",  bacnet: "300|2|125|85|-1"       }
];
// ── END GENERATED BMS_BINDINGS ──

// ─── POINTS ──────────────────────────────────────────────────────────────────
// Named non-meter BACnet points (BMS calculation points: NABERS rating, degree
// days, energy intensity, site sensors, …). This is the SINGLE source for these
// addresses — pages reference a point by name with `data-point="<name>"` and the
// resolver below fills in data-bacnet + data-format on load (mirroring
// data-meter-id). Edit a point's address here, once; build.py reads this block
// (read_points) for validation. To add a point: add a `<name>: { bacnet, format }`.
//
// Schema: <name>: { bacnet: "300|<inst>|<obj>|85|-1", format: "<fmt>" }
//   format ∈ number | energy | power | percentage | temperature | nabers | status
// ── BEGIN POINTS ──
const POINTS = {
    hdd_15_5:           { bacnet: "300|2|89|85|-1", format: "number" },
    cdd_15_5:           { bacnet: "300|2|90|85|-1", format: "number" },
    occupancy_above_20: { bacnet: "300|2|91|85|-1", format: "number" },
    annual_electricity: { bacnet: "300|2|87|85|-1", format: "energy" },
    annual_gas:         { bacnet: "300|2|88|85|-1", format: "energy" },
    energy_intensity:   { bacnet: "300|2|84|85|-1", format: "number" },
    nabers_rating:      { bacnet: "300|2|99|85|-1", format: "nabers" }
};
// ── END POINTS ──

// ─── Lookup map for O(1) access by meter id ──────────────────────────────────
const METER_BY_ID = {};
METER_REGISTRY.forEach(function(m) { METER_BY_ID[m.id] = m; });

// ─── Helpers ─────────────────────────────────────────────────────────────────

function slugify(tag) {
    return tag
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function getPowerOffset(type) {
    var t = (type || '').trim().toLowerCase();
    if (t === 'modbus') return 40;
    if (t.indexOf('calc') === 0) return 82;
    return 40;
}

function bacnet(objectType, objectInstance) {
    return '300|' + objectType + '|' + objectInstance + '|85|-1';
}

// ─── Field definitions ───────────────────────────────────────────────────────
const FIELD_CONFIG = {
    status: {
        getBacnet: function(meter) { return bacnet(3, meter.base); },
        format: 'status'
    },
    demand: {
        getBacnet: function(meter) { return bacnet(0, meter.base + getPowerOffset(meter.type)); },
        format: 'power'
    },
    energy: {
        getBacnet: function(meter) { return bacnet(0, meter.base); },
        format: 'energy'
    },
    daily: {
        getBacnet: function(meter) { return bacnet(0, meter.daily); },
        format: 'energy'
    },
    monthly: {
        getBacnet: function(meter) { return bacnet(0, meter.monthly); },
        format: 'energy'
    }
};

// ─── Public API ──────────────────────────────────────────────────────────────

function getMeter(meterId) {
    return METER_BY_ID[parseInt(meterId)] || null;
}

function getMeterDivId(meterId, field) {
    var meter = getMeter(meterId);
    if (!meter) return null;
    return 'live-' + slugify(meter.tag) + '-' + field;
}

function getMeterBacnet(meterId, field) {
    var meter = getMeter(meterId);
    var fieldCfg = FIELD_CONFIG[field];
    if (!meter || !fieldCfg) return null;
    return fieldCfg.getBacnet(meter);
}

// ─── Auto-resolve data-meter-id elements on DOM ready ────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var elements = document.querySelectorAll('[data-meter-id]');

    elements.forEach(function(el) {
        var meterId = el.getAttribute('data-meter-id');
        var field   = el.getAttribute('data-meter-field');

        if (!meterId || !field) {
            console.warn('Meter template: missing data-meter-id or data-meter-field', el);
            return;
        }

        var meter    = getMeter(meterId);
        var fieldCfg = FIELD_CONFIG[field];

        if (!meter) {
            console.error('Meter template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }
        if (!fieldCfg) {
            console.error('Meter template: unknown field "' + field + '"', el);
            el.textContent = 'Error: unknown field "' + field + '"';
            return;
        }

        // Set auto-generated id (only if not already set)
        if (!el.id) {
            el.id = 'live-' + slugify(meter.tag) + '-' + field;
        }

        // Set data-bacnet
        el.setAttribute('data-bacnet', fieldCfg.getBacnet(meter));

        // Set data-format (only if not already overridden)
        if (!el.getAttribute('data-format')) {
            el.setAttribute('data-format', fieldCfg.format);
        }

        // Set sensible defaults for status fields
        if (field === 'status') {
            if (!el.getAttribute('data-status-online-svg')) {
                el.setAttribute('data-status-online-svg', 'img/status-online.svg');
            }
            if (!el.getAttribute('data-status-offline-svg')) {
                el.setAttribute('data-status-offline-svg', 'img/status-offline.svg');
            }
        }

        // Set default refresh if not specified
        if (!el.getAttribute('data-refresh')) {
            el.setAttribute('data-refresh', '10');
        }
    });
});

// ─── Auto-resolve data-point elements on DOM ready ───────────────────────────
// Mirrors the data-meter-id resolver, but for named non-meter BACnet points
// (POINTS). Fills data-bacnet + data-format from the named point.
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-point]').forEach(function(el) {
        var name = el.getAttribute('data-point');
        var pt = POINTS[name];

        if (!pt) {
            console.error('Point template: unknown point "' + name + '"', el);
            el.textContent = 'Error: unknown point "' + name + '"';
            return;
        }

        el.setAttribute('data-bacnet', pt.bacnet);
        if (!el.getAttribute('data-format') && pt.format) {
            el.setAttribute('data-format', pt.format);
        }
        if (!el.getAttribute('data-refresh')) {
            el.setAttribute('data-refresh', '10');
        }
    });
});

// ─── Auto-resolve data-swb-meter elements on DOM ready ───────────────────────
// Generates the full switchboard meter widget (power link + status indicator)
// from a single placeholder element.
//
// Usage:
//   <div data-swb-meter="39" data-power-pos="557,679" data-status-pos="635,652"></div>
//
// Optional attributes:
//   data-online-svg   – status online SVG  (default: img/online-indicator.svg)
//   data-offline-svg  – status offline SVG (default: img/offline-indicator.svg)
//
// Generates:
//   <a href="/meters/MeterDisplay.html?meter.id=39" target="_blank" rel="noopener noreferrer">
//       <div id="live-tx1-demand" class="info-item-value data-overlay power loading"
//            data-position="557,679" data-bacnet="300|0|13840|85|-1"
//            data-format="power" data-refresh="10">Loading...</div>
//   </a>
//   <div id="live-tx1-status" class="info-item-value data-overlay"
//        data-position="635,652" data-bacnet="300|3|13800|85|-1"
//        data-format="status" data-refresh="10"
//        data-status-online-svg="img/online-indicator.svg"
//        data-status-offline-svg="img/offline-indicator.svg"
//        data-status-online-text=" " data-status-offline-text=" "
//        style="font-size: 10px;"></div>
// Run immediately (not DOMContentLoaded) — the script tag is at the bottom
// of <body>, so the data-swb-meter elements already exist in the DOM.
(function() {
    var elements = document.querySelectorAll('[data-swb-meter]');
    if (!elements.length) return;

    elements.forEach(function(el) {
        var meterId   = parseInt(el.getAttribute('data-swb-meter'));
        var powerPos  = el.getAttribute('data-power-pos');
        var statusPos = el.getAttribute('data-status-pos');

        if (!powerPos || !statusPos) {
            console.warn('SWB template: missing data-power-pos or data-status-pos', el);
            return;
        }

        var meter = getMeter(meterId);
        if (!meter) {
            console.error('SWB template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        var slug        = slugify(meter.tag);
        var powerBacnet = FIELD_CONFIG.demand.getBacnet(meter);
        var statusBcnt  = FIELD_CONFIG.status.getBacnet(meter);
        var onlineSvg   = el.getAttribute('data-online-svg')  || 'img/online-indicator.svg';
        var offlineSvg  = el.getAttribute('data-offline-svg') || 'img/offline-indicator.svg';

        // ── Power link ───────────────────────────────────────────────────
        var link = document.createElement('a');
        link.href   = '/meters/MeterDisplay.html?meter.id=' + meterId;
        link.target = '_blank';
        link.rel    = 'noopener noreferrer';

        var powerDiv = document.createElement('div');
        powerDiv.id        = 'live-' + slug + '-demand';
        powerDiv.className = 'info-item-value data-overlay power loading';
        powerDiv.setAttribute('data-position', powerPos);
        powerDiv.setAttribute('data-bacnet',   powerBacnet);
        powerDiv.setAttribute('data-format',   'power');
        powerDiv.setAttribute('data-refresh',  '10');
        powerDiv.textContent = 'Loading...';
        link.appendChild(powerDiv);

        // ── Status indicator ─────────────────────────────────────────────
        var statusDiv = document.createElement('div');
        statusDiv.id        = 'live-' + slug + '-status';
        statusDiv.className = 'info-item-value data-overlay';
        statusDiv.setAttribute('data-position',           statusPos);
        statusDiv.setAttribute('data-bacnet',             statusBcnt);
        statusDiv.setAttribute('data-format',             'status');
        statusDiv.setAttribute('data-refresh',            '10');
        statusDiv.setAttribute('data-status-online-svg',  onlineSvg);
        statusDiv.setAttribute('data-status-offline-svg', offlineSvg);
        statusDiv.setAttribute('data-status-online-text', ' ');
        statusDiv.setAttribute('data-status-offline-text',' ');
        statusDiv.style.fontSize = '10px';

        // ── Replace placeholder ──────────────────────────────────────────
        var parent = el.parentNode;
        parent.insertBefore(link, el);
        parent.insertBefore(statusDiv, el);
        parent.removeChild(el);
    });

    console.log('SWB template: resolved ' + elements.length + ' meter widgets');

    // Re-apply positioning after elements are created (position-handler may
    // not have loaded yet, so defer until it's available)
    setTimeout(function() {
        if (typeof window.applyDataPositions === 'function') {
            window.applyDataPositions();
        }
    }, 50);
})();

// ─── Auto-resolve data-floor-meter elements on DOM ready ─────────────────────
// Generates a full floor-card meter row (link + subheader + demand/month
// stat boxes) from a single placeholder element. Same idea as data-swb-meter,
// but for meters listed in a floor-card rather than positioned on an image —
// no data-power-pos / data-status-pos needed.
//
// Usage:
//   <div data-floor-meter="419"></div>
//
// Optional overrides (default to the meter registry's function/utility):
//   data-label    – subheader text, e.g. "LTHW"
//   data-utility  – meter-<utility> CSS class, e.g. "lthw"
//
// Generates:
//   <a href="/meters/MeterDisplay.html?meter.id=419" target="_blank" rel="noopener noreferrer" class="floor-stats-group-link">
//       <div class="floor-stats-group">
//           <div class="floor-stats-subheader meter-lthw floor-stats-subheader-flex">
//               <span>LTHW</span>
//               <div data-bacnet="..." data-format="status" data-refresh="10">Loading...</div>
//           </div>
//           <div class="floor-stats floor-stats-flex">
//               <div class="stat-box stat-box-flex">...Demand...</div>
//               <div class="stat-box stat-box-flex">...Current Month...</div>
//               <div class="stat-box stat-box-flex">...Previous Month...</div>
//           </div>
//       </div>
//   </a>
// Run immediately (not DOMContentLoaded) — the script tag is at the bottom
// of <body>, so the data-floor-meter elements already exist in the DOM.
(function() {
    // live-points.js's [data-bacnet] auto-scan keys everything off element.id
    // (DashboardLivePoints.init(element.id, ...)) — an element with no id
    // resolves to "" and fails with "Element with ID "" not found". Every
    // data-bacnet element built here needs one; -{field} keeps the several
    // per meter (status/demand/daily/monthly) unique.
    function meterDivId(meterId, field) {
        return 'meter-id-' + meterId + '-' + field;
    }

    function statBox(labelText, field, meter) {
        var fieldCfg = FIELD_CONFIG[field];
        var box = document.createElement('div');
        box.className = 'stat-box stat-box-flex';
        box.innerHTML =
            '<span class="stat-label">' + labelText + ':</span>' +
            '<span class="stat-value">' +
                '<span id="' + meterDivId(meter.id, field) + '" data-bacnet="' + fieldCfg.getBacnet(meter) + '" data-format="' + fieldCfg.format + '" data-refresh="10">Loading...</span>' +
            '</span>';
        return box;
    }

    // Shared by data-floor-meter and data-floor-stats: the Demand/Current
    // Month/Previous Month stat-box row every floor-card meter shows.
    function buildStatsBlock(meter) {
        var stats = document.createElement('div');
        stats.className = 'floor-stats floor-stats-flex';
        stats.appendChild(statBox('Demand', 'demand', meter));
        stats.appendChild(statBox('Current Month', 'daily', meter));
        stats.appendChild(statBox('Previous Month', 'monthly', meter));
        return stats;
    }

    var meterElements = document.querySelectorAll('[data-floor-meter]');
    meterElements.forEach(function(el) {
        var meterId = parseInt(el.getAttribute('data-floor-meter'));
        var meter = getMeter(meterId);

        if (!meter) {
            console.error('Floor meter template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        var label   = el.getAttribute('data-label')   || meter.function || meter.tag;
        var utility = el.getAttribute('data-utility') || meter.utility  || 'electricity';

        var link = document.createElement('a');
        link.href      = '/meters/MeterDisplay.html?meter.id=' + meterId;
        link.target    = '_blank';
        link.rel       = 'noopener noreferrer';
        link.className = 'floor-stats-group-link';

        var group = document.createElement('div');
        group.className = 'floor-stats-group';

        var subheader = document.createElement('div');
        subheader.className = 'floor-stats-subheader meter-' + utility + ' floor-stats-subheader-flex';
        subheader.innerHTML =
            '<span>' + label + '</span>' +
            '<div id="' + meterDivId(meterId, 'status') + '" data-bacnet="' + FIELD_CONFIG.status.getBacnet(meter) + '" data-format="status" data-refresh="10">Loading...</div>';

        group.appendChild(subheader);
        group.appendChild(buildStatsBlock(meter));
        link.appendChild(group);

        el.parentNode.replaceChild(link, el);
    });
    if (meterElements.length) {
        console.log('Floor meter template: resolved ' + meterElements.length + ' meter rows');
    }

    // ─── data-floor-stats: just the stat-box row, no subheader/link ─────────
    // For cards that already hand-render their own title/link elsewhere (see
    // floor_summary_card in macros.j2 — Total/Tenants/Landlords Electricity),
    // so the label doesn't get shown twice.
    //
    // Usage:
    //   <div data-floor-stats="588"></div>
    // Generates just the .floor-stats.floor-stats-flex block (Demand/Current
    // Month/Previous Month), same as the stats half of data-floor-meter.
    var statsElements = document.querySelectorAll('[data-floor-stats]');
    statsElements.forEach(function(el) {
        var meterId = parseInt(el.getAttribute('data-floor-stats'));
        var meter = getMeter(meterId);

        if (!meter) {
            console.error('Floor stats template: unknown meter id ' + meterId, el);
            el.textContent = 'Error: unknown meter #' + meterId;
            return;
        }

        el.parentNode.replaceChild(buildStatsBlock(meter), el);
    });
    if (statsElements.length) {
        console.log('Floor stats template: resolved ' + statsElements.length + ' stat rows');
    }
})();

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.MeterTemplates = {
        registry: METER_REGISTRY,
        points: POINTS,
        getMeter: getMeter,
        getMeterDivId: getMeterDivId,
        getMeterBacnet: getMeterBacnet,
        slugify: slugify
    };
}
