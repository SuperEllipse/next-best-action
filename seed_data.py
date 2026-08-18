"""Seed Iceberg operational demo data — INSERT uses full catalog path like Quickstart notebook."""

from spark_session import ICEBERG_NAMESPACE, ensure_database, get_spark_session, verify_iceberg_runtime

NS = ICEBERG_NAMESPACE

# Quickstart pattern: INSERT INTO spark_catalog.testdb.newtesttable VALUES (...)
SEED_STATEMENTS = [
    (
        "flight_operational_events",
        f"""
        INSERT INTO {NS}.flight_operational_events VALUES
        ('EVT-9001', 'PNR-881A', 'CUST-101', 'EK002', 'LHR-DXB-SIN', 90, 35, TRUE,  timestamp('2026-08-12 11:30:00')),
        ('EVT-9002', 'PNR-442B', 'CUST-202', 'EK002', 'LHR-DXB-BKK', 85, 35, TRUE,  timestamp('2026-08-12 11:30:00')),
        ('EVT-9003', 'PNR-109C', 'CUST-303', 'EK002', 'LHR-DXB-SYD', 75, 25, TRUE,  timestamp('2026-08-12 11:30:00')),
        ('EVT-9004', 'PNR-404D', 'CUST-404', 'EK002', 'LHR-DXB-SIN', 90, 35, TRUE,  timestamp('2026-08-12 11:30:00'))
        """,
    ),
    (
        "unstructured_chat_signals",
        f"""
        INSERT INTO {NS}.unstructured_chat_signals VALUES
        ('SIG-01', 'PNR-109C', 'CUST-303', timestamp('2026-08-12 11:32:10'), 'FRUSTRATED',
         'Unbelievable. Another inbound delay. My connection is down to 25 mins. Get me on another flight or refund my return ticket.'),
        ('SIG-02', 'PNR-442B', 'CUST-202', timestamp('2026-08-12 11:33:00'), 'CALM',
         'Hi, my connection time just dropped to 35 minutes in Dubai. Will I make it, or can you look at alternate flights and lounge access?'),
        ('SIG-03', 'PNR-881A', 'CUST-101', timestamp('2026-08-12 11:33:30'), 'SILENT', NULL)
        """,
    ),
    (
        "action_gesture_shelf",
        f"""
        INSERT INTO {NS}.action_gesture_shelf VALUES
        ('ACT-001', 'PROACTIVE_REBOOK_NOTIFY', 'Rebook next flight + Push notification',          120.00, FALSE, 'Automatically secure seat on next flight and notify user via app.'),
        ('ACT-002', 'LOUNGE_PASS_MEAL',        'Express Lounge Pass + $50 Meal Voucher',           45.00,  FALSE, 'Provide fast-track lounge pass and digital dining voucher.'),
        ('ACT-003', 'FULL_CONCIERGE_CARE',     'Auto-Rebook + First Lounge + $200 Loyalty Credits', 280.00, TRUE,  'Requires human agent signoff or high-tier automated policy.'),
        ('ACT-004', 'NO_ACTION_MONITOR',       'Monitor connection status without push',             0.00,  FALSE, 'Allow passenger to self-navigate or wait for operational update.'),
        ('ACT-005', 'HOLD_AND_PROMPT',         'Hold alternate seats + Push choice micro-prompt',   15.00,  FALSE, 'Pre-hold inventory options; invite passenger into concierge chat to choose.')
        """,
    ),
    (
        "historical_uplift_experiments",
        f"""
        INSERT INTO {NS}.historical_uplift_experiments VALUES
        ('EXP-101', 'CUST-101', 'SURE_THING',       'ACT-003', TRUE,  0.02),
        ('EXP-102', 'CUST-101', 'SURE_THING',       'ACT-004', TRUE,  0.00),
        ('EXP-201', 'CUST-202', 'PERSUADABLE',      'ACT-002', TRUE,  0.42),
        ('EXP-202', 'CUST-202', 'PERSUADABLE',      'ACT-004', FALSE, 0.00),
        ('EXP-301', 'CUST-303', 'SLEEPING_DOG',     'ACT-002', FALSE, -0.25),
        ('EXP-302', 'CUST-303', 'SLEEPING_DOG',     'ACT-001', TRUE,   0.15),
        ('EXP-401', 'CUST-404', 'CHOICE_ORIENTED',  'ACT-005', TRUE,   0.38),
        ('EXP-402', 'CUST-404', 'CHOICE_ORIENTED',  'ACT-001', FALSE, -0.12)
        """,
    ),
    (
        "concierge_inventory_lookup",
        f"""
        INSERT INTO {NS}.concierge_inventory_lookup VALUES
        ('LKP-001', 'PNR-881A', 'EK354', timestamp('2026-08-12 15:10:00'), timestamp('2026-08-12 19:45:00'), 4, TRUE,  'AVAILABLE', FALSE, 'SIN', 'AVAILABLE', NULL, NULL, NULL, NULL),
        ('LKP-002', 'PNR-442B', 'EK372', timestamp('2026-08-12 16:30:00'), timestamp('2026-08-12 20:15:00'), 2, TRUE,  'AVAILABLE', FALSE, 'BKK', 'AVAILABLE', NULL, NULL, NULL, NULL),
        ('LKP-003', 'PNR-109C', 'EK414', timestamp('2026-08-12 22:00:00'), timestamp('2026-08-12 08:30:00'), 0, FALSE, 'FULL',       TRUE,  'SYD', 'AVAILABLE', NULL, NULL, NULL, NULL),
        ('LKP-004', 'PNR-404D', 'EK372', timestamp('2026-08-12 15:10:00'), timestamp('2026-08-12 17:15:00'), 2, TRUE,  'AVAILABLE', FALSE, 'SIN', 'AVAILABLE', timestamp('2026-08-12 16:00:00'), 'QUIET_POD', 'POD-4', 'AVAILABLE'),
        ('LKP-005', 'PNR-404D', 'EK380', timestamp('2026-08-12 18:00:00'), timestamp('2026-08-12 21:30:00'), 4, TRUE,  'AVAILABLE', FALSE, 'SIN', 'AVAILABLE', timestamp('2026-08-12 19:00:00'), NULL, NULL, 'UNAVAILABLE')
        """,
    ),
]


def seed_data():
    spark = get_spark_session("IROP-SeedData")
    verify_iceberg_runtime(spark)
    ensure_database(spark)

    for idx, (table, sql) in enumerate(SEED_STATEMENTS, start=1):
        print(f"  [{idx}/{len(SEED_STATEMENTS)}] Inserting into {NS}.{table} ...", flush=True)
        spark.sql(sql)
        count = spark.sql(f"SELECT COUNT(*) AS c FROM {NS}.{table}").collect()[0]["c"]
        print(f"  [{idx}/{len(SEED_STATEMENTS)}] {table}: {count} rows committed", flush=True)

    print("Seed data inserted into Iceberg operational tables.")


if __name__ == "__main__":
    seed_data()
