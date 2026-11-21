"""Reconstruct historical schemas only in invocation-owned migration fixtures."""

def remove_managed_schema(conn):
    remove_assistant_schema(conn)
    for table in ['fhir_acquisition_event', 'fhir_acquisition']:
        conn.execute('DROP TABLE IF EXISTS ' + table)
    conn.execute('DELETE FROM schema_migration WHERE version=12')
    for table in ['feed_window_event', 'feed_exception', 'feed_decision', 'feed_version', 'feed_job_event', 'feed_job', 'feed_delivery', 'feed_contract', 'feed_config', 'feed_window', 'feed_issue', 'feed']:
        conn.execute('DROP TABLE IF EXISTS ' + table)
    conn.execute('DELETE FROM schema_migration WHERE version=11')


def remove_assistant_schema(conn):
    for table in ['assistant_run_event', 'assistant_run']:
        conn.execute('DROP TABLE IF EXISTS ' + table)
    conn.execute('DELETE FROM schema_migration WHERE version=13')
