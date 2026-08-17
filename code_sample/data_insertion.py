

-- 2. Populate Operational Events (Connection Time dropped to 35m)
INSERT INTO spark_catalog.airline_irop.flight_operational_events VALUES
('EVT-9001', 'PNR-881A', 'CUST-101', 'EK002', 'LHR-DXB-SIN', 90, 35, TRUE, '2026-08-12 11:30:00'),
('EVT-9002', 'PNR-442B', 'CUST-202', 'EK002', 'LHR-DXB-BKK', 85, 35, TRUE, '2026-08-12 11:30:00'),
('EVT-9003', 'PNR-109C', 'CUST-303', 'EK002', 'LHR-DXB-SYD', 75, 25, TRUE, '2026-08-12 11:30:00');

-- 3. Populate Unstructured Signals (The 3 Tonal Variants)
INSERT INTO spark_catalog.airline_irop.unstructured_chat_signals VALUES
('SIG-01', 'PNR-109C', 'CUST-303', '2026-08-12 11:32:10', 'FRUSTRATED', 'Unbelievable. Another inbound delay. My connection is down to 25 mins. Get me on another flight or refund my return ticket.'),
('SIG-02', 'PNR-442B', 'CUST-202', '2026-08-12 11:33:00', 'CALM',       'Hi, my connection time just dropped to 35 minutes in Dubai. Will I make it, or can you look at alternate flights and lounge access?'),
('SIG-03', 'PNR-881A', 'CUST-101', '2026-08-12 11:33:30', 'SILENT',     NULL); -- Platinum member hasn't messaged; silence triggers proactive intervention.

-- 4. Populate Gesture Shelf
INSERT INTO spark_catalog.airline_irop.action_gesture_shelf VALUES
('ACT-001', 'PROACTIVE_REBOOK_NOTIFY', 'Rebook next flight + Push notification',          120.00, FALSE, 'Automatically secure seat on next flight and notify user via app.'),
('ACT-002', 'LOUNGE_PASS_MEAL',        'Express Lounge Pass + $50 Meal Voucher',           45.00,  FALSE, 'Provide fast-track lounge pass and digital dining voucher.'),
('ACT-003', 'FULL_CONCIERGE_CARE',     'Auto-Rebook + First Lounge + $200 Loyalty Credits', 280.00, TRUE,  'Requires human agent signoff or high-tier automated policy.'),
('ACT-004', 'NO_ACTION_MONITOR',       'Monitor connection status without push',             0.00,  FALSE, 'Allow passenger to self-navigate or wait for operational update.');

-- 5. Populate Historical Uplift Experiments (Holds the 3 Archetypes)
INSERT INTO spark_catalog.airline_irop.historical_uplift_experiments VALUES
-- Archetype: Sure Thing (Top-tier loyalist: high base propensity, near-zero uplift gain from expensive gestures)
('EXP-101', 'CUST-101', 'SURE_THING', 'ACT-003', TRUE,  0.02),
('EXP-102', 'CUST-101', 'SURE_THING', 'ACT-004', TRUE,  0.00),

-- Archetype: Persuadable (Mid-tier: moderate propensity, gesture heavily sways retention decision)
('EXP-201', 'CUST-202', 'PERSUADABLE', 'ACT-002', TRUE,  0.42),
('EXP-202', 'CUST-202', 'PERSUADABLE', 'ACT-004', FALSE, 0.00),

-- Archetype: Sleeping Dog (Time-sensitive/transactional: apologetic gestures backfire if rebooking is delayed)
('EXP-301', 'CUST-303', 'SLEEPING_DOG', 'ACT-002', FALSE, -0.25), -- Voucher annoyed them; wanted instant rebook.
('EXP-302', 'CUST-303', 'SLEEPING_DOG', 'ACT-001', TRUE,   0.15); -- Direct rebook without fluff worked.

-- 6. Populate Concierge Inventory Lookup (Mocked for Live AI Tool Calling)
INSERT INTO spark_catalog.airline_irop.concierge_inventory_lookup VALUES
('LKP-001', 'PNR-881A', 'EK354', '2026-08-12 15:10:00', 4, TRUE,  'AVAILABLE', FALSE),
('LKP-002', 'PNR-442B', 'EK372', '2026-08-12 16:30:00', 2, TRUE,  'AVAILABLE', FALSE),
('LKP-003', 'PNR-109C', 'EK414', '2026-08-12 22:00:00', 0, FALSE, 'FULL',       TRUE),
('LKP-004', 'PNR-404D', 'EK372', '2026-08-12 16:30:00', 3, TRUE,  'AVAILABLE', FALSE);