import sqlite3

from se_pov_builder.db import init_db, make_engine


def test_existing_database_gains_new_nullable_columns(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)  # a pov_plans table from before portal_group existed
    con.execute("CREATE TABLE pov_plans (id INTEGER PRIMARY KEY, deal_id INTEGER, title VARCHAR(300))")
    con.commit()
    con.close()
    init_db(make_engine(f"sqlite:///{path}"))
    cols = {row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(pov_plans)")}
    assert "portal_group" in cols
